#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试节点和关系创建修复的脚本
"""

import logging
import sys
import os
from datetime import datetime, timezone, timedelta

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from neo4j_connection import Neo4jConnection
from knowledge_graph_updater import KnowledgeGraphUpdater

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_node_and_relationship_creation():
    """测试节点和关系创建"""
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

        # 创建知识图谱更新器
        updater = KnowledgeGraphUpdater(neo4j_conn)

        # 测试数据
        test_data = [
            {
                "name": "布达拉宫",
                "location": "拉萨市",
                "address": "西藏拉萨市城关区北京中路35号",
                "description": "布达拉宫是西藏拉萨的标志性建筑",
                "pub_timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "source_type": "test"
            },
            {
                "name": "大昭寺",
                "location": "拉萨市", 
                "address": "西藏拉萨市城关区八廓街",
                "description": "大昭寺是西藏现存最辉煌的吐蕃时期的建筑",
                "pub_timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "source_type": "test"
            },
            {
                "name": "纳木措",
                "location": "当雄县",
                "address": "西藏拉萨市当雄县",
                "description": "纳木措是西藏第二大湖泊",
                "pub_timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat(),
                "source_type": "test"
            }
        ]

        # 清空测试数据（可选）
        logger.info("清空现有测试数据...")
        with neo4j_conn.driver.session() as session:
            session.run("MATCH (n) WHERE n.source_type = 'test' DETACH DELETE n")

        # 测试节点和关系创建
        logger.info("开始测试节点和关系创建...")
        for i, data in enumerate(test_data):
            try:
                log_id = f"test_{data['name']}_{i}"
                reason = "测试节点和关系创建"
                weights = {"rules_valid": 1.0, "llm_valid": 0.8, "weight_valid": 0.9}
                
                logger.info(f"处理测试数据: {data['name']}")
                updater.update_knowledge_graph(data, log_id, reason, weights)
                logger.info(f"成功处理: {data['name']}")
                
            except Exception as e:
                logger.error(f"处理失败 {data['name']}: {e}")

        # 验证结果
        logger.info("验证创建结果...")
        with neo4j_conn.driver.session() as session:
            # 检查节点数量
            attraction_count = session.run("MATCH (a:Attraction) WHERE a.source_type = 'test' RETURN count(a) as count").single()["count"]
            city_count = session.run("MATCH (a:Attraction)-[:LOCATED_IN]->(c:City) WHERE a.source_type = 'test' RETURN count(DISTINCT c) as count").single()["count"]
            relationship_count = session.run("MATCH (a:Attraction)-[r:LOCATED_IN]->(c:City) WHERE a.source_type = 'test' RETURN count(r) as count").single()["count"]
            
            logger.info(f"创建结果统计:")
            logger.info(f"  - Attraction 节点: {attraction_count}")
            logger.info(f"  - City 节点: {city_count}")
            logger.info(f"  - LOCATED_IN 关系: {relationship_count}")
            
            # 显示具体的节点和关系
            results = session.run("""
                MATCH (a:Attraction)-[r:LOCATED_IN]->(c:City) 
                WHERE a.source_type = 'test' 
                RETURN a.name as attraction, c.name as city
            """)
            
            logger.info("创建的关系:")
            for record in results:
                logger.info(f"  - {record['attraction']} -> {record['city']}")

        logger.info("测试完成！")
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        raise
    finally:
        if neo4j_conn:
            neo4j_conn.close()

if __name__ == "__main__":
    test_node_and_relationship_creation()
