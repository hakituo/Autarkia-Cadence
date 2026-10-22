"""Sleep-window policy: goodnight probes and focus-mode low-disturb gates.

During a sleep session ordinary proactive messages must be suppressed. The
only exception is a bounded "goodnight probe": first probe 10-30 minutes after
the user said goodnight, then increasingly sparse follow-ups. ``sleep_hint``
mode (the user said "no reply means I'm asleep") uses its own, longer gap.
"""

from __future__ import annotations

from typing import Any, Dict

from .tuning import PROBABLE_SLEEP_PROBE_GAP_SECONDS

# Probe window after a goodnight signal: wait 10 minutes, probe by 30.
PROBE_WINDOW_MIN_SECONDS = 600
PROBE_WINDOW_MAX_SECONDS = 1800
# Upper bound on how long a probe decision may ask the caller to wait.
MAX_PROBE_WAIT_SECONDS = 3600


class SleepPolicy:
    """Pure policy decisions for sleep sessions and reduced modes."""

    def build_sleep_session_archive_updates(
        self,
        state_data: Dict[str, Any],
        now_ts: float,
        safe_ts_func=None,
    ) -> Dict[str, Any]:
        """Build the archive record for the sleep session that just ended."""
        state = state_data if isinstance(state_data, dict) else {}
        if safe_ts_func:
            start_ts = safe_ts_func(state.get("last_goodnight_ts"))
            end_ts = safe_ts_func(now_ts)
        else:
            try:
                start_ts = float(state.get("last_goodnight_ts") or 0.0)
                end_ts = float(now_ts)
            except (TypeError, ValueError):
                start_ts = 0.0
                end_ts = 0.0

        duration_seconds = 0
        if start_ts > 0 and end_ts > start_ts:
            duration_seconds = int(end_ts - start_ts)

        return {
            "last_sleep_session_start_ts": start_ts,
            "last_sleep_session_end_ts": end_ts,
            "last_sleep_session_duration_seconds": duration_seconds,
        }

    def resolve_sleep_probe_policy(
        self,
        *,
        now: float,
        sleep_session_active: bool,
        allow_goodnight_probe: bool,
        reduced_mode_active: bool,
        reduced_mode_reason: str,
        last_goodnight_ts: float,
        last_goodnight_probe_ts: float,
        default_next_check: int,
        min_gap_seconds: int,
        goodnight_probe_gap_seconds: int,
        goodnight_low_disturb_gap_seconds: int,
    ) -> Dict[str, Any]:
        """Decide whether a probe may be sent while the user sleeps.

        Returns keys ``allow_send``, ``skip_reason``, ``wait_seconds`` and,
        when sending, ``is_probe`` / ``is_first_probe``.
        """
        if not sleep_session_active:
            if reduced_mode_active and reduced_mode_reason == "sleep_hint":
                return self._resolve_probable_sleep_probe_policy(
                    now=now,
                    last_goodnight_probe_ts=last_goodnight_probe_ts,
                    default_next_check=default_next_check,
                    goodnight_low_disturb_gap_seconds=goodnight_low_disturb_gap_seconds,
                )
            return {"allow_send": True, "skip_reason": "", "wait_seconds": 0}

        if not allow_goodnight_probe:
            return {
                "allow_send": False,
                "skip_reason": "goodnight_quiet_block",
                "wait_seconds": max(default_next_check, 3600),
            }

        elapsed_since_goodnight = (
            max(0.0, now - last_goodnight_ts) if last_goodnight_ts > 0 else 0.0
        )

        if elapsed_since_goodnight < PROBE_WINDOW_MIN_SECONDS:
            wait_seconds = max(
                default_next_check,
                int(PROBE_WINDOW_MIN_SECONDS - elapsed_since_goodnight),
            )
            return {
                "allow_send": False,
                "skip_reason": "goodnight_probe_window_wait",
                "wait_seconds": wait_seconds,
            }

        # First probe: any time from the end of the wait to the end of the
        # window. The two runtime branches were identical; kept as one.
        if last_goodnight_probe_ts <= 0:
            return {
                "allow_send": True,
                "skip_reason": "",
                "wait_seconds": 0,
                "is_probe": True,
                "is_first_probe": True,
            }

        elapsed_since_probe = now - last_goodnight_probe_ts
        elapsed_since_goodnight_total = (
            now - last_goodnight_ts if last_goodnight_ts > 0 else 0
        )

        # Probe spacing grows with the length of the sleep session.
        if elapsed_since_goodnight_total < 3600:
            probe_gap = max(1800, goodnight_probe_gap_seconds)
        elif elapsed_since_goodnight_total < 2 * 3600:
            probe_gap = max(3600, goodnight_probe_gap_seconds)
        else:
            probe_gap = max(goodnight_low_disturb_gap_seconds, 2 * 3600)

        if elapsed_since_probe < probe_gap:
            wait_seconds = max(default_next_check, int(probe_gap - elapsed_since_probe))
            return {
                "allow_send": False,
                "skip_reason": "goodnight_probe_gap",
                "wait_seconds": wait_seconds,
            }

        return {
            "allow_send": True,
            "skip_reason": "",
            "wait_seconds": 0,
            "is_probe": True,
        }

    def _resolve_probable_sleep_probe_policy(
        self,
        *,
        now: float,
        last_goodnight_probe_ts: float,
        default_next_check: int,
        goodnight_low_disturb_gap_seconds: int,
    ) -> Dict[str, Any]:
        """Probe policy for ``sleep_hint`` (longer gaps, capped wait)."""
        probe_gap = min(goodnight_low_disturb_gap_seconds, PROBABLE_SLEEP_PROBE_GAP_SECONDS)

        if last_goodnight_probe_ts <= 0:
            return {
                "allow_send": True,
                "skip_reason": "",
                "wait_seconds": 0,
                "is_probe": True,
                "is_first_probe": True,
            }

        elapsed_since_probe = now - last_goodnight_probe_ts
        if elapsed_since_probe < probe_gap:
            wait_seconds = max(default_next_check, int(probe_gap - elapsed_since_probe))
            wait_seconds = min(wait_seconds, MAX_PROBE_WAIT_SECONDS)
            return {
                "allow_send": False,
                "skip_reason": "sleep_hint_probe_gap",
                "wait_seconds": wait_seconds,
            }

        return {
            "allow_send": True,
            "skip_reason": "",
            "wait_seconds": 0,
            "is_probe": True,
        }

    def resolve_focus_reduced_policy(
        self,
        *,
        now: float,
        reduced_mode_active: bool,
        reduced_mode_reason: str,
        latest_user_signal_ts: float,
        last_sent_ts: float,
        default_next_check: int,
        focus_user_quiet_seconds: int,
        focus_low_disturb_gap_seconds: int,
    ) -> Dict[str, Any]:
        """Low-disturb gate for ``reduced_mode_reason == "focus"``.

        Two guards: a quiet period after the user's latest signal, and a
        minimum gap since the last sent message.
        """
        if not (reduced_mode_active and str(reduced_mode_reason or "") == "focus"):
            return {"allow_send": True, "skip_reason": "", "wait_seconds": 0}

        if latest_user_signal_ts > 0:
            elapsed_user = max(0.0, now - latest_user_signal_ts)
            if elapsed_user < focus_user_quiet_seconds:
                wait_seconds = max(
                    default_next_check,
                    int(focus_user_quiet_seconds - elapsed_user),
                )
                return {
                    "allow_send": False,
                    "skip_reason": "focus_recent_user_interaction_guard",
                    "wait_seconds": wait_seconds,
                }

        if last_sent_ts > 0:
            elapsed_sent = max(0.0, now - last_sent_ts)
            if elapsed_sent < focus_low_disturb_gap_seconds:
                wait_seconds = max(
                    default_next_check,
                    int(focus_low_disturb_gap_seconds - elapsed_sent),
                )
                return {
                    "allow_send": False,
                    "skip_reason": "focus_low_disturb_backoff",
                    "wait_seconds": wait_seconds,
                }

        return {"allow_send": True, "skip_reason": "", "wait_seconds": 0}


__all__ = [
    "SleepPolicy",
    "PROBE_WINDOW_MIN_SECONDS",
    "PROBE_WINDOW_MAX_SECONDS",
    "MAX_PROBE_WAIT_SECONDS",
]
