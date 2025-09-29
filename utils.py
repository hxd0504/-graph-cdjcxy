from sentence_transformers import SentenceTransformer
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Initialize SentenceTransformer model
model = SentenceTransformer('all-MiniLM-L6-v2')

def compute_semantic_similarity(text1: str, text2: str) -> float:
    try:
        if not text1 or not text2:
            return 0.0
        embeddings = model.encode([text1, text2])
        similarity = float(embeddings[0] @ embeddings[1].T)
        return max(0.0, min(1.0, similarity))
    except Exception as e:
        logger.error(f"计算语义相似度失败: {e}")
        return 0.0

def compute_dynamic_weight(data: dict, metrics: dict) -> float:
    """
    计算动态权重，基于数据的时间戳、来源类型和指标（如评分）。
    Args:
        data: 实体数据，包含 pub_timestamp, source_type 等
        metrics: 评估指标，如 ratings
    Returns:
        float: 权重值（0.0 到 1.0）
    """
    try:
        base_weight = metrics.get("ratings", 0.0) / 5.0  # 假设评分范围 0-5
        if data.get("source_type") == "crawler":
            base_weight *= 0.8  # 爬虫数据权重稍低
        elif data.get("source_type") == "manual":
            base_weight *= 1.0  # 人工数据权重最高
        timestamp = data.get("pub_timestamp", "")
        if timestamp:
            timestamp_date = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            age_days = (datetime.now().astimezone() - timestamp_date).days
            freshness = max(0.0, 1.0 - age_days / 365.0)  # 数据新鲜度衰减
            base_weight *= freshness
        return max(0.0, min(1.0, base_weight))
    except Exception as e:
        logger.error(f"计算动态权重失败: {e}")
        return 0.0

def normalize_location(location: str) -> str:
    CITY_MAP = {
        "拉萨市": "拉萨市",
        "当雄县": "拉萨市",
        "墨竹工卡县": "拉萨市",
        "林周县": "拉萨市",
        "尼木县": "拉萨市",
        "曲水县": "拉萨市"
    }
    return CITY_MAP.get(location, location)