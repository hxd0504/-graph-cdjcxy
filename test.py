import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

try:
    with open("D:/PythonCode/动态知识图谱的自适应演化/data/lhasa_knowledge_graph.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    nodes = data.get("nodes", data) if isinstance(data, dict) else data
    logger.info(f"总节点数: {len(nodes)}")
    
    # 统计字段分布
    vp_non_empty = [node for node in nodes if node.get("visitor_percentage") and node.get("visitor_percentage") != "0%"]
    logger.info(f"visitor_percentage 非空且非 0% 的节点数: {len(vp_non_empty)}")
    
    # 前 10 个节点详情
    logger.info("前 10 个节点详情:")
    for node in nodes[:10]:
        logger.info(f"Name: {node.get('name')}, Location: {node.get('location')}, Description: {node.get('description', '')[:50]}..., Visitor Percentage: {node.get('visitor_percentage', '')}")
    
    # 有效节点示例
    if vp_non_empty:
        logger.info("有效节点示例 (visitor_percentage > 0%):")
        for node in vp_non_empty[:5]:
            logger.info(f"Name: {node.get('name')}, Location: {node.get('location')}, Description: {node.get('description', '')[:50]}..., Visitor Percentage: {node.get('visitor_percentage')}")
    else:
        logger.warning("没有节点满足 visitor_percentage > 0%，检查数据")
except Exception as e:
    logger.error(f"读取 JSON 失败: {e}")