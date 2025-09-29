#负责文本处理和 LLM 管道逻辑
from datetime import datetime
import json
import logging
import os
from pathlib import Path
import asyncio
import httpx
from typing import Dict, List
from httpx import AsyncClient
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from time_converter import convert_to_beijing_time
from neo4j_connection import Neo4jConnection
from config import Config
from utils import normalize_location
from conflict_resolution import ConflictResolver
from knowledge_graph_updater import KnowledgeGraphUpdater

logger = logging.getLogger(__name__)

http_client = AsyncClient(timeout=30.0)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

llm_log_file = os.path.join(PROJECT_DIR, "llm_response_log.json")
with open(llm_log_file, "a", encoding="utf-8") as f:
    f.write("")

request_semaphore = asyncio.Semaphore(10)

# Cache for LLM descriptions
description_cache = {}

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.RequestError)),
    before_sleep=lambda retry_state: logger.debug(f"重试 LLM 调用，第 {retry_state.attempt_number} 次")
)
async def call_deepseek_with_retry(prompt: str, model_name: str = "default") -> str:
    config = Config.get_llm_config(model_name)
    input_tokens = estimate_tokens(prompt)
    max_model_tokens = 16384  # 调整为实际模型限制（如 4096）
    max_output_tokens = 1024
    if input_tokens >= max_model_tokens - max_output_tokens:
        logger.warning(f"Prompt 过长 ({input_tokens} tokens)，截断到安全长度")
        prompt = prompt[:int(len(prompt) * (max_model_tokens - max_output_tokens - 100) / input_tokens)]
        input_tokens = estimate_tokens(prompt)
    
    logger.debug(f"输入 token 数: {input_tokens}, max_tokens: {max_output_tokens}")
    
    api_key = config.get("api_key", "")
    if not api_key:
        logger.error("API密钥为空，无法发起请求")
        raise ValueError("API密钥为空")
    
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    async with request_semaphore:
        async with AsyncClient(timeout=config["timeout"]) as client:
            try:
                response = await client.post(
                    config["api_base"],
                    json={
                        "model": config["model"],
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": max_output_tokens
                    },
                    headers=headers
                )
                response.raise_for_status()
                response_data = response.json()
                with open(llm_log_file, "a", encoding="utf-8") as f:
                    json.dump(
                        {
                            "prompt": prompt,
                            "response": response_data,
                            "input_tokens": input_tokens,
                            "timestamp": await convert_to_beijing_time()
                        },
                        f,
                        ensure_ascii=False
                    )
                    f.write("\n")
                return json.dumps(response_data)
            except httpx.HTTPStatusError as e:
                logger.error(f"LLM 调用失败: {e}, Response: {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"LLM 调用失败: {e}")
                raise

#用于估算token，保证不超令牌数
def estimate_tokens(text: str) -> int:
    """估算文本的 token 数（简化为 1 token ≈ 0.75 个中文字符或 0.5 个英文字符）"""
    chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 0.75 + other_chars * 0.5)

async def infer_description(name: str, location: str) -> str:
    """使用 LLM 生成描述"""
    prompt = f"Generate a brief description (50-100 words) for a tourist attraction named '{name}' located in '{location}'. The description should highlight its cultural, historical, or natural significance."
    try:
        response = await call_deepseek_with_retry(prompt, model_name="default")
        description = json.loads(response).get("choices", [{}])[0].get("message", {}).get("content", "")
        return description.strip()
    except Exception as e:
        logger.error(f"生成描述失败 for {name}: {e}")
        return f"Description for {name}"

async def reset_database(neo4j_conn):
    """
    Reset the Neo4j database by clearing all nodes and relationships
    and creating indexes for Attraction and City nodes.
    """
    try:
        neo4j_conn.clear_database()
        logger.info("清空所有节点和关系")

        with neo4j_conn.driver.session() as session:
            session.run("CREATE INDEX attraction_name IF NOT EXISTS FOR (a:Attraction) ON (a.name)")
            logger.debug("执行查询: CREATE INDEX attraction_name IF NOT EXISTS FOR (a:Attraction) ON (a.name)")
            
            session.run("CREATE INDEX city_name IF NOT EXISTS FOR (c:City) ON (c.name)")
            logger.debug("执行查询: CREATE INDEX city_name IF NOT EXISTS FOR (c:City) ON (c.name)")
        
        logger.info("创建 Attraction 和 City 名称索引")
    except Exception as e:
        logger.error(f"重置数据库失败: {e}", exc_info=True)
        raise

async def extract_best_comment(description: str, debug_mode: bool = False) -> str:
    """使用 LLM 提取最佳评论"""
    if debug_mode:
        return f"Sample comment for {description[:20]}..."
    prompt = f"Generate a concise, positive visitor comment (20-50 words) for a tourist attraction based on this description: {description}"
    try:
        response = await call_deepseek_with_retry(prompt, model_name="default")
        comment = json.loads(response).get("choices", [{}])[0].get("message", {}).get("content", "")
        return comment.strip()
    except Exception as e:
        logger.error(f"生成评论失败: {e}")
        return ""

