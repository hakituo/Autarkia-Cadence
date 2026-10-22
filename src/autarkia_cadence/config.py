"""Declarative cadence configuration.

The runtime read these values from a YAML config tree; the library takes a
plain dataclass instead so it has no host dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import FrozenSet, Mapping, Optional


DEFAULT_GLOBAL_PROACTIVE_COOLDOWN = 40 * 60
DEFAULT_QUESTION_COOLDOWN = 75 * 60
DEFAULT_SAME_TOPIC_COOLDOWN = 3 * 3600
DEFAULT_MAX_UNANSWERED_PROACTIVE = 1
DEFAULT_MAX_CURIOUS_QUESTION_PER_DAY = 3
DEFAULT_UNANSWERED_SUPPRESS_WINDOW = 6 * 3600

# Hard-event intents: real reminders, notification relays, digital-wellbeing
# nudges, goodnight/good-morning tasks. They are "genuinely new events" and
# bypass the ordinary proactive cooldowns.
DEFAULT_EXEMPT_INTENTS: FrozenSet[str] = frozenset({
    "reminder",
    "notification_assistant",
    "usage_limit_exceeded",
    "goodnight_proactive",
    "good_morning_proactive",
    "wake_up_greeting",
    "morning_report",
    "activity_return_proactive",
    "sleep_again_proactive",
    "insomnia",
    "focus_nudge",
    "bio_complaint",
    "user_health_reminder",
})

# Ordinary question intents. Unanswered suppression, the daily soft cap and
# the question cooldown only apply to these.
DEFAULT_QUESTION_INTENTS: FrozenSet[str] = frozenset({"curious_question", "checking"})

# Intents whose messages are grouped by topic so that rephrasing the same
# subject ("did you eat" -> "did the delivery arrive") cannot bypass cooldown.
DEFAULT_GROUP_COOLDOWN_INTENTS: FrozenSet[str] = frozenset({
    "curious_question",
    "checking",
    "share_thought",
    "emotional_support",
    "gossip_share",
    "weather_complaint",
    "share_peer_chat",
    "planned_topic",
})


@dataclass(frozen=True)
class CadenceConfig:
    """Tunables for :class:`autarkia_cadence.CadenceGuard`.

    Defaults mirror the runtime's fallbacks. Every value is injected rather
    than read from a global config object.
    """

    global_cooldown_seconds: int = DEFAULT_GLOBAL_PROACTIVE_COOLDOWN
    question_cooldown_seconds: int = DEFAULT_QUESTION_COOLDOWN
    same_topic_cooldown_seconds: int = DEFAULT_SAME_TOPIC_COOLDOWN
    max_unanswered_proactive: int = DEFAULT_MAX_UNANSWERED_PROACTIVE
    max_curious_question_per_day: int = DEFAULT_MAX_CURIOUS_QUESTION_PER_DAY
    unanswered_suppress_window_seconds: int = DEFAULT_UNANSWERED_SUPPRESS_WINDOW
    exempt_intents: FrozenSet[str] = DEFAULT_EXEMPT_INTENTS
    question_intents: FrozenSet[str] = DEFAULT_QUESTION_INTENTS
    group_cooldown_intents: FrozenSet[str] = DEFAULT_GROUP_COOLDOWN_INTENTS

    @classmethod
    def from_mapping(cls, values: Optional[Mapping[str, object]]) -> "CadenceConfig":
        """Build a config from a plain mapping.

        Only known keys are consumed; unknown keys are ignored so callers can
        pass a larger settings dictionary without filtering it first.
        """
        if not values:
            return cls()
        data = dict(values)
        kwargs = {}
        for name in (
            "global_cooldown_seconds",
            "question_cooldown_seconds",
            "same_topic_cooldown_seconds",
            "max_unanswered_proactive",
            "max_curious_question_per_day",
            "unanswered_suppress_window_seconds",
        ):
            if name in data and data[name] is not None:
                kwargs[name] = int(data[name])
        for name in ("exempt_intents", "question_intents", "group_cooldown_intents"):
            if name in data and data[name] is not None:
                kwargs[name] = frozenset(str(item) for item in data[name])
        return cls(**kwargs)


__all__ = [
    "CadenceConfig",
    "DEFAULT_GLOBAL_PROACTIVE_COOLDOWN",
    "DEFAULT_QUESTION_COOLDOWN",
    "DEFAULT_SAME_TOPIC_COOLDOWN",
    "DEFAULT_MAX_UNANSWERED_PROACTIVE",
    "DEFAULT_MAX_CURIOUS_QUESTION_PER_DAY",
    "DEFAULT_UNANSWERED_SUPPRESS_WINDOW",
    "DEFAULT_EXEMPT_INTENTS",
    "DEFAULT_QUESTION_INTENTS",
    "DEFAULT_GROUP_COOLDOWN_INTENTS",
]
