---
title: llm-radar 线上数据新鲜度探针 — 实现报告
topic: llm-radar
type: impl
version: 1.0
date: 2026-08-14
author: hermes-1.2.0 (dev)
tags: [llm-radar, cron, watchdog, monitoring, health]
profile: dev
provider: deepseek
model: deepseek-v4-pro
---

# llm-radar — 线上数据新鲜度探针 实现报告

> 版本: v1.0 | 日期: 2026-08-14
> 作者: dev (hermes-1.2.0)
> 依据设计: documents/solutions/llm-radar-health-probe-design-v1.2-20260813.md
> 依据复审: documents/reviews/llm-radar-health-probe-rereview-v1.2-20260813.md (PASS 100/100)
> 交付 commit: 294bfd1 `feat@llm-radar: 线上数据新鲜度探针 scripts/llm-radar-health.py (三态退出 watchdog)`

## 变更清单

| # | 设计项 | 实现 | 位置 |
|:-:|:-------|:-----|:-----|
| B1 | 探针脚本 | `scripts/llm-radar-health.py`（项目内，随 repo 版本化，纯 stdlib 零依赖） | `scripts/llm-radar-health.py` |
| B2 | cron 注册 | job `llm-radar-freshness`（no_agent=true, `0 3,9,15,21 * * *`, deliver=local） | job_id `534bea76c7eb` |
| B4 | 阈值常量 | `STALE_HOURS = 7` 写入脚本顶部，可用 `LLM_RADAR_STALE_HOURS` 覆盖（供验收测试） | 脚本 `:38` |

## 三态退出契约（O-1，已写入脚本注释）

| 场景 | exit | stdout |
|:-----|:----:|:-------|
| 数据过期 (now - last_run_at > STALE_HOURS) | 1 | 告警「数据过期」 |
| 网络失败 / JSON 解析失败 / 字段缺失 / 时间戳无法解析 | 1 | 告警「探针错误」 |
| 质量门禁失败 (status != success，但数据新鲜) | 0 | 告警「质量告警」(软) |
| 健康 (新鲜且 success) | 0 | 空 (静默) |

## 时区契约（O-2，已写入脚本注释）

- `last_run_at` 为采集器 `datetime.now().isoformat()` 写盘的本地时间（naive 无时区后缀）。
- 探针以本机 `datetime.now()` 直接相减；服务器/本机均 +08:00（已实测本机 CST +0800）。

## 关键实现细节（设计文档未覆盖）

- **cache-busting (RIG-2)**: 请求 `timestamp.json?t=<epoch>`。
- **脚本路径桥接**: hermes cron 的 no_agent `script` 字段仅接受 profile scripts/ 目录下的文件名（实测解析到 `~/.hermes/profiles/dev/scripts/`），不能引用项目绝对路径。故在 `~/.hermes/profiles/dev/scripts/llm-radar-health.py` 放了一个 `os.execv` 薄 wrapper，原地委派到项目内脚本——单一逻辑源（repo 版本化），无副本漂移。此 wrapper 非 repo 内容（部署胶水）。

## 验收结果

| # | 验收标准 | 结果 |
|:-:|:---------|:-----|
| 1 | 手动执行 exit 0 静默 / 阈值 0h exit 1 告警 | ✅ 健康 exit 0 stdout 空；`LLM_RADAR_STALE_HOURS=0` exit 1 告警 |
| 2 | cron list 可见 + 首次运行 last_status=ok | ✅ job `534bea76c7eb` last_status=ok |
| 3 | 探针触发无 git 残留 / 无副作用 | ✅ git status 仅新增脚本，无 rebase 残留 |

补充：全逻辑路径已逐项验证（健康/过期/质量软告警/过期+failed 新鲜度优先/缺字段/无法解析/网络失败/JSON 解析失败）——8 路径全部符合契约。

## 交付物

- `scripts/llm-radar-health.py`（项目内，repo 版本化，commit `294bfd1`）
- `~/.hermes/profiles/dev/scripts/llm-radar-health.py`（cron 入口 wrapper，非 repo）
- hermes cron job `llm-radar-freshness`（job_id `534bea76c7eb`，deliver=local）