async def batch_call_deepseek(prompts: List[str], model_name: str = "default") -> List[str]:
    """批量调用 DeepSeek API，按 token 限制分块处理"""
    max_model_tokens = 16384
    max_output_tokens = 1024
    max_input_tokens = max_model_tokens - max_output_tokens - 100
    semaphore = asyncio.Semaphore(10)
    
    async def call_with_semaphore(prompt):
        async with semaphore:
            try:
                return await call_deepseek_with_retry(prompt, model_name)
            except Exception as e:
                logger.error(f"批量调用失败 for prompt: {prompt[:50]}...: {e}")
                return str(e)
    
    chunks = []
    current_chunk = []
    current_token_count = 0
    
    for prompt in prompts:
        prompt_tokens = estimate_tokens(prompt)
        if current_token_count + prompt_tokens > max_input_tokens:
            chunks.append(current_chunk)
            current_chunk = [prompt]
            current_token_count = prompt_tokens
        else:
            current_chunk.append(prompt)
            current_token_count += prompt_tokens
    if current_chunk:
        chunks.append(current_chunk)
    
    logger.debug(f"分块数量: {len(chunks)}, 总 prompts: {len(prompts)}")
    
    results = []
    for i, chunk in enumerate(chunks):
        logger.debug(f"处理第 {i+1} 块，包含 {len(chunk)} 个 prompts")
        tasks = [call_with_semaphore(prompt) for prompt in chunk]
        chunk_results = await asyncio.gather(*tasks, return_exceptions=True)
        results.extend(chunk_results)
    
    for i, result in enumerate(results):
        if isinstance(result, str) and result.startswith("Client error"):
            logger.warning(f"批量调用结果 {i} 失败: {result}")
    
    return results

async def extract_relationships(data: Dict) -> Dict:
    """增强数据，生成描述和评论"""
    data = data.copy()
    if not data.get("best_comment"):
        data["best_comment"] = await extract_best_comment(data.get("description", ""), debug_mode=False)
    if not data.get("location"):
        data["location"] = "拉萨市"
    if not data.get("description"):
        data["description"] = await infer_description(data.get("name", "Unknown"), data.get("location", "拉萨市"))
    
    cultural_keywords = ["寺", "庙", "宫", "博物馆", "文化", "宗教", "历史", "古街", "遗址", "纪念碑"]
    is_cultural = any(keyword in data.get("name", "") or keyword in data.get("description", "") for keyword in cultural_keywords)
    data["is_cultural"] = is_cultural
    logger.debug(f"LLM 处理数据: {data['name']}, is_cultural: {is_cultural}, location: {data['location']}, description: {data['description']}")
    return data

