---
title: 回执 · llm-radar「数据偏旧」判据改为「当日首采 + 30min」
author: ops
date: 2026-10-27
from_repo: /Users/jadenli/CodeSpace/llm-radar.lab
target_repo: /Users/jadenli/CodeSpace/daily-checker
related: DAILY-CHECKER-CL191 / crossrepo-llm-radar-staleness-20261027
status: 已上线（2026-10-27 11:5x，本仓 main）
---

# 回执：陈旧度改为「判定点」口径（当天首采 / 应到时刻 + 宽限）

## 一句话

`lr status` 不再用绝对小时数判陈旧：**当日首次成功采集 + 30min 之前不判**；当天还没首采则以
**当日应到时刻（默认 09:40）+ 30min = 10:10** 为判定点。跨夜合盖导致的早晨误报已消除，
`status` 四值语义、七字段协议与 `actions` 全部不变。

## 口径（实现即此，无隐藏分支）

1. `first_success_today`：取 `data/metrics.json` 的 `run_history` 里**当天（本地时区）最早一条 success**；
   `run_history` 被裁剪/缺失时回退 `timestamp.json.last_run_at`（要求 `last_run_status=success` 且是今天）。
2. 判定点 `judge_at`：
   - 今天已有首采 ⇒ `first_success_today + STALENESS_GRACE_MIN`（默认 30min）
   - 今天还没有首采 ⇒ `今日 09:40 + 30min = 10:10`（`LLM_RADAR_FIRST_SLOT` 可改应到时刻）
3. `now < judge_at` ⇒ **不评陈旧**（`status=ok`），message 说明原因，如：
   - `今日待首采・判定点 10:10・最近 12.2h 前`（无今日首采）
   - `今日首采 09:00・判定点 09:30・最近 0.2h 前`（刚采完）
4. `now >= judge_at` ⇒ 回到阈值口径：`age > 12h → warning`、`age > 48h → critical`
   （`age = now - last_run_at`，未来时间戳按 0 处理）。
5. **例外**：`age > 48h` 不受判定点保护 —— 凌晨 03:00 查也会是 `critical`
   （防止安静窗口把「两天没采」盖成 ok）。

## ⚠️ 需要你们同步的一处事实偏差

`features.md` 记的 `ok(<7h)` 是旧值：**上游自 2026-09-03 起 `STALE_HOURS = 12`**（当时为消除跨夜误报从 7h 放宽）。
本次改造没有动这个阈值，请把 `评估:` 行改成：

```
ok: 未到判定点 或 (age <= 12h 且成功且未分叉)
warning: 到判定点后 12h < age <= 48h 或 git 分叉或质量 failed
critical: age > 48h（不受判定点保护） 或 snapshot 缺失 或 全局失败 >= 3
```

若你们希望收紧到 7h，说一声即可（`LLM_RADAR_STALE_HOURS=7` 一条 env 就能切换，但需重跑一周噪音复核）。

## 验收（本仓已落地，全绿）

`tests/test_status.py::TestStalenessJudgePoint`（8 例）逐条对应你们给的验收建议：

| 你们的验收 | 用例 | 结果 |
|---|---|---|
| 昨日 19:33 采到、今天 07:42 查询 ⇒ 不得 warning | `test_morning_query_after_yesterday_run_is_not_warning` | ok・`今日待首采・判定点 10:10` |
| 今天 09:00 首采、判定点前查询 ⇒ ok | `test_ok_right_after_first_success` | ok |
| 采集开始后按阈值判 warning | `test_warning_after_judge_point_when_truly_stale`（09:00 首采、22:00 查 → 13h） | warning |
| 连续两天无采集 ⇒ 仍 critical | `test_critical_after_two_days_without_collection` + `test_critical_override_before_judge_point` | critical |
| 时钟偏移防御 | `test_future_timestamp_is_clamped_not_negative` | ok・无负数 |
| 应到时刻/env 解析 | `test_invalid_first_slot_env_falls_back_to_0940`、`test_grace_minutes_env` | 回退 09:40 |

真机复算（真实数据，`now` 注入）：`07:42 → ok`、`11:00 → ok（数据新鲜 2.6h）`、`21:30 → warning（13.1h）`。

## 你们那层降噪怎么处理

建议**保留** `quiet_windows 00:00–09:30` 作双保险（我们这层已不会再在 10:10 前报偏旧，
两者叠加只会更安静，不会互相打架）。若想收窄到 `00:00–08:00` 也可以，取决于你们对其他 checkpoint 的统一手感。

## 上线信息

- 仓：`/Users/jadenli/CodeSpace/llm-radar.lab`（main），提交见仓库 `git log --grep=staleness`
- 生效面：`lr status` / `lr status --json`（wrapper `~/.local/bin/lr` 指向 `cache/system-command/llm-radar-wrapper.sh`，无需重装）
- 环境变量（可选）：`LLM_RADAR_FIRST_SLOT`（应到时刻，默认 `09:40`）、`LLM_RADAR_STALENESS_GRACE_MIN`（默认 `30`）、
  `LLM_RADAR_STALE_HOURS`（默认 `12`）、`LLM_RADAR_CRITICAL_HOURS`（默认 `48`）

## 追加（同日 12:0x）：线上新鲜度探针也同口径

你们只依赖 `lr status`，但本仓还有第二个陈旧度出口会发飞书 —— `scripts/llm-radar-health.py`
（cron `llm-radar-freshness`，10:00 / 15:00 / 21:00 跑；ops 侧是 execv wrapper 委派到本仓脚本，无需重装）。
为避免「你们拿到 ok、我们自己的探针仍在 10:00 报过期」，它已改成同一判定点口径：

- 差别只有一处：探针只拿得到线上 `timestamp.json`（没有 `run_history`），故用 `last_run_at` 近似
  「今日成功时刻」⇒ 判定点只会**更晚**，即更宽松，不会多报；
- 顺序不变：`>48h` 兜底 → 判定点前静默 → 判定点后按 12h 阈值；
- message 末尾附 `[判定点 10:10 已过]` / `[>48h 兜底判定]` 便于区分触发原因；
- 钉子 `tests/test_health_staleness.py` 10 例，其中 `test_parity_with_collector` 用 6×8×2=96 组输入
  逐一对齐两处实现（防口径漂移）；
- 真机复现：用线上 payload 把 `last_run_at` 替换为「昨日 19:33」⇒ `07:42` 静默、`10:11` 报
  `数据过期 … > 12h [判定点 10:10 已过]`。
