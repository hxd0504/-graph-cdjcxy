##时间转换
from datetime import datetime, timezone, timedelta
import logging

logger = logging.getLogger(__name__)

async def convert_to_beijing_time(timestamp: str = None) -> str:
    """转换为北京时间（UTC+8）
    
    Args:
        timestamp: 可选，ISO格式的时间戳字符串（例如 '2025-06-27T10:39:56+00:00'）。
                  如果未提供，返回当前北京时间。
    
    Returns:
        北京时间的ISO格式字符串（例如 '2025-06-27T22:39:56+08:00'）。
    """
    beijing_tz = timezone(timedelta(hours=8))
    if timestamp is None:
        # 无参数，返回当前北京时间
        return datetime.now(beijing_tz).isoformat()
    try:
        # 解析传入的时间戳并转换为北京时间
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        dt_beijing = dt.astimezone(beijing_tz)
        return dt_beijing.isoformat()
    except ValueError as e:
        logger.error(f"无效的时间戳格式: {timestamp}, 错误: {e}")
        # 回退到当前北京时间
        return datetime.now(beijing_tz).isoformat()

def convert_to_now_time():
    now_time = datetime.now()
    return now_time.isoformat()