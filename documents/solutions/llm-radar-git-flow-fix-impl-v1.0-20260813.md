---
title: llm-radar git 处理逻辑修复 — 实现报告
topic: llm-radar
type: impl
version: 1.0
date: 2026-08-13
author: hermes-1.2.0 (dev)
tags: [llm-radar, git, cron, data-collection]
profile: dev
provider: deepseek
model: deepseek-v4-pro
---

# llm-radar — run() git 处理逻辑修复 实现报告

> 版本: v1.0 | 日期: 2026-08-13
> 作者: dev (hermes-1.2.0)
> 依据设计: documents/solutions/llm-radar-git-flow-fix-design-v1.2-20260812.md
> 依据复审: documents/reviews/llm-radar-git-flow-fix-rereview-v1.2-20260812.md (PASS 100/100)
> 交付 commit: cb82792 `fix@llm-radar: git flow fix 方案D — _sync_remote + auto-push 自愈 + 冲突标记防护 + 本机每小时 cron`

## 变更清单（对照设计 D1-D4）

| # | 设计项 | 实现 | 位置 |
|:-:|:-------|:-----|:-----|
| D1 | 新增 `_sync_remote()` | pre-run fetch + `merge --ff-only`；分叉本地优先；先 `_abort_rebase()` 清理残留；fetch 失败仅 warning | `llm-radar-collector.py:249` |
| D2 | 改造 `_auto_push()` | rejected → `pull --rebase` → `push --force-with-lease` → dead-letter；结束 `_abort_rebase()` 兜底 | `_push_with_recovery()` `:327` |
| D3 | 写盘冲突标记防护 | `_clean_conflict_file()`：tracked → `checkout --theirs`；untracked → `os.remove` | `_save_snapshot/_write_timestamp/_write_overview` 写盘前调用 |
| D4 | 本机 cron 每小时 | `CRON_SCHEDULE` 平台感知：Darwin → `0 * * * *`，Linux → `0 7,14,21 * * *`；本机 crontab 已改 `0 * * * *` | `:1891` |

## 新增辅助方法

| 方法 | 职责 |
|:-----|:-----|
| `_git_run(*args)` | 统一 git 子进程封装，list-form，禁止 shell=True，不抛异常 |
| `_has_rebase_state()` | 检测 `.git/rebase-merge` / `.git/rebase-apply` |
| `_abort_rebase()` | 残留 rebase 清理 |
| `_write_dead_letter()` | 推送失败存档（最近 10 次），不抛异常 |

## 额外修复（实现中发现）

- `_auto_push()` 增加 `_skip_push` 顶部守卫：原 partial 模式不检查 `_skip_push`，测试运行会触发真实 `git add/commit/push` 污染历史（本实现过程中实测触发 3 次，已 `git reset` 清理）。现移到方法顶部统一拦截。

## 测试覆盖

| 文件 | 用例数 | 覆盖 |
|:-----|:------:|:-----|
| `tests/test_gitflow.py` | 12 | `_sync_remote` 快进/分叉/fetch 失败/rebase 清理；`_push_with_recovery` 成功/rejected→rebase→force-with-lease/冲突→dead-letter/全失败不抛异常；`_clean_conflict_file` 无标记/tracked/untracked/`_save_snapshot` 清理 |

## 验证结果

| 项 | 方法 | 结果 |
|:---|:-----|:-----|
| 单元测试 | `pytest tests/test_gitflow.py` | 12/12 ✅ |
| 真实 git 演练 | 临时 bare remote + 双 clone：快进/分叉/收敛/冲突清理 | 6/6 ✅ |
| 全量测试 | `pytest tests/ -m "not selenium" --ignore=test_cli --ignore=test_selenium` | 86 passed, 2 failed* |
| 本机 crontab | `crontab -l` | `0 * * * *` ✅ |

\* 2 个失败为 pre-existing（`test_timestamp.py` 两条，硬编码日期 2026-07-13 被 14 天日期过滤拒绝），在干净代码（stash 本改动后）已复现，与本次改动无关。

## 交付物

- `llm-radar-collector.py`（+166/-50）
- `tests/test_gitflow.py`（新增 12 用例）
- commit `cb82792`（仅 commit，未 push）
- 本机 crontab 已改 `0 * * * *`
