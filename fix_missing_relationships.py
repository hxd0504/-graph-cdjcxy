#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复缺失的节点和关系
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

def fix_missing_relationships():
    """修复缺失的节点和关系"""
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
            # 1. 首先创建所有缺失的City节点
            logger.info("=== 步骤1: 创建缺失的City节点 ===")
            
            # 获取所有需要创建的City节点
            missing_cities_query = """
                MATCH (a:Attraction) 
                WHERE a.location IS NOT NULL 
                AND NOT EXISTS {
                    MATCH (c:City {name: a.location})
                }
                RETURN DISTINCT a.location as location, count(a) as attraction_count
                ORDER BY attraction_count DESC
            """
            missing_cities = session.run(missing_cities_query)
            
            cities_created = 0
            for record in missing_cities:
                location = record['location']
                attraction_count = record['attraction_count']
                
                # 创建City节点
                create_city_query = """
                MERGE (c:City {name: $location})
                SET c.created_by = 'fix_script'
                RETURN c
                """
                result = session.run(create_city_query, location=location).single()
                if result:
                    cities_created += 1
                    logger.info(f"创建City节点: {location} (将连接{attraction_count}个景点)")
            
            logger.info(f"总共创建了 {cities_created} 个City节点")

            # 2. 创建所有缺失的LOCATED_IN关系
            logger.info("\n=== 步骤2: 创建缺失的LOCATED_IN关系 ===")
            
            # 为所有有location但没有LOCATED_IN关系的Attraction创建关系
            create_relationships_query = """
                MATCH (a:Attraction), (c:City)
                WHERE a.location IS NOT NULL 
                AND a.location = c.name
                AND NOT (a)-[:LOCATED_IN]->()
                MERGE (a)-[r:LOCATED_IN]->(c)
                SET r.created_by = 'fix_script'
                RETURN count(r) as relationships_created
            """
            result = session.run(create_relationships_query).single()
            relationships_created = result['relationships_created'] if result else 0
            logger.info(f"创建了 {relationships_created} 个LOCATED_IN关系")

            # 3. 验证修复结果
            logger.info("\n=== 步骤3: 验证修复结果 ===")
            
            # 检查还有多少孤立的Attraction节点
            orphaned_count = session.run("""
                MATCH (a:Attraction) 
                WHERE NOT (a)-[:LOCATED_IN]->() 
                RETURN count(a) as count
            """).single()["count"]
            logger.info(f"修复后还有 {orphaned_count} 个孤立的Attraction节点")

            # 检查总的关系数量
            total_relations = session.run("""
                MATCH ()-[r:LOCATED_IN]->() 
                RETURN count(r) as count
            """).single()["count"]
            logger.info(f"现在总共有 {total_relations} 个LOCATED_IN关系")

            # 检查City节点数量
            total_cities = session.run("""
                MATCH (c:City) 
                RETURN count(c) as count
            """).single()["count"]
            logger.info(f"现在总共有 {total_cities} 个City节点")

            # 4. 显示一些修复后的示例
            logger.info("\n=== 修复后的关系示例 ===")
            sample_relations = session.run("""
                MATCH (a:Attraction)-[r:LOCATED_IN]->(c:City) 
                WHERE r.created_by = 'fix_script'
                RETURN a.name as attraction, c.name as city 
                LIMIT 10
            """)
            for record in sample_relations:
                logger.info(f"  {record['attraction']} -> {record['city']}")

            # 5. 检查是否还有问题
            logger.info("\n=== 剩余问题检查 ===")
            
            # 检查有location但仍然没有关系的节点
            still_missing = session.run("""
                MATCH (a:Attraction) 
                WHERE a.location IS NOT NULL 
                AND NOT (a)-[:LOCATED_IN]->() 
                RETURN a.name as name, a.location as location
                LIMIT 5
            """)
            
            still_missing_count = 0
            for record in still_missing:
                logger.info(f"仍然缺失关系: {record['name']} (location: {record['location']})")
                still_missing_count += 1
            
            if still_missing_count == 0:
                logger.info("✅ 所有有location的Attraction都已经有LOCATED_IN关系了！")
            else:
                logger.info(f"⚠️  还有一些节点需要手动检查")

        logger.info("\n修复完成！")
        
    except Exception as e:
        logger.error(f"修复失败: {e}")
        raise
    finally:
        if neo4j_conn:
            neo4j_conn.close()

if __name__ == "__main__":
    fix_missing_relationships()
