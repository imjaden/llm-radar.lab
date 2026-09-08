---
title: llm-radar CLI 治理 — ops 独立核查报告 v1.0
topic: llm-radar
type: review
version: 1.0
date: 2026-08-23
author: hermes-1.2.0
tags: [llm-radar, cli, governance, cli-registry, checkpoint, verify]
profile: ops
provider: deepseek
model: deepseek-v4-flash
---

# llm-radar CLI 治理与全局注册 — ops 独立核查报告 v1.0

> 闭环: CL-SEC11 | 设计: v1.1 (7bd8f26) | 复审: PASS 95/A (8d089bd) | 实施: 26219ba
> 核查方法: 不采信 dev 自报, CLI 实测 + pytest 复跑 + wrapper 内容检查

## 核查结论

✅ **全部通过** — 验收标准 8 条独立实测 7 条 + 单测证据 1 条, pytest 120 passed。
实施质量良好, 发现 1 项非阻断观察(O-1 已确认无害)。

## CLI 实测(独立执行, 非 dev 报告)

| # | 验收项 | 实测方法 | 结果 |
|:---|:---|:---|:---|
| 1 | 分组 help | `python3 llm-radar-collector.py help` | ✅ hm-style 4 组【采集执行/数据管理/Git 集成/定时任务】+ 功能概述 |
| 2 | 空入参 exit=0 | 无参运行, 检查 exit code | ✅ exit=0 |
| 3 | status --json 七字段 | json.loads 校验 | ✅ 七字段齐全, status=warning, icon=🟡 匹配, message 无 emoji |
| 4 | status 四态 + checks/actions | 解析输出 | ✅ checks 4 项(数据日期/实体数/质量门禁/Git 同步), actions 3 项(run/push/repair) |
| 5 | status 文本输出 | 无 --json 运行 | ✅ 单行摘要(质量 failed \| 1 ahead/0 behind), 无 emoji |
| 6 | positional help 拦截 | `crontab help` / `fetch help` / `run help` | ✅ 全部打印用法 exit=0, 不触发采集副作用(run help 秒回) |
| 7 | 全局注册 | ls ~/.local/bin + 双命令 diff | ✅ llm-radar + lr symlink 存在, 两命令 status --json 输出一致 |
| 8 | wrapper .env + 耦合处理 | 读 wrapper 内容 | ✅ exec 前 set -a source .env (L81-83); script-miner 仅注释提及(说明 RIG-3 处理), 无 calls.log 统计段 |
| — | .cli-registry.yaml | 读文件 | ✅ bin_dir/python/env.conda py3.12 + commands llm-radar + alias_list [lr], Linux 注记含 AGENTS.md 引用 |

## 测试复跑(独立执行)

```
python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_selenium.py -q
→ 120 passed, 2 deselected, 3 warnings in 3.89s
```

与 dev 自报一致(109 passed 忽略 test_cli + 11 新增 = 120)。

## 观察项

| # | 项 | 级别 | 说明 |
|:---|:---|:---|:---|
| O-1 | pytest 跑完污染数据文件 | 🟢 已知 | test_timestamp/test_isolation 用真实 project_root 写脏 snapshot/overview/timestamp, AGENTS.md 已记载; 已 git checkout 还原到 HEAD 基线。HEAD 本身含 1 处 isolation-test 历史遗留(8/16 auto-push 误提交, 非本次引入) |
| O-2 | .hermes-project.yaml 未提交 | 🟢 会话前已存在 | 与 dev 无关, 保持不动 |

## 边界验证

- run help 拦截: 实测秒回用法, 未触发 DEEPSEEK_API_KEY 错误(与评审实测的旧行为对比, 拦截生效)。
- 无 snapshot → critical: dev 单测覆盖(test_status.py), 核查未重复执行(避免再次污染数据)。

## 结论

**核查通过** — 可进入实现审计(review role)。建议审计聚焦:
1. dev commit 26219ba 的 status 评估逻辑与设计 §4.2 一致性
2. wrapper 模板 fork 的完整性(RIG-2/3/10 落地)
3. test_status.py fixture 隔离是否真正不触真实项目根(O-4 路径注意)

---

*报告: documents/reviews/llm-radar-cli-governance-ops-verify-v1.0-20260823.md | 闭环: CL-SEC11 | 核查: ops*
