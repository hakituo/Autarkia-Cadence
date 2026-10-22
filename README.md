<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/hakituo/Autarkia-Cadence/main/autarkia-dark.svg">
    <img src="https://raw.githubusercontent.com/hakituo/Autarkia-Cadence/main/autarkia.svg" alt="Autarkia" width="300">
  </picture>
</p>

<p align="center">
  <b>Autarkia-Cadence</b><br>
  <sub>主动消息节奏治理 · Proactive message cadence governance for AI companions</sub>
</p>

<p align="center">
  <a href="https://pypi.org/project/Autarkia-Cadence/"><img alt="PyPI" src="https://img.shields.io/pypi/v/autarkia-cadence.svg"></a>
  <a href="https://pypi.org/project/Autarkia-Cadence/"><img alt="Python" src="https://img.shields.io/pypi/pyversions/autarkia-cadence.svg"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
</p>

<p align="center">
  <a href="#中文">简体中文</a> · <a href="#english">English</a>
</p>

---

## 中文

分层冷却、话题组抑制、每日提问上限、自适应检查间隔（等抖动退避）、静默时段、睡眠探测策略——**在 LLM 被调用之前**就决定「现在到底该不该说话」。

来自长期无人值守运行的 [Autarkia](https://qishihao.icu/projects/autarkia) agent 运行时：它让一个自托管陪伴体没有变成通知轰炸机。整个系列见[组件库路线图](https://github.com/hakituo/Autarkia-tool/blob/main/ROADMAP.md)。

### 为什么

当角色能主动找你说话之后，难的问题不是「它该说什么」，而是**「此刻它到底该不该开口」**。提示词约束是守不住的。这个库在 LLM 调用之前划一条确定性的线：

- **全局冷却**：任意两条主动消息之间的最小间隔。
- **提问冷却**：刚问过问题，短时间内不再问。
- **同话题组**：「吃了吗」「外卖到了没」「饭好了吗」归入同一个 `meal` 组——换个说法也绕不过窗口。
- **未回复抑制**：上一条主动消息没有回应时，普通提问被抑制。
- **每日软上限**：好奇提问每天有上限。
- **专注闸门**：正式专注会话期间普通消息硬拦截；真提醒与定时任务豁免。
- **生成后复检**：一个以问号结尾的 `share_thought` 会被当作提问处理——意图名掩盖不了追问。

同包还带上闸门周围的调度算术：由精力/饥饿/情绪驱动的自适应间隔、等抖动的未回复退避、可注入数据源的下发时间表与静默时段加载、时钟窗口helper、晚安探测策略、长静默覆盖闸门。

零运行时依赖。纯函数 + 普通数据结构：不做 I/O、不发网络、不调 LLM、不读全局配置。

### 安装

```bash
pip install autarkia-cadence
```

### 快速开始

```python
import time
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
    print(verdict.retry_after_minutes) # 140
```

闸门不写状态：`last_proactive_*`、`last_sent_topic`、`today_sent_events` 由你持久化，它只读。

生成后复检：

```python
verdict = guard.evaluate_final_text(
    now=time.time(),
    intent="share_thought",
    final_text="在炒菜。你做饭还是点外卖？",
    proactive_state=state,
)
# 上一条主动消息未回复时，这条会被当作提问拦下
```

自适应间隔：

```python
from autarkia_cadence import SchedulerConfig, SchedulerLogic

scheduler = SchedulerLogic(SchedulerConfig(active_interval_seconds=300))
delay = scheduler.calculate_dynamic_interval(
    bio_state={"life": {"energy": 20, "hunger": 90}},
    emotion_state={"primary_emotion": "sad", "intensity": 0.8},
    consecutive_non_responses=2,
)
```

睡眠探测：

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
policy["allow_send"]  # 晚安后 10–30 分钟的第一次探测
```

### 模块分工

| 组件 | 模块 | 决定什么 |
| --- | --- | --- |
| `CadenceGuard` / `CadenceVerdict` | `autarkia_cadence.guard` | 放行 / 推迟、原因、重试延迟 |
| `CadenceConfig` | `autarkia_cadence.config` | 全部阈值，注入式 |
| `classify_topic`、`group_for_topic_label` | `autarkia_cadence.topics`、`.topic_groups` | 话题标签与冷却分组 |
| `SchedulerLogic` | `autarkia_cadence.scheduling` | 下一次检查间隔 |
| `SilenceGate` / `SilenceContext` | `autarkia_cadence.silence` | 强制发送的覆盖条件 |
| `SleepPolicy` | `autarkia_cadence.sleep` | 晚安探测、专注低打扰 |
| `ScheduleConfigLoader` | `autarkia_cadence.schedule_config` | 下发时间表 + 静默时段 |
| `parse_hhmm`、`is_in_range_minutes` | `autarkia_cadence.windows` | 支持跨零点的时钟窗口 |

推迟原因（`reason`）：`cadence_no_intent`、`formal_focus_session_active`、`last_proactive_unanswered`、`cadence_global_cooldown`、`cadence_question_cooldown`、`cadence_same_topic_group`、`cadence_curious_question_daily_cap`。

### 设计说明

- **豁免要显式声明，不靠推断**：硬事件意图（`reminder`、`good_morning_proactive` 等）写在 `CadenceConfig.exempt_intents` 里；未登记的意图一律走正常节奏检查。
- **用话题组，不做文本相似度**：确定性分桶更便宜，也更难被绕开。
- **专注状态是注入的**：库里没有学习子系统，你传一个 callable；provider 抛异常按「未在专注」处理。
- **时间全部由外部传入**：闸门内部不读墙钟，测试是纯的。

### 系列与链接

- 项目页：<https://qishihao.icu/projects/autarkia>
- 运行时仓库：<https://github.com/hakituo/Autarkia>
- 本包：<https://github.com/hakituo/Autarkia-Cadence>
- 组件库路线图：<https://github.com/hakituo/Autarkia-tool/blob/main/ROADMAP.md>
- 作者：Shihao Qi — <https://qishihao.icu>

### 许可

MIT

---

## English

Layered cooldowns, topic-group suppression, daily question caps, adaptive check intervals with equal-jitter backoff, quiet hours, and sleep-window probes — a deterministic "should it speak at all, right now" line drawn **before** any LLM call.

Extracted from the [Autarkia](https://qishihao.icu/projects/autarkia) agent runtime, where it keeps a self-hosted companion from turning into a notification machine over months of unattended operation. See the [component roadmap](https://github.com/hakituo/Autarkia-tool/blob/main/ROADMAP.md) for the rest of the series.

### Why

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

### Install

```bash
pip install autarkia-cadence
```

### Quick start

```python
import time
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
    print(verdict.retry_after_minutes) # 140
```

The guard never writes state. You persist `last_proactive_*`, `last_sent_topic` and `today_sent_events`; the guard only reads them.

#### Recheck after generation

```python
verdict = guard.evaluate_final_text(
    now=time.time(),
    intent="share_thought",
    final_text="在炒菜。你做饭还是点外卖？",
    proactive_state=state,
)
# blocked as a question if the previous proactive message is unanswered
```

#### Adaptive intervals

```python
from autarkia_cadence import SchedulerConfig, SchedulerLogic

scheduler = SchedulerLogic(SchedulerConfig(active_interval_seconds=300))
delay = scheduler.calculate_dynamic_interval(
    bio_state={"life": {"energy": 20, "hunger": 90}},
    emotion_state={"primary_emotion": "sad", "intensity": 0.8},
    consecutive_non_responses=2,
)
```

#### Sleep probes

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

### Concepts

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

#### Defer reasons

`cadence_no_intent`, `formal_focus_session_active`, `last_proactive_unanswered`, `cadence_global_cooldown`, `cadence_question_cooldown`, `cadence_same_topic_group`, `cadence_curious_question_daily_cap`.

### Design notes

- **Explicit exemption, not inference.** Hard-event intents (`reminder`, `good_morning_proactive`, ...) are declared in `CadenceConfig.exempt_intents`. Unknown intents go through normal cadence.
- **Topic groups, not text similarity.** Deterministic buckets are cheaper and harder to game than fuzzy matching.
- **Injected focus state.** The library has no study subsystem; pass a callable. Provider errors mean "not active".
- **All time is passed in.** No wall-clock reads inside the guard; tests are pure.

### The bigger picture

- Project page: <https://qishihao.icu/projects/autarkia>
- Runtime repository: <https://github.com/hakituo/Autarkia>
- This package: <https://github.com/hakituo/Autarkia-Cadence>
- Roadmap: <https://github.com/hakituo/Autarkia-tool/blob/main/ROADMAP.md>
- Author: Shihao Qi — <https://qishihao.icu>

### License

MIT
