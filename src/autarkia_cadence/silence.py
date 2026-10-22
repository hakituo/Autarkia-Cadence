"""Long-silence overrides for a "do nothing" decision.

The decision model may choose silence because it lacks a reason to speak. Two
hard time facts can override that: the companion has been silent for a long
time, or nothing has been sent for too long while the user has been silent
long enough. Overrides are still suppressed in quiet/sleep/focus modes and
once the daily limit is reached.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Tuple

from .tuning import LONG_SILENCE_THRESHOLD_SECONDS

logger = logging.getLogger(__name__)


@dataclass
class SilenceContext:
    """Everything the silence gate needs to know about the current round."""

    now: float = 0.0
    now_dt: datetime | None = None
    elapsed: float = 0.0
    count: int = 0
    last_sent_ts: float = 0.0
    last_attempt_ts: float = 0.0
    min_gap_seconds: int = 600
    daily_limit: int = 20
    quiet_mode_active: bool = False
    sleep_session_active: bool = False
    reduced_mode_active: bool = False
    reduced_mode_reason: str = "none"
    latest_user_signal_ts: float = 0.0
    state_data: Dict[str, Any] = field(default_factory=dict)

    @property
    def long_silence_seconds(self) -> float:
        # Matches the runtime: a default 10-minute gap still means one hour of
        # silence before an override, and a larger gap scales up.
        if self.min_gap_seconds > 1200:
            return max(self.min_gap_seconds * 3, 3600)
        return 3600.0

    @property
    def has_long_silence(self) -> bool:
        last_attempt = max(self.last_sent_ts, self.last_attempt_ts)
        return last_attempt <= 0 or (self.now - last_attempt) >= self.long_silence_seconds

    @property
    def has_recent_signal_for_long_silence(self) -> bool:
        return (
            self.latest_user_signal_ts > 0
            and (self.now - self.latest_user_signal_ts) <= 6 * 3600
        )

    @property
    def no_send_for_too_long(self) -> bool:
        last_attempt = max(self.last_sent_ts, self.last_attempt_ts)
        return (
            last_attempt <= 0
            or (self.now - last_attempt) >= max(self.min_gap_seconds * 4, 3600)
        )

    @property
    def user_silent_long_enough(self) -> bool:
        return self.elapsed >= max(self.min_gap_seconds * 2, 1800)

    @property
    def is_early_morning(self) -> bool:
        if self.now_dt is None:
            return False
        try:
            return 0 <= self.now_dt.hour < 6
        except (AttributeError, TypeError):
            return False


class SilenceGate:
    """Rules that may force a send despite a ``should_send=False`` decision."""

    def is_override_allowed(
        self, ctx: SilenceContext, has_non_response_pressure: bool = False
    ) -> bool:
        """Common conditions shared by all overrides."""
        if ctx.quiet_mode_active or ctx.sleep_session_active:
            return False
        if ctx.reduced_mode_active:
            if ctx.reduced_mode_reason == "sleep_hint":
                return not has_non_response_pressure
            if ctx.reduced_mode_reason == "goodnight":
                is_daytime = False
                if ctx.now_dt is not None:
                    try:
                        is_daytime = 10 <= ctx.now_dt.hour < 18
                    except (AttributeError, TypeError):
                        pass
                if is_daytime:
                    return not has_non_response_pressure
            return False
        if ctx.count >= ctx.daily_limit:
            return False
        return True

    def should_force_send(
        self,
        ctx: SilenceContext,
        non_response_count: int = 0,
    ) -> Tuple[bool, str]:
        """Return ``(should_force, reason)``.

        When the user has already ignored messages, the required silence
        duration grows so the gate does not fight the unanswered suppression.
        """
        has_non_response_pressure = non_response_count > 0

        if has_non_response_pressure:
            min_silence_for_force = max(ctx.min_gap_seconds * (non_response_count + 2), 7200)
            last_attempt = max(ctx.last_sent_ts, ctx.last_attempt_ts)
            silence_duration = (ctx.now - last_attempt) if last_attempt > 0 else float("inf")
            if silence_duration < min_silence_for_force:
                return False, ""

        if (
            ctx.has_long_silence
            and ctx.has_recent_signal_for_long_silence
            and self.is_override_allowed(ctx, has_non_response_pressure)
        ):
            return True, "long_silence_fallback"

        if (
            ctx.no_send_for_too_long
            and ctx.user_silent_long_enough
            and self.is_override_allowed(ctx, has_non_response_pressure)
        ):
            return True, "no_send_timeout_fallback"

        return False, ""

    def apply_silence_overrides(
        self,
        ctx: SilenceContext,
        should_send: bool,
        thought: str,
        non_response_count: int,
    ) -> Tuple[bool, str]:
        """Apply the gate to a decision, optionally filling an empty thought."""
        if should_send:
            return should_send, thought

        force_send, reason = self.should_force_send(ctx, non_response_count=non_response_count)
        if force_send:
            should_send = True
            if not thought:
                thought = reason
            if reason == "long_silence_fallback":
                logger.info(
                    "Forcing send due to long silence fallback (>%ss).",
                    int(ctx.long_silence_seconds),
                )
            elif reason == "no_send_timeout_fallback":
                logger.info(
                    "Forcing send due to no-send timeout (last_sent=%ss ago, user_silent=%ss).",
                    int(ctx.now - ctx.last_sent_ts) if ctx.last_sent_ts > 0 else -1,
                    int(ctx.elapsed),
                )
        return should_send, thought


__all__ = ["SilenceContext", "SilenceGate"]
