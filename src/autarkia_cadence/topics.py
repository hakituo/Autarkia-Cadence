"""Topic labelling: intent + subtopic -> ``"<intent>:<subtopic>"``.

The runtime classified topics with a keyword table; here the table is a
regular mapping so applications can replace it. No LLM calls, no network.
"""

from __future__ import annotations

from typing import Dict, Iterable, Mapping, Optional, Tuple

TOPIC_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "SLEEP": (
        "睡", "熬夜", "晚睡", "不睡", "休息", "睡觉", "困了",
        "tired", "sleep", "bedtime",
        "凌晨", "深夜", "早点休息", "快去睡", "该睡了", "还不睡",
        "别熬夜", "少熬夜", "伤身", "伤身体", "stay up", "up late",
    ),
    "GREETING": (
        "在吗", "在呢", "在不在", "嗨", "你好", "hey", "hello", "早上好",
        "晚安", "早安", "还在", "醒着", "awake",
    ),
    "CARE": (
        "关心", "想你了", "想你", "担心", "miss", "在乎", "惦记",
        "最近怎么样", "过得如何", "还好吗",
    ),
    "VEHICLE": (
        "车", "开车", "加油", "油耗", "汽油", "92", "95", "98",
        "油站", "加油站", "油费", "油钱", "油价", "标号", "耐烧",
        "斯巴鲁", "驾驶", "司机", "买车", "驾车", "排量",
        "car", "gas", "fuel", "mileage", "driving",
    ),
    "FOOD": (
        "吃", "饭", "美食", "菜", "外卖", "零食", "水果", "喝",
        "早餐", "午餐", "晚餐", "宵夜", "火锅", "烧烤", "奶茶",
        "和牛", "牛肉", "海鲜", "料理",
        "food", "meal", "hungry", "delivery",
    ),
    "STUDY": (
        "学习", "复习", "背单词", "单词", "英语", "考试", "作业",
        "上课", "看书", "刷题", "论文", "study", "exam", "homework",
        "review", "vocabulary",
    ),
    "HEALTH": (
        "健康", "吃药", "药", "身体", "不舒服", "头疼", "胃疼",
        "感冒", "发烧", "医院", "体检", "睡觉", "喝水",
        "health", "medicine", "doctor",
    ),
    "PEER": (
        "她", "他", "朋友", "聊天", "群里", "另一个", "伙伴",
        "peer", "friend", "chat",
    ),
}

# intent -> default subtopic when nothing can be extracted from the text
INTENT_DEFAULT_TOPIC: Dict[str, str] = {
    "share_thought": "general",
    "curious_question": "probe",
    "bio_complaint": "health",
    "emotional_support": "care",
    "share_peer_chat": "peer",
    "user_health_reminder": "health",
    "do_nothing": "none",
    "reminder": "task",
    "planned_topic": "task",
    "wake_up_greeting": "greeting",
    "morning_report": "greeting",
    "goodnight_proactive": "sleep",
    "activity_return_proactive": "general",
}

CATEGORY_TO_SLOT: Dict[str, str] = {
    "SLEEP": "sleep",
    "GREETING": "greeting",
    "CARE": "care",
    "VEHICLE": "vehicle",
    "FOOD": "food",
    "STUDY": "study",
    "HEALTH": "health",
    "PEER": "peer",
}


def detect_topic_category(
    text: str,
    keywords: Optional[Mapping[str, Iterable[str]]] = None,
) -> str:
    """Score ``text`` against the keyword table and return the top category.

    Returns ``"unknown"`` for empty text and ``"other"`` when nothing matches.
    """
    text_lower = str(text or "").strip().lower()
    if not text_lower:
        return "unknown"
    table = keywords if keywords is not None else TOPIC_KEYWORDS
    scores: Dict[str, int] = {}
    for category, keyword_list in table.items():
        count = sum(1 for keyword in keyword_list if str(keyword).lower() in text_lower)
        if count > 0:
            scores[category] = count
    if not scores:
        return "other"
    return max(scores, key=scores.get)


def classify_topic(
    intent: str,
    planned_topic: str = "",
    sent_content: str = "",
    *,
    keywords: Optional[Mapping[str, Iterable[str]]] = None,
) -> str:
    """Derive a topic label ``"<intent>:<subtopic>"`` for a proactive message.

    ``planned_topic`` wins over the actual sent content; when neither yields a
    known category the intent's default subtopic is used.

    The signature (three positional strings + keyword-only ``keywords``) is
    the callable shape accepted by :class:`autarkia_cadence.CadenceGuard`.
    """
    primary = str(intent or "").strip() or "share_thought"
    default_sub = INTENT_DEFAULT_TOPIC.get(primary, "general")

    sub: Optional[str] = None
    if planned_topic:
        sub = _normalize_category(detect_topic_category(planned_topic, keywords), keywords)
    if sub is None and sent_content:
        sub = _normalize_category(detect_topic_category(sent_content, keywords), keywords)
    if sub is None:
        sub = default_sub
    return f"{primary}:{sub}"


def topic_to_state_slot(topic: str) -> str:
    """Extract only the subtopic part of a label (used for state features)."""
    if not topic or ":" not in topic:
        return "general"
    return topic.split(":", 1)[1] or "general"


def _normalize_category(category: str, keywords: Optional[Mapping[str, Iterable[str]]] = None) -> Optional[str]:
    key = str(category or "").strip().upper()
    if not key or key in ("OTHER", "UNKNOWN"):
        return None
    if keywords is not None:
        # A custom table may use lowercase or arbitrary category names; fall
        # back to the category name itself when it is not a known slot.
        return CATEGORY_TO_SLOT.get(key, key.lower())
    return CATEGORY_TO_SLOT.get(key)


__all__ = [
    "TOPIC_KEYWORDS",
    "INTENT_DEFAULT_TOPIC",
    "CATEGORY_TO_SLOT",
    "detect_topic_category",
    "classify_topic",
    "topic_to_state_slot",
]
