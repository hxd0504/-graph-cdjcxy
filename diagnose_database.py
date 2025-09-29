#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
诊断数据库中节点和关系的问题
"""

import logging
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import Config
from neo4j_connection import Neo4jConnection

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def diagnose_database():
    """诊断数据库中的节点和关系问题"""
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
            # 1. 检查所有节点标签和数量
            logger.info("=== 数据库节点统计 ===")
            labels_result = session.run("CALL db.labels()")
            for record in labels_result:
                label = record[0]
                count = session.run(f"MATCH (n:{label}) RETURN count(n) as count").single()["count"]
                logger.info(f"{label}: {count} 个节点")

            # 2. 检查关系类型和数量
            logger.info("\n=== 数据库关系统计 ===")
            rel_types_result = session.run("CALL db.relationshipTypes()")
            for record in rel_types_result:
                rel_type = record[0]
                count = session.run(f"MATCH ()-[r:{rel_type}]->() RETURN count(r) as count").single()["count"]
                logger.info(f"{rel_type}: {count} 个关系")

            # 3. 检查孤立的Attraction节点（没有LOCATED_IN关系的）
            logger.info("\n=== 孤立的Attraction节点 ===")
            orphaned_attractions = session.run("""
                MATCH (a:Attraction) 
                WHERE NOT (a)-[:LOCATED_IN]->() 
                RETURN a.name as name 
                LIMIT 10
            """)
            orphaned_count = 0
            for record in orphaned_attractions:
                logger.info(f"孤立节点: {record['name']}")
                orphaned_count += 1
            
            total_orphaned = session.run("""
                MATCH (a:Attraction) 
                WHERE NOT (a)-[:LOCATED_IN]->() 
                RETURN count(a) as count
            """).single()["count"]
            logger.info(f"总共有 {total_orphaned} 个孤立的Attraction节点")

            # 4. 检查没有对应City节点的location
            logger.info("\n=== 缺失的City节点 ===")
            missing_cities = session.run("""
                MATCH (a:Attraction) 
                WHERE a.location IS NOT NULL 
                AND NOT EXISTS {
                    MATCH (c:City {name: a.location})
                }
                RETURN DISTINCT a.location as location, count(a) as attraction_count
                ORDER BY attraction_count DESC
                LIMIT 10
            """)
            for record in missing_cities:
                logger.info(f"缺失City节点: {record['location']} (有{record['attraction_count']}个景点)")

            # 5. 检查数据完整性
            logger.info("\n=== 数据完整性检查 ===")
            
            # 检查有多少Attraction有location但没有LOCATED_IN关系
            no_relation_count = session.run("""
                MATCH (a:Attraction) 
                WHERE a.location IS NOT NULL 
                AND NOT (a)-[:LOCATED_IN]->() 
                RETURN count(a) as count
            """).single()["count"]
            logger.info(f"有location但没有LOCATED_IN关系的Attraction: {no_relation_count}")

            # 检查有多少LOCATED_IN关系指向不存在的City
            broken_relations = session.run("""
                MATCH (a:Attraction)-[r:LOCATED_IN]->(c) 
                WHERE NOT c:City 
                RETURN count(r) as count
            """).single()["count"]
            logger.info(f"指向非City节点的LOCATED_IN关系: {broken_relations}")

            # 6. 显示一些示例数据
            logger.info("\n=== 示例数据 ===")
            sample_data = session.run("""
                MATCH (a:Attraction)-[r:LOCATED_IN]->(c:City) 
                RETURN a.name as attraction, c.name as city 
                LIMIT 5
            """)
            logger.info("正常的关系示例:")
            for record in sample_data:
                logger.info(f"  {record['attraction']} -> {record['city']}")

        logger.info("\n诊断完成！")
        
    except Exception as e:
        logger.error(f"诊断失败: {e}")
        raise
    finally:
        if neo4j_conn:
            neo4j_conn.close()

if __name__ == "__main__":
    diagnose_database()
