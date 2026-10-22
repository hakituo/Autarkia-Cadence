"""Clock-window helpers: HH:MM parsing and wrap-around range arithmetic.

All ranges are half-open ``[start, end)`` in minutes since midnight. A range
whose start is after its end wraps midnight (e.g. 23:00 -> 07:00).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional


def parse_hhmm(value: str) -> Optional[int]:
    """Convert ``"HH:MM"`` to minutes since midnight, or ``None`` if invalid."""
    if not value:
        return None
    text = str(value).strip()
    if ":" not in text:
        return None
    try:
        hour_str, minute_str = text.split(":", 1)
        hour = int(hour_str)
        minute = int(minute_str)
    except ValueError:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour * 60 + minute


def is_in_range_minutes(now_min: int, start_min: int, end_min: int) -> bool:
    """Whether ``now_min`` is inside ``[start_min, end_min)`` (wrap-aware)."""
    if start_min == end_min:
        return True
    if start_min < end_min:
        return start_min <= now_min < end_min
    return now_min >= start_min or now_min < end_min


def next_range_end_dt(now_dt: datetime, start_min: int, end_min: int) -> datetime:
    """The next datetime at which the range ends."""
    now_min = now_dt.hour * 60 + now_dt.minute
    end_hour, end_minute = end_min // 60, end_min % 60
    if start_min < end_min:
        return now_dt.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
    if now_min >= start_min:
        tomorrow = now_dt + timedelta(days=1)
        return tomorrow.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
    return now_dt.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)


def next_window_start_dt(now_dt: datetime, start_min: int, end_min: int) -> datetime:
    """The next datetime at which the range starts (now if already inside)."""
    now_min = now_dt.hour * 60 + now_dt.minute
    if is_in_range_minutes(now_min, start_min, end_min):
        return now_dt
    start_hour, start_minute = start_min // 60, start_min % 60
    if start_min < end_min:
        if now_min < start_min:
            return now_dt.replace(
                hour=start_hour, minute=start_minute, second=0, microsecond=0
            )
        tomorrow = now_dt + timedelta(days=1)
        return tomorrow.replace(
            hour=start_hour, minute=start_minute, second=0, microsecond=0
        )
    if now_min < end_min:
        return now_dt.replace(
            hour=start_hour, minute=start_minute, second=0, microsecond=0
        )
    if now_min < start_min:
        return now_dt.replace(
            hour=start_hour, minute=start_minute, second=0, microsecond=0
        )
    tomorrow = now_dt + timedelta(days=1)
    return tomorrow.replace(
        hour=start_hour, minute=start_minute, second=0, microsecond=0
    )


__all__ = [
    "parse_hhmm",
    "is_in_range_minutes",
    "next_range_end_dt",
    "next_window_start_dt",
]
