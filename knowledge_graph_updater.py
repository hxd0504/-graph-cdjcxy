# 负责知识图谱更新逻辑。
import logging
from typing import Dict, List
from neo4j_crud import Neo4jCRUD
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

class KnowledgeGraphUpdater:
    def __init__(self, neo4j_conn):
        self.crud = Neo4jCRUD(neo4j_conn)

    def preprocess_data(self, data: Dict) -> Dict:
        """预处理数据以处理潜在的重复或规范化名称"""
        if data.get("name") == "纳木错":
            data["name"] = "纳木措"
        return data

    def update_knowledge_graph(self, data: Dict, log_id: str, reason: str, weights: Dict, all_nodes: List[Dict] = None):
        if not data.get("name"):
            logger.error(f"无效数据，缺少 'name' 字段: {data}")
            raise ValueError("Data must include 'name' field")
        try:
            with self.crud.driver.session() as session:
                session.execute_write(self.tx_work, self.preprocess_data(data), reason, log_id, weights)
        except Exception as e:
            logger.error(f"更新知识图谱失败 for {data.get('name', 'Unknown')}: {e}", exc_info=True)
            raise

    def tx_work(self, tx, data, reason, log_id, weights):
        # 创建或更新 Attraction 节点
        attraction_data = {
            "name": data.get("name", ""),
            "location": data.get("location", "拉萨市"),
            "address": data.get("address", ""),
            "description": data.get("description", f"Description for {data.get('name', 'Unknown')}"),
            "pub_timestamp": data.get("pub_timestamp", datetime.now(timezone(timedelta(hours=8))).isoformat() + "+08:00"),
            "best_comment": data.get("best_comment", ""),
            "source_type": data.get("source_type", "crawler"),
            "metrics": data.get("metrics", "{}"),
            "ranking": data.get("ranking", ""),
            "visitor_percentage": data.get("visitor_percentage", "")
        }
        if not attraction_data["name"] or not attraction_data["location"]:
            logger.warning(f"跳过处理，缺少必要字段: name={attraction_data['name']}, location={attraction_data['location']}")
            return

        # 直接使用Cypher查询创建节点，确保节点创建成功
        attraction_query = """
        MERGE (a:Attraction {name: $name})
        SET a += $props
        RETURN a
        """
        attraction_result = tx.run(attraction_query, name=attraction_data["name"], props=attraction_data).single()
        if attraction_result:
            logger.debug(f"成功创建/更新 Attraction 节点: {attraction_data['name']}")
        else:
            logger.warning(f"创建 Attraction 节点失败: {attraction_data['name']}")
            return

        # 创建或更新 City 节点
        city_data = {"name": attraction_data["location"]}
        city_query = """
        MERGE (c:City {name: $name})
        SET c += $props
        RETURN c
        """
        city_result = tx.run(city_query, name=city_data["name"], props=city_data).single()
        if city_result:
            logger.debug(f"成功创建/更新 City 节点: {city_data['name']}")
        else:
            logger.warning(f"创建 City 节点失败: {city_data['name']}")
            return

        # 创建 LOCATED_IN 关系 - 直接使用MERGE创建关系，不需要先检查节点是否存在
        try:
            relationship_query = """
            MATCH (a:Attraction {name: $attraction_name})
            MATCH (c:City {name: $city_name})
            MERGE (a)-[r:LOCATED_IN]->(c)
            SET r += $props
            RETURN r
            """
            rel_result = tx.run(
                relationship_query,
                attraction_name=attraction_data["name"],
                city_name=city_data["name"],
                props={"reason": reason}
            ).single()

            if rel_result:
                logger.debug(f"成功创建 LOCATED_IN 关系: {attraction_data['name']} -> {city_data['name']}")
            else:
                logger.warning(f"创建关系失败，可能节点不存在: {attraction_data['name']} -> {city_data['name']}")
        except Exception as e:
            logger.error(f"创建 LOCATED_IN 关系失败: {attraction_data['name']} -> {city_data['name']}: {str(e)}")
            # 不抛出异常，继续处理其他数据

        # 记录更新日志
        log_data = {
            "name": log_id,
            "log_id": log_id,
            "entity_name": attraction_data["name"],
            "reason": reason,
            "weights": str(weights),
            "timestamp": datetime.now(timezone(timedelta(hours=8))).isoformat()
        }
        log_query = """
        MERGE (l:UpdateLog {name: $name})
        SET l += $props
        """
        tx.run(log_query, name=log_data["name"], props=log_data)
        logger.debug(f"创建 UpdateLog 节点: {log_id}")

    def close(self):
        self.crud.close()