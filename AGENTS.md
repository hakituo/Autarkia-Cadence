# AGENTS.md — Autarkia-Cadence（Autarkia 组件库系列）

给改动本仓库的 agent 看的说明书。读完应该能回答：这是什么、语义以谁为准、怎么验证、怎么发布。

## 这是什么

Autarkia 运行时组件库系列的第 2 个库：主动消息节奏治理——分层频控、同题材分组冷却、每日提问上限、自适应间隔、等抖动退避、静默时段、晚安探针、长沉默强制发送门。

- PyPI：<https://pypi.org/project/Autarkia-Cadence/>
- 系列路线图：<https://github.com/hakituo/Autarkia-tool/blob/main/ROADMAP.md>（**先读它**）
- 主运行时（语义权威源）：本地 `D:\AI\xiaoyou-public`，GitHub <https://github.com/hakituo/Autarkia>
- 作者站点：<https://qishihao.icu/projects/autarkia>

## 了解背景：先看主仓库的哪些文件

本库从主运行时抽取而来，**行为语义以主仓库为准**。改任何行为前按顺序看：

1. `D:\AI\xiaoyou-public\PROJECT_TECHNICAL_REFERENCE.md`
2. 源头文件对照表：

| 本库模块 | 主仓库源头（D:\AI\xiaoyou-public\） |
| --- | --- |
| `src/autarkia_cadence/guard.py` | `core\services\active_care\cadence\cadence_guard.py` |
| `src/autarkia_cadence/topic_groups.py` | `core\services\active_care\cadence\topic_groups.py` |
| `src/autarkia_cadence/topics.py` | `core\services\active_care\decision\topic_classifier.py`、`prompt\topic_diversity.py`、`shared\keywords.py` |
| `src/autarkia_cadence/scheduling.py` | `core\services\active_care\scheduling\scheduler_logic.py`、`shared\scheduling_utils.py`、`checker\checker_throttle.py` |
| `src/autarkia_cadence/windows.py` | `core\utils\time\time_utils.py`（`parse_hhmm`）+ `scheduler_logic.py` 的窗口函数 |
| `src/autarkia_cadence/schedule_config.py` | `core\services\active_care\scheduling\schedule_config_loader.py` |
| `src/autarkia_cadence/sleep.py` | `core\services\active_care\core\sleep_policy.py`、`shared\sleep_thresholds.py` |
| `src/autarkia_cadence/silence.py` | `core\services\active_care\checker\checker_time_gate.py`、`decision\action_builder.py`（`should_force_send`）、`decision\decision_context.py` |
| `src/autarkia_cadence/tuning.py` | `core\services\active_care\shared\tuning.py` + `sleep_thresholds.py` |

3. 宿主测试母本：`D:\AI\xiaoyou-public\tests\unit\test_active_care_poke_gate.py`、`test_focus_session_active_care_guard.py`

抽取时做过的通用化改造（不要再改回去）：
- `config.*` / `core.utils.*` → 无依赖；阈值收进 `CadenceConfig` / `SchedulerConfig`。
- 正式 FocusSession 单例 → `focus_session_provider` 注入，异常视为"未激活"。
- 题材分类器 → 可注入 callable，默认内置关键词表。
- 模块级全局配置缓存 → `ScheduleConfigLoader` 实例级 TTL 缓存。
- 宿主日志 → stdlib `logging`；`cleanup_legacy_schedule_files` 属宿主迁移逻辑，已删除。

## 本仓库结构

```text
AGENTS.md                 本文件
src/autarkia_cadence/     包本体（import 名 autarkia_cadence）
tests/                    行为测试（不跑 LLM/网络/真实时钟）
pyproject.toml            hatchling；无运行时依赖；Python >=3.10
```

## 硬规则

1. **零运行时依赖**。新增依赖必须先在 ROADMAP 立项说明理由。
2. **宿主 import 一个不许进 src/**：`config.*`、`core.*`、`clients.*` 只能以参数注入形式存在。
3. 判定只读状态、不写状态；时间一律由调用方传入 `now`，库内不读墙钟（`ScheduleConfigLoader` 的 TTL 计时除外）。
4. 行为变更先改/加测试，全绿再提交。
5. **每次 `twine upload` 前必须递增 `pyproject.toml` 的 version**。
6. PyPI token 不进 git；只存在于 `%USERPROFILE%\.pypirc`。

## 命令（本机环境）

venv 与主库共用：`D:\AI\autarkia\.venv\`（Python 3.10）。

| 用途 | 命令 |
| --- | --- |
| 测试 | `$env:PYTHONPATH="src"; D:\AI\autarkia\.venv\Scripts\python -m pytest -q` |
| 构建 | `D:\AI\autarkia\.venv\Scripts\python -m build --no-isolation` |
| 发布检查 | `D:\AI\autarkia\.venv\Scripts\python -m twine check dist\*` |
| 发布 | `$env:HTTP_PROXY="http://127.0.0.1:7897"; $env:HTTPS_PROXY=$env:HTTP_PROXY; D:\AI\autarkia\.venv\Scripts\python -m twine upload dist\* --non-interactive` |

**本机 pip 坑**：不加 `-i https://pypi.org/simple --proxy http://127.0.0.1:7897` 会报 `from versions: none`。**twine 坑**：不认 `--proxy`，走环境变量。

## 提交

- commit message 中文一句话；Windows 下写进临时文件用 `git commit -F` 防乱码。
- 改完自己提交并推送 `origin main`，不要停在"改好了"等确认。
- 推送前 `git status --porcelain` 确认只含本次任务涉及的文件。
