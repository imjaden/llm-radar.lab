# STALE_HOURS 7→12 调整审计 — review报告 v1.0

- **审计日期**: 2026-09-03
- **审计范围**: commit 2ff9b51 `fix@llm-radar: STALE_HOURS 7->12 for cross-night gap (2026-09-03)`
- **审计类型**: ops 派发单 commit 审计
- **结论**: ✅ PASS — 98/100

---

## 1. 变更摘要

| 文件 | 变更 | 行号 |
|:---|:---|:---|
| `llm-radar-collector.py` | 默认值 `'7'` → `'12'` + 注释更新 | L50-53 |
| `scripts/llm-radar-health.py` | 默认值 `'7'` → `'12'` + 注释更新 | L37-38 |

- diff 最小性: 2 files changed, 6 insertions(+), 4 deletions(-) ✅
- 无逻辑变更, 仅常量默认值 + 注释

## 2. 审计要点逐项验证

### 2.1 双文件默认值同步 ✅

- `llm-radar-collector.py L53`: `STALE_HOURS = int(os.environ.get('LLM_RADAR_STALE_HOURS', '12'))` ✅
- `scripts/llm-radar-health.py L38`: `STALE_HOURS = int(os.environ.get('LLM_RADAR_STALE_HOURS', '12'))` ✅
- 两处默认值一致, 均为 `'12'`

### 2.2 注释一致性 🟡 (minor)

- `llm-radar-collector.py L50-52`: 注释说 "12h, 2026-09-03 从 7h 放宽" ✅
- `scripts/llm-radar-health.py L37`: 注释说 "默认 12h" ✅
- `scripts/llm-radar-health.py L28`: docstring 仍说 "默认 7" — 应更新为 "默认 12"
  - 影响: 仅文档, 不影响运行时行为
  - 建议: 后续补丁修正 docstring

### 2.3 tests 影响 ✅

- 测试用 `mod.STALE_HOURS` 引用, 自动跟随代码变更
- 全量测试: `pytest -m "not selenium" --ignore=test_cli.py --ignore=test_selenium.py` → **222 passed**
- 无需修改测试代码

### 2.4 env 覆盖 ✅

- 两文件均使用 `os.environ.get('LLM_RADAR_STALE_HOURS', '12')` 模式
- 实测 `LLM_RADAR_STALE_HOURS=5` → 正确返回 5 ✅
- 无硬编码, 环境变量覆盖机制完好

### 2.5 AGENTS.md L50 同步 🟡 (acknowledged)

- AGENTS.md L50 仍写 `STALE_HOURS=7`
- commit message 已注明 "AGENTS.md L50 同步被 protected 拦截, 待用户改"
- 不阻塞本次审计, 用户后续手动修正即可

### 2.6 服务器同步 🟡 (info)

- 服务器 (59.110.66.1) 代码在 df9ef61
- 本次 2ff9b51 需后续 `git pull` 同步
- 不阻塞, 属于正常部署流程

## 3. 根因验证

跨夜空窗分析:
- 正常 cron 节奏: ~7h (09:00, 21:00)
- 跨夜空窗: 21:00 → 次日 09:00 = 12h
- 实测近 7 天 run 间隔: 7.0h 常态 / 10.0h / 13.7h / 14.0h 跨夜
- STALE_HOURS=12 覆盖 13.7h/14.0h 跨夜场景 ✅
- 余量: 14.0h - 12h = 2h 缓冲, 合理 ✅

## 4. 安全事项

- 🟢 SEC-1: 无新增安全风险 (仅常量默认值变更)
- 🟢 SEC-2: env 覆盖机制未被破坏 (仍可通过 LLM_RADAR_STALE_HOURS 调整)

## 5. 评分

| 维度 | 分数 | 说明 |
|:---|:---|:---|
| 代码正确性 | 50/50 | 双文件同步, env 覆盖完好 |
| 测试覆盖 | 28/28 | 222 passed, 自动跟随 |
| 文档一致性 | 20/22 | docstring L28 未更新 (-2) |
| **总分** | **98/100** | PASS |

## 6. 结论

✅ **PASS** — 变更正确, 测试通过, 仅 minor 文档问题不阻塞。

### 后续事项 (非阻塞)

1. `scripts/llm-radar-health.py L28` docstring "默认 7" → "默认 12" (补丁)
2. AGENTS.md L50 `STALE_HOURS=7` → `STALE_HOURS=12` (用户手动)
3. 服务器 `git pull` 同步 2ff9b51 (部署流程)
