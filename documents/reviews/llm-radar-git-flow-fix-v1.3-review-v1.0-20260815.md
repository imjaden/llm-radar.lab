# llm-radar git flow fix v1.3 — review报告 v1.0

> 日期: 2026-08-15
> 文件: documents/solutions/llm-radar-git-flow-fix-design-v1.3-20260815.md
> 项目路径: ~/CodeSpace/llm-radar.jaden.tech
> 待 push commit: 3acce2b (v1.3)
> review维度: 合理性 / 严格性 / 安全性 + Commit 规范 / 命名规范

## 数据验证

| 验证项 | 方法 | 结果 |
|:-------|:-----|:-----|
| 未 push commit 数 | `git log origin/main..HEAD --oneline \| wc -l` | 1 |
| 根因代码定位 | `read_file llm-radar-collector.py:350-355` | else 分支 abort 后直接 fall-through 到 dead-letter, **未尝试 force-with-lease** ✅ |
| 收敛链缺口 | 读 `_push_with_recovery()` 全函数 | push rejected → pull --rebase → 仅"成功"才 force-with-lease; "冲突"分支跳过 force ✅ |
| v1.3 文件命名 | 读 frontmatter | version=1.3, type=design, kebab-case ✅ |
| 单点改动范围 | 读实施范围表 | 仅 `_push_with_recovery()` else 分支 ✅ |

## 合理性评估

### 评分表

| # | 项 | 评估 |
|:-:|:---|:----:|
| 1 | 根因是否成立 | ✅ 代码级验证: `else` 分支 (rebase 冲突) 只 abort 不清除不收敛, 直接 dead-letter; 日志与代码一致 |
| 2 | rebase 冲突 = 分叉信号 | ✅ 正确: rebase 冲突恰是「本地有未 push commit + 远端有新增」的双向分叉 |
| 3 | force-with-lease 安全性 | ✅ lease 保护语义正确: 仅远端 ref 未变时生效, 不覆盖他人新 push |
| 4 | 改动范围 | ✅ 单点修改, 不触碰 _sync_remote 策略, 不引入新机制 |
| 5 | A1 vs A2 选择 | ✅ 推荐 A1 (直接尝试) 正确 — lease 检查本身就是「本地领先」的安全边界, A2 的 rev-list 预检冗余 |
| 6 | B1 测试覆盖 | ✅ 推荐 B1 (2 个单测) 正确 — 确定性覆盖新增两分支 |

**评级**: 🟢 (根因成立, 方案正确, A1/B1 推荐合理)

## 严格性评估

### 评分表

| # | 项 | 评估 |
|:-:|:---|:----:|
| 1 | 边界情况 | ✅ rebase 冲突→force 成功 / force 失败→dead-letter 两分支都覆盖; finally 清理残留 rebase 保持 |
| 2 | 验收标准可测 | ✅ 4 条: 2 个新单测 + 12 个回归 + 真实场景 |
| 3 | 风险评估 | ✅ 3 项有缓解 |
| 4 | 数据覆盖语义 | 🟡 RIG-1: 风险表写「覆盖远端**旧**数据快照是期望行为」— 但两机并发时远端数据**不旧**(是对方本轮新采集)。force-push 会暂时丢失对方本轮实体, 直至对方下轮 `_sync_remote` + `merge_entities` 重新合并。文档应显式承认此临时丢失窗口 |

**评级**: 🟡 (1 处语义低估)

## 安全事项

🟢 无安全发现。

| 检查项 | 结果 |
|:-------|:----:|
| force 变体 | ✅ `--force-with-lease` (非裸 `--force`), lease 保护正确 |
| subprocess 模式 | ✅ 复用 `_git_run` list-form, 无 shell=True |
| 凭证/注入 | ✅ 无 |
| 残留 rebase 清理 | ✅ `finally: _abort_rebase()` 保持 |

## Commit 规范评估

| # | SHA | Subject | 验证 |
|:-:|:-----|:--------|:----:|
| 1 | 3acce2b | `docs@design: git flow fix v1.3 — rebase-conflict force-with-lease path (server 5/10 diverge event)` | ✅ docs@design |

## 命名规范评估

| 检查项 | 文件 | 结果 |
|:-------|:-----|:----:|
| 设计文档 | `llm-radar-git-flow-fix-design-v1.3-20260815.md` | ✅ kebab-case, topic-type-version-date |
| Frontmatter | title/topic/type/version/date/author/tags | ✅ 7 字段, version=1.3 |

## 评分

| 扣分项 | 严重度 | 扣分 |
|:-------|:------:|:----:|
| RIG-1: 数据覆盖语义低估 (并发时覆盖对方新实体, 非仅旧数据) | 🟡 | -5 |

**得分**: 100 - 5 = **95 / 100 → Rating: A**

| 🔴 | 🟡 | 🟢 |
|:--:|:--:|:--:|
| 0 | 1 | 0 |

## 结论

**PASS** — 根因代码级成立, 单点修复正确, force-with-lease 安全边界清晰。1 个 🟡 为文档语义澄清, 不阻塞实施。

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | A1 直接尝试 force-with-lease (推荐, 已审) | 合理性 |
| □ | B1 新增 2 个单测 (rebase冲突→force成功 / →force失败→dead-letter) | 严格性 |
| □ | RIG-1: 风险表「覆盖远端旧数据」改为「覆盖远端快照会暂时丢失对方本轮新实体, 下轮 _sync_remote + merge_entities 重新合并」 | 严格性 🟡 |

## 实现 prompt

────────────────────────────────────────
  实现 prompt — git flow fix v1.3 (force-with-lease 补丁)
────────────────────────────────────────

对 llm-radar 项目 ~/CodeSpace/llm-radar.jaden.tech 修补 `_push_with_recovery()` 收敛链缺口。

聚焦文件: documents/solutions/llm-radar-git-flow-fix-design-v1.3-20260815.md

核心变更:
  1. `_push_with_recovery()` else 分支: abort 清理后尝试 `push --force-with-lease`
     - 成功 → return (收敛完成)
     - 失败 → dead-letter (不抛异常)

实现文件:
  - llm-radar-collector.py (_push_with_recovery else 分支)

参考:
  - 设计: documents/solutions/llm-radar-git-flow-fix-design-v1.3-20260815.md
  - 审查: documents/reviews/llm-radar-git-flow-fix-v1.3-review-v1.0-20260815.md

产出:
  1. 按治理规范 commit 规范提交
  2. 按验收标准 4 项逐项验证:
     1) 单测: rebase冲突 → force成功 → 收敛 exit 0 无 dead-letter
     2) 单测: rebase冲突 → force失败 → dead-letter 不抛异常
     3) 现有 12 个 gitflow 测试全通过 (不回归)
     4) 真实场景: 两端分叉 run 收敛成功无 rebase 残留
  3. 实施完成后通知 review role 做 implementation audit
