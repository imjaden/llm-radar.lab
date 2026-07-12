# LLM-Radar Security Audit Log

## 2026-07-11 — Re-review (post-fix)

- **Reviewer**: Security Reviewer (IRIS)
- **Level**: L2
- **Scope**: Re-review after security fixes (commit cfa3e0f)
- **Commit(s)**: HEAD (9ed7c3c)
- **Verdict**: PASS
- **Score**: 100 / 100 (Rating: A)
- **Findings total**: 8 (🔴:0 / 🟡:0 / 🟢:2)

### Summary

复查确认 5 项修复全部到位。LR-SEC-001 🔴 已通过自动生成随机 key 解决；LR-SEC-003/004/005 🟡 已修复；LR-SEC-002 🟡 因 Tailwind CDN 不支持 SRI 已接受风险。新发现一项 🟢：docstring 中残留旧 key 引用（已修复）。score 从 65 升至 100。

### Findings

| # | Severity | Title | File:Line | Status |
|:-:|:--------:|:------|:---------:|:------:|
| 1 | 🔴 | 硬编码默认 MCP API Key | `llm-radar-mcp-server.py:33` 等 | ✅ Fixed |
| 2 | 🟡 | Tailwind CDN 缺少 SRI | `index.html:8`, `changelog.html:8` | Accepted Risk |
| 3 | 🟡 | 外部链接缺失 rel="noopener" | `index.html:149,152` | ✅ Fixed |
| 4 | 🟡 | 缺少 Content-Security-Policy | `index.html`, `changelog.html` | ✅ Fixed |
| 5 | 🟡 | 脚本硬编码本地绝对路径 | `scripts/audit_snapshot.py`, `scripts/mcp_submit_update.py` | ✅ Fixed |
| 6 | 🟢 | Git 历史含 /Users/jadenli/ 路径 | commit afde7c6 | Open (low) |
| 7 | 🟢 | data/collector.log 已从 git 删除 | commit b7b1dae | Closed |
| 8 | 🟢 | docstring 残留旧 key 引用 | `llm-radar-mcp-server.py:19` | ✅ Fixed |

### Positives

- `tests/test_security.py` 新增 3 个安全测试类验证 key 生成逻辑
- MCP key 自动生成使用 `secrets.token_hex(32)`，符合密码学安全标准
- `mcp_submit_update.py` 改为命令行参数读取数据，不再内嵌数据 payload
- 新增 `_skip_push` 测试夹具，防止测试触发副作用

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------:|:--------:|:------:|
| LR-SEC-001 | 硬编码默认 MCP API Key | HIGH | P0 | ✅ Closed |
| LR-SEC-002 | Tailwind CDN 缺少 SRI | MEDIUM | P1 | Accepted Risk |
| LR-SEC-003 | 外部链接缺失 rel="noopener" | MEDIUM | P1 | ✅ Closed |
| LR-SEC-004 | 缺少 Content-Security-Policy | MEDIUM | P2 | ✅ Closed |
| LR-SEC-005 | 脚本硬编码本地路径 | MEDIUM | P2 | ✅ Closed |
| LR-SEC-006 | Git 历史 /Users/jadenli/ 路径 | LOW | P2 | Open |
| LR-SEC-007 | collector.log 已从 git 删除 | LOW | — | Closed |
| LR-SEC-008 | docstring 残留旧 key 引用 | LOW | — | ✅ Closed |

---

## 2026-07-11 — Initial Security Audit

- **Reviewer**: Security Reviewer (IRIS)
- **Level**: L2
- **Scope**: Full codebase — Python collector, MCP server, scripts, static HTML frontend, git history
- **Commit(s)**: HEAD (afde7c6)
- **Verdict**: FAIL
- **Score**: 65 / 100 (Rating: C)
- **Findings total**: 7 (🔴:1 / 🟡:4 / 🟢:2)

### Summary

首次安全审查覆盖了全部源码、Git 历史、静态前端和依赖项。发现 1 个高危问题：MCP Server 的默认 API Key 硬编码在 3 个文件中，HTTP 模式下绑定 0.0.0.0 存在外部访问风险。中危问题包括 CDN 脚本缺少 SRI 完整性校验、3 处外部链接缺失 rel="noopener"、无 CSP 头、脚本中硬编码本地路径。低危为 Git 历史中的开发路径泄露和已删除的日志文件。subprocess 调用全部使用 list form，无 shell 注入风险。无 eval/exec 使用。`.env` 已正确加入 `.gitignore`。

