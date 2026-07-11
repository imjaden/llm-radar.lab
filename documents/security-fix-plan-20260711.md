# Security Audit 修复方案

> 基于 AUDITLOG.md (2026-07-11)
> Verdict: FAIL / Score: 65/100 (C)
> Findings: 7 (🔴1 / 🟡4 / 🟢2)

---

## 问题 → 修复映射

| # | ID | Severity | 问题 | 文件 | 修复方案 | Effort |
|:--|:---|:--------:|:---|:---|:---|:---:|
| 1 | LR-SEC-001 | 🔴 P0 | 硬编码默认 MCP API Key | 3 files | 移除默认值 → 环境变量强制 | S |
| 2 | LR-SEC-002 | 🟡 P1 | Tailwind CDN 缺 SRI | 2 HTML | 接受风险 + 文档说明 | S |
| 3 | LR-SEC-003 | 🟡 P1 | 3 处链接缺 rel="noopener" | index.html | 补充 rel="noopener noreferrer" | S |
| 4 | LR-SEC-004 | 🟡 P2 | 缺少 CSP 头 | 2 HTML | 添加 CSP meta 标签 | S |
| 5 | LR-SEC-005 | 🟡 P2 | 硬编码本地绝对路径 | 2 scripts | 改为相对路径 / Path(__file__) | S |
| 6 | LR-SEC-006 | 🟢 P2 | Git 历史含个人路径 | — | 文档说明，不修代码 | — |
| 7 | LR-SEC-007 | 🟢 — | collector.log 已删除 | — | Closed ✓ | — |

---

## 详细设计

### 1. LR-SEC-001: 移除硬编码 MCP API Key (P0)

**当前状态：**
```
llm-radar-mcp-server.py:33  → API_KEY = os.environ.get('LLM_RADAR_MCP_KEY', 'llm-radar-mcp-2026')
scripts/mcp-protocol-demo.py:44 → API_KEY = 'llm-radar-mcp-2026'
scripts/mcp_submit_update.py:12 → API_KEY = 'llm-radar-mcp-2026'
```

**修复策略：**

a) `llm-radar-mcp-server.py`（主服务）：
   - 移除默认值，改为空字符串
   - 启动时检查：未设置 → 生成随机 key + 打印到 stderr + 写入 `.env` 提示
   - 不因 key 缺失而退出（保持向后兼容手动启动的场景），但打印醒目的安全警告

b) `scripts/mcp-protocol-demo.py`（测试脚本）：
   - 改为从环境变量读取，fallback 到启动时自动生成临时 key
   - 每次运行使用随机临时 key，不固定

c) `scripts/mcp_submit_update.py`（提交脚本）：
   - 改为从 `LLM_RADAR_MCP_KEY` 环境变量读取
   - 未设置时打印错误并退出

**实现细节：**
```python
# llm-radar-mcp-server.py
import secrets
API_KEY = os.environ.get('LLM_RADAR_MCP_KEY', '')
if not API_KEY:
    API_KEY = secrets.token_hex(16)
    log.warning('=' * 60)
    log.warning('⚠️  LLM_RADAR_MCP_KEY 未设置，已生成临时随机 key')
    log.warning(f'   本次会话 key: {API_KEY[:8]}...')
    log.warning('   建议: export LLM_RADAR_MCP_KEY=<your-secure-key>')
    log.warning('=' * 60)
```

### 2. LR-SEC-002: Tailwind CDN SRI (P1)

**分析：** Tailwind CDN 按请求头的 User-Agent 动态生成不同 CSS，不支持固定 SRI hash。官方没有提供 SRI 方案。

**决策：** 接受风险，不做代码修改。记录理由：
- Tailwind CSS CDN 由 Tailwind Labs 官方运营
- 两个页面都是静态仪表盘，无用户输入
- 篡改 CDN 的攻击面与 DNS/供应链攻击等价，SRI 不能完全防止

### 3. LR-SEC-003: 补充 rel="noopener" (P1)

