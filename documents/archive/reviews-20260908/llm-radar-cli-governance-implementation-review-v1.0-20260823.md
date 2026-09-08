---
title: llm-radar CLI 治理与全局注册 — 实现审计报告 v1.0
topic: llm-radar
type: review
version: 1.0
date: 2026-08-23
author: hermes-1.2.0
tags: [llm-radar, cli, governance, cli-registry, checkpoint, audit]
profile: review
provider: deepseek
model: deepseek-v4-flash
---

# llm-radar CLI 治理与全局注册 — 实现审计 review报告 v1.0

> 日期: 2026-08-23
> 文件: documents/solutions/llm-radar-cli-governance-design-v1.1-20260823.md (PASS 95/A, 8d089bd)
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.jaden.tech
> 实施 commit: 26219ba feat@cli: llm-radar/lr 全局注册 + 分组 help + lr status checkpoint (CL-SEC11)
> ops 核查: documents/reviews/llm-radar-cli-governance-ops-verify-v1.0-20260823.md (PASS, 8/8 实测)
> 待 push commit: 5830b5b, 26219ba (实测 ahead=2; prompt 所列 6 个中 8d089bd/7bd8f26/a714a7c/552307e 已在 origin/main)
> review维度: 实现与设计一致性 / 测试质量 / 治理合规 / 安全性

## 数据验证

全部条目以实际执行/读取为准, 不采信 dev 或 ops 自报。

