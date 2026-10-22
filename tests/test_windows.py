"""Clock window arithmetic tests."""

from datetime import datetime

import pytest

from autarkia_cadence import (
    is_in_range_minutes,
    next_range_end_dt,
    next_window_start_dt,
    parse_hhmm,
)


class TestParseHHMM:
    @pytest.mark.parametrize(
        "value,minutes",
        [("00:00", 0), ("09:30", 570), ("23:59", 1439), (" 7:05 ", 425)],
    )
    def test_valid(self, value, minutes):
        assert parse_hhmm(value) == minutes

    @pytest.mark.parametrize(
        "value", ["", None, "930", "24:00", "12:60", "-1:00", "ab:cd", "12:aa"]
    )
    def test_invalid(self, value):
        assert parse_hhmm(value) is None


class TestRangeChecks:
    def test_simple_range(self):
        assert is_in_range_minutes(600, 540, 720) is True
        assert is_in_range_minutes(540, 540, 720) is True
        assert is_in_range_minutes(720, 540, 720) is False

    def test_wrapping_range(self):
        # 23:00 -> 07:00
        start, end = 23 * 60, 7 * 60
        assert is_in_range_minutes(23 * 60 + 30, start, end) is True
        assert is_in_range_minutes(2 * 60, start, end) is True
        assert is_in_range_minutes(12 * 60, start, end) is False

    def test_equal_bounds_means_all_day(self):
        assert is_in_range_minutes(0, 600, 600) is True
        assert is_in_range_minutes(1439, 600, 600) is True


class TestNextRangeEnd:
    def test_same_day(self):
        now = datetime(2026, 1, 1, 9, 0)
        assert next_range_end_dt(now, 9 * 60, 12 * 60) == datetime(2026, 1, 1, 12, 0)

    def test_wrap_before_start_returns_today_end(self):
        now = datetime(2026, 1, 1, 2, 0)
        assert next_range_end_dt(now, 23 * 60, 7 * 60) == datetime(2026, 1, 1, 7, 0)

    def test_wrap_after_start_returns_tomorrow_end(self):
        now = datetime(2026, 1, 1, 23, 30)
        assert next_range_end_dt(now, 23 * 60, 7 * 60) == datetime(2026, 1, 2, 7, 0)

    def test_seconds_are_zeroed(self):
        now = datetime(2026, 1, 1, 9, 0, 33, 123)
        result = next_range_end_dt(now, 9 * 60, 12 * 60)
        assert result.second == 0 and result.microsecond == 0


class TestNextWindowStart:
    def test_inside_returns_now(self):
        now = datetime(2026, 1, 1, 10, 0)
        assert next_window_start_dt(now, 9 * 60, 12 * 60) == now

    def test_before_start_same_day(self):
        now = datetime(2026, 1, 1, 8, 0)
        assert next_window_start_dt(now, 9 * 60, 12 * 60) == datetime(2026, 1, 1, 9, 0)

    def test_after_end_returns_tomorrow(self):
        now = datetime(2026, 1, 1, 13, 0)
        assert next_window_start_dt(now, 9 * 60, 12 * 60) == datetime(2026, 1, 2, 9, 0)

    def test_wrap_outside_range_returns_today_start(self):
        now = datetime(2026, 1, 1, 12, 0)
        assert next_window_start_dt(now, 23 * 60, 7 * 60) == datetime(2026, 1, 1, 23, 0)

    def test_wrap_inside_returns_now(self):
        now = datetime(2026, 1, 1, 23, 30)
        assert next_window_start_dt(now, 23 * 60, 7 * 60) == now
