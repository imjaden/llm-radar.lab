# llm-radar git 处理逻辑修复 — ops 验证报告

> 日期: 2026-08-13
> 验证人: ops (hermes-1.2.0)
> 实现: cb82792 fix@llm-radar (dev) | 实现报告: 1464f80
> 设计依据: llm-radar-git-flow-fix-design-v1.2-20260812.md

## 验证方式

独立运行 dev 报告的测试命令 + 代码逐项核对 + 真实 run --force 端到端。不信任 dev 自报,全部实测。

## 单元测试

```
pytest tests/test_gitflow.py -v → 12/12 PASSED (0.35s)
```

12 用例覆盖: _sync_remote 快进/分叉/fetch 失败/rebase 清理; _push_with_recovery 成功/rejected→rebase→force-with-lease/冲突→dead-letter/全失败不抛异常; _clean_conflict_file 无标记/tracked/untracked/_save_snapshot 清理

## 全量测试

```
pytest tests/ -m "not selenium" --ignore=test_cli --ignore=test_selenium -q
→ 86 passed, 2 failed (test_timestamp 2 条)
```

**pre-existing 确认**: stash 回退到实现前,同样 2 条失败(硬编码日期 2026-07-13 被 14 天日期过滤拒绝)。与本次改动无关。✅

## 核心变更逐项核对(6 项)

| # | 变更 | 代码位置 | 核对 |
|:-:|:-----|:---------|:-----|
| 1 | _sync_remote | :249-275 | ✅ fetch→merge-base→ff-only; 分叉本地优先; 先 _abort_rebase; fetch 失败 warning 返回 |
| 2 | _push_with_recovery | :327-357 | ✅ rejected→pull --rebase→force-with-lease→dead-letter; finally _abort_rebase 兜底 |
| 3 | _clean_conflict_file | :277-308 | ✅ tracked→checkout --theirs; untracked→os.remove; 三写盘函数(:1265/:1299/:1330)调用 |
| 4 | CRON_SCHEDULE 平台感知 | :1891 | ✅ Darwin→0 * * * *, Linux→0 7,14,21 * * * |
| 5 | 技术要点 | _git_run :226 | ✅ 全 list-form subprocess.run(['git',...]); 0 处 shell=True(仅注释提及) |
| 6 | _skip_push 守卫 | :362 | ✅ 方法顶部 getattr 拦截, 覆盖 partial 模式 |

## 验收标准 5 项

| # | 标准 | 结果 |
|:-:|:-----|:-----|
| 1 | run 后 git 干净无 rebase 残留 | ✅ run --force 后 git status 空, .git/rebase-merge|apply 不存在, 0/0 同步 |
| 2 | 模拟分叉不卡死、数据正常写盘 | ✅ 实测 3 ahead/1 behind 分叉状态下 run --force, 快照正常保存(66 changes) |
| 3 | 冲突标记 → run 后合法 JSON | ✅ _clean_conflict_file 逻辑 + test_save_snapshot_cleans_markers 通过 |
| 4 | rejected → 成功或 dead-letter 不抛异常 | ✅ 分叉态 push 自愈成功(7e1d851 auto-push 66 changes), _push_with_recovery 全失败路径不抛异常 |
| 5 | 本机每小时、服务器 7/14/21 | ✅ 本机 `0 * * * *`; 服务器 `0 7,14,21 * * *`; crontab --status 已启用 |

## 端到端实测

- run --force: 5/5 源成功 → 66 实体 → 质量门禁通过 → 快照保存 → auto-push 66 changes 成功
- git log: 7e1d851 auto-push (66 changes), 0/0 与 origin 同步
- 分叉收敛实测: 本次验证前恰好处于 3 ahead/1 behind 分叉态, run 完整走通 D1(分叉本地优先)+ D2(auto-push 收敛), 无卡死无残留

## 测试残留说明

test_timestamp 用真实 project_root 写 timestamp/overview, 全量测试会弄脏工作区(已 git checkout 还原)。建议后续将测试改用 tmp_path 隔离, 属观察项非阻断项。

## 结论

**PASS** — 实现与设计 v1.2 一致, 6 项核心变更全部落地, 单元测试 12/12, 全量 86/88(2 个 pre-existing), 验收标准 5/5, 端到端分叉自愈实测通过。可进入最终实施审计(review role)。