async def process_json_chunk(neo4j_conn, data: List[Dict], crawl_timestamp: str, source_type: str, metrics: Dict):
    updater = KnowledgeGraphUpdater(neo4j_conn)
    conflict_resolver = ConflictResolver(updater.crud)
    results = []

    # 处理节点
    for item in data:
        try:
            processed_item = await extract_relationships(item)  # 假设已定义
            log_id = f"{processed_item['name']}_{crawl_timestamp}"
            weights = {"rules_valid": 1.0, "llm_valid": 0.8, "weight_valid": 0.9}
            reason = "Initial import from JSON with LLM enhancement"
            updater.update_knowledge_graph(processed_item, log_id, reason, weights)
            logger.info(f"成功处理实体: {processed_item['name']}")
            results.append({"name": processed_item["name"], "status": "success"})
        except Exception as e:
            logger.error(f"处理实体 {item.get('name', 'Unknown')} 失败: {e}", exc_info=True)
            results.append({"name": item.get("name", "Unknown"), "status": "failed", "error": str(e)})
            continue

    # 过滤景点（例如，只处理 visitor_percentage > 0 的景点）
    filtered_data = [item for item in data if float(item.get("visitor_percentage", "0%").strip("%")) > 0]
    logger.info(f"过滤后景点数量: {len(filtered_data)}")

    # 批量推断关系
    relationship_prompts = []
    node_pairs = []
    for i, node1 in enumerate(filtered_data):
        for node2 in filtered_data[i+1:]:
            if node1.get("name") != node2.get("name"):
                prompt = f"""
                You are an expert in analyzing relationships between tourist attractions. Given the following two attractions, infer possible relationships between them based on their attributes (name, description, location, ranking, visitor_percentage). Return a JSON list of relationships, each with 'type' (e.g., NEARBY, SIMILAR_TYPE, COMPLEMENTARY_VISIT, HISTORICAL_LINK), 'reason', and 'confidence' (0 to 1). Consider the following criteria:
                - NEARBY: Same location and high visitor overlap (difference in visitor_percentage < 20%).
                - SIMILAR_TYPE: Similar descriptions (e.g., both are temples or museums).
                - COMPLEMENTARY_VISIT: Attractions that complement each other (e.g., a temple and a nearby cultural street).
                - HISTORICAL_LINK: Shared historical or cultural significance (e.g., both related to Tibetan Buddhism).

                Attraction 1:
                Name: {node1.get('name', '')}
                Location: {node1.get('location', '')}
                Description: {node1.get('description', '')}
                Ranking: {node1.get('ranking', '')}
                Visitor Percentage: {node1.get('visitor_percentage', '')}

                Attraction 2:
                Name: {node2.get('name', '')}
                Location: {node2.get('location', '')}
                Description: {node2.get('description', '')}
                Ranking: {node2.get('ranking', '')}
                Visitor Percentage: {node2.get('visitor_percentage', '')}

                Return a JSON list of inferred relationships, e.g.:
                [
                    {{"type": "NEARBY", "reason": "Same location and similar visitor percentage", "confidence": 0.9}},
                    {{"type": "SIMILAR_TYPE", "reason": "Both are temples", "confidence": 0.8}}
                ]
                """
                relationship_prompts.append(prompt)
                node_pairs.append((node1, node2))

    # 批量调用 LLM
    responses = await batch_call_deepseek(relationship_prompts)
    
    # 创建关系并检测冲突
    with neo4j_conn.driver.session() as session:
        for (node1, node2), response in zip(node_pairs, responses):
            try:
                if isinstance(response, Exception):
                    logger.error(f"LLM 调用失败 for {node1['name']} -> {node2['name']}: {response}")
                    continue
                relationships = json.loads(response).get("choices", [{}])[0].get("message", {}).get("content", "[]")
                relationships = json.loads(relationships.strip("```json\n").strip("\n```")) if isinstance(relationships, str) else relationships
                existing_rels = updater.crud.get_relationships(session, "Attraction", node1["name"])
                for rel in relationships:
                    if isinstance(rel, dict) and all(k in rel for k in ["type", "reason", "confidence"]):
                        rel_data = {
                            "source_name": node1["name"],
                            "target_name": node2["name"],
                            "type": rel["type"],
                            "properties": {"reason": rel["reason"], "confidence": rel["confidence"]}
                        }
                        if await conflict_resolver.check_relationship_conflict(rel_data, existing_rels):
                            conflict_resolver.log_conflict({
                                "entity_name": f"{node1['name']}_{node2['name']}_{rel['type']}",
                                "conflict_data": rel_data,
                                "existing_data": existing_rels,
                                "timestamp": await convert_to_beijing_time()
                            })
                            continue
                        updater.crud.create_relationship(
                            tx=session,
                            source_label="Attraction",
                            source_name=node1["name"],
                            target_label="Attraction",
                            target_name=node2["name"],
                            rel_type=rel["type"],
                            properties={"reason": rel["reason"], "confidence": rel["confidence"]}
                        )
                        logger.debug(f"创建 {rel['type']} 关系: {node1['name']} -> {node2['name']}")
            except Exception as e:
                logger.error(f"创建关系失败: {node1['name']} -> {node2['name']}: {str(e)}")

    updater.close()
    return results

async def process_json_files(neo4j_conn, json_file_path: str, crawl_timestamp: str, source_type: str, metrics: Dict):
    logger.info(f"读取 JSON 文件: {json_file_path}")
    try:
        file_path = Path(json_file_path)
        if file_path.is_dir():
            raise ValueError(f"路径是目录而非文件: {json_file_path}")
        if not file_path.is_file():
            raise FileNotFoundError(f"文件不存在: {json_file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        nodes = data.get("nodes", [])
        logger.info(f"JSON 文件包含 {len(nodes)} 条记录")
        
        seen_names = set()
        duplicates = []
        unique_nodes = []
        for node in nodes:
            if node["name"] in seen_names:
                duplicates.append(node["name"])
            else:
                seen_names.add(node["name"])
                unique_nodes.append(node)
        logger.info(f"去重后节点数: {len(unique_nodes)}, 重复节点: {duplicates if duplicates else '无'}")

        batch_size = 3
        results = []
        for i in range(0, len(unique_nodes), batch_size):
            batch = unique_nodes[i:i + batch_size]
            batch_result = await process_json_chunk(
                neo4j_conn=neo4j_conn,
                data=batch,
                crawl_timestamp=crawl_timestamp,
                source_type=source_type,
                metrics=metrics
            )
            results.extend(batch_result)
        
        return {
            "status": "success",
            "processed": len([r for r in results if r["status"] == "success"]),
            "failed": len([r for r in results if r["status"] == "failed"]),
            "details": results
        }
    except Exception as e:
        logger.error(f"处理 JSON 文件失败: {e}", exc_info=True)
        return {"status": "failed", "error": str(e)}


    
async def close_resources():
    """
    Close any resources if needed.
    """
    logger.info("关闭资源")
    
CITY_MAP = {
        "西藏拉萨": "拉萨市",
        "拉萨": "拉萨市",
        "林芝": "林芝市",
        "日喀则": "日喀则市",
        "昌都": "昌都市",
        "那曲": "那曲市",
        "阿里": "阿里地区",
        "山南": "山南市",
        "八廓街": "拉萨市",
        "西藏市": "拉萨市",
        "当雄县": "拉萨市",  # Normalize to Lhasa for tourist attractions
        "墨竹工卡县": "拉萨市",
        "林周县": "拉萨市",
        "尼木县": "拉萨市",
        "曲水县": "拉萨市"
}
