#用来处理知识图谱更新时的数据冲突的模块，主要是为了在动态知识图谱中决定如何合并新旧数据。它结合了时间戳优先级、来源权重和规则来解决冲突，确保图谱中的数据是最优的。

#具体功能：
#       1.冲突检测与解决：当新数据和已有数据（如景点信息）发生冲突时（例如 location 或 highlights 不同），
#         它会根据 pub_timestamp（发布时间）、source_type（来源类型，如政府、新闻）和 metrics（来源指标，如流量、评分）计算权重，决定采用哪部分数据。
#       2.动态权重计算：通过 compute_dynamic_weight 函数，根据来源类型和指标动态调整权重，还考虑了时间衰减（数据越旧，权重越低）。
#       3.规则应用：从 rules.txt 加载优先级规则，比如优先采用政府来源的数据。
#       4.冲突记录：如果冲突无法自动解决，会将冲突数据记录到 conflict_queue.json，供后续手动或 LLM 辅助解决。
import json
import logging
import os
from typing import Dict, List
from neo4j_crud import Neo4jCRUD
from utils import compute_semantic_similarity, compute_dynamic_weight
from datetime import datetime

logger = logging.getLogger(__name__)

class ConflictResolver:
    def __init__(self, crud: Neo4jCRUD):
        self.crud = crud
        self.conflict_log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "conflict_queue.json")
        logger.info("ConflictResolver initialized")

    def log_conflict(self, conflict: Dict):
        """记录冲突到文件"""
        try:
            with open(self.conflict_log_file, "a", encoding="utf-8") as f:
                json.dump(conflict, f, ensure_ascii=False)
                f.write("\n")
            logger.info(f"冲突记录到文件: {conflict['entity_name']}")
        except Exception as e:
            logger.error(f"记录冲突失败: {e}")

    async def resolve_conflict(self, conflict: Dict, model_name: str = "conflict_llm") -> Dict:
        """解决冲突（目前仅记录，未来可扩展为自动解决）"""
        logger.warning(f"检测到冲突，记录但不自动解决: {conflict['entity_name']}")
        return conflict

    async def check_relationship_conflict(self, rel: Dict, existing_rels: List[Dict]) -> bool:
        """检查关系冲突"""
        try:
            for existing in existing_rels:
                if (rel["source_name"] == existing["source_name"] and
                    rel["target_name"] == existing["target_name"] and
                    rel["type"] == existing["type"]):  # Changed rel_type to type
                    similarity = compute_semantic_similarity(
                        json.dumps(rel["properties"]), json.dumps(existing["properties"])
                    )
                    if similarity > 0.7:  # 语义相似度阈值
                        logger.warning(
                            f"检测到关系冲突: {rel['source_name']} -[{rel['type']}]-> {rel['target_name']}, "
                            f"相似度: {similarity}"
                        )
                        return True
            return False
        except Exception as e:
            logger.error(f"检查关系冲突失败: {e}")
            raise

    def get_conflict_log(self) -> List[Dict]:
        """获取冲突日志"""
        conflicts = []
        try:
            if os.path.exists(self.conflict_log_file):
                with open(self.conflict_log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            conflicts.append(json.loads(line.strip()))
                        except json.JSONDecodeError:
                            logger.error(f"解析冲突日志行失败: {line}")
            return conflicts
        except Exception as e:
            logger.error(f"读取冲突日志失败: {e}")
            return []