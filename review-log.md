---
name: review-log-template
description: Append-only review log template for project root (review-log.md)
version: 1.0
author: IRIS
tags: [template, review, governance]
quality:
  coverage: 0.60
  depth: 0.50
  maintainability: 0.85
  cross_profile: 0.85
---

# {Project Name} — review-log

> 产出文档的元信息必须遵循 `skills-governance/document-frontmatter.md` 规范。

> 作用: review运行日志。由 ops profile 在review后 append，review profile 验证后更新状态。
>
> 触发机制: ops profile 完成校准/review后写入条目（状态=⏳ AWAITING REVIEW）；
>         review profile 验证通过后将状态更新为 ✅ PASS。
>
> 文件命名: 固定为 `review-log.md`，放项目根目录。
> 适用: 风格 B 文件（无版本号，持续 append），不可删除历史条目。

- **reviewer**: {role}/{session-title}（如 ops/hermes-manager-ops）

## {YYYY-MM-DD} — {review标题}

- **review者**: {profile}/{session} ({agent version})
- **范围**: {review范围描述}
- **Tracking**: {PROJECT-CODE-SEC-NNN ~ SEC-MMM}（可选，对应详细报告中的发现编号）
- **状态**: ✅ PASS / ⏳ AWAITING REVIEW / ❌ FAIL
- **报告**: {path to full audit report}
- **实现 prompt**: ✅ 已生成 / ⬜ 无需生成

### 发现摘要

{简要列出关键发现项或分数变化}

（可选: 详细表格）

#### 发现摘要格式示例

**安全审计型:**
```
| # | Severity | Title | Status |
|---|----------|-------|--------|
| HM-SEC-001 | 🔴 | Hardcoded credential in config.py | Fixed |
| HM-SEC-002 | 🟡 | Missing input validation on --port | Open |
```

**质量校准型:**
```
| Skill | Before | After (C/D/M/X) | Grade |
|-------|--------|-------------------|-------|
| spec-review | 0.42 | 0.85 (0.85/0.90/0.75/0.85) | 优秀 |
```

---

## 条目格式说明

```
## YYYY-MM-DD — Title

- **review者**: <profile>/<session> (<agent-version>)
- **范围**: <scope>
- **Tracking**: <PROJECT-CODE-SEC-NNN ~ SEC-MMM>（可选）
- **状态**: ✅ PASS | ⏳ AWAITING REVIEW | ❌ FAIL
- **报告**: <path>
- **实现 prompt**: ✅ 已生成 | ⬜ 无需生成

### 发现摘要
<summary>

---
```
