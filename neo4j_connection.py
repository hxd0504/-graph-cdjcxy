#定义Neo4jConnection类
import logging
from neo4j import GraphDatabase
from typing import Dict, Any

logger = logging.getLogger(__name__)

class Neo4jConnection:
    def __init__(self, uri: str, user: str, password: str):
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            logger.info(f"初始化 Neo4j 连接: {uri}, 用户: {user}")
        except Exception as e:
            logger.error(f"初始化 Neo4j 驱动失败: {e}")
            raise

    def verify_connectivity(self):
        try:
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info("Neo4j 连接验证成功")
        except Exception as e:
            logger.error(f"Neo4j 连接验证失败: {e}")
            raise

    def execute_query(self, query: str, params: Dict[str, Any] = None):
        try:
            with self.driver.session() as session:
                session.run(query, params or {})
            logger.debug(f"执行查询: {query}, 参数: {params}")
        except Exception as e:
            logger.error(f"执行查询失败: {query}, 错误: {e}")
            raise

    def clear_database(self):
        try:
            query = "MATCH (n) DETACH DELETE n"
            with self.driver.session() as session:
                session.run(query)
            logger.info("清空所有节点和关系")
        except Exception as e:
            logger.error(f"清空数据库失败: {e}")
            raise

    def close(self):
        try:
            self.driver.close()
            logger.info("Neo4j 连接已关闭")
        except Exception as e:
            logger.error(f"关闭 Neo4j 连接失败: {e}")