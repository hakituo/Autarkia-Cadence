"""Scheduler interval, backoff and jitter tests."""

import random

import pytest

from autarkia_cadence import (
    SchedulerConfig,
    SchedulerLogic,
    apply_interval_jitter,
    calculate_non_response_backoff,
)


class TestBackoff:
    def test_zero_responses_returns_one(self):
        assert calculate_non_response_backoff(0) == 1.0
        assert calculate_non_response_backoff(-3) == 1.0

    def test_backoff_grows_with_count(self):
        rng = random.Random(7)
        values = [calculate_non_response_backoff(n, rng=rng) for n in range(5)]
        # Equal jitter ranges [expo/2, expo]; check the lower envelope grows.
        assert values[0] == 1.0
        assert values[2] >= 1.8
        assert values[4] >= values[3] / 2.0

    def test_backoff_capped(self):
        for _ in range(20):
            assert calculate_non_response_backoff(50) <= 12.0

    def test_backoff_never_below_one(self):
        rng = random.Random(3)
        for n in range(1, 10):
            assert calculate_non_response_backoff(n, base=1.0, cap=1.0, rng=rng) >= 1.0


class TestJitter:
    def test_zero_ratio_returns_base(self):
        assert apply_interval_jitter(100, jitter_ratio=0.0) == 100

    def test_respects_minimum(self):
        rng = random.Random(1)
        for _ in range(20):
            assert apply_interval_jitter(5, min_seconds=30, rng=rng) >= 30

    def test_ratio_is_clamped(self):
        rng = random.Random(2)
        value = apply_interval_jitter(100, jitter_ratio=10.0, rng=rng)
        assert 55 <= value <= 145

    def test_stays_within_band(self):
        rng = random.Random(9)
        for _ in range(50):
            value = apply_interval_jitter(600, jitter_ratio=0.2, rng=rng)
            assert 480 <= value <= 720


class TestSchedulerLogic:
    def make(self, **config):
        return SchedulerLogic(SchedulerConfig(**config), rng=random.Random(42))

    def test_quiet_mode_uses_quiet_interval(self):
        scheduler = self.make(jitter_low_ratio=1.0, jitter_high_ratio=1.0)
        assert scheduler.calculate_dynamic_interval(quiet_mode=True) == 600

    def test_active_mode_uses_active_interval(self):
        scheduler = self.make(jitter_low_ratio=1.0, jitter_high_ratio=1.0)
        assert scheduler.calculate_dynamic_interval() == 300

    def test_non_response_backoff_applied(self):
        scheduler = self.make(jitter_low_ratio=1.0, jitter_high_ratio=1.0)
        interval = scheduler.calculate_dynamic_interval(consecutive_non_responses=2)
        assert 300 * 1.62 <= interval <= 300 * 3.24

    def test_quiet_mode_ignores_bio_state(self):
        scheduler = self.make(jitter_low_ratio=1.0, jitter_high_ratio=1.0)
        sick = {"is_sick": True, "life": {"energy": 10}}
        assert scheduler.calculate_dynamic_interval(bio_state=sick, quiet_mode=True) == 600

    def test_sick_multiplier(self):
        scheduler = self.make(jitter_low_ratio=1.0, jitter_high_ratio=1.0)
        interval = scheduler.calculate_dynamic_interval(bio_state={"is_sick": True})
        assert interval == 600

    def test_low_energy_multiplier(self):
        scheduler = self.make(jitter_low_ratio=1.0, jitter_high_ratio=1.0)
        interval = scheduler.calculate_dynamic_interval(bio_state={"life": {"energy": 20}})
        assert interval == 450

    def test_high_energy_multiplier(self):
        scheduler = self.make(jitter_low_ratio=1.0, jitter_high_ratio=1.0)
        interval = scheduler.calculate_dynamic_interval(bio_state={"life": {"energy": 90}})
        assert interval == 240

    def test_hunger_multiplier(self):
        scheduler = self.make(jitter_low_ratio=1.0, jitter_high_ratio=1.0)
        interval = scheduler.calculate_dynamic_interval(bio_state={"life": {"hunger": 90}})
        assert interval == 210

    def test_sick_wins_over_energy(self):
        scheduler = self.make(jitter_low_ratio=1.0, jitter_high_ratio=1.0)
        interval = scheduler.calculate_dynamic_interval(
            bio_state={"is_sick": True, "life": {"energy": 20}}
        )
        assert interval == 600

    def test_emotion_multiplier_object(self):
        scheduler = self.make(jitter_low_ratio=1.0, jitter_high_ratio=1.0)

        class Emotion:
            primary_emotion = "sad"
            intensity = 1.0

        # sad -> 1.0 + 0.8 * 1.0 = 1.8
        assert scheduler.calculate_dynamic_interval(emotion_state=Emotion()) == 540

    def test_emotion_multiplier_dict(self):
        scheduler = self.make(jitter_low_ratio=1.0, jitter_high_ratio=1.0)
        interval = scheduler.calculate_dynamic_interval(
            emotion_state={"primary_emotion": "anxious", "intensity": 1.0}
        )
        # anxious -> 0.8 + 0 = 0.8
        assert interval == 240

    def test_unknown_emotion_ignored(self):
        scheduler = self.make(jitter_low_ratio=1.0, jitter_high_ratio=1.0)
        assert scheduler.calculate_dynamic_interval(
            emotion_state={"primary_emotion": "puzzled", "intensity": 1.0}
        ) == 300

    def test_enum_emotion_value(self):
        class EnumValue:
            value = "happy"

        class Emotion:
            primary_emotion = EnumValue()
            intensity = 0.0

        scheduler = self.make(jitter_low_ratio=1.0, jitter_high_ratio=1.0)
        assert scheduler.calculate_dynamic_interval(emotion_state=Emotion()) == 300

    def test_interval_is_clamped_to_max(self):
        scheduler = self.make(
            jitter_low_ratio=1.1, jitter_high_ratio=1.1, max_interval_multiplier=2.0
        )
        interval = scheduler.calculate_dynamic_interval(
            bio_state={"is_sick": True}, consecutive_non_responses=10
        )
        assert interval <= 1200

    def test_interval_never_below_minimum(self):
        scheduler = self.make(
            active_interval_seconds=10,
            quiet_interval_seconds=10,
            min_interval_seconds=30,
            jitter_low_ratio=0.5,
            jitter_high_ratio=0.5,
        )
        assert scheduler.calculate_dynamic_interval() == 30

    @pytest.mark.parametrize("seed", range(5))
    def test_intervals_are_positive_ints(self, seed):
        scheduler = SchedulerLogic(rng=random.Random(seed))
        value = scheduler.calculate_dynamic_interval(consecutive_non_responses=seed)
        assert isinstance(value, int) and value > 0
