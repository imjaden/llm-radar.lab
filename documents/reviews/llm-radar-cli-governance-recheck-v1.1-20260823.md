# LLM Radar — 收敛审计尾项复核 (LR-SEC-015/016/017) — review报告 v1.1

- **日期**: 2026-08-23
- **reviewer**: Security Reviewer (IRIS)
- **项目**: llm-radar.jaden.tech (L2)
- **范围**: 收敛复核 (be7464d, PASS 90/A) 遗留尾项修复复核 — LR-SEC-015/016/017
- **Commit(s)**: 6b69de8 (fix@cli, LR-SEC-015), b55c8fb (docs@llm-radar, LR-SEC-016)
- **状态**: ✅ PASS — 100/100 (A)
- **报告系列**: v1.0 收敛复核 → v1.1 尾项复核

## 数据验证

| # | 验证项 | 方法 | 结果 |
|:--:|:-------|:-----|:-----:|
| 1 | LR-SEC-015 修复 diff | `git show 6b69de8` | ✅ 2 文件 3 处: mcp_submit_update.py:13 + mcp-protocol-demo.py:44 均补 `'scripts'` 段, demo L18 依赖注释同步 |
| 2 | 路径实际解析 | Python 复算 `_PROJECT_ROOT / 'scripts' / 'llm-radar-mcp-server.py'` | ✅ 两者均解析为 `/Users/jadenli/CodeSpace/llm-radar.jaden.tech/scripts/llm-radar-mcp-server.py`, 文件存在 (30KB) |
| 3 | Popen 消费者 | 读 mcp-protocol-demo.py:191-192 | ✅ `proc = subprocess.Popen([sys.executable, str(MCP_SERVER)], ...)` 使用解析后变量, 非裸文件名 |
| 4 | py_compile | `python3 -m py_compile` 3 脚本 | ✅ OK |
| 5 | 残留断链扫描 | grep `llm-radar-mcp-server` scripts/ tests/ | ✅ 全部引用含 `scripts/` 段, 0 残留根路径引用 (docstring 流程图为描述性文字, 实际 Popen 用变量) |
| 6 | LR-SEC-016 修复 diff | `git show b55c8fb` | ✅ 2 文件 5 处: README.md:139 config 示例 + integ 文档 L230/L239/L266/L304 |
| 7 | 文档残留扫描 | grep README/AGENTS/documents/ 中裸 `llm-radar-mcp-server.py` | ✅ 残留仅 archive/ (历史修复计划, 不改写) + reviews/ (审计记录本身) + 文件名提及 (非路径消费者) |
| 8 | LR-SEC-017 SHA 映射 | `git log` 对照提交信息 | ✅ 90b5aa5→2f827ac, 59c8b92→9897d6c, 26219ba→f371d49 (信息逐条匹配) |
| 9 | 测试 | `pytest tests/test_security.py tests/test_gitflow.py` | ✅ 19 passed (test_security 直接覆盖 mcp_server 路径 3 处) |
| 10 | 待 push 实况 | `git log origin/main..HEAD` | ✅ 恰好 b55c8fb + 6b69de8 两个 |

## 尾项评估

### LR-SEC-015 — mcp-server 重构消费者断链 🟡 → ✅ Resolved

修复 commit 6b69de8:

| 文件 | 修复前 | 修复后 | 验证 |
|:-----|:-------|:-------|:-----:|
| scripts/mcp_submit_update.py:13 | `_PROJECT_ROOT / 'llm-radar-mcp-server.py'` | `_PROJECT_ROOT / 'scripts' / 'llm-radar-mcp-server.py'` | ✅ 解析存在 |
| scripts/mcp-protocol-demo.py:44 | `PROJECT_ROOT / 'llm-radar-mcp-server.py'` | `PROJECT_ROOT / 'scripts' / 'llm-radar-mcp-server.py'` | ✅ 解析存在 |
| scripts/mcp-protocol-demo.py:18 | 注释"在项目根目录" | 注释同步 `scripts/llm-radar-mcp-server.py` | ✅ |

- scripts/ + tests/ 全量 grep 无残留根路径引用 (唯一裸文件名是 demo:23 流程图文案, 实际 Popen 用 MCP_SERVER 变量)。
- 修复后运行路径: `python3 scripts/mcp-protocol-demo.py` / `python3 scripts/mcp_submit_update.py` 均可找到 server。

### LR-SEC-016 — 文档路径未同步 🟡 → ✅ Resolved

修复 commit b55c8fb (2 文件 5 处):

| 位置 | 修复内容 |
|:-----|:---------|
| README.md:139 | config 示例 `args: ["/path/to/llm-radar-mcp-server.py"]` → `scripts/llm-radar-mcp-server.py` |
| integ L230 | 绝对路径补 `scripts/` |
| integ L239 | `args` 说明补 `scripts/` |
| integ L266 | 已完成列表补 `scripts/` |
| integ L304 | 文件表补 `scripts/` |

- 残留裸引用检查: 仅 documents/archive/security-fix-plan-20260711.md (历史修复计划, 属审计档案不改写)、documents/reviews/*.md (审计记录本身)、requirements-spec.md:38 (文件名提及, 非路径)、design v1.1 L191 (边界声明"不修改", 非路径) — 均非消费者, 不构成断链。

### LR-SEC-017 — 审计记录 SHA 映射注记 🟢 → 注记/Closed

审计记录 (review-log.md / .review-level.yaml) 引用了 rebase 前的 SHA。本次复核确认映射:

| 旧 SHA (rebase 前) | 新 SHA (当前) | 提交内容 |
|:-------------------|:--------------|:---------|
| 90b5aa5 | 2f827ac | fix@cli: help 全 args 扫描拦截 (LR-SEC-011) |
| 59c8b92 | 9897d6c | docs@design: v1.1 O-5 边界标注 |
| 26219ba | f371d49 | feat@cli: llm-radar/lr 全局注册 |

提交信息逐条匹配, 映射无歧义。按协议以注记方式记录, 不改写历史审计条目 (append-only 原则)。🟢 不计分, Closed。

## 安全事项

- 本次改动仅路径常量 + 文档字符串, 无新增攻击面。
- 无新增 API key / 凭据; LLM_RADAR_MCP_KEY 仍走 env (L2 既有约定)。
- 无 🔴 发现, 无需人工通知。

## 评分

| 项 | 值 |
|:---|:---|
| Base | 100 |
| 🔴 HIGH (-15) | 0 |
| 🟡 MEDIUM (-5) | 0 |
| 🟢 LOW (0) | 1 (LR-SEC-017 注记, 不计分) |
| **Score** | **100 / 100 (A)** |

## 结论

**PASS** — LR-SEC-015 Resolved, LR-SEC-016 Resolved, LR-SEC-017 注记/Closed。收敛审计 (be7464d) 全部 3 项尾项闭合, `findings_open: 0`。执行 push (待 push = 6b69de8 + b55c8fb) + audit 记录 commit。

### 待确认清单

□ 无 — 全部确认项已核实, 无遗留。
