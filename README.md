# Autarkia-Cadence

**Proactive message cadence governance for AI companions** — layered cooldowns, topic-group suppression, daily question caps, adaptive check intervals with equal-jitter backoff, quiet hours, and sleep-window probes.

Extracted from the [Autarkia](https://qishihao.icu/projects/autarkia) agent runtime, where it keeps a self-hosted companion from turning into a notification machine over months of unattended operation. See the [component roadmap](https://github.com/hakituo/Autarkia-tool/blob/main/ROADMAP.md) for the rest of the series.

## Why

Once a companion can message you first, the hard question is not "what should it say" but **"should it speak at all, right now"**. Prompt instructions do not hold. This library holds a deterministic line before any LLM call:

- **Global cooldown** — minimum gap between any two proactive messages.
- **Question cooldown** — after asking something, don't ask again soon.
- **Same topic group** — "did you eat?" / "did the delivery arrive?" / "food ready?" collapse into one `meal` group, so rephrasing cannot bypass the window.
- **Unanswered suppression** — if the last proactive message got no reply, ordinary questions are suppressed.
- **Daily soft cap** — a bounded number of curious questions per day.
- **Focus gate** — a formal focus session hard-blocks ordinary messages; real reminders and scheduled tasks stay exempt.
- **Post-generation recheck** — a `share_thought` that ends with a question is treated as a question. The intent name cannot hide a follow-up.

It also ships the scheduling arithmetic around the gate: adaptive intervals driven by energy/hunger/emotion, equal-jitter non-response backoff, push-schedule/quiet-hours loading with an injectable source, clock-window helpers, goodnight probe policy, and the long-silence override gate.

Zero runtime dependencies. Pure functions and plain data; no I/O, no network, no LLM, no global config.

## Install

```bash
pip install autarkia-cadence
```

## Quick start

```python
from autarkia_cadence import CadenceGuard

guard = CadenceGuard(
    focus_session_provider=lambda: my_focus_service.has_active_session(),
)

verdict = guard.evaluate(
    now=time.time(),
    chosen_action="curious_question",
    proactive_state={
        "last_proactive_at": time.time() - 45 * 60,
        "last_proactive_type": "share_thought",
        "last_proactive_replied": True,
        "last_sent_topic": "curious_question:food",
    },
    candidate_topic_label="curious_question:food",
)

if not verdict.allowed:
    print(verdict.reason)              # "cadence_same_topic_group"
    print(verdict.retry_after_minutes) # 135
```

The guard never writes state. You persist `last_proactive_*`, `last_sent_topic` and `today_sent_events`; the guard only reads them.

### Recheck after generation

```python
verdict = guard.evaluate_final_text(
    now=time.time(),
    intent="share_thought",
    final_text="在炒菜。你做饭还是点外卖？",
    proactive_state=state,
)
# blocked as a question if the previous proactive message is unanswered
```

### Adaptive intervals

```python
from autarkia_cadence import SchedulerConfig, SchedulerLogic

scheduler = SchedulerLogic(SchedulerConfig(active_interval_seconds=300))
delay = scheduler.calculate_dynamic_interval(
    bio_state={"life": {"energy": 20, "hunger": 90}},
    emotion_state={"primary_emotion": "sad", "intensity": 0.8},
    consecutive_non_responses=2,
)
```

### Sleep probes

```python
from autarkia_cadence import SleepPolicy

policy = SleepPolicy().resolve_sleep_probe_policy(
    now=time.time(),
    sleep_session_active=True,
    allow_goodnight_probe=True,
    reduced_mode_active=False,
    reduced_mode_reason="none",
    last_goodnight_ts=goodnight_ts,
    last_goodnight_probe_ts=0,
    default_next_check=300,
    min_gap_seconds=600,
    goodnight_probe_gap_seconds=7200,
    goodnight_low_disturb_gap_seconds=7200,
)
policy["allow_send"]  # first probe 10-30 minutes after goodnight
```

## Concepts

| Piece | Module | What it decides |
| --- | --- | --- |
| `CadenceGuard` / `CadenceVerdict` | `autarkia_cadence.guard` | allow / defer, reason, retry delay |
| `CadenceConfig` | `autarkia_cadence.config` | all thresholds, injected |
| `classify_topic`, `group_for_topic_label` | `autarkia_cadence.topics`, `.topic_groups` | topic labels and cooldown groups |
| `SchedulerLogic` | `autarkia_cadence.scheduling` | next check interval |
| `SilenceGate` / `SilenceContext` | `autarkia_cadence.silence` | force-send overrides |
| `SleepPolicy` | `autarkia_cadence.sleep` | goodnight probes, focus low-disturb |
| `ScheduleConfigLoader` | `autarkia_cadence.schedule_config` | push schedule + quiet hours |
| `parse_hhmm`, `is_in_range_minutes` | `autarkia_cadence.windows` | clock windows with midnight wrap |

### Defer reasons

`cadence_no_intent`, `formal_focus_session_active`, `last_proactive_unanswered`, `cadence_global_cooldown`, `cadence_question_cooldown`, `cadence_same_topic_group`, `cadence_curious_question_daily_cap`.

## Design notes

- **Explicit exemption, not inference.** Hard-event intents (`reminder`, `good_morning_proactive`, ...) are declared in `CadenceConfig.exempt_intents`. Unknown intents go through normal cadence.
- **Topic groups, not text similarity.** Deterministic buckets are cheaper and harder to game than fuzzy matching.
- **Injected focus state.** The library has no study subsystem; pass a callable. Provider errors mean "not active".
- **All time is passed in.** No wall-clock reads inside the guard; tests are pure.

## The bigger picture

- Project page: <https://qishihao.icu/projects/autarkia>
- Runtime repository: <https://github.com/hakituo/Autarkia>
- This package: <https://github.com/hakituo/Autarkia-Cadence>
- Roadmap: <https://github.com/hakituo/Autarkia-tool/blob/main/ROADMAP.md>
- Author: Shihao Qi — <https://qishihao.icu>

## License

MIT