**受影响位置（重新核实）：**
- `index.html:149` — GitHub profile 链接 → ✅ 缺 rel
- `index.html:152` — GitHub repo 链接 → ✅ 缺 rel
- `index.html:441` — 动态实体 URL → ❌ 已有 rel="noopener"（审计时可能版本不同）

**修复：** 给 L149 和 L152 的 `<a>` 标签添加 `rel="noopener noreferrer"`

### 4. LR-SEC-004: 添加 CSP (P2)

**策略：**
- 使用 `<meta http-equiv="Content-Security-Policy">` 方式（无需服务器配置）
- 允许 Tailwind CDN 脚本、Google Fonts、自域资源
- 两个 HTML 文件都添加

```html
<meta http-equiv="Content-Security-Policy"
      content="default-src 'self'; script-src 'self' 'unsafe-inline' cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' fonts.googleapis.com; font-src fonts.gstatic.com; img-src 'self' data:; connect-src 'self';">
```

### 5. LR-SEC-005: 硬编码路径改为相对路径 (P2)

**受影响文件：**
- `scripts/audit_snapshot.py:7` → `with open('/Users/jadenli/.../snapshot.json')` 
  改: `Path(__file__).resolve().parent.parent / 'data' / 'snapshot.json'`
- `scripts/mcp_submit_update.py:11` → `SERVER = '/Users/jadenli/.../llm-radar-mcp-server.py'`
  改: `Path(__file__).resolve().parent.parent / 'llm-radar-mcp-server.py'`
- `scripts/mcp_submit_update.py:13` → `PROJECT_DIR = '/Users/jadenli/...'`
  改: `Path(__file__).resolve().parent.parent`

---

## 测试策略

| 修复 | 测试方式 | 类型 |
|:---|:---|:---|
| LR-SEC-001 | 单元测试: 环境变量设置时使用正确 key、未设置时生成随机 key | 新增 test_security.py |
| LR-SEC-003 | 手动验证 HTML → 无需自动化测试 | — |
| LR-SEC-004 | 手动验证 CSP meta 标签存在 → 无需自动化测试 | — |
| LR-SEC-005 | 脚本语法检查（Python 编译通过） | 现有 CLI 测试覆盖 |

---

## 不修复项

| # | 原因 |
|:--|:---|
| LR-SEC-002 | Tailwind CDN 不支持 SRI，接受风险 |
| LR-SEC-006 | Git 历史路径泄露，重写历史的破坏性大于收益 |

---

## 实施顺序

1. **LR-SEC-001** (P0): MCP API Key → 写 test_security.py → 实现 → 回归
2. **LR-SEC-003** (P1): HTML rel="noopener" → 手工确认
3. **LR-SEC-004** (P2): CSP meta → 手工确认
4. **LR-SEC-005** (P2): 路径去硬编码 → 回归

---

## 实施记录 (2026-07-11)

### 已实施

| ID | 状态 | 变更文件 | 测试 |
|:---|:---:|:---|:---|
| LR-SEC-001 | ✅ Fixed | `llm-radar-mcp-server.py`, `scripts/mcp-protocol-demo.py`, `scripts/mcp_submit_update.py` | test_security.py ×5 |
| LR-SEC-003 | ✅ Fixed | `index.html` (L149, L152) | 手工验证 |
| LR-SEC-004 | ✅ Fixed | `index.html`, `changelog.html` | 手工验证 |
| LR-SEC-005 | ✅ Fixed | `scripts/audit_snapshot.py`, `scripts/mcp_submit_update.py` | 编译验证 |

### 方案偏差

- **LR-SEC-005**: `mcp_submit_update.py` 在修复路径硬编码时顺便重构了完整文件（原始文件有重复的 send/recv/main 定义），统一为单一 main() 入口
- **LR-SEC-003**: 审计报告提到的 L441 经核实已有 `rel="noopener"`，实际只需修复 L149/L152

### 接受风险

- **LR-SEC-002**: Tailwind CDN 不支持 SRI 哈希，官方无方案，接受风险
- **LR-SEC-006**: Git 历史中 `/Users/jadenli/` 路径，重写历史破坏性大于收益

### 测试结果

52/52 passed (5 security + 47 existing)