| # | 验证项 | 方法 | 结果 |
|:--|:-------|:-----|:-----|
| 1 | 分组 help | `python3 llm-radar-collector.py help` | ✅ exit=0, 6 个【】组(功能概述/采集执行/数据管理/Git 集成/定时任务/其他), 📖 标题, 无危险指令/⚠️ |
| 2 | 空入参 exit=0 | 无参运行 | ✅ exit=0 + 分组 help (原 exit=1 已改) |
| 3 | positional help 拦截 | `run help` / `fetch help` / `commit help` / `crontab help` 逐条实测 | ✅ 全部打印"用法" exit=0; `run help` 实测 0.24s 秒回, 无采集副作用 |
| 4 | status --json 七字段 | json.loads 校验 stdout | ✅ 七字段齐全 {id,label,status,icon,message,checks,actions}; 实测 status=warning (质量门禁失败), icon=🟡 匹配, message 无 emoji |
| 5 | status 四态 + checks/actions | 解析输出 | ✅ checks 4 项(数据日期/实体数/质量门禁/Git 同步), actions 3 项(run/push/repair, cmd 静态字符串) |
| 6 | status 文本输出 | 无 --json 运行 | ✅ 单行摘要 `LLM Radar: ... | 质量 failed | 2 ahead / 0 behind`, 无 emoji |
| 7 | stdout 纯净性 | subprocess 分离 stdout/stderr | ✅ stdout 纯 JSON; stderr 仅 import 期 urllib3 NotOpenSSLWarning (既有环境噪音, 非本次引入) |
| 8 | env 可配阈值 | LLM_RADAR_CRITICAL_HOURS=0/1 注入 | ✅ 0 → critical (数据过期), 1 → warning; STALE_HOURS/CRITICAL_HOURS 独立常量 (collector.py:48-51) |
| 9 | 全局注册 | ls ~/.local/bin + 双命令 diff | ✅ llm-radar + lr symlink 存在; `llm-radar help` vs `lr help` diff 为空, `status --json` 输出一致 |
| 10 | wrapper 内容 | 读 cache/system-command/*-wrapper.sh + cache/cli-registry/wrapper.sh.tmpl | ✅ L81-83 exec 前 set -a source .env (RIG-2); script-miner 仅注释提及, 无 calls.log 统计段 (RIG-3); TARGET_SCRIPT 绝对路径, exec list-form 无 shell 注入面 |
| 11 | .cli-registry.yaml | 读文件 + git ls-files | ✅ 入 git; bin_dir ~/.local/bin, cache_dir cache/system-command, env.conda py3.12, commands llm-radar + alias_list [lr] |
| 12 | 全量测试 | `python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_selenium.py -q` | ✅ 120 passed, 2 deselected, 3 warnings in 4.19s (与 ops 复跑一致) |
| 13 | 测试污染还原 | git status 前后对比 | ✅ test_timestamp 写脏 snapshot/overview/timestamp 已 git checkout 还原, 仅剩会话前已存在的 .hermes-project.yaml 修改 (不动) |
| 14 | 敏感信息 | pending commits diff 扫描 sk-/ghp_/AKIA/PRIVATE KEY | ✅ 0 hits |
| 15 | commit 格式 | git log 最近 8 条 type@scope 扫描 | ✅ 全部合规 (feat@cli / docs@verify / audit@review / docs@design / docs@handoff) |
| 16 | metrics 字段语义 | 读 data/metrics.json 顶层键 | ✅ `consecutive_fails` 是全局 run 级顶层字段 (值 0), 非 source_health 子键 — 与设计 §4.3 锁定语义一致 |

## 实现与设计一致性评估

| # | 设计项 (v1.1) | 实现 | 核验 |
|:--|:--------------|:-----|:----:|
| C1 | hm-style 分组 help (4 组 + 功能概述) | collector.py:2135-2178 `print_grouped_help()` | ✅ |
| C2 | 空入参 → 分组 help exit=0 | main() L2207-2210 | ✅ |
| C3 | positional help 拦截 args[0].upper()=='HELP', exit=0 无副作用 | main() L2213-2216 + `print_command_usage()` | ✅ |
| C4 | status --json 七字段 checkpoint 协议 | status() L1777-1923 | ✅ |
| C5 | 四态评估 ok/warning/critical/info | status() L1836-1850 (critical > warning > ok; info 仅用于 checks 附属项) | ✅ |
| C6 | 数据源全只读 (timestamp 项目根 / metrics 全局 fails / rev-list 不 fetch / snapshot) | L1814-1823 + `_git_divergence()` L1789-1800 | ✅ |
| C7 | STALE_HOURS=7 / CRITICAL_HOURS=48 独立常量 env 可配 | L48-51 | ✅ |
| C8 | .cli-registry.yaml 入 git (bin_dir/conda py3.12/alias [lr]) | 根目录, git ls-files 确认 | ✅ |
| C9 | wrapper fork 模板: 去 calls.log (RIG-3) + exec 前 .env (RIG-2) | cache/cli-registry/wrapper.sh.tmpl + 生成物 | ✅ |
| C10 | 文本输出单行无 emoji | status() 非 json 分支 L1921 | ✅ |
| C11 | run --force 绕过 6h 节流 | main() L2260-2262 force='--force' in args → run(source_keys, force) | ✅ |

### 严格性细节核验

- 边界语义: `age_hours > STALE_HOURS` / `> CRITICAL_HOURS` 均为严格大于 — 与测试 `test_boundary_just_below_stale_ok` / `test_boundary_just_below_critical_warning` 锁定语义一致 (设计 D2 表 "7-48h=warning" 在恰为 7h 时实现判 ok, 属边界点歧义, 见 🟢 O-5)。
- `not snapshot` 覆盖"缺失"与"空 dict"两种情况 (空 snapshot 视为 critical) — 比设计更防御, 合理。
- `_git_divergence` 非 git 仓库/rev-list 失败 → (None, None, 'info'), 不升级整体状态 — 超出设计的防御性增强, 合理。
- quality 字段缺失 → 'info' 不升级 (设计未定义, 实现选择宽容处理) — 合理。

## 测试质量评估

| # | 项 | 证据 | 核验 |
|:--|:---|:-----|:----:|
| T1 | 四态覆盖 | tests/test_status.py TestStatusOk/TestStatusStates — ok/warning(偏旧)/warning(质量)/warning(git 分叉)/critical(过期/缺 snapshot/缺 timestamp/连续失败) | ✅ |
| T2 | 边界 | TestStatusBoundary — STALE-0.1h ok / CRITICAL-0.1h warning / 不可解析时间戳 critical | ✅ |
| T3 | fixture 隔离 (RIG-4) | status_env: patch project_root → tmp_path + 预置 3 文件 (L19-42); `_run_status` monkeypatch `_git_run` → 128; git 分叉测试在 tmp_path 内 init 真实仓库 (L179-198) | ✅ 不触真实项目根 |
| T4 | 全只读断言 | test_git_no_fetch — 断言 _git_run 无 fetch/pull 调用 | ✅ |
| T5 | 输出纯净 | test_json_pure_stdout / test_text_single_line_no_emoji (capsys 校验 stdout) | ✅ |
| T6 | CLI 层 | test_cli.py — 空入参/help 分组/run/fetch/commit/crontab help 拦截/status json+text | ✅ |
| T7 | 全量复跑 | 120 passed (独立执行) | ✅ |

### 测试局限 (🟢 观察, 不扣分)

- test_cli.py 的 status 测试 (`test_cli_status_json`) 跑真实 collector + 真实项目根 — status 全只读, 无污染风险, 可接受。
- T3 的 git 分叉测试用真实 `git init` + `update-ref` 构造分叉 — 依赖 git 二进制, CI 环境有 git, 无 flaky 风险。

## 治理合规评估

| # | 项 | 证据 | 核验 |
|:--|:---|:-----|:----:|
| G1 | commit 格式 type@scope | 26219ba feat@cli / 5830b5b docs@verify / 8d089bd audit@review / 7bd8f26+a714a7c docs@design / 552307e docs@handoff | ✅ |
| G2 | subject 含 CL-SEC11 | 26219ba + 5830b5b subject 均含 (CL-SEC11) | ✅ |
| G3 | .cli-registry.yaml 入 git | git ls-files 确认, 未被 .gitignore 吞掉 | ✅ |
| G4 | AGENTS.md CLI 指令表更新 | 26219ba 新增 CLI 治理段 (git show 确认) | ✅ |
| G5 | wrapper 生成物在 gitignored cache/ | .gitignore L20 `cache/`; wrapper 不入库 (设计预期) | ✅ |
| G6 | 设计 v1.1 frontmatter 与文件名一致 | version: 1.1 + -v1.1- 文件名 | ✅ |

## 安全事项

🟡 LR-SEC-011 — `run --force help` / `fetch --force help` 绕过 positional help 拦截 (help 非首位参数时)

- 描述: 拦截条件为 `args[0].upper()=='HELP'` (main() L2213-2216), 与设计 §3.2 字面一致; 但当 help token 出现在非首位 (如 `lr run --force help`) 时不拦截, `--force` 还被当作节流绕过标志, 触发 run 流水线。实测 (2026-08-23): `python3 llm-radar-collector.py run --force help` 输出 "抓取完成，0/1 个源成功 / 指标已记录到 metrics.json" — 真实副作用: git fetch (_sync_remote) + metrics.json 写入 + 一次以 'help' 为源的失败采集 (因 'help' 非合法源而快速失败, 无真实数据抓取、无 push)。影响有界, 但违背设计 §3.2 "禁止当参数执行 (对齐 pc magnet 事故教训)" 的意图。
- 修复建议: fetch/run 分支将 HELP 检测扩展为扫描全部 args (`any(a.upper()=='HELP' for a in args)` — 'help' 永远不是合法源名, 无歧义), 或至少对 `--force help` 组合显式拦截; commit/crontab 保持 args[0] 语义 (message/子命令为自由文本, 全扫描会误伤)。
- 级别: 🟡 (-5)。非 🔴: 无注入/提权/数据破坏, 副作用有界且快速失败。

🟢 LR-SEC-012 — status 数据源全只读 (设计 §4.3 全项落地)

- `_read_json_quiet` 只读文件; `_git_divergence` 仅 rev-list --count (本地 ref, 无 fetch/pull — 有测试断言); 无任何写盘/网络调用。实测 `status` 后 git status 无新增脏文件。✅

🟢 LR-SEC-013 — actions[].cmd 静态字符串, 无注入面

- 三个 cmd 均硬编码 ("lr run --force" / "lr auto-push"), 不拼接任何输入; status 输出仅 print, 不被本脚本执行。消费方 (下游 daily-checkin) 若执行 cmd 属其自身职责, 本实现无 shell 拼接。✅

🟢 LR-SEC-014 — 全局注册 user-level symlink, 无提权面

- ~/.local/bin/llm-radar + lr → cache/system-command/*-wrapper.sh (user-writable, 无 sudo/setuid); wrapper exec list-form (`exec $interpreter "$TARGET_SCRIPT" "$@"`), 无 eval/字符串拼接, TARGET_SCRIPT 为绝对路径常量。✅

## 评分

| 项 | 级别 | 扣分 |
|:---|:-----|:-----|
| Base | — | 100 |
| LR-SEC-011 (help 拦截仅 args[0], 非首位绕过) | 🟡 | -5 |
| LR-SEC-012/013/014 (确认项) | 🟢 | 0 |
| 🟢 O-1 ~ O-5 (观察) | 🟢 | 0 |

得分: **95 / 100 → Rating A**

## 结论

**PASS (A, ≥85)** — 实现与设计 v1.1 高度一致 (C1~C11 全 ✅), 测试质量扎实 (120 passed, fixture 隔离满足 RIG-4), 治理合规全项通过, 安全面无注入/提权/副作用失控。唯一 🟡 LR-SEC-011 为防御性加固建议 (非阻断), 可后置处理。**可 push** — 由 review 角色执行 push (5830b5b + 26219ba + 本次审计交付物)。

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | LR-SEC-011: fetch/run help 拦截扩展为全 args 扫描 (防 `run --force help` 触发流水线副作用) | 安全 🟡 |
| □ | 🟢 O-5: 设计 §4.2 表 "7-48h=warning" 与实现严格 `>` 的边界点 (恰 7h 判 ok) 二选一标注 | 严格性 🟢 |

### 观察项 (🟢, 不扣分)

- O-1: 全量 pytest 写脏 timestamp/overview/snapshot 为 test_timestamp 已知问题 (AGENTS.md 记载, 08-15 同源), 已还原, 非本次引入。
- O-2: HEAD snapshot 含 1 处 isolation-test 历史遗留 (snapshot.json:1894, 8/16 误提交), 非本次引入。
- O-3: prompt 声称 6 个待 push commit, 实测仅 2 个 ahead (5830b5b, 26219ba); 其余 4 个已在 origin/main — 以 git 为准。
- O-4: stderr urllib3 NotOpenSSLWarning 为 import 期既有环境噪音 (py3.9 + LibreSSL), 不污染 stdout, 不影响 checkpoint 消费。
- O-5: 边界点歧义 (恰 7h): 设计表 "7-48h=warning" 含 7h, 实现 `> STALE_HOURS` 判 ok; 测试锁定的语义是"严格 > 才 warning", 建议设计 doc 补一行标注即可。

---

*报告: documents/reviews/llm-radar-cli-governance-implementation-review-v1.0-20260823.md | 闭环: CL-SEC11 | 审计: review*
