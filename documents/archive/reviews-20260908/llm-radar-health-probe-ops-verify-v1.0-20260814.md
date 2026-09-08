# llm-radar 线上数据新鲜度探针 — ops 验证报告

> 日期: 2026-08-14
> 验证人: ops (hermes-1.2.0)
> 实现: 294bfd1 feat@llm-radar (dev) | 实现报告: a72f03f
> 设计依据: llm-radar-health-probe-design-v1.2-20260813.md

## 验证方式

独立运行验证命令 + 代码逐项核对 + cron 跨 profile 审计。不信任 dev 自报,全部实测。

## 功能验证(验收标准 1)

| 场景 | 命令 | 结果 |
|:-----|:-----|:-----|
| 健康 | `python3 scripts/llm-radar-health.py` | exit 0, stdout 空 ✅ |
| 过期 | `LLM_RADAR_STALE_HOURS=0 python3 scripts/llm-radar-health.py` | exit 1, 告警 "数据过期: 1.0h 前 > 0h" ✅ |
| 线上实测 | fetch timestamp.json | last_run_at=2026-08-14T00:02, status=success, news=2026-08-14 ✅ |

## 代码核对(检查项 1/3/4)

| # | 检查项 | 结果 |
|:-:|:-------|:-----|
| 1 | 脚本请求 `?t=<epoch>` cache-busting | ✅ fetch() 加 `?t={int(time.time())}` (RIG-2) |
| 2 | 三态退出契约 | ✅ 新鲜度>7h → exit 1 硬告警; status!=success 但新鲜 → exit 0 软告警; 健康 → exit 0 静默 (REA-2) |
| 3 | 时区契约 | ✅ last_run_at 本地 naive, datetime.fromisoformat 同机解析, 双机 +08:00 (RIG-1) |
| 4 | 网络/JSON 失败 | ✅ except → 错误告警 exit 1, 非静默 |
| 5 | 阈值常量 | ✅ STALE_HOURS=7 顶部, LLM_RADAR_STALE_HOURS 覆盖 |
| 6 | 脚本独立 | ✅ 未修改 llm-radar-collector.py (git show 确认) |

## Cron 注册验证(验收标准 2)

**发现并修正 profile 归属错误**:
- dev 将 job 534bea76c7eb 注册在 **dev profile**(与 wrapper 同目录)
- 探针是监控职责, 应与 health-daily/health-weekly 同 profile → **ops**
- 修正: dev job 移除 → ops 注册新 job 02a2cdc5db20 (schedule `0 3,9,15,21 * * *`, no_agent=true, deliver=local)
- ops wrapper 复制到 ~/.hermes/profiles/ops/scripts/ + chmod +x
- `hermes cron run` 手动触发: "Ran now: succeeded", Last run: ok, Execution: completed ✅

## 设计偏差记录(dev 侧, 已确认合理)

hermes cron no_agent script 字段仅接受 profile scripts/ 目录下文件名(实测解析到 profile scripts/), 不接受项目绝对路径。故 wrapper 方案: profile scripts/ 放 os.execv 薄 wrapper 委派到项目内脚本(单一逻辑源, 无副本漂移)。wrapper 非 repo 内容, 属部署胶水。与设计 B1"项目内 scripts/"不冲突——项目内脚本仍是唯一逻辑源。

## 验收标准 3

git status 干净, 无 rebase 残留, 探针触发无副作用 ✅

## 结论

**PASS** — 功能/代码/cron 全部达标。附带修正: cron job profile 归属 dev→ops(与监控职责一致)。可交最终 implementation audit。
