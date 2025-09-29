"""
冲突解决策略实验评估模块

该模块实现了三种不同的冲突解决策略，并提供了一个框架来评估它们的决策准确性。
这三种策略分别是：
1. Weight-First: 只考虑来源权重
2. Latest-First: 只考虑时间戳
3. Hybrid: 混合策略，结合权重和时间戳
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Tuple, Any
from utils import compute_dynamic_weight, compute_semantic_similarity

logger = logging.getLogger(__name__)

def resolve_conflict_weight_first(conflicting_facts: List[Dict]) -> Dict:
    """
    仅基于来源权重解决冲突。
    
    参数:
        conflicting_facts: 冲突事实列表
        
    返回:
        具有最高权重的事实
    """
    if not conflicting_facts:
        return {}
    
    # 按权重排序，权重高的排前面
    sorted_facts = sorted(conflicting_facts, key=lambda x: x.get('source', {}).get('weight', 0), reverse=True)
    
    # 返回权重最高的事实
    return sorted_facts[0]

def resolve_conflict_latest_first(conflicting_facts: List[Dict]) -> Dict:
    """
    仅基于时间戳解决冲突，最新的事实胜出。
    
    参数:
        conflicting_facts: 冲突事实列表
        
    返回:
        时间戳最新的事实
    """
    if not conflicting_facts:
        return {}
    
    # 将字符串时间戳转换为datetime对象进行排序
    def parse_timestamp(fact):
        try:
            timestamp_str = fact.get('timestamp', '')
            if timestamp_str:
                return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            return datetime.min
        except (ValueError, TypeError):
            logger.warning(f"无效的时间戳格式: {fact.get('timestamp')}")
            return datetime.min
    
    # 按时间戳排序，最新的排前面
    sorted_facts = sorted(conflicting_facts, key=parse_timestamp, reverse=True)
    
    # 返回时间戳最新的事实
    return sorted_facts[0]

def resolve_conflict_with_hybrid(conflicting_facts: List[Dict]) -> Tuple[Dict, Dict]:
    """
    混合策略解决冲突，考虑权重和时间戳。
    
    参数:
        conflicting_facts: 冲突事实列表
        
    返回:
        获胜的事实和决策说明
    """
    if not conflicting_facts:
        return {}, {"reason": "没有提供冲突事实"}
    
    # 对每个事实计算综合分数 = 基础权重 + 时间衰减调整
    scored_facts = []
    now = datetime.now()
    
    for fact in conflicting_facts:
        # 获取基础权重
        base_weight = fact.get('source', {}).get('weight', 0.5)
        
        # 计算时间因素
        try:
            timestamp_str = fact.get('timestamp', '')
            if timestamp_str:
                fact_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                time_diff_days = (now - fact_time).days
                
                # 修改时间衰减系数：降低底线至0.3，增加衰减速率
                time_decay = max(0.3, 1 - (time_diff_days / 30) * 0.15)
                
                # 计算时间新鲜度分数 (1.0表示最新，随时间递减)
                time_freshness = 1.0 - min(1.0, time_diff_days / 365) * 0.7
            else:
                time_decay = 0.3  # 没有时间戳，使用默认衰减
                time_freshness = 0.3
        except (ValueError, TypeError):
            logger.warning(f"无效的时间戳格式: {fact.get('timestamp')}")
            time_decay = 0.3
            time_freshness = 0.3
        
        # 计算内容质量分数 (基于内容长度，简单估计)
        content_value = fact.get('value', '')
        content_quality = min(1.0, len(content_value) / 200) * 0.5 + 0.5
        
        # 修改综合分数计算方式：权重占60%，时间占30%，内容质量占10%
        final_score = base_weight * 0.6 + time_freshness * 0.3 + content_quality * 0.1
        
        # 将事实及其分数添加到列表
        scored_facts.append((fact, final_score, {
            "base_weight": base_weight, 
            "time_decay": time_decay,
            "time_freshness": time_freshness,
            "content_quality": content_quality
        }))
    
    # 按综合分数排序
    sorted_facts = sorted(scored_facts, key=lambda x: x[1], reverse=True)
    
    # 获取综合分数最高的事实
    winning_fact = sorted_facts[0][0]
    explanation = {
        "reason": "基于综合评分选择的获胜事实",
        "scores": {
            fact.get('source', {}).get('url', f"事实{i}"): {
                "final_score": score,
                "details": details
            } for i, (fact, score, details) in enumerate(sorted_facts)
        }
    }
    
    return winning_fact, explanation

def run_conflict_resolution_experiment():
    """
    运行冲突解决策略实验，比较三种不同策略的决策准确性。
    """
    print("\n" + "="*80)
    print("开始冲突解决策略实验评估".center(80))
    print("="*80 + "\n")
    
    # 定义测试用例
    manual_test_set = [
        # 原有的测试用例
        {
            "name": "高权重但旧数据 vs 低权重但新数据",
            "conflicts": [
                {
                    "entity_name": "布达拉宫",
                    "attribute": "描述",
                    "value": "布达拉宫是世界上海拔最高、最雄伟的宫殿，是西藏最重要的象征。",
                    "source": {
                        "type": "government",
                        "url": "http://gov.cn/palace_info",
                        "weight": 0.9
                    },
                    "timestamp": "2022-01-15T14:30:00Z"
                },
                {
                    "entity_name": "布达拉宫",
                    "attribute": "描述",
                    "value": "布达拉宫位于中国西藏自治区拉萨市，是一座宫堡式建筑群，最初建于公元7世纪。",
                    "source": {
                        "type": "blog",
                        "url": "http://travel-blog.com/lhasa/palace",
                        "weight": 0.4
                    },
                    "timestamp": "2023-05-20T09:15:00Z"
                }
            ],
            "expected_winner_id": "http://gov.cn/palace_info"  # 权重应该战胜时间戳
        },
        {
            "name": "权重相近但时间差异大",
            "conflicts": [
                {
                    "entity_name": "大昭寺",
                    "attribute": "游览时间",
                    "value": "推荐游览时间：2-3小时",
                    "source": {
                        "type": "travel_site",
                        "url": "http://travel.com/temple",
                        "weight": 0.6
                    },
                    "timestamp": "2021-03-10T10:20:00Z"
                },
                {
                    "entity_name": "大昭寺",
                    "attribute": "游览时间",
                    "value": "推荐游览时间：1.5-2小时，周末人多需预留更多时间",
                    "source": {
                        "type": "travel_site",
                        "url": "http://visit-tibet.com/jokhang",
                        "weight": 0.65
                    },
                    "timestamp": "2023-08-05T16:45:00Z"
                }
            ],
            "expected_winner_id": "http://visit-tibet.com/jokhang"  # 权重相近，新数据应该胜出
        },
        {
            "name": "权重差异大，时间差异小",
            "conflicts": [
                {
                    "entity_name": "纳木错",
                    "attribute": "门票",
                    "value": "门票：120元/人",
                    "source": {
                        "type": "official_tourism",
                        "url": "http://tibet-tourism.gov/namtso",
                        "weight": 0.95
                    },
                    "timestamp": "2023-04-01T08:30:00Z"
                },
                {
                    "entity_name": "纳木错",
                    "attribute": "门票",
                    "value": "门票：100元/人",
                    "source": {
                        "type": "social_media",
                        "url": "http://weibo.com/user/travel_post",
                        "weight": 0.3
                    },
                    "timestamp": "2023-04-15T14:20:00Z"
                }
            ],
            "expected_winner_id": "http://tibet-tourism.gov/namtso"  # 权重应该战胜近期的错误信息
        },
        {
            "name": "低权重旧数据 vs 高权重新数据",
            "conflicts": [
                {
                    "entity_name": "羊卓雍错",
                    "attribute": "最佳游览季节",
                    "value": "最佳游览时间：5-10月",
                    "source": {
                        "type": "forum",
                        "url": "http://travel-forum.com/lakes",
                        "weight": 0.4
                    },
                    "timestamp": "2021-12-20T11:10:00Z"
                },
                {
                    "entity_name": "羊卓雍错",
                    "attribute": "最佳游览季节",
                    "value": "最佳游览时间：6-9月，尤其7-8月风景最佳",
                    "source": {
                        "type": "tourism_bureau",
                        "url": "http://lhasa-tourism.gov/yamdrok",
                        "weight": 0.85
                    },
                    "timestamp": "2023-03-15T09:30:00Z"
                }
            ],
            "expected_winner_id": "http://lhasa-tourism.gov/yamdrok"  # 高权重和新数据双重优势
        },
        
        # 新增测试用例
        {
            "name": "相同权重但时间差异巨大",
            "conflicts": [
                {
                    "entity_name": "扎什伦布寺",
                    "attribute": "开放时间",
                    "value": "开放时间：夏季9:00-18:00，冬季9:00-17:00",
                    "source": {
                        "type": "travel_guide",
                        "url": "http://travel-guide.com/shigatse",
                        "weight": 0.7
                    },
                    "timestamp": "2020-06-10T11:30:00Z"
                },
                {
                    "entity_name": "扎什伦布寺",
                    "attribute": "开放时间",
                    "value": "开放时间：全年9:00-18:00，周一闭馆",
                    "source": {
                        "type": "travel_guide",
                        "url": "http://tourist-handbook.com/shigatse",
                        "weight": 0.7
                    },
                    "timestamp": "2023-10-05T15:20:00Z"
                }
            ],
            "expected_winner_id": "http://tourist-handbook.com/shigatse"  # 权重相同，应选择最新数据
        },
        {
            "name": "中等权重新数据 vs 高权重旧数据（临界情况）",
            "conflicts": [
                {
                    "entity_name": "噶丹寺",
                    "attribute": "门票价格",
                    "value": "门票价格：50元/人",
                    "source": {
                        "type": "official_site",
                        "url": "http://tibet-culture.gov/gandan",
                        "weight": 0.85
                    },
                    "timestamp": "2021-04-18T09:45:00Z"
                },
                {
                    "entity_name": "噶丹寺",
                    "attribute": "门票价格",
                    "value": "门票价格：60元/人，学生半价",
                    "source": {
                        "type": "travel_agency",
                        "url": "http://tibet-travel.com/monastery",
                        "weight": 0.7
                    },
                    "timestamp": "2023-11-22T14:10:00Z"
                }
            ],
            "expected_winner_id": "http://tibet-travel.com/monastery"  # 权重差不太多，但时间差距大，新数据应胜出
        },
        {
            "name": "权重差异极大的情况",
            "conflicts": [
                {
                    "entity_name": "西藏博物馆",
                    "attribute": "馆藏数量",
                    "value": "馆藏文物超过1万件，包括唐卡、佛像等珍贵文物",
                    "source": {
                        "type": "government",
                        "url": "http://xizang-museum.gov.cn/stats",
                        "weight": 0.95
                    },
                    "timestamp": "2022-08-15T10:30:00Z"
                },
                {
                    "entity_name": "西藏博物馆",
                    "attribute": "馆藏数量",
                    "value": "据说有几千件文物，最著名的是金瓶掣签",
                    "source": {
                        "type": "personal_blog",
                        "url": "http://my-travels.blog/tibet-museum",
                        "weight": 0.2
                    },
                    "timestamp": "2023-12-01T16:25:00Z"
                }
            ],
            "expected_winner_id": "http://xizang-museum.gov.cn/stats"  # 极高权重应压倒新但不可靠的数据
        },
        {
            "name": "同源但内容更新的情况",
            "conflicts": [
                {
                    "entity_name": "色拉寺",
                    "attribute": "辩经时间",
                    "value": "辩经时间：每周一、三、五下午3点",
                    "source": {
                        "type": "official_site",
                        "url": "http://sera-monastery.org/info",
                        "weight": 0.9
                    },
                    "timestamp": "2022-03-10T08:15:00Z"
                },
                {
                    "entity_name": "色拉寺",
                    "attribute": "辩经时间",
                    "value": "辩经时间：每周一至周五下午3点，节假日暂停",
                    "source": {
                        "type": "official_site",
                        "url": "http://sera-monastery.org/info",
                        "weight": 0.9
                    },
                    "timestamp": "2023-09-28T11:45:00Z"
                }
            ],
            "expected_winner_id": "http://sera-monastery.org/info"  # 同源情况下，应选择最新的数据
        },
        {
            "name": "权重和时间戳都相近的情况",
            "conflicts": [
                {
                    "entity_name": "哲蚌寺",
                    "attribute": "地址",
                    "value": "地址：西藏自治区拉萨市城关区哲蚌路1号",
                    "source": {
                        "type": "map_service",
                        "url": "http://maps-tibet.com/drepung",
                        "weight": 0.75
                    },
                    "timestamp": "2023-05-10T14:30:00Z"
                },
                {
                    "entity_name": "哲蚌寺",
                    "attribute": "地址",
                    "value": "地址：拉萨市城关区哲蚌寺路，距市中心约9公里",
                    "source": {
                        "type": "tourism_bureau",
                        "url": "http://lhasa-tourism.org/drepung",
                        "weight": 0.78
                    },
                    "timestamp": "2023-06-15T09:20:00Z"
                }
            ],
            "expected_winner_id": "http://lhasa-tourism.org/drepung"  # 权重略高且更新，应该胜出
        },
        {
            "name": "权威政府源与流量大的商业源对比",
            "conflicts": [
                {
                    "entity_name": "八廓街",
                    "attribute": "介绍",
                    "value": "八廓街是拉萨古城区的核心区域，是西藏历史文化保护区",
                    "source": {
                        "type": "government",
                        "url": "http://lhasa.gov.cn/barkhor",
                        "weight": 0.9
                    },
                    "timestamp": "2022-11-20T10:40:00Z"
                },
                {
                    "entity_name": "八廓街",
                    "attribute": "介绍",
                    "value": "八廓街是拉萨最热闹的商业街区，有众多纪念品商店和传统藏式餐厅",
                    "source": {
                        "type": "commercial_travel",
                        "url": "http://ctrip.com/lhasa/barkhor",
                        "weight": 0.7
                    },
                    "timestamp": "2023-07-30T16:55:00Z"
                }
            ],
            "expected_winner_id": "http://lhasa.gov.cn/barkhor"  # 政府源权威性更高，应该胜出
        },
        {
            "name": "多数据源冲突",
            "conflicts": [
                {
                    "entity_name": "普莫雍错",
                    "attribute": "湖面海拔",
                    "value": "海拔5030米，是世界上海拔最高的咸水湖之一",
                    "source": {
                        "type": "scientific_journal",
                        "url": "http://geo-science.org/tibet-lakes",
                        "weight": 0.85
                    },
                    "timestamp": "2021-08-14T11:25:00Z"
                },
                {
                    "entity_name": "普莫雍错",
                    "attribute": "湖面海拔",
                    "value": "海拔约5018米",
                    "source": {
                        "type": "travel_guide",
                        "url": "http://lonely-planet.com/pumoyongcuo",
                        "weight": 0.7
                    },
                    "timestamp": "2022-06-20T15:30:00Z"
                },
                {
                    "entity_name": "普莫雍错",
                    "attribute": "湖面海拔",
                    "value": "海拔5010-5020米之间，具体数值随季节变化",
                    "source": {
                        "type": "research_institute",
                        "url": "http://tibet-research.org/lakes/pmy",
                        "weight": 0.9
                    },
                    "timestamp": "2023-02-28T09:15:00Z"
                }
            ],
            "expected_winner_id": "http://tibet-research.org/lakes/pmy"  # 最高权重且相对较新
        },
        {
            "name": "旧数据但详细 vs 新数据但简略",
            "conflicts": [
                {
                    "entity_name": "雍布拉康",
                    "attribute": "历史",
                    "value": "雍布拉康始建于公元前2世纪松赞干布时期以前，是西藏第一座宫殿式建筑，后改为寺庙。建筑呈塔楼式，主体为三层，其上为十三层金顶，整体依山而建，外形如同城堡。",
                    "source": {
                        "type": "historical_record",
                        "url": "http://tibet-history.org/yumbulagang",
                        "weight": 0.8
                    },
                    "timestamp": "2021-05-12T14:20:00Z"
                },
                {
                    "entity_name": "雍布拉康",
                    "attribute": "历史",
                    "value": "雍布拉康建于公元前2世纪，是西藏最古老的建筑之一",
                    "source": {
                        "type": "travel_site",
                        "url": "http://travel-guide.net/yumbulagang",
                        "weight": 0.6
                    },
                    "timestamp": "2023-10-05T11:30:00Z"
                }
            ],
            "expected_winner_id": "http://tibet-history.org/yumbulagang"  # 详细且高权重的历史信息应该胜出
        },
        {
            "name": "信息冲突但两者都有部分正确",
            "conflicts": [
                {
                    "entity_name": "萨迦寺",
                    "attribute": "特色",
                    "value": "萨迦寺以其丰富的藏书和壁画闻名，尤其是十万余册的经书和历史文献",
                    "source": {
                        "type": "academic",
                        "url": "http://culture-tibet.edu/sakya",
                        "weight": 0.85
                    },
                    "timestamp": "2022-02-10T10:15:00Z"
                },
                {
                    "entity_name": "萨迦寺",
                    "attribute": "特色",
                    "value": "萨迦寺的建筑风格独特，有'灰红相间'的特点，是藏传佛教萨迦派的主寺",
                    "source": {
                        "type": "travel_guide",
                        "url": "http://tibet-explorer.com/sakya",
                        "weight": 0.7
                    },
                    "timestamp": "2023-08-22T16:40:00Z"
                }
            ],
            "expected_winner_id": "http://culture-tibet.edu/sakya"  # 学术权重更高，内容关于核心文化特色
        },
        {
            "name": "不同媒体类型的冲突",
            "conflicts": [
                {
                    "entity_name": "米拉日巴佛阁",
                    "attribute": "介绍",
                    "value": "米拉日巴佛阁是为纪念大师米拉日巴而建，建于14世纪",
                    "source": {
                        "type": "video",
                        "url": "http://youtube.com/tibet-travel/milarepa",
                        "weight": 0.6
                    },
                    "timestamp": "2023-06-10T14:25:00Z"
                },
                {
                    "entity_name": "米拉日巴佛阁",
                    "attribute": "介绍",
                    "value": "米拉日巴佛阁位于定日县扎西宗乡境内，是为纪念藏传佛教噶举派创始人米拉日巴尊者而建，建于11世纪末12世纪初",
                    "source": {
                        "type": "book",
                        "url": "http://tibet-encyclopedia.org/milarepa",
                        "weight": 0.8
                    },
                    "timestamp": "2020-11-05T09:30:00Z"
                }
            ],
            "expected_winner_id": "http://tibet-encyclopedia.org/milarepa"  # 百科全书类型权威性更高，尽管更旧
        },
        {
            "name": "极高权重新数据 vs 极高权重旧数据",
            "conflicts": [
                {
                    "entity_name": "珠穆朗玛峰",
                    "attribute": "高度",
                    "value": "高度：8844.43米（基于2005年测量数据）",
                    "source": {
                        "type": "government",
                        "url": "http://gov.cn/everest-2005",
                        "weight": 0.95
                    },
                    "timestamp": "2021-01-20T08:20:00Z"
                },
                {
                    "entity_name": "珠穆朗玛峰",
                    "attribute": "高度",
                    "value": "高度：8848.86米（基于2020年最新联合测量数据）",
                    "source": {
                        "type": "government",
                        "url": "http://gov.cn/everest-2020",
                        "weight": 0.95
                    },
                    "timestamp": "2023-04-15T11:40:00Z"
                }
            ],
            "expected_winner_id": "http://gov.cn/everest-2020"  # 权重相同，应选择最新数据
        },
        {
            "name": "低权重新数据（但错误明显）",
            "conflicts": [
                {
                    "entity_name": "日喀则",
                    "attribute": "人口",
                    "value": "市区人口约为8万人，全市约70万人",
                    "source": {
                        "type": "government",
                        "url": "http://shigatse.gov.cn/stats",
                        "weight": 0.9
                    },
                    "timestamp": "2022-03-01T10:15:00Z"
                },
                {
                    "entity_name": "日喀则",
                    "attribute": "人口",
                    "value": "人口约3000万人",  # 明显错误的数据
                    "source": {
                        "type": "social_media",
                        "url": "http://weibo.com/travel_note/shigatse",
                        "weight": 0.3
                    },
                    "timestamp": "2023-11-10T16:30:00Z"
                }
            ],
            "expected_winner_id": "http://shigatse.gov.cn/stats"  # 尽管旧但明显更准确
        }
    ]
    
    # 新增扩展测试用例集
    extended_conflict_test_set = [
        {
            "name": "历史人物时间记载冲突",
            "conflicts": [
                {
                    "entity_name": "松赞干布",
                    "attribute": "在位时间",
                    "value": "公元617年至650年",
                    "source": {
                        "type": "historical_record",
                        "url": "http://tibet-history.org/songtsen-gampo",
                        "weight": 0.85
                    },
                    "timestamp": "2021-09-15T10:20:00Z"
                },
                {
                    "entity_name": "松赞干布",
                    "attribute": "在位时间",
                    "value": "公元629年至649年",
                    "source": {
                        "type": "academic_journal",
                        "url": "http://archaeology.edu/tibet-kings",
                        "weight": 0.9
                    },
                    "timestamp": "2023-03-20T14:15:00Z"
                }
            ],
            "expected_winner_id": "http://archaeology.edu/tibet-kings"  # 高权重且更新的学术来源
        },
        {
            "name": "文化艺术描述冲突",
            "conflicts": [
                {
                    "entity_name": "唐卡艺术",
                    "attribute": "起源",
                    "value": "唐卡艺术起源于公元7世纪的吐蕃王朝时期，最初是受到尼泊尔和印度佛教艺术的影响",
                    "source": {
                        "type": "museum",
                        "url": "http://tibet-museum.org/thangka",
                        "weight": 0.85
                    },
                    "timestamp": "2022-05-10T09:45:00Z"
                },
                {
                    "entity_name": "唐卡艺术",
                    "attribute": "起源",
                    "value": "唐卡艺术可追溯到10世纪左右，与藏传佛教的传播密切相关",
                    "source": {
                        "type": "art_blog",
                        "url": "http://tibetan-arts.com/thangka-history",
                        "weight": 0.55
                    },
                    "timestamp": "2023-11-18T16:30:00Z"
                }
            ],
            "expected_winner_id": "http://tibet-museum.org/thangka"  # 博物馆权重更高，虽然较旧
        },
        {
            "name": "地理实体数据冲突",
            "conflicts": [
                {
                    "entity_name": "雅鲁藏布大峡谷",
                    "attribute": "深度",
                    "value": "平均深度约为5000米，最深处达6009米",
                    "source": {
                        "type": "scientific_publication",
                        "url": "http://geo-journal.org/yarlung-tsangpo",
                        "weight": 0.9
                    },
                    "timestamp": "2020-08-22T11:15:00Z"
                },
                {
                    "entity_name": "雅鲁藏布大峡谷",
                    "attribute": "深度",
                    "value": "最深处超过5300米",
                    "source": {
                        "type": "travel_guide",
                        "url": "http://lonely-planet.com/yarlung",
                        "weight": 0.6
                    },
                    "timestamp": "2023-05-15T14:30:00Z"
                },
                {
                    "entity_name": "雅鲁藏布大峡谷",
                    "attribute": "深度",
                    "value": "最深处达6057米，是世界最深的峡谷",
                    "source": {
                        "type": "research_report",
                        "url": "http://chinese-academy.cn/yarlung-2022",
                        "weight": 0.95
                    },
                    "timestamp": "2022-12-10T09:20:00Z"
                }
            ],
            "expected_winner_id": "http://chinese-academy.cn/yarlung-2022"  # 权重最高且较新的研究报告
        },
        {
            "name": "传统节日日期变更",
            "conflicts": [
                {
                    "entity_name": "雪顿节",
                    "attribute": "举办日期",
                    "value": "每年藏历六月底七月初举行，一般在公历8月中旬",
                    "source": {
                        "type": "tourism_bureau",
                        "url": "http://lhasa-tourism.org/shoton",
                        "weight": 0.85
                    },
                    "timestamp": "2021-07-12T10:45:00Z"
                },
                {
                    "entity_name": "雪顿节",
                    "attribute": "举办日期",
                    "value": "2023年雪顿节将于8月15日至8月20日举行",
                    "source": {
                        "type": "news",
                        "url": "http://xizang-news.cn/shoton-2023",
                        "weight": 0.75
                    },
                    "timestamp": "2023-07-25T09:10:00Z"
                }
            ],
            "expected_winner_id": "http://xizang-news.cn/shoton-2023"  # 较新的具体信息，虽然权重略低
        },
        {
            "name": "高权重但极旧数据",
            "conflicts": [
                {
                    "entity_name": "西藏人口",
                    "attribute": "总人口",
                    "value": "西藏自治区总人口约315万（2016年统计）",
                    "source": {
                        "type": "government",
                        "url": "http://stats.gov.cn/tibet-2016",
                        "weight": 0.95
                    },
                    "timestamp": "2017-03-10T14:30:00Z"
                },
                {
                    "entity_name": "西藏人口",
                    "attribute": "总人口",
                    "value": "西藏自治区总人口约370万（2022年统计）",
                    "source": {
                        "type": "news",
                        "url": "http://xinhua.com/tibet-population",
                        "weight": 0.8
                    },
                    "timestamp": "2023-02-15T11:20:00Z"
                }
            ],
            "expected_winner_id": "http://xinhua.com/tibet-population"  # 虽然权重较低，但时间差距过大
        },
        {
            "name": "流通信息类冲突",
            "conflicts": [
                {
                    "entity_name": "青藏铁路",
                    "attribute": "票价",
                    "value": "拉萨至西宁硬卧票价约280元",
                    "source": {
                        "type": "railway_official",
                        "url": "http://12306.cn/qinghai-tibet",
                        "weight": 0.9
                    },
                    "timestamp": "2021-05-20T08:45:00Z"
                },
                {
                    "entity_name": "青藏铁路",
                    "attribute": "票价",
                    "value": "拉萨至西宁硬卧票价约330元，软卧约520元",
                    "source": {
                        "type": "travel_agency",
                        "url": "http://ctrip.com/tibet-train",
                        "weight": 0.7
                    },
                    "timestamp": "2023-09-05T15:20:00Z"
                }
            ],
            "expected_winner_id": "http://ctrip.com/tibet-train"  # 票价信息应选择较新的
        },
        {
            "name": "医学建议信息冲突",
            "conflicts": [
                {
                    "entity_name": "高原反应",
                    "attribute": "预防措施",
                    "value": "抵达高原前建议服用红景天等药物，并在抵达后48小时内避免剧烈运动",
                    "source": {
                        "type": "medical_journal",
                        "url": "http://medical-journal.org/altitude-sickness",
                        "weight": 0.9
                    },
                    "timestamp": "2020-11-15T09:30:00Z"
                },
                {
                    "entity_name": "高原反应",
                    "attribute": "预防措施",
                    "value": "最新研究表明，抵达高原前3天开始服用乙酰唑胺（俗称'高反片'）比红景天更有效，抵达后应保持72小时充分休息",
                    "source": {
                        "type": "health_organization",
                        "url": "http://who.int/altitude-health-2023",
                        "weight": 0.85
                    },
                    "timestamp": "2023-06-12T14:15:00Z"
                }
            ],
            "expected_winner_id": "http://who.int/altitude-health-2023"  # 医学信息应选择较新的
        },
        {
            "name": "相同权重但长短不一",
            "conflicts": [
                {
                    "entity_name": "冈仁波齐峰",
                    "attribute": "宗教意义",
                    "value": "冈仁波齐峰被认为是印度教湿婆神的住所，也是藏传佛教中的神山",
                    "source": {
                        "type": "religious_text",
                        "url": "http://sacred-mountains.org/kailash",
                        "weight": 0.8
                    },
                    "timestamp": "2022-04-18T10:35:00Z"
                },
                {
                    "entity_name": "冈仁波齐峰",
                    "attribute": "宗教意义",
                    "value": "冈仁波齐峰（Mount Kailash）是世界四大宗教（印度教、藏传佛教、耆那教和苯教）的圣地，印度教徒视其为湿婆神的住所，藏传佛教徒称其为'宝贵的雪山'，相信这里是胜乐金刚的道场，围绕此峰转山一周可消除一生罪孽",
                    "source": {
                        "type": "academic_study",
                        "url": "http://comparative-religion.edu/kailash",
                        "weight": 0.8
                    },
                    "timestamp": "2021-08-30T14:25:00Z"
                }
            ],
            "expected_winner_id": "http://comparative-religion.edu/kailash"  # 内容更全面详细，虽然较旧
        },
        {
            "name": "技术数据快速迭代",
            "conflicts": [
                {
                    "entity_name": "羊湖水质",
                    "attribute": "水质报告",
                    "value": "水质达到国家II类标准，可用于生活饮用水",
                    "source": {
                        "type": "environmental_agency",
                        "url": "http://environment.gov.cn/yamdrok-2022",
                        "weight": 0.9
                    },
                    "timestamp": "2022-06-15T11:20:00Z"
                },
                {
                    "entity_name": "羊湖水质",
                    "attribute": "水质报告",
                    "value": "水质监测结果显示局部水域存在轻微污染，整体仍保持III类水质标准",
                    "source": {
                        "type": "research_center",
                        "url": "http://water-research.org/yamdrok-2023",
                        "weight": 0.85
                    },
                    "timestamp": "2023-10-05T09:15:00Z"
                }
            ],
            "expected_winner_id": "http://water-research.org/yamdrok-2023"  # 技术监测数据应选择较新的
        },
        {
            "name": "传说与史实的冲突",
            "conflicts": [
                {
                    "entity_name": "文成公主",
                    "attribute": "历史贡献",
                    "value": "文成公主带到西藏的不仅有汉文化的医药、历法、农业技术，还有大量佛教典籍和佛像，促进了藏传佛教的发展",
                    "source": {
                        "type": "historical_record",
                        "url": "http://history.cn/princess-wencheng",
                        "weight": 0.85
                    },
                    "timestamp": "2021-12-10T10:40:00Z"
                },
                {
                    "entity_name": "文成公主",
                    "attribute": "历史贡献",
                    "value": "传说文成公主带到西藏的释迦牟尼12岁等身金像，是现今大昭寺的镇寺之宝，被称为'觉卧'",
                    "source": {
                        "type": "folklore",
                        "url": "http://tibet-legends.com/wencheng",
                        "weight": 0.5
                    },
                    "timestamp": "2023-08-12T15:30:00Z"
                }
            ],
            "expected_winner_id": "http://history.cn/princess-wencheng"  # 历史记载权重高于传说
        }
    ]
    
    # 合并测试用例集
    final_test_set = manual_test_set + extended_conflict_test_set
    
    # 初始化计数器
    weight_first_correct = 0
    latest_first_correct = 0
    hybrid_correct = 0
    total_tests = len(final_test_set)
    
    # 测试结果详情
    test_results = []
    
    # 遍历所有测试用例
    for i, test_case in enumerate(final_test_set):
        print(f"\n测试用例 {i+1}: {test_case['name']}")
        print("-" * 80)
        
        # 应用三种策略
        winner_weight = resolve_conflict_weight_first(test_case['conflicts'])
        winner_latest = resolve_conflict_latest_first(test_case['conflicts'])
        winner_hybrid, explanation = resolve_conflict_with_hybrid(test_case['conflicts'])
        
        # 提取每个策略选择的获胜者URL
        weight_winner_id = winner_weight.get('source', {}).get('url', '')
        latest_winner_id = winner_latest.get('source', {}).get('url', '')
        hybrid_winner_id = winner_hybrid.get('source', {}).get('url', '')
        expected_id = test_case['expected_winner_id']
        
        # 判断哪种策略正确
        weight_first_result = weight_winner_id == expected_id
        latest_first_result = latest_winner_id == expected_id
        hybrid_result = hybrid_winner_id == expected_id
        
        # 更新计数
        if weight_first_result:
            weight_first_correct += 1
        if latest_first_result:
            latest_first_correct += 1
        if hybrid_result:
            hybrid_correct += 1
        
        # 保存本次测试结果
        test_results.append({
            "test_name": test_case['name'],
            "weight_first": weight_first_result,
            "latest_first": latest_first_result,
            "hybrid": hybrid_result,
            "expected": expected_id,
            "weight_chose": weight_winner_id,
            "latest_chose": latest_winner_id,
            "hybrid_chose": hybrid_winner_id
        })
        
        # 打印结果
        print(f"预期获胜者: {expected_id}")
        print(f"Weight-First 策略结果: {weight_winner_id} - {'✓ 正确' if weight_first_result else '✗ 错误'}")
        print(f"Latest-First 策略结果: {latest_winner_id} - {'✓ 正确' if latest_first_result else '✗ 错误'}")
        print(f"Hybrid 策略结果: {hybrid_winner_id} - {'✓ 正确' if hybrid_result else '✗ 错误'}")
        print(f"Hybrid 决策说明: {json.dumps(explanation, ensure_ascii=False, indent=2)}")
    
    # 计算各策略的准确率
    weight_first_accuracy = weight_first_correct / total_tests * 100
    latest_first_accuracy = latest_first_correct / total_tests * 100
    hybrid_accuracy = hybrid_correct / total_tests * 100
    
    # 打印总结
    print("\n" + "="*80)
    print("实验结果总结".center(80))
    print("="*80)
    print(f"总测试用例数: {total_tests}")
    print(f"Weight-First 决策准确率: {weight_first_accuracy:.2f}% ({weight_first_correct}/{total_tests})")
    print(f"Latest-First 决策准确率: {latest_first_accuracy:.2f}% ({latest_first_correct}/{total_tests})")
    print(f"Hybrid 决策准确率: {hybrid_accuracy:.2f}% ({hybrid_correct}/{total_tests})")
    print("="*80)
    
    # 详细结果表格
    print("\n详细结果表格:")
    print("-" * 100)
    print(f"{'测试名称':<30} | {'Weight-First':<15} | {'Latest-First':<15} | {'Hybrid':<15}")
    print("-" * 100)
    for result in test_results:
        weight_status = "✓" if result["weight_first"] else "✗"
        latest_status = "✓" if result["latest_first"] else "✗"
        hybrid_status = "✓" if result["hybrid"] else "✗"
        print(f"{result['test_name']:<30} | {weight_status:<15} | {latest_status:<15} | {hybrid_status:<15}")
    print("-" * 100)
    
    return {
        "weight_first_accuracy": weight_first_accuracy,
        "latest_first_accuracy": latest_first_accuracy,
        "hybrid_accuracy": hybrid_accuracy,
        "test_results": test_results
    }

if __name__ == "__main__":
    # 直接运行这个文件时，执行实验
    run_conflict_resolution_experiment() 