"""Long-silence override gate tests."""

from datetime import datetime

from autarkia_cadence import SilenceContext, SilenceGate


NOW = 1_800_000_000.0


def context(**overrides):
    params = dict(
        now=NOW,
        now_dt=datetime(2026, 1, 1, 12, 0),
        elapsed=3600,
        count=0,
        last_sent_ts=NOW - 4000,
        last_attempt_ts=NOW - 4000,
        min_gap_seconds=600,
        daily_limit=20,
        latest_user_signal_ts=NOW - 600,
    )
    params.update(overrides)
    return SilenceContext(**params)


class TestDerivedFlags:
    def test_long_silence_threshold_default(self):
        assert context(min_gap_seconds=600).long_silence_seconds == 3600

    def test_long_silence_threshold_scales(self):
        assert context(min_gap_seconds=1800).long_silence_seconds == 5400

    def test_has_long_silence(self):
        assert context(last_sent_ts=NOW - 4000).has_long_silence is True
        assert context(last_sent_ts=NOW - 100, last_attempt_ts=NOW - 100).has_long_silence is False

    def test_no_attempt_means_long_silence(self):
        assert context(last_sent_ts=0, last_attempt_ts=0).has_long_silence is True

    def test_recent_signal_window(self):
        assert context(latest_user_signal_ts=NOW - 600).has_recent_signal_for_long_silence is True
        assert context(latest_user_signal_ts=NOW - 7 * 3600).has_recent_signal_for_long_silence is False

    def test_no_send_timeout(self):
        assert context(last_sent_ts=NOW - 5000).no_send_for_too_long is True
        assert context(last_sent_ts=NOW - 100).no_send_for_too_long is False

    def test_user_silent_long_enough(self):
        assert context(elapsed=1800).user_silent_long_enough is True
        assert context(elapsed=100).user_silent_long_enough is False

    def test_early_morning(self):
        assert context(now_dt=datetime(2026, 1, 1, 3, 0)).is_early_morning is True
        assert context(now_dt=datetime(2026, 1, 1, 15, 0)).is_early_morning is False
        assert context(now_dt=None).is_early_morning is False


class TestOverrideAllowed:
    def test_quiet_mode_blocks(self):
        assert SilenceGate().is_override_allowed(context(quiet_mode_active=True)) is False

    def test_sleep_session_blocks(self):
        assert SilenceGate().is_override_allowed(context(sleep_session_active=True)) is False

    def test_sleep_hint_allows_without_pressure(self):
        gate = SilenceGate()
        ctx = context(reduced_mode_active=True, reduced_mode_reason="sleep_hint")
        assert gate.is_override_allowed(ctx, False) is True
        assert gate.is_override_allowed(ctx, True) is False

    def test_goodnight_daytime(self):
        gate = SilenceGate()
        ctx = context(
            reduced_mode_active=True,
            reduced_mode_reason="goodnight",
            now_dt=datetime(2026, 1, 1, 12, 0),
        )
        assert gate.is_override_allowed(ctx, False) is True
        assert gate.is_override_allowed(ctx, True) is False

    def test_goodnight_night_blocked(self):
        ctx = context(
            reduced_mode_active=True,
            reduced_mode_reason="goodnight",
            now_dt=datetime(2026, 1, 1, 2, 0),
        )
        assert SilenceGate().is_override_allowed(ctx) is False

    def test_daily_limit_blocks(self):
        assert SilenceGate().is_override_allowed(context(count=20)) is False

    def test_normal_allows(self):
        assert SilenceGate().is_override_allowed(context()) is True


class TestShouldForceSend:
    def test_long_silence_forces(self):
        force, reason = SilenceGate().should_force_send(context())
        assert (force, reason) == (True, "long_silence_fallback")

    def test_no_send_timeout_forces(self):
        # No recent user signal, so the long-silence branch cannot fire and
        # the no-send timeout is the only trigger left.
        ctx = context(
            last_sent_ts=NOW - 5000,
            last_attempt_ts=NOW - 5000,
            latest_user_signal_ts=NOW - 7 * 3600,
            elapsed=3600,
        )
        force, reason = SilenceGate().should_force_send(ctx)
        assert (force, reason) == (True, "no_send_timeout_fallback")

    def test_quiet_mode_prevents_force(self):
        force, reason = SilenceGate().should_force_send(context(quiet_mode_active=True))
        assert (force, reason) == (False, "")

    def test_non_response_pressure_requires_more_silence(self):
        ctx = context(last_sent_ts=NOW - 4000, last_attempt_ts=NOW - 4000)
        force, _ = SilenceGate().should_force_send(ctx, non_response_count=1)
        assert force is False

    def test_non_response_pressure_passes_after_longer_silence(self):
        ctx = context(last_sent_ts=NOW - 9000, last_attempt_ts=NOW - 9000)
        force, reason = SilenceGate().should_force_send(ctx, non_response_count=1)
        assert (force, reason) == (True, "long_silence_fallback")

    def test_recent_user_signal_required_for_long_silence(self):
        ctx = context(latest_user_signal_ts=NOW - 7 * 3600, last_sent_ts=NOW - 4000)
        # no_send timeout also fails because there is no recent signal? No:
        # the no-send branch does not require a recent signal, only elapsed.
        force, reason = SilenceGate().should_force_send(ctx)
        assert force is True
        assert reason == "no_send_timeout_fallback"


class TestApplyOverrides:
    def test_send_decision_untouched(self):
        sent, thought = SilenceGate().apply_silence_overrides(context(), True, "hi", 0)
        assert (sent, thought) == (True, "hi")

    def test_force_fills_empty_thought(self):
        sent, thought = SilenceGate().apply_silence_overrides(context(), False, "", 0)
        assert sent is True
        assert thought == "long_silence_fallback"

    def test_force_keeps_existing_thought(self):
        sent, thought = SilenceGate().apply_silence_overrides(context(), False, "有话说", 0)
        assert (sent, thought) == (True, "有话说")

    def test_no_override_returns_false(self):
        ctx = context(quiet_mode_active=True)
        assert SilenceGate().apply_silence_overrides(ctx, False, "", 0) == (False, "")
