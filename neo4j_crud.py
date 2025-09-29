#负责 Neo4j 数据库的 CRUD 操作。
import logging
from typing import Dict, List, Optional
from neo4j import GraphDatabase
from neo4j.exceptions import CypherSyntaxError
import json
from datetime import datetime
from neo4j_connection import Neo4jConnection
import os

logger = logging.getLogger(__name__)

class Neo4jCRUD:
    def __init__(self, connection: Neo4jConnection):
        self.driver = connection.driver
        self.conflict_log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conflict_queue.json")
        logger.info("Neo4jCRUD initialized with provided connection")

    def close(self):
        self.driver.close()
        logger.info("Neo4jCRUD connection closed")

    def node_exists(self, tx, label: str, name: str) -> bool:
        """检查节点是否存在"""
        try:
            query = f"MATCH (n:{label} {{name: $name}}) RETURN n"
            result = tx.run(query, name=name)
            return result.single() is not None
        except Exception as e:
            logger.error(f"检查节点存在失败: {label}:{name}, 错误: {str(e)}")
            return False

    def get_entity_with_changes(self, tx, label: str, name: str) -> Optional[Dict]:
        """获取实体及其变更日志"""
        try:
            query = f"MATCH (a:{label} {{name: $name}}) RETURN a"
            result = tx.run(query, name=name)
            record = result.single()
            if record:
                entity = dict(record["a"])
                changes = []
                if "changelog" in entity:
                    changes = [json.loads(c) for c in entity["changelog"]]
                    entity.pop("changelog", None)
                return {"entity": entity, "changes": changes}
            return None
        except CypherSyntaxError as e:
            logger.error(f"Cypher 语法错误: {e}, 查询: {query}, 参数: {name}")
            raise
        except Exception as e:
            logger.error(f"查询失败: {e}, 查询: {query}, 参数: {name}")
            return None

    def create_or_update_entity(self, tx, data: Dict, change_log: str, label: str = "Attraction"):
        """创建或更新实体"""
        query = f"""
        MERGE (a:{label} {{name: $name}})
        SET a += $props
        """
        try:
            result = tx.run(query, name=data["name"], props=data)
            summary = result.consume()
            if summary.counters.properties_set > 0:
                with open(self.conflict_log_file, "a", encoding="utf-8") as f:
                    json.dump({"name": data["name"], "change_log": change_log, "timestamp": datetime.now().isoformat()}, f, ensure_ascii=False)
                    f.write("\n")
                logger.debug(f"更新实体: {label}, 名称: {data['name']}")
            else:
                logger.debug(f"创建实体: {label}, 名称: {data['name']}")
        except CypherSyntaxError as e:
            logger.error(f"Cypher 语法错误: {e}, 查询: {query}, 参数: {data['name']}")
            raise
        except Exception as e:
            logger.error(f"创建或更新实体失败: {label}, 名称: {data['name']}, 错误: {e}")
            raise

    def create_relationship(self, tx, source_label: str, source_name: str, target_label: str, target_name: str, rel_type: str, properties: Dict = {}):
        """创建关系"""
        try:
            # 首先确保两个节点都存在
            create_nodes_query = f"""
            MERGE (source:{source_label} {{name: $source_name}})
            MERGE (target:{target_label} {{name: $target_name}})
            RETURN source, target
            """
            nodes_result = tx.run(create_nodes_query, source_name=source_name, target_name=target_name).single()

            if not nodes_result:
                logger.warning(f"无法创建节点: {source_label}:{source_name} 或 {target_label}:{target_name}")
                return False

            # 然后创建关系
            query = f"""
            MATCH (source:{source_label} {{name: $source_name}})
            MATCH (target:{target_label} {{name: $target_name}})
            MERGE (source)-[r:{rel_type}]->(target)
            SET r += $props
            RETURN r
            """
            result = tx.run(query, source_name=source_name, target_name=target_name, props=properties)
            rel = result.single()

            if rel:
                logger.debug(f"创建关系: {source_label}:{source_name} -[{rel_type}]-> {target_label}:{target_name}")
                return True
            else:
                logger.warning(f"关系创建失败: {source_label}:{source_name} -[{rel_type}]-> {target_label}:{target_name}")
                return False

        except CypherSyntaxError as e:
            logger.error(f"Cypher 语法错误: {e}, 查询: {query}, 参数: {source_name} -> {target_name}")
            return False
        except Exception as e:
            logger.error(f"创建关系失败: {source_label}:{source_name} -[{rel_type}]-> {target_label}:{target_name}, 错误: {e}")
            return False

    def get_relationships(self, tx, label: str, name: str) -> List[Dict]:
        """获取与指定节点相关的所有关系"""
        try:
            query = f"""
            MATCH (a:{label} {{name: $name}})-[r]->(b)
            RETURN a.name AS source_name, type(r) AS type, b.name AS target_name, properties(r) AS properties
            """
            result = tx.run(query, name=name)
            relationships = [{"source_name": record["source_name"], "type": record["type"], "target_name": record["target_name"], "properties": dict(record["properties"])} for record in result]
            logger.debug(f"获取关系: {label}:{name}, 找到 {len(relationships)} 个关系")
            return relationships
        except CypherSyntaxError as e:
            logger.error(f"Cypher 语法错误: {e}, 查询: {query}, 参数: {name}")
            raise
        except Exception as e:
            logger.error(f"获取关系失败: {label}, 名称: {name}, 错误: {e}")
            return []

    def delete_entity(self, tx, label: str, name: str):
        """删除实体"""
        try:
            query = f"""
            MATCH (a:{label} {{name: $name}})
            DETACH DELETE a
            """
            tx.run(query, name=name).consume()
            logger.debug(f"删除实体: {label}, 名称: {name}")
        except CypherSyntaxError as e:
            logger.error(f"Cypher 语法错误: {e}, 查询: {query}, 参数: {name}")
            raise
        except Exception as e:
            logger.error(f"删除实体失败: {label}, 名称: {name}, 错误: {e}")
            raise

    def execute_query(self, tx, query: str, params: Dict = None):
        """执行Cypher查询"""
        try:
            result = tx.run(query, params or {})
            result.consume()
        except CypherSyntaxError as e:
            logger.error(f"Cypher 语法错误: {e}, 查询: {query}, 参数: {params}")
            raise
        except Exception as e:
            logger.error(f"执行查询失败: {query}, 参数: {params}, 错误: {e}")
            raise