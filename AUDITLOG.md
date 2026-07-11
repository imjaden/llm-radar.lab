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
| LR-SEC-005 | 脚本中硬编码本地路径 | MEDIUM | P2 | Closed |
| LR-SEC-006 | Git 历史 /Users/jadenli/ 路径 | LOW | P2 | Open |
| LR-SEC-007 | collector.log 已从 git 删除 | LOW | — | Closed |

---
