---
title: llm-radar CLI 治理 — 实现审计尾项复核报告 v1.0
topic: llm-radar
type: review
version: 1.0
date: 2026-08-23
author: hermes-1.2.0
tags: [llm-radar, cli, governance, cli-registry, recheck, CL-SEC11]
profile: review
provider: deepseek
model: deepseek-v4-flash
---

# llm-radar CLI 治理与全局注册 — 实现审计尾项复核 review报告 v1.0

> 日期: 2026-08-23
> 上游: 实现审计 PASS 95/A (972db8d) — 遗留 1 🟡 LR-SEC-011 + 1 🟢 O-5
> 复核 commit: 90b5aa5 fix@cli (LR-SEC-011, CL-SEC11); 59c8b92 docs@design (O-5, CL-SEC11)
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.jaden.tech
> review维度: 尾项修复正确性 / 边界一致性 / 副作用 / 测试质量

## 数据验证

全部条目以实际执行/读取为准, 不采信 ops 自报。

| # | 验证项 | 方法 | 结果 |
|:--|:-------|:-----|:-----|
| 1 | 90b5aa5 全 args 扫描 | `git show 90b5aa5` diff | ✅ 拦截条件从 `args[0].upper()=='HELP'` 改为 `any(a.upper()=='HELP' for a in args)` (collector.py:2213-2220), 覆盖 `run --force help` / `fetch qbitai help` 非首位绕过 |
| 2 | 副作用范围 | `crontab --list` 实测 | ✅ exit=0, 正常输出 cron 行; 正常参数不含 HELP token, 不受全 args 扫描影响 |
| 3 | 绕过场景实测 | `python3 llm-radar-collector.py run --force help` | ✅ exit=0, stdout 仅 "用法: lr run ..." 一行, 无采集副作用 (无 DEEPSEEK 调用 / 无 git fetch / 无 metrics 写入) |
| 4 | 新增测试 | 读 tests/test_cli.py | ✅ 2 测试 (test_cli_run_force_help_intercepted / test_cli_fetch_source_help_intercepted), 断言 returncode=0 + "用法" in stdout + 未触发采集 |
| 5 | 测试复跑 | `python3 -m pytest tests/test_cli.py -q` | ✅ 13 passed in 3.79s (原 11 + 新 2) |
| 6 | O-5 边界标注一致性 | 读 collector.py:1843-1846 | ✅ 实现 `age_hours > CRITICAL_HOURS` → critical, `age_hours > STALE_HOURS` → warning; 恰 7h 两条件均不成立 → 默认 ok。文档标注 "严格小于; 恰 7h 判 ok" 与实现 `>` 语义完全一致 |
| 7 | 59c8b92 文档改动 | `git show 59c8b92` diff | ✅ 仅设计 v1.1 §4.2 status 表 ok 行补边界标注, 无其他漂移 |

## 尾项评估

| ID | Severity | 修复 | 核验 | 结论 |
|:---|:--------:|:-----|:----:|:----:|
| LR-SEC-011 | 🟡 | 90b5aa5 全 args HELP 扫描 + 2 测试 | 代码 diff + 实测拦截 + pytest 13 passed | ✅ Resolved |
| O-5 | 🟢 | 59c8b92 设计 §4.2 ok 行补边界标注 | 文档与 collector.py:1845 `>` 语义一致 | ✅ Resolved |

### LR-SEC-011 细节

- 原缺陷: 拦截仅检查 `args[0]`, `run --force help` 中 help 非首位可绕过, 实测触发 run 流水线副作用 (git fetch + metrics 写入, 'help' 非合法源快速失败, 有界)。
- 修复正确性: `any()` 全 args 扫描覆盖任意位置 HELP; 大小写归一化 (`.upper()`) 与既有行为一致; 拦截仅限 fetch/run/commit/crontab 四个带参子命令, 不含 help/status/sources 等无参命令 — 作用域无扩大。
- 副作用: `crontab --list` 参数无 HELP token, 不受影响 (实测 exit=0 正常输出)。全量非 selenium 122 passed (原 120 + 2 新) 由 ops 复跑记录, 本次独立复跑 test_cli 13 passed 确认。

### O-5 细节

- 设计 v1.1 §4.2 status 表 ok 行: `last_run_at < 7h 且质量门禁 success (严格小于; 恰 7h 判 ok, 实现 > STALE_HOURS 才 warning)`。
- 实现 collector.py:1845: `elif age_hours > STALE_HOURS: freshness = 'warning'` — `>` 而非 `>=`, 恰 7h → 保持初始值 ok。边界语义一致, 无 off-by-one。

## 安全事项

- 无新增 🟡 SEC 项。全 args HELP 扫描属输入归一化加固, 不引入新的注入/越权面; 拦截路径只调用 `print_command_usage()` + `sys.exit(0)`, 无 IO 副作用。
- 两 commit diff 无敏感信息 (纯逻辑/文档改动)。

## 评分

100 / 100 (A) — 实现审计 95 分基础上 LR-SEC-011 (🟡, -5) 已修复, 复核无新增扣分项; O-5 为 🟢 观察项 (0 扣分) 已补标注。

## 结论

PASS — 尾项全部 Resolved。LR-SEC-011 → Resolved (90b5aa5), O-5 → Resolved (59c8b92)。review-log.md 该条 tracking 已改 ✅ Closed, .review-level.yaml findings_open 置 0。执行 push: 59c8b92 + 90b5aa5 + 本复核记录。

## 待确认清单

- [x] 90b5aa5 全 args 扫描实现正确, 无副作用
- [x] 59c8b92 边界标注与实现一致
- [x] `run --force help` → 用法 exit=0 不采集
- [x] `crontab --list` → 正常执行
- [x] pytest tests/test_cli.py → 13 passed
