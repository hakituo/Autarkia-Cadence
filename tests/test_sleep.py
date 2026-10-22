"""Sleep probe / focus low-disturb policy tests."""

from autarkia_cadence import SleepPolicy


NOW = 1_800_000_000.0


def probe(policy, **overrides):
    params = dict(
        now=NOW,
        sleep_session_active=True,
        allow_goodnight_probe=True,
        reduced_mode_active=False,
        reduced_mode_reason="none",
        last_goodnight_ts=NOW - 1200,
        last_goodnight_probe_ts=0.0,
        default_next_check=300,
        min_gap_seconds=600,
        goodnight_probe_gap_seconds=7200,
        goodnight_low_disturb_gap_seconds=7200,
    )
    params.update(overrides)
    return policy.resolve_sleep_probe_policy(**params)


class TestSleepProbe:
    def test_awake_always_allowed(self):
        result = probe(SleepPolicy(), sleep_session_active=False)
        assert result["allow_send"] is True

    def test_probe_disabled_blocks_long(self):
        result = probe(SleepPolicy(), allow_goodnight_probe=False)
        assert result["allow_send"] is False
        assert result["skip_reason"] == "goodnight_quiet_block"
        assert result["wait_seconds"] >= 3600

    def test_waits_ten_minutes_after_goodnight(self):
        result = probe(SleepPolicy(), last_goodnight_ts=NOW - 300)
        assert result["skip_reason"] == "goodnight_probe_window_wait"
        assert result["wait_seconds"] >= 300

    def test_first_probe_allowed(self):
        result = probe(SleepPolicy(), last_goodnight_ts=NOW - 1200)
        assert result["allow_send"] is True
        assert result["is_probe"] is True
        assert result["is_first_probe"] is True

    def test_first_probe_allowed_after_window(self):
        result = probe(SleepPolicy(), last_goodnight_ts=NOW - 2000)
        assert result["allow_send"] is True
        assert result["is_first_probe"] is True

    def test_second_probe_gap_one_hour(self):
        result = probe(
            SleepPolicy(),
            last_goodnight_ts=NOW - 3000,
            last_goodnight_probe_ts=NOW - 1200,
        )
        assert result["skip_reason"] == "goodnight_probe_gap"
        assert result["wait_seconds"] >= 600

    def test_second_probe_allowed_after_gap(self):
        result = probe(
            SleepPolicy(),
            last_goodnight_ts=NOW - 5 * 3600,
            last_goodnight_probe_ts=NOW - 8000,
        )
        assert result["allow_send"] is True
        assert not result.get("is_first_probe")

    def test_late_session_uses_low_disturb_gap(self):
        result = probe(
            SleepPolicy(),
            last_goodnight_ts=NOW - 3 * 3600,
            last_goodnight_probe_ts=NOW - 100,
        )
        assert result["skip_reason"] == "goodnight_probe_gap"
        assert result["wait_seconds"] >= 7000

    def test_sleep_hint_first_probe(self):
        result = probe(
            SleepPolicy(),
            sleep_session_active=False,
            reduced_mode_active=True,
            reduced_mode_reason="sleep_hint",
        )
        assert result["allow_send"] is True
        assert result["is_first_probe"] is True

    def test_sleep_hint_gap(self):
        result = probe(
            SleepPolicy(),
            sleep_session_active=False,
            reduced_mode_active=True,
            reduced_mode_reason="sleep_hint",
            last_goodnight_probe_ts=NOW - 100,
        )
        assert result["skip_reason"] == "sleep_hint_probe_gap"
        assert result["wait_seconds"] <= 3600

    def test_other_reduced_mode_allowed(self):
        result = probe(
            SleepPolicy(),
            sleep_session_active=False,
            reduced_mode_active=True,
            reduced_mode_reason="focus",
        )
        assert result["allow_send"] is True


class TestFocusPolicy:
    def resolve(self, policy, **overrides):
        params = dict(
            now=NOW,
            reduced_mode_active=True,
            reduced_mode_reason="focus",
            latest_user_signal_ts=0.0,
            last_sent_ts=0.0,
            default_next_check=300,
            focus_user_quiet_seconds=900,
            focus_low_disturb_gap_seconds=1800,
        )
        params.update(overrides)
        return policy.resolve_focus_reduced_policy(**params)

    def test_not_focus_allowed(self):
        result = self.resolve(SleepPolicy(), reduced_mode_active=False)
        assert result["allow_send"] is True

    def test_recent_user_interaction_blocks(self):
        result = self.resolve(SleepPolicy(), latest_user_signal_ts=NOW - 60)
        assert result["skip_reason"] == "focus_recent_user_interaction_guard"
        assert result["wait_seconds"] >= 300

    def test_user_quiet_expired_allows(self):
        result = self.resolve(SleepPolicy(), latest_user_signal_ts=NOW - 1000)
        assert result["allow_send"] is True

    def test_low_disturb_backoff(self):
        result = self.resolve(
            SleepPolicy(), latest_user_signal_ts=NOW - 1000, last_sent_ts=NOW - 300
        )
        assert result["skip_reason"] == "focus_low_disturb_backoff"

    def test_low_disturb_expired_allows(self):
        result = self.resolve(
            SleepPolicy(), latest_user_signal_ts=NOW - 1000, last_sent_ts=NOW - 2000
        )
        assert result["allow_send"] is True


class TestArchive:
    def test_duration(self):
        record = SleepPolicy().build_sleep_session_archive_updates(
            {"last_goodnight_ts": 1000}, 2000
        )
        assert record["last_sleep_session_start_ts"] == 1000
        assert record["last_sleep_session_end_ts"] == 2000
        assert record["last_sleep_session_duration_seconds"] == 1000

    def test_missing_goodnight(self):
        record = SleepPolicy().build_sleep_session_archive_updates({}, 2000)
        assert record["last_sleep_session_start_ts"] == 0
        assert record["last_sleep_session_duration_seconds"] == 0

    def test_invalid_values(self):
        record = SleepPolicy().build_sleep_session_archive_updates(
            {"last_goodnight_ts": "bad"}, 2000
        )
        assert record["last_sleep_session_duration_seconds"] == 0

    def test_custom_safe_ts(self):
        record = SleepPolicy().build_sleep_session_archive_updates(
            {"last_goodnight_ts": 10}, 20, safe_ts_func=lambda value: float(value or 0)
        )
        assert record["last_sleep_session_start_ts"] == 10.0