### Findings

| # | Severity | Title | File:Line | Status |
|:-:|:--------:|:------|:---------:|:------:|
| 1 | 🔴 | 硬编码默认 MCP API Key | `llm-radar-mcp-server.py:33`, `scripts/mcp-protocol-demo.py:44`, `scripts/mcp_submit_update.py:12` | Open |
| 2 | 🟡 | Tailwind CDN 缺少 SRI 完整性校验 | `index.html:8`, `changelog.html:8` | Open |
| 3 | 🟡 | 外部链接缺失 rel="noopener" | `index.html:149,152,441` | Open |
| 4 | 🟡 | 缺少 Content-Security-Policy | `index.html` | Open |
| 5 | 🟡 | 脚本中硬编码本地绝对路径 | `scripts/audit_snapshot.py:7`, `scripts/mcp_submit_update.py:11,13` | Open |
| 6 | 🟢 | Git 历史中含 /Users/jadenli/ 路径 | commit afde7c6 (audit_snapshot.py) | Open |
| 7 | 🟢 | data/collector.log 已从 git 删除 | commit b7b1dae | Closed |

### Positives

- 所有 subprocess 调用使用 list form，无 shell=True 注入风险
- 无 eval/exec/compile 使用
- .env 正确加入 .gitignore，未追踪到 git
- API Key 正确从环境变量或 .env 加载
- target="_blank" 链接大部分已加 rel="noopener"（7/10）
- 无 PEM/CRT/KEY/PDF/resume 等敏感文件历史
- 测试文件使用模拟 key（test-key），无真实凭证

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------:|:--------:|:------:|
| LR-SEC-001 | 硬编码默认 MCP API Key | HIGH | P0 | Closed |
| LR-SEC-002 | Tailwind CDN 缺少 SRI | MEDIUM | P1 | Accepted Risk |
| LR-SEC-003 | 外部链接缺失 rel="noopener" | MEDIUM | P1 | Closed |
| LR-SEC-004 | 缺少 Content-Security-Policy | MEDIUM | P2 | Closed |
| LR-SEC-005 | 脚本中硬编码本地路径 | MEDIUM | P2 | REGRESSION |
| LR-SEC-006 | Git 历史 /Users/jadenli/ 路径 | LOW | P2 | Open |
| LR-SEC-007 | collector.log 已从 git 删除 | LOW | — | Closed |

---

## 2026-07-13 — Commit-range review (283eb6c → f0cde02, 5 commits)

- **Reviewer**: Security Reviewer (IRIS)
- **Level**: L2
- **Scope**: 5 local commits — _skip_push guard, test isolation, date filtering, security fixes, docs reorganization
- **Commit(s)**: 283eb6c, a8c58a1, c44df1c, cfa3e0f, f0cde02
- **Verdict**: CONDITIONAL PASS
- **Score**: 75 / 100 (Rating: B)
- **Findings total**: 3 (🔴:1 / 🟡:2 / 🟢:0)

### Summary

共审查 5 个 commits。4 个代码提交 (283eb6c~c44df1c) 质量良好：_skip_push 测试保护、merge 测试隔离、日期过滤逻辑完整有边界测试，无安全问题。安全修复 commit (cfa3e0f) 正确解决了 LR-SEC-001/003/004/005。但最后一个 docs 重组 commit (f0cde02) 引入的新文件 `tasks/al-scanner.py` 再次硬编码了本地绝对路径，导致 LR-SEC-005 回归 (🔴)。同时 `al-scanner.py` 的 `sh()` 函数使用 `shell=True` 存在注入风险接口 (🟡)，且 `al-dev.sh`/`al-review.sh` 硬编码 `$HOME` 路径 (🟡)。

### Findings

| # | Severity | Title | File:Line | Status |
|:-:|:--------:|:------|:---------:|:------:|
| 1 | 🔴 | LR-SEC-005 REGRESSION: 硬编码本地绝对路径 | `tasks/al-scanner.py:27` | Open |
| 2 | 🟡 | LR-SEC-009: shell=True 注入风险接口 | `tasks/al-scanner.py:45` | Open |
| 3 | 🟡 | LR-SEC-010: Shell 脚本硬编码 $HOME 路径 | `tasks/al-dev.sh:8`, `tasks/al-review.sh:6` | Open |

### Details

