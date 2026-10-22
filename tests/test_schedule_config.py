"""Push-schedule and quiet-hours configuration tests."""

import asyncio

import pytest

from autarkia_cadence import (
    ScheduleConfigLoader,
    build_default_push_schedule,
    build_default_quiet_hours,
    load_schedule_configs,
    merge_configs,
)


class TestDefaults:
    def test_push_schedule_shape(self):
        schedule = build_default_push_schedule()
        assert schedule["schema_version"] == 1
        assert schedule["timezone"] == "Asia/Shanghai"
        assert schedule["rules"] == {
            "daily_limit": 20,
            "min_gap_seconds": 600,
            "default_next_check_seconds": 300,
        }
        assert schedule["windows"] == []

    def test_push_schedule_overrides(self):
        schedule = build_default_push_schedule(
            daily_limit=5,
            min_gap_seconds=900,
            default_next_check_seconds=60,
            timezone="UTC",
        )
        assert schedule["rules"]["daily_limit"] == 5
        assert schedule["rules"]["min_gap_seconds"] == 900
        assert schedule["timezone"] == "UTC"

    def test_quiet_hours_defaults(self):
        assert build_default_quiet_hours() == {
            "enabled": True,
            "goodnight_probe_gap_seconds": 7200,
            "allow_goodnight_probe": False,
        }

    def test_defaults_are_copies(self):
        first = build_default_push_schedule()
        first["rules"]["daily_limit"] = 999
        assert build_default_push_schedule()["rules"]["daily_limit"] == 20

    def test_defaults_without_overrides(self):
        schedule, quiet = load_schedule_configs()
        assert schedule["rules"]["daily_limit"] == 20
        assert quiet["enabled"] is True


class TestMerge:
    def test_shallow_merge(self):
        merged = merge_configs({"a": 1, "b": {"c": 2}}, {"b": {"d": 3}})
        assert merged == {"a": 1, "b": {"d": 3}}

    def test_none_overrides(self):
        assert merge_configs({"a": 1}, None) == {"a": 1}

    def test_overrides_applied(self):
        schedule, quiet = load_schedule_configs(
            push_overrides={"rules": {"daily_limit": 3}},
            quiet_overrides={"allow_goodnight_probe": True},
        )
        assert schedule["rules"] == {"daily_limit": 3}
        assert quiet["allow_goodnight_probe"] is True


class TestLoader:
    def test_default_loader(self):
        loader = ScheduleConfigLoader()
        schedule, quiet = asyncio.run(loader.get())
        assert schedule["rules"]["min_gap_seconds"] == 600
        assert quiet["enabled"] is True

    def test_sync_provider(self):
        loader = ScheduleConfigLoader(lambda: ({"rules": {"daily_limit": 7}}, {}))
        schedule, _ = asyncio.run(loader.get())
        assert schedule["rules"]["daily_limit"] == 7

    def test_async_provider(self):
        async def provider():
            return {"rules": {"daily_limit": 9}}, {"enabled": False}

        loader = ScheduleConfigLoader(provider)
        schedule, quiet = asyncio.run(loader.get())
        assert schedule["rules"]["daily_limit"] == 9
        assert quiet["enabled"] is False

    def test_cache_avoids_repeated_reads(self):
        calls = []

        def provider():
            calls.append(1)
            return {}, {}

        loader = ScheduleConfigLoader(provider, ttl_seconds=60)
        asyncio.run(loader.get())
        asyncio.run(loader.get())
        assert len(calls) == 1

    def test_zero_ttl_disables_cache(self):
        calls = []

        def provider():
            calls.append(1)
            return {}, {}

        loader = ScheduleConfigLoader(provider, ttl_seconds=0)
        asyncio.run(loader.get())
        asyncio.run(loader.get())
        assert len(calls) == 2

    def test_invalidate_forces_reload(self):
        calls = []

        def provider():
            calls.append(1)
            return {}, {}

        loader = ScheduleConfigLoader(provider)
        asyncio.run(loader.get())
        loader.invalidate()
        asyncio.run(loader.get())
        assert len(calls) == 2

    def test_bad_provider_result_falls_back_to_defaults(self):
        loader = ScheduleConfigLoader(lambda: "nonsense")
        schedule, _ = asyncio.run(loader.load())
        assert schedule["rules"]["daily_limit"] == 20

    def test_sync_in_running_loop_raises(self):
        from autarkia_cadence import get_schedule_configs_sync

        loader = ScheduleConfigLoader()

        async def main():
            with pytest.raises(RuntimeError):
                get_schedule_configs_sync(loader)

        asyncio.run(main())

    def test_sync_wrapper_outside_loop(self):
        from autarkia_cadence import get_schedule_configs_sync

        schedule, _ = get_schedule_configs_sync(ScheduleConfigLoader())
        assert schedule["schema_version"] == 1
