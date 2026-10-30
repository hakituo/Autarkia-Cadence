"""Autarkia-Cadence: proactive message cadence governance.

Extracted from the Autarkia agent runtime. Pure decision logic: no I/O, no
network, no LLM, no global configuration.
"""

from .config import (
    CadenceConfig,
    DEFAULT_EXEMPT_INTENTS,
    DEFAULT_GROUP_COOLDOWN_INTENTS,
    DEFAULT_GLOBAL_PROACTIVE_COOLDOWN,
    DEFAULT_MAX_UNANSWERED_PROACTIVE,
    DEFAULT_QUESTION_COOLDOWN,
    DEFAULT_QUESTION_INTENTS,
    DEFAULT_SAME_TOPIC_COOLDOWN,
    DEFAULT_UNANSWERED_SUPPRESS_WINDOW,
)
from .guard import CadenceGuard, CadenceVerdict, looks_like_question
from .schedule_config import (
    ScheduleConfigLoader,
    build_default_push_schedule,
    build_default_quiet_hours,
    get_schedule_configs_sync,
    load_schedule_configs,
    merge_configs,
)
from .scheduling import (
    SchedulerConfig,
    SchedulerLogic,
    apply_interval_jitter,
    calculate_non_response_backoff,
)
from .silence import SilenceContext, SilenceGate
from .sleep import SleepPolicy
from .topic_groups import (
    COOLDOWN_ELIGIBLE_GROUPS,
    SUBTOPIC_GROUP_MAP,
    group_for_subtopic,
    group_for_topic_label,
    is_eligible_for_group_cooldown,
)
from .topics import (
    CATEGORY_TO_SLOT,
    INTENT_DEFAULT_TOPIC,
    TOPIC_KEYWORDS,
    classify_topic,
    detect_topic_category,
    topic_to_state_slot,
)
from .windows import (
    is_in_range_minutes,
    next_range_end_dt,
    next_window_start_dt,
    parse_hhmm,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # guard
    "CadenceGuard",
    "CadenceVerdict",
    "looks_like_question",
    "CadenceConfig",
    "DEFAULT_GLOBAL_PROACTIVE_COOLDOWN",
    "DEFAULT_QUESTION_COOLDOWN",
    "DEFAULT_SAME_TOPIC_COOLDOWN",
    "DEFAULT_MAX_UNANSWERED_PROACTIVE",
    "DEFAULT_UNANSWERED_SUPPRESS_WINDOW",
    "DEFAULT_EXEMPT_INTENTS",
    "DEFAULT_QUESTION_INTENTS",
    "DEFAULT_GROUP_COOLDOWN_INTENTS",
    # topics
    "TOPIC_KEYWORDS",
    "INTENT_DEFAULT_TOPIC",
    "CATEGORY_TO_SLOT",
    "detect_topic_category",
    "classify_topic",
    "topic_to_state_slot",
    "SUBTOPIC_GROUP_MAP",
    "COOLDOWN_ELIGIBLE_GROUPS",
    "group_for_subtopic",
    "group_for_topic_label",
    "is_eligible_for_group_cooldown",
    # scheduling
    "SchedulerConfig",
    "SchedulerLogic",
    "calculate_non_response_backoff",
    "apply_interval_jitter",
    # windows
    "parse_hhmm",
    "is_in_range_minutes",
    "next_range_end_dt",
    "next_window_start_dt",
    # schedule config
    "ScheduleConfigLoader",
    "build_default_push_schedule",
    "build_default_quiet_hours",
    "merge_configs",
    "load_schedule_configs",
    "get_schedule_configs_sync",
    # sleep / silence
    "SleepPolicy",
    "SilenceContext",
    "SilenceGate",
]
