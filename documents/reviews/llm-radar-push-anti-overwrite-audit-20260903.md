# Push 防覆盖修复审计 — review报告 v1.0

- **日期**: 2026-09-03
- **审查者**: Security Reviewer (review profile)
- **范围**: commit 074ac1b `fix@llm-radar: disable force-with-lease on rebase conflict (CL005 fork prevention v1.4)`
- **项目**: llm-radar.lab
- **级别**: L2 (scripts, git ops, no auth)
- **结论**: PASS — 100/100 (A)

## 背景

CL005 闭环后发生 fork 事故: 服务器 clone (59.110.66.1) 在 rebase 冲突后 abort, 用
`force-with-lease` push 旧链 `ad62fa8` 覆盖远端, 抹掉 Mac 侧 CL005 全链 (16 ahead/3
behind, reflog forced-update)。

漏洞本质: `_push_with_recovery` else 分支 (rebase 冲突) 的 v1.3 逻辑调用
`push --force-with-lease`, 但 `force-with-lease` 仅校验「远端从 fetch 后未被再改」,
不校验「push 内容是否包含远端 commit」。服务器 fetch 后 lease 基线 = `4362e84` 与远端
一致 → 校验通过 → 但 push 的是不含 `4362e84` 的旧链 `ad62fa8` → 覆盖丢数据。

## 审计要点逐项验证

### 1. else 分支修改 ✅

**文件**: `llm-radar-collector.py:356-366`

修改正确。rebase 冲突 (pull --rebase returncode != 0) 路径:
1. `_abort_rebase()` 清理残留 rebase 状态 (L358)
2. `_print_err()` 输出 "rebase 冲突: 双向数据分叉, 已停止 auto-push (防覆盖), 需人工 merge" (L363)
3. `_write_dead_letter()` 记录 "rebase 冲突 (双向分叉): 停止 auto-push 防覆盖, 人工 merge 后重试" (L364-365)
4. `return` 终止, 不尝试 force-with-lease (L366)

dead-letter 字段语义正确: `time`/`changelog_count`/`error`/`changelog_snapshot` 均为
`_write_dead_letter` 标准字段 (L316-331), `error[:500]` 截断安全。

### 2. rebase 成功路径 (r2 force-with-lease) 保留 ✅

**文件**: `llm-radar-collector.py:348-355`

`pull --rebase` 成功 (returncode == 0) 路径仍调用 `push --force-with-lease origin main`
(L351)。此路径安全: rebase 成功 = 本地已 rebase 到远端之上, push 内容含远端 commit,
force-with-lease 不会覆盖。

### 3. 测试更新 ✅

**文件**: `tests/test_gitflow.py`

3 个用例覆盖新行为:

| 用例 | 行号 | 断言 | 状态 |
|:-----|:-----|:-----|:-----|
| `test_rejected_rebase_force_lease` | 82-97 | rebase 成功 → force-with-lease 被调用 | 保留 ✅ |
| `test_rejected_rebase_conflict_dead_letter` | 99-125 | 冲突 → 无 force-with-lease + dead-letter 含 "双向分叉" | 更新 ✅ |
| `test_rebase_conflict_no_force_dead_letter` | 135-155 | 冲突 → 即使 force 会成功也不调用 + dead-letter 含 "人工 merge" | 新增 ✅ |

旧 v1.3 用例 `test_rebase_conflict_then_force_lease_success` 和
`test_rebase_conflict_force_lease_fail_dead_letter` 已正确移除 (测试已删除的旧行为)。

独立复跑: `pytest tests/test_gitflow.py` → 13 passed ✅

### 4. _sync_remote / 正常 push 路径不受影响 ✅

- `_sync_remote` (L255-281): 使用 `fetch + merge --ff-only`, 完全独立于 `_push_with_recovery`
- 正常 push 路径 (L339-342): `push origin main` 成功直接 return, 不受影响
- `finally` 块 (L370-371): `_abort_rebase()` 仍在, 保证 rebase 状态清理

### 5. 无遗漏 ✅

- `finally` abort 清理: L370-371 `finally: self._abort_rebase()` 保留, 与 else 分支
  L358 的显式 abort 形成双重清理 (幂等安全)
- dead-letter 保留最近 10 次 (L327), 不会失控
- `_print_err` 用于冲突路径 (区别于 `_print_warn`), 日志级别正确

## 数据验证

- 全量测试: `pytest -m "not selenium" --ignore=test_cli.py --ignore=test_selenium.py` → 222 passed ✅
- diff 最小性: 2 files changed, 22 insertions(+), 41 deletions(-) — 净减 19 行
- 无新增依赖, 无新增文件

## 发现

| # | Severity | Title | Status |
|---|----------|-------|--------|
| (无) | — | — | — |

## 评分

- 基础分: 100
- 扣分: 0
- 最终: 100/100 (A) → PASS

## 结论

修复正确且最小化。else 分支从 "尝试 force-with-lease" 改为 "dead-letter + 人工 merge",
彻底阻断了 rebase 冲突场景下的自动覆盖风险。rebase 成功路径的 force-with-lease 保留
正确 (该路径 push 内容含远端, force 安全)。测试覆盖充分, 全量回归 222 passed。
