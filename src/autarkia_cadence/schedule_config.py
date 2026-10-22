"""Push-schedule / quiet-hours configuration with an injectable source.

The runtime read two dicts from its global config and cached them for 60
seconds. Here the data source is a callable returning
``(push_schedule_overrides, quiet_hours_overrides)``; it may be sync or async.
Defaults are merged first, then overrides are applied shallowly, matching the
runtime semantics.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any, Awaitable, Callable, Dict, Mapping, Optional, Tuple

from .tuning import (
    DEFAULT_DAILY_LIMIT,
    DEFAULT_MIN_GAP_SECONDS,
    DEFAULT_NEXT_CHECK_SECONDS,
)

PushSchedule = Dict[str, Any]
QuietHours = Dict[str, Any]
ConfigProvider = Callable[
    [], Tuple[Mapping[str, Any], Mapping[str, Any]]
]
AsyncConfigProvider = Callable[
    [], Awaitable[Tuple[Mapping[str, Any], Mapping[str, Any]]]
]


def build_default_push_schedule(
    *,
    daily_limit: int = DEFAULT_DAILY_LIMIT,
    min_gap_seconds: int = DEFAULT_MIN_GAP_SECONDS,
    default_next_check_seconds: int = DEFAULT_NEXT_CHECK_SECONDS,
    timezone: str = "Asia/Shanghai",
) -> PushSchedule:
    """Build the default push schedule."""
    return {
        "schema_version": 1,
        "timezone": str(timezone),
        "rules": {
            "daily_limit": int(daily_limit),
            "min_gap_seconds": int(min_gap_seconds),
            "default_next_check_seconds": int(default_next_check_seconds),
        },
        "windows": [],
    }


def build_default_quiet_hours() -> QuietHours:
    """Build the default quiet-hours configuration."""
    return {
        "enabled": True,
        "goodnight_probe_gap_seconds": 2 * 3600,
        "allow_goodnight_probe": False,
    }


def merge_configs(
    defaults: Mapping[str, Any], overrides: Optional[Mapping[str, Any]]
) -> Dict[str, Any]:
    """Shallow-merge overrides onto a copy of defaults (runtime semantics)."""
    merged = dict(defaults)
    if isinstance(overrides, Mapping):
        merged.update(overrides)
    return merged


def load_schedule_configs(
    *,
    push_overrides: Optional[Mapping[str, Any]] = None,
    quiet_overrides: Optional[Mapping[str, Any]] = None,
    daily_limit: int = DEFAULT_DAILY_LIMIT,
    min_gap_seconds: int = DEFAULT_MIN_GAP_SECONDS,
    default_next_check_seconds: int = DEFAULT_NEXT_CHECK_SECONDS,
    timezone: str = "Asia/Shanghai",
) -> Tuple[PushSchedule, QuietHours]:
    """Build defaults and apply explicit overrides."""
    push_schedule = build_default_push_schedule(
        daily_limit=daily_limit,
        min_gap_seconds=min_gap_seconds,
        default_next_check_seconds=default_next_check_seconds,
        timezone=timezone,
    )
    return (
        merge_configs(push_schedule, push_overrides),
        merge_configs(build_default_quiet_hours(), quiet_overrides),
    )


class ScheduleConfigLoader:
    """Load schedule configs through a provider, with a TTL cache.

    Args:
        provider: Zero-argument callable returning ``(push_overrides,
            quiet_overrides)``. May be a coroutine function. ``None`` means
            defaults only.
        ttl_seconds: Cache lifetime; ``<= 0`` disables caching.
    """

    def __init__(
        self,
        provider: Optional[Callable[[], Any]] = None,
        *,
        ttl_seconds: float = 60.0,
    ) -> None:
        self._provider = provider
        self._ttl_seconds = float(ttl_seconds)
        self._cache: Optional[Tuple[PushSchedule, QuietHours]] = None
        self._loaded_at = 0.0

    async def load(self) -> Tuple[PushSchedule, QuietHours]:
        """Re-read the provider and build fresh config dicts."""
        push_overrides: Optional[Mapping[str, Any]] = None
        quiet_overrides: Optional[Mapping[str, Any]] = None
        if self._provider is not None:
            result = self._provider()
            if inspect.isawaitable(result):
                result = await result
            if isinstance(result, tuple) and len(result) == 2:
                push_overrides, quiet_overrides = result
        return load_schedule_configs(
            push_overrides=push_overrides,
            quiet_overrides=quiet_overrides,
        )

    async def get(self) -> Tuple[PushSchedule, QuietHours]:
        """Return cached configs, refreshing them when the TTL expired."""
        now = time.monotonic()
        if (
            self._ttl_seconds > 0
            and self._cache is not None
            and (now - self._loaded_at) < self._ttl_seconds
        ):
            return self._cache
        self._cache = await self.load()
        self._loaded_at = time.monotonic()
        return self._cache

    def invalidate(self) -> None:
        """Drop the cached value."""
        self._cache = None
        self._loaded_at = 0.0


def get_schedule_configs_sync(
    loader: ScheduleConfigLoader,
) -> Tuple[PushSchedule, QuietHours]:
    """Convenience wrapper for synchronous call sites."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(loader.get())
    raise RuntimeError(
        "get_schedule_configs_sync() cannot run inside an active event loop; "
        "await loader.get() instead"
    )


__all__ = [
    "PushSchedule",
    "QuietHours",
    "build_default_push_schedule",
    "build_default_quiet_hours",
    "merge_configs",
    "load_schedule_configs",
    "ScheduleConfigLoader",
    "get_schedule_configs_sync",
]
