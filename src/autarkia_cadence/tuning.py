"""Numeric defaults for scheduling, backoff, jitter and silence gates.

These are fallback values only; callers override them through
:class:`autarkia_cadence.SchedulerConfig` or function arguments.
"""

from typing import Dict, Tuple

# -- scheduling and generation defaults ------------------------------------
DEFAULT_NEXT_CHECK_SECONDS = 300
DEFAULT_MIN_GAP_SECONDS = 600
DEFAULT_DAILY_LIMIT = 20
DEFAULT_USER_QUIET_SECONDS = 300
DEFAULT_TONE_REFERENCE_MAX_CHARS = 3000
DEFAULT_GENERATION_TEMPERATURE = 0.65
DEFAULT_GENERATION_MAX_TOKENS = 220
DEFAULT_DECISION_TEMPERATURE = 0.45
DEFAULT_BANDIT_EPSILON = 0.2

# -- silence and reminders --------------------------------------------------
SILENCE_BREAKER_SECONDS = 1800
REMINDER_MAX_CONSECUTIVE_RETRIES = 3
REMINDER_RETRY_BACKOFF_BASE_SECONDS = 300
LONG_SILENCE_THRESHOLD_SECONDS = 1800
RECENT_HISTORY_LIMIT = 8
RECENT_HISTORY_CONTENT_MAX_CHARS = 180
RECENT_HISTORY_MAX_AGE_SECONDS = 24 * 3600
USER_MESSAGE_MAX_AGE_SECONDS = 300

# -- non-response backoff ---------------------------------------------------
BACKOFF_BASE = 1.8
BACKOFF_CAP = 12.0
MAX_CONSECUTIVE_NON_RESPONSES_BEFORE_SKIP = 4

# -- jitter and minimum interval -------------------------------------------
JITTER_LOW_RATIO = 0.9
JITTER_HIGH_RATIO = 1.1
INTERVAL_MIN_SECONDS = 30

# -- accidental short replies ----------------------------------------------
ACCIDENTAL_REPLY_WINDOW_SECONDS = 300
ACCIDENTAL_REPLY_MAX_LENGTH = 4

# emotion -> (base multiplier, intensity multiplier), used to adapt the
# heartbeat interval.
EMOTION_INTERVAL_MULTIPLIERS: Dict[str, Tuple[float, float]] = {
    "sad": (1.0, 0.8),
    "tired": (1.0, 0.8),
    "lost": (1.0, 0.8),
    "wronged": (1.0, 0.8),
    "angry": (1.0, 0.8),
    "happy": (1.0, -0.3),
    "excited": (1.0, -0.3),
    "coquetry": (1.0, -0.3),
    "anxious": (0.8, 0.0),
}

# -- goodnight / low-disturb sleep windows ---------------------------------
AUTO_WAKE_MAX_HOURS = 14
GOODNIGHT_SIGNAL_GAP_SECONDS = 300
GOODNIGHT_INITIAL_QUIET_SECONDS = 1800
MIN_QUIET_EVEN_INCOMPLETE_SECONDS = 180
PROBABLE_SLEEP_PROBE_GAP_SECONDS = 3600

# -- rhythm adaptation windows ---------------------------------------------
PROBABLE_SLEEP_SILENCE_NIGHT_SECONDS = 7200
PROBABLE_SLEEP_SILENCE_MORNING_SECONDS = 10800
PROBABLE_SLEEP_SILENCE_EVENING_SECONDS = 3600
PROBABLE_SLEEP_NIGHT_HOUR_START = 0
PROBABLE_SLEEP_NIGHT_HOUR_END = 6
PROBABLE_SLEEP_MORNING_HOUR_START = 6
PROBABLE_SLEEP_MORNING_HOUR_END = 10
PROBABLE_SLEEP_EVENING_HOUR_START = 18
PROBABLE_SLEEP_EVENING_HOUR_END = 24


__all__ = [name for name in dir() if name.isupper()]
