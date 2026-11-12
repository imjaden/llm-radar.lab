---
loop: LLM-RADAR-CL009
title: 失效静默 → 跃迁式告警（CL009 复盘）
date: 2026-11-12
level: L1
---

# LLM-RADAR-CL009 复盘 · 失效静默 → 跃迁式告警

## 1. 背景与问题

系统里「采集失败」有三种命运：**看得见**（`lr status` 判 critical）、**看不全**（只写 metrics 不推送）、**完全静默**。
第三种代价最大：2026-11-09 09:25Z → 11-10 10:21Z，X 采集因 `page target=0` 连败 10 轮，
`data/twitter.json` **停更 24.9 小时**，没有任何渠道告诉人 —— 是人工进会话看日志才发现的。

原台账写的是「飞书告警接入」，但飞书涉及跨角色凭据，且此前已有「暂不做飞书」的裁定。本次**缩范围**：
先把「跃迁式告警 + 本地通道」做成可用最小版，飞书只留开关。

## 2. 判据设计（7 类失效）

| kind | 判据来源 | 门槛 | 级别 |
|---|---|---|---|
| `auth_missing` / `auth` | `metrics.last_error.kind` | **1 次即报** | critical |
| `model` / `quota` | 同上 | 连败 ≥2 | warning |
| `network` / `other` | 同上 | 连败 ≥3 | warning |
| `stale` | `timestamp.json:last_run_at` 年龄 | > 6.5h | critical |
| `source_degraded` | `metrics.source_health[*].consecutive_fails` | ≥3 | warning |
| `x_health` | `cache/state/x-health.json`（巡检写入） | status≠ok 且 12h 内 | critical |

发送语义是**跃迁式**，不是「每轮报」：首次出现发、升级为 critical 立即发、同类 24h 内不重发、**恢复必发一条回执**。

## 3. 改动

- 新增 `scripts/llm_radar_alert.py`（`classify` / `decide` / `deliver` / `check` + CLI，含 `cli_interrupt` 守卫）。
- `llm-radar-collector.py`：`_observe()` 在 metrics 落盘后调用 `_dispatch_alerts()`，包在 `try/except` 里，
  **告警失败不得改变采集退出码**；人类可读行走 `_log_stream()`（`--json` 时去 stderr）。
- ops 侧巡检 `llm-radar-twitter-login-verify.py`：把四条判据的结果写成 `cache/state/x-health.json`，
  再调同一个分流器 —— 出口唯一，避免「每处各写一套通知」。
- 状态文件 `cache/state/alert-state.json`（gitignored），`--dry-run` 不落状态。

## 4. 验证

- `pytest tests/test_alert_dispatch.py -q -n0` → **15 passed**（门槛、跃迁、去重、升级、恢复、dry-run、接线位置）。
- 全量 `pytest -m "not selenium"` → **602 passed**；`test_cli` 24 passed；门禁 `中断收敛 10/10`。
- 真机：`classify --json` → `alerts: []`（健康时不空响）；合成 `auth` 故障 → `sent=1`（本地通知到达）；
  巡检真跑 `PASS` → 只写 sidecar，不发通知。

## 5. 经验

1. 告警要报「状态跃迁」，不报「每轮结果」；否则真故障会被噪音淹掉，人会把通知关掉。
2. `--dry-run` 必须不落状态 —— 一次演练就会把真故障永久去重掉。
3. 事实源只认产物（metrics / timestamp / sidecar），告警时**不重新探网**：告警不能自己变成故障源。
4. 通道选本地 osascript（与 X 登录墙同一条），零凭据即可上线；飞书留 `--channel feishu` 待裁定。

## 6. 遗留

- 飞书通道未启用（等解除「暂不做飞书」裁定）。
- 「直改源码型」条目没有独立设计/评审轮次，本复盘与 `cache/closed-loop/…-retro.json` 为补档记录。
