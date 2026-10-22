"""Adaptive interval calculation with non-response backoff and jitter."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple

from .tuning import (
    BACKOFF_BASE,
    BACKOFF_CAP,
    EMOTION_INTERVAL_MULTIPLIERS,
    INTERVAL_MIN_SECONDS,
    JITTER_HIGH_RATIO,
    JITTER_LOW_RATIO,
)


def calculate_non_response_backoff(
    non_response_count: int,
    *,
    base: float = BACKOFF_BASE,
    cap: float = BACKOFF_CAP,
    rng: Optional[random.Random] = None,
) -> float:
    """Non-response backoff multiplier using the Equal Jitter algorithm.

    Half of the exponential value is a deterministic floor, the other half is
    random. This keeps the mean of plain exponential backoff while raising the
    variance so proactive messages do not form a predictable mechanical
    pattern. Returns ``1.0`` when there were no non-responses.
    """
    n = max(0, int(non_response_count or 0))
    if n <= 0:
        return 1.0
    source = rng or random
    exponential = min(float(base) ** n, float(cap))
    return max(1.0, exponential / 2.0 + source.uniform(0.0, exponential / 2.0))


def apply_interval_jitter(
    base_seconds: float,
    *,
    min_seconds: int = INTERVAL_MIN_SECONDS,
    jitter_ratio: float = 0.20,
    rng: Optional[random.Random] = None,
) -> int:
    """Apply symmetric random jitter, clamped to ``[min_seconds, ...]``."""
    base = max(float(min_seconds), float(base_seconds or 0.0))
    ratio = max(0.0, min(float(jitter_ratio or 0.0), 0.45))
    if ratio <= 0.0:
        return int(base)
    source = rng or random
    low = max(float(min_seconds), base * (1.0 - ratio))
    high = max(low, base * (1.0 + ratio))
    return int(max(float(min_seconds), source.uniform(low, high)))


@dataclass
class SchedulerConfig:
    """Tunables for :class:`SchedulerLogic`."""

    active_interval_seconds: int = 300
    quiet_interval_seconds: int = 600
    min_interval_seconds: int = INTERVAL_MIN_SECONDS
    max_interval_multiplier: float = 2.0
    jitter_low_ratio: float = JITTER_LOW_RATIO
    jitter_high_ratio: float = JITTER_HIGH_RATIO
    backoff_base: float = BACKOFF_BASE
    backoff_cap: float = BACKOFF_CAP
    emotion_multipliers: Mapping[str, Tuple[float, float]] = field(
        default_factory=lambda: dict(EMOTION_INTERVAL_MULTIPLIERS)
    )


class SchedulerLogic:
    """Compute the next check interval from bio/emotion/non-response state.

    Args:
        config: Tunables.
        rng: Optional ``random.Random`` for deterministic tests.
    """

    def __init__(
        self,
        config: Optional[SchedulerConfig] = None,
        *,
        rng: Optional[random.Random] = None,
    ) -> None:
        self.config = config or SchedulerConfig()
        self._rng = rng or random.Random()

    def calculate_dynamic_interval(
        self,
        bio_state: Optional[Dict[str, Any]] = None,
        emotion_state: Any = None,
        consecutive_non_responses: int = 0,
        quiet_mode: bool = False,
    ) -> int:
        """Return the next check interval in seconds.

        Quiet mode uses only the quiet base interval, backoff and jitter.
        Active mode additionally adapts to sickness/energy/hunger and emotion
        intensity, then clamps to ``max(active, quiet) * multiplier``.
        """
        cfg = self.config
        base_interval = (
            cfg.quiet_interval_seconds if quiet_mode else cfg.active_interval_seconds
        )

        backoff_multiplier = calculate_non_response_backoff(
            consecutive_non_responses,
            base=cfg.backoff_base,
            cap=cfg.backoff_cap,
            rng=self._rng,
        )

        if quiet_mode:
            jitter = self._rng.uniform(cfg.jitter_low_ratio, cfg.jitter_high_ratio)
            final_quiet = int(base_interval * backoff_multiplier * jitter)
            return max(cfg.min_interval_seconds, final_quiet)

        multiplier = backoff_multiplier

        if bio_state:
            life = bio_state.get("life", {}) or {}
            energy = float(life.get("energy", 50))
            hunger = float(life.get("hunger", 50))
            is_sick = bool(bio_state.get("is_sick", False)) or bool(
                life.get("is_sick", False)
            )
            if is_sick:
                multiplier *= 2.0
            elif energy < 30:
                multiplier *= 1.5
            elif energy > 80:
                multiplier *= 0.8
            if hunger > 80:
                multiplier *= 0.7

        if emotion_state:
            primary, intensity = _emotion_values(emotion_state)
            emotion_config = cfg.emotion_multipliers.get(primary)
            if emotion_config:
                base_mod, intensity_mod = emotion_config
                multiplier *= base_mod + (intensity_mod * intensity)

        multiplier *= self._rng.uniform(cfg.jitter_low_ratio, cfg.jitter_high_ratio)
        final_interval = int(base_interval * multiplier)

        max_interval = int(
            max(cfg.active_interval_seconds, cfg.quiet_interval_seconds)
            * cfg.max_interval_multiplier
        )
        return max(cfg.min_interval_seconds, min(final_interval, max_interval))


def _emotion_values(emotion_state: Any) -> Tuple[str, float]:
    """Read ``(primary_emotion, intensity)`` from an object or a mapping."""
    if isinstance(emotion_state, Mapping):
        primary = emotion_state.get("primary_emotion") or emotion_state.get("primary") or "neutral"
        intensity = emotion_state.get("intensity", 0.5)
    else:
        primary = getattr(emotion_state, "primary_emotion", None)
        intensity = getattr(emotion_state, "intensity", 0.5)
    if hasattr(primary, "value"):
        primary = primary.value
    primary_text = str(primary or "neutral").lower()
    try:
        intensity_value = float(intensity)
    except (TypeError, ValueError):
        intensity_value = 0.5
    return primary_text, intensity_value


__all__ = [
    "SchedulerConfig",
    "SchedulerLogic",
    "calculate_non_response_backoff",
    "apply_interval_jitter",
]