**LR-SEC-005 REGRESSION (🔴 P0)**: 曾在 cfa3e0f 修复 (`audit_snapshot.py`/`mcp_submit_update.py` 改用 `Path(__file__)`)，但在 f0cde02 新增的 `tasks/al-scanner.py:27` 中再次出现 `PROJECT = Path("/Users/jadenli/CodeSpace/llm-radar.jaden.tech")`。建议改用 `pwd.getpwuid(os.getuid()).pw_dir`（`al-init.py` 已使用此模式）。

**LR-SEC-009 (🟡 P2)**: `tasks/al-scanner.py:45` 的 `sh()` 函数接受任意 `cmd: str` 并用 `shell=True` 执行。当前调用者仅传硬编码 git 命令 (`"git pull"`, `"git push origin main"`)，但函数接口本身是注入向量，未来调者传入动态参数即构成风险。建议改为 list form: `subprocess.run(['git', 'pull'], ...)`。

**LR-SEC-010 (🟡 P2)**: `tasks/al-dev.sh:8` 和 `tasks/al-review.sh:6` 使用 `BASE="$HOME/CodeSpace/llm-radar.jaden.tech"`。虽比硬编码 `/Users/jadenli/` 好但不可移植。`al-rename.sh` 已使用 `$(cd "$(dirname "$0")/.." && pwd)` 的相对路径解析模式，建议统一。

### Positives

- Credential scan Pass 1 + Pass 2 均通过：无硬编码 API key / token / password
- MCP API key 正确使用 `os.environ.get()` + 随机降级 (`secrets.token_hex(32)`)
- `_skip_push` 测试保护机制正确，防止测试触发 git push
- 测试隔离 (`temp_snapshot` fixture) 避免污染真实数据
- 日期过滤逻辑边界完善（含 ≤14 天、>14 天、无日期、已有实体更新 4 种场景）
- 无 eval/exec/compile 使用
- `al-init.py` 正确使用 `pwd.getpwuid(os.getuid()).pw_dir` 动态解析 HOME

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------:|:--------:|:------:|
| LR-SEC-005 | 硬编码本地路径 | MEDIUM→🔴 | P0 | ✅ Closed (commit 3714860) |
| LR-SEC-009 | shell=True 注入风险接口 | MEDIUM | P2 | ✅ Closed (commit 3714860) |
| LR-SEC-010 | Shell 脚本硬编码 $HOME 路径 | MEDIUM | P2 | ✅ Closed (commit 3714860) |

---

## 2026-07-13 — Re-review (post-fix)

- **Reviewer**: Security Reviewer (IRIS)
- **Level**: L2
- **Scope**: Verify fixes for LR-SEC-005 REGRESSION, LR-SEC-009, LR-SEC-010
- **Commit(s)**: 3714860 (fix@llm-radar: commit-review fixes)
- **Verdict**: PASS
- **Score**: 100 / 100 (Rating: A)
- **Findings total**: 0 (🔴:0 / 🟡:0 / 🟢:0)

### Summary

复查确认 3 项修复全部到位。LR-SEC-005 使用 `Path(__file__).resolve().parent.parent` 替换硬编码路径；LR-SEC-009 `sh()` 函数改为 list form `subprocess.run(cmd)` 无 shell 注入风险；LR-SEC-010 shell 脚本统一使用 `$(cd "$(dirname "$0")/.." && pwd)` 相对路径解析。Credential scan Pass 1+2 0 hits, shell=True 0 hits, 硬编码路径 0 hits。score 从 75 回到 100。

### Findings

(无新增发现)

| # | Severity | Title | File:Line | Status |
|:-:|:--------:|:------|:---------:|:------:|
| — | — | — | — | All clear |

### Positives

- 3 项修复均精确对应建议方案
- al-scanner.py 改用 Path(__file__) 与 al-init.py 的 pwd.getpwuid 模式保持一致性
- sh() 函数签名从 `cmd: str` 改为 `cmd: list`，防御性设计预防未来注入

### Tracking

| Issue | Title | Severity | Priority | Status |
|:------|:------|:--------:|:--------:|:------:|
| LR-SEC-005 | 硬编码本地路径 | MEDIUM→🔴 | P0 | ✅ Closed |
| LR-SEC-009 | shell=True 注入风险接口 | MEDIUM | P2 | ✅ Closed |
| LR-SEC-010 | Shell 脚本硬编码 $HOME 路径 | MEDIUM | P2 | ✅ Closed |

---
