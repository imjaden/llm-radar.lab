# llm-radar 收敛复核 + CL-SEC11 链批量审计 — review报告 v1.0

> 日期: 2026-08-23
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.jaden.tech
> 审计对象: 13 个已 push commit (9d88886 → 21b50c5, 双机分叉 rebase 收敛后)
> review维度: 收敛正确性 / CL-SEC11 链完整性 / 代码质量 / 重构正确性 / 治理合规
> 审核人: Security Reviewer (IRIS)

## 数据验证

| 验证项 | 方法 | 结果 |
|:-------|:-----|:-----|
| HEAD = origin/main, 0/0 分叉 | `git rev-parse HEAD` + `git rev-list --left-right --count origin/main...HEAD` | ✅ 21b50c5 = origin/main, 0 0 |
| 13 commits 全为代码/文档/审计, 无数据 commit 混入 | `git log fec3c58..21b50c5` 逐条 | ✅ 13 条, 类型分布 docs@8 / audit@3 / refactor@1 / fix@1 / feat@1; fec3c58 (auto-push data 21:02) 是 chain 的 parent, 即远端数据基线在链底 |
| 本地旧数据 auto-push 被 skip | reflog `rebase (pick)` 13 次, 链外无 auto-push | ✅ rebase 仅重放 13 个功能/文档/审计 commit, 旧数据 commit 未进入新链 |
| HEAD snapshot 保持远端最新数据 (21:02) | `data/snapshot.json` generated_at + `timestamp.json` | ✅ generated_at 2026-08-23T21:02:19, last_run_status success, entity_count 324, server=linux (远端) |
| 无 isolation-test 残留 | `grep -c isolation-test data/snapshot.json` | ✅ 0 hits |
| CL-SEC11 8 步链 commit 齐全 | git log 逐条对照 | ✅ 9d09745(设计v1.0)→3d38e18(修复v1.1)→b8ebbf2(复审)→f371d49(dev)→53608b4(核查)→3926f65(审计)→2f827ac+9897d6c(尾项)→77840ff(尾项复核) |
| 审计 trail 文件存在且条目对应 | review-log.md L253/283/319/348 + .review-level.yaml tail | ✅ 4 条 CL-SEC11 记录: v1.0 CONDITIONAL 70 → v1.1 PASS 95 → impl audit PASS 95 → recheck PASS 100 |
| CLI 测试通过 | `pytest tests/test_cli.py tests/test_status.py -q` | ✅ 32 passed (含 help 拦截、七字段协议、边界、只读性) |
| 全量回归 | `pytest tests/ -m "not selenium" --ignore=tests/test_selenium.py -q` | ✅ 122 passed, 2 deselected |
| mcp-server 消费者路径扫描 | `grep -rn llm-radar-mcp-server` (排除 .git/data) | ⚠️ scripts/mcp_submit_update.py:13 + scripts/mcp-protocol-demo.py:44 仍指向项目根 (见 LR-SEC-015) |
| rebase 前 SHA 引用有效性 | `git merge-base --is-ancestor 90b5aa5 59c8b92 26219ba HEAD` | ⚠️ 3 个均为 rebase 前 dangling, 不在 main 历史 (见 LR-SEC-017) |
| 测试数据污染还原 | `git checkout -- data/snapshot.json overview.json timestamp.json` | ✅ 还原, 工作区仅剩并发会话 .hermes-project.yaml |

## 一、收敛正确性评估 (✅ PASS)

- ✅ 13 commits 全部为功能/文档/审计类, 无本地旧数据 auto-push 混入。数据 commit (fec3c58/ea1bf9d) 位于链底, 是远端基线, 非本次 13 个。
- ✅ HEAD snapshot = 远端最新 21:02 数据 (generated_at 21:02:19, server=linux), 无 isolation-test 残留, 与"远端数据最新、本地旧数据无价值"的收敛前提一致。
- ✅ 148774b (isolation 清理) 被 skip 符合设计: 远端数据无该实体, 价值被取代, 非丢失。

## 二、CL-SEC11 链完整性评估 (✅ PASS)

| 步 | commit | 内容 | 验证 |
|:--:|:-------|:-----|:----:|
| 1 设计 | 9d09745 | CLI governance design v1.0 | ✅ review-log L253 对应 |
| 2 评审 | (b8ebbf2 携带 v1.0 review report) | .review-level v1.0 CONDITIONAL 70, 6 findings | ✅ |
| 3 修复 | 3d38e18 | v1.1 resolve 6 yellow + 3 green | ✅ |
| 4 复审 | b8ebbf2 | re-review PASS 95/A, 9/9 fixes verified | ✅ review-log L283 |
| 5 dev | f371d49 | feat@cli 全局注册 + 分组 help + lr status | ✅ review-log L319 对应 |
| 6 核查 | 53608b4 | ops verification 8/8 | ✅ |
| 7 审计 | 3926f65 | impl audit PASS 95/A, LR-SEC-011 non-blocking | ✅ review-log L319 |
| 8 尾项 | 2f827ac + 9897d6c | fix@cli 全 args help 扫描 + O-5 边界注释 | ✅ LR-SEC-011 Closed |
| 9 尾项复核 | 77840ff | recheck PASS 100/A, LR-SEC-011/O-5 Resolved | ✅ review-log L348 |

8 步链 (设计→评审→修复→复审→dev→核查→审计→尾项) 完整, 尾项复核闭环。review-log + .review-level.yaml 双轨记录齐全。

## 三、代码质量评估 (✅ PASS, 2 处 🟢 观察)

