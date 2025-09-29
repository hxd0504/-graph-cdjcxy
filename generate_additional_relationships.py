#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成额外的关系类型
"""

import logging
import sys
import os
import json
import asyncio
from typing import List, Dict, Tuple

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from neo4j_connection import Neo4jConnection
from text_processor import call_deepseek_with_retry

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def generate_relationships_for_pair(attraction1: Dict, attraction2: Dict) -> List[Dict]:
    """为一对景点生成关系"""
    prompt = f"""
    你是一个专业的旅游景点关系分析专家。请分析以下两个西藏景点之间可能存在的关系，并返回JSON格式的关系列表。

    景点1:
    名称: {attraction1.get('name', '')}
    位置: {attraction1.get('location', '')}
    描述: {attraction1.get('description', '')}
    地址: {attraction1.get('address', '')}

    景点2:
    名称: {attraction2.get('name', '')}
    位置: {attraction2.get('location', '')}
    描述: {attraction2.get('description', '')}
    地址: {attraction2.get('address', '')}

    请根据以下关系类型分析：
    1. NEARBY - 地理位置相近（同一区域或相邻区域）
    2. SIMILAR_TYPE - 相似类型（都是寺庙、都是自然景观等）
    3. COMPLEMENTARY_VISIT - 互补游览（适合一起游览的景点）
    4. HISTORICAL_LINK - 历史关联（有共同的历史背景或文化联系）
    5. CULTURAL_RELATED - 文化相关（属于同一文化体系或宗教体系）

    返回JSON格式，每个关系包含：
    - type: 关系类型
    - reason: 关系原因（中文）
    - confidence: 置信度（0.0-1.0）
    - direction: 关系方向（"bidirectional"表示双向，"forward"表示单向）

    示例格式：
    [
        {{"type": "NEARBY", "reason": "两个景点都位于拉萨市中心区域", "confidence": 0.8, "direction": "bidirectional"}},
        {{"type": "CULTURAL_RELATED", "reason": "都是藏传佛教寺庙", "confidence": 0.9, "direction": "bidirectional"}}
    ]

    如果没有明显关系，返回空数组 []
    """
    
    try:
        response = await call_deepseek_with_retry(prompt, model_name="default")
        content = json.loads(response).get("choices", [{}])[0].get("message", {}).get("content", "[]")
        
        # 清理可能的markdown格式
        if content.startswith("```json"):
            content = content.strip("```json\n").strip("\n```")
        elif content.startswith("```"):
            content = content.strip("```\n").strip("\n```")
            
        relationships = json.loads(content)
        return relationships if isinstance(relationships, list) else []
        
    except Exception as e:
        logger.error(f"生成关系失败 {attraction1['name']} <-> {attraction2['name']}: {e}")
        return []

def create_relationship_in_db(session, source_name: str, target_name: str, rel_type: str, properties: Dict):
    """在数据库中创建关系"""
    try:
        query = """
        MATCH (a:Attraction {name: $source_name})
        MATCH (b:Attraction {name: $target_name})
        MERGE (a)-[r:%s]->(b)
        SET r += $props
        RETURN r
        """ % rel_type
        
        result = session.run(query, source_name=source_name, target_name=target_name, props=properties)
        return result.single() is not None
    except Exception as e:
        logger.error(f"创建关系失败 {source_name} -[{rel_type}]-> {target_name}: {e}")
        return False

async def generate_additional_relationships():
    """生成额外的关系"""
    neo4j_conn = None
    try:
        # 连接到Neo4j
        neo4j_config = Config.get_neo4j_config()
        neo4j_conn = Neo4jConnection(
            uri=neo4j_config["uri"],
            user=neo4j_config["user"],
            password=neo4j_config["password"]
        )
        neo4j_conn.verify_connectivity()
        logger.info("成功连接到Neo4j数据库")

        with neo4j_conn.driver.session() as session:
            # 获取所有有描述的景点（限制数量以避免过多的API调用）
            attractions_query = """
            MATCH (a:Attraction)
            WHERE a.description IS NOT NULL 
            AND a.description <> ''
            AND a.name IS NOT NULL
            RETURN a.name as name, a.location as location, a.description as description, a.address as address
            ORDER BY a.name
            LIMIT 50
            """
            
            attractions = list(session.run(attractions_query))
            logger.info(f"获取到 {len(attractions)} 个景点用于关系生成")

            if len(attractions) < 2:
                logger.warning("景点数量不足，无法生成关系")
                return

            # 生成景点对
            pairs_to_process = []
            for i, attr1 in enumerate(attractions):
                for attr2 in attractions[i+1:i+6]:  # 每个景点最多与5个其他景点比较
                    if attr1['name'] != attr2['name']:
                        pairs_to_process.append((dict(attr1), dict(attr2)))

            logger.info(f"将处理 {len(pairs_to_process)} 个景点对")

            # 批量处理关系生成
            relationships_created = 0
            batch_size = 5  # 每批处理5对
            
            for i in range(0, len(pairs_to_process), batch_size):
                batch = pairs_to_process[i:i+batch_size]
                logger.info(f"处理批次 {i//batch_size + 1}/{(len(pairs_to_process)-1)//batch_size + 1}")
                
                # 为当前批次生成关系
                for attr1, attr2 in batch:
                    try:
                        relationships = await generate_relationships_for_pair(attr1, attr2)
                        
                        for rel in relationships:
                            if not isinstance(rel, dict) or 'type' not in rel:
                                continue
                                
                            rel_type = rel['type']
                            reason = rel.get('reason', '')
                            confidence = rel.get('confidence', 0.5)
                            direction = rel.get('direction', 'forward')
                            
                            # 创建关系属性
                            props = {
                                'reason': reason,
                                'confidence': confidence,
                                'created_by': 'relationship_generator'
                            }
                            
                            # 创建正向关系
                            if create_relationship_in_db(session, attr1['name'], attr2['name'], rel_type, props):
                                relationships_created += 1
                                logger.info(f"创建关系: {attr1['name']} -[{rel_type}]-> {attr2['name']} (置信度: {confidence})")
                            
                            # 如果是双向关系，创建反向关系
                            if direction == 'bidirectional':
                                if create_relationship_in_db(session, attr2['name'], attr1['name'], rel_type, props):
                                    relationships_created += 1
                                    logger.info(f"创建反向关系: {attr2['name']} -[{rel_type}]-> {attr1['name']}")
                                    
                    except Exception as e:
                        logger.error(f"处理景点对失败 {attr1['name']} <-> {attr2['name']}: {e}")
                        continue
                
                # 避免API限制，批次间稍作延迟
                await asyncio.sleep(1)

            logger.info(f"总共创建了 {relationships_created} 个新关系")

            # 统计结果
            logger.info("\n=== 关系生成结果统计 ===")
            rel_stats = session.run("""
                MATCH ()-[r]->()
                WHERE r.created_by = 'relationship_generator'
                RETURN type(r) as rel_type, count(r) as count
                ORDER BY count DESC
            """)
            
            for record in rel_stats:
                logger.info(f"{record['rel_type']}: {record['count']} 个关系")

        logger.info("\n关系生成完成！")
        
    except Exception as e:
        logger.error(f"关系生成失败: {e}")
        raise
    finally:
        if neo4j_conn:
            neo4j_conn.close()

if __name__ == "__main__":
    asyncio.run(generate_additional_relationships())
