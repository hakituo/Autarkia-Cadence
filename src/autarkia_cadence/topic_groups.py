"""Collapse fine-grained subtopics into "the same thing" groups.

Rephrasing the same subject chain (``吃饭没`` / ``外卖点了吗`` / ``饭到了吗``)
must hit one cooldown bucket. ``meal`` is the canonical example: all food
subtopics share it.
"""

from __future__ import annotations

from typing import Optional

SUBTOPIC_GROUP_MAP = {
    "food": "meal",
    "sleep": "sleep",
    "study": "study",
    "care": "care",
    "vehicle": "vehicle",
    "greeting": "greeting",
    "health": "health",
    "peer": "social",
    "task": "general",
    "probe": "general",
    "general": "general",
    "none": "general",
    "other": "general",
    "unknown": "general",
}

# ``general`` can contain anything; cooling it down would kill legitimate new
# topics, so only specific groups participate.
COOLDOWN_ELIGIBLE_GROUPS = frozenset({
    "meal", "sleep", "study", "care", "vehicle", "greeting", "health", "social",
})

_EMPTY_GROUP = "general"


def group_for_subtopic(subtopic: Optional[str]) -> str:
    """Map a subtopic (the part after the colon) to a topic group."""
    key = str(subtopic or "").strip().lower()
    if not key:
        return _EMPTY_GROUP
    return SUBTOPIC_GROUP_MAP.get(key, _EMPTY_GROUP)


def group_for_topic_label(topic_label: Optional[str]) -> str:
    """Parse ``"<intent>:<subtopic>"`` into a topic group.

    Labels without a colon are treated as a bare subtopic.
    """
    label = str(topic_label or "").strip()
    if not label:
        return _EMPTY_GROUP
    subtopic = label.split(":", 1)[1].strip() if ":" in label else label
    return group_for_subtopic(subtopic)


def is_eligible_for_group_cooldown(group: Optional[str]) -> bool:
    """Whether this group is specific enough to deserve a cooldown."""
    return str(group or "") in COOLDOWN_ELIGIBLE_GROUPS


__all__ = [
    "SUBTOPIC_GROUP_MAP",
    "COOLDOWN_ELIGIBLE_GROUPS",
    "group_for_subtopic",
    "group_for_topic_label",
    "is_eligible_for_group_cooldown",
]