- ✅ f371d49: `main()` 空入参 → grouped help exit=0; `help` 命令不实例化 collector (避免构造期 API key 日志噪音); `status` 走 `_silent_collector()` 抑制构造期日志, `--json` 纯 JSON stdout。
- ✅ status checkpoint 七字段协议: id/label/status/icon/message/checks/actions, 全只读 (timestamp.json + metrics.json + git rev-list 本地 ref + snapshot.json, 无 fetch 无采集副作用)。
- ✅ 四态评估 ok/warning/critical/info 优先级正确 (critical > warning > ok); 阈值 STALE_HOURS=7 / CRITICAL_HOURS=48, env 可配; `age_hours > STALE_HOURS` 严格大于, 恰 7h 判 ok (O-5 边界已文档化)。
- ✅ 2f827ac: help 拦截从 `args[0]` 扩展为 `any(a.upper()=='HELP' for a in args)`, 修复 LR-SEC-011 `run --force help` 绕过; 覆盖 fetch/run/commit/crontab 四个带参子命令。
- ✅ test_status.py 20+ 用例覆盖: 七字段、ok/warning/critical 各态、快照缺失、timestamp 缺失、连续失败、Git 分叉、无 fetch、边界 (恰 7h ok / 恰 48h warning)、不可解析 timestamp、--json 纯净、--force 绕过节流。
- 🟢 OBS-1: `commit help` 会被拦截 (自由文本消息 "help" 无法作为 commit message) — 设计意图明确 (help 禁止当参数执行), 可接受, 不修。
- 🟢 OBS-2: `mcp-protocol-design` L17 ASCII 图右边界因插入 `scripts/` 长度不齐 (21b50c5) — 纯格式, 不修。

## 四、重构正确性评估 (🟡 2 项待修)

- ✅ 38bde8f: `llm-radar-mcp-server.py` → `scripts/`, PROJECT_ROOT 推导 `parent` → `parent.parent` 正确 (scripts/ 上移一级到项目根)。
- ✅ tests/test_security.py 3 处 import 路径同步更新。
- 🟡 LR-SEC-015 — mcp-server 移动后辅助脚本消费者断链
  `scripts/mcp_submit_update.py:13` `SERVER = str(_PROJECT_ROOT / 'llm-radar-mcp-server.py')` (PROJECT_ROOT = scripts/ 的 parent.parent = 项目根) 与 `scripts/mcp-protocol-demo.py:44` `MCP_SERVER = PROJECT_ROOT / 'llm-radar-mcp-server.py'` (含 L18 注释"在项目根目录") 仍指向移动前的项目根路径, 运行 subprocess.Popen 将 FileNotFoundError。修复: 两者补 `'scripts'` 段: `_PROJECT_ROOT / 'scripts' / 'llm-radar-mcp-server.py'`, 同步 L18 注释。
- 🟡 LR-SEC-016 — 文档路径未同步
  README.md:139 config 示例仍为 `args: ["/path/to/llm-radar-mcp-server.py"]` (21b50c5 只改了结构树 L79, 未改 config 示例); `documents/integ/hermes-integration-v1.0-20260624.md:230` 仍为绝对路径根目录引用。修复: README config 示例补 `scripts/`; integ 文档补 `scripts/` (绝对路径引用本身建议改为相对占位)。

## 五、治理合规评估 (✅ PASS)

- ✅ 13 个 subject 全部符合 `type@scope: subject`; type 集合 (docs/refactor/audit/fix/feat) 均在项目约定内; 12/13 英文, 1 个中文 (9d88886, 2026-08-16 历史遗留, 已知边界不误报)。
- ✅ commit body 有实质内容 (CL-SEC11 标注、LR-SEC-011 关联)。
- 🟢 LR-SEC-017 — 审计记录 SHA 引用为 rebase 前
  review-log L338/L351 + .review-level.yaml 引用 90b5aa5/59c8b92/26219ba, 均为 rebase 前 SHA (当前历史对应 2f827ac/9897d6c/f371d49)。对象仍在对象库但不在分支历史, rebase 收敛的正常副作用; 建议在尾项复核报告补注映射, 不阻塞。

## 安全事项

无 🔴。本批 commit 无凭证暴露、无注入、无越权; status 全只读设计符合最小权限原则。

## 评分

| 级别 | 数量 | 扣分 |
|:----:|:----:|:----:|
| 🔴 HIGH | 0 | 0 |
| 🟡 MEDIUM | 2 (LR-SEC-015, 016) | -10 |
| 🟢 LOW | 1 (LR-SEC-017) | 0 |

得分: 90 / 100 → Rating: A

## 结论

**PASS (90/A)** — 13 个 commit 收敛正确 (远端数据完整保留, 无本地旧数据混入, 无 isolation-test 残留), CL-SEC11 8 步链完整闭环, CLI 实现质量高且测试充分 (122 passed), 重构主体正确但遗漏 2 处消费者路径 (LR-SEC-015/016)。

**需处理**: LR-SEC-015 (辅助脚本断链, 功能影响) + LR-SEC-016 (文档路径未同步) 建议尽快修复; 均为非阻塞项, 不影响本批 commit 的收敛结论。

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | LR-SEC-015: 修 scripts/mcp_submit_update.py:13 + scripts/mcp-protocol-demo.py:44 路径 (补 'scripts' 段) | 重构 🟡 |
| □ | LR-SEC-016: README.md:139 config 示例 + integ 文档 L230 补 scripts/ | 文档 🟡 |
| □ | LR-SEC-017: 尾项复核报告补 rebase SHA 映射注记 (可选) | 文档 🟢 |
