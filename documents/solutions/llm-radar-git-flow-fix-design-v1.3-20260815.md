---
title: llm-radar git 处理逻辑修复设计
topic: llm-radar
type: design
version: 1.3
date: 2026-08-15
author: hermes-1.2.0
tags: [llm-radar, git, cron, data-collection]
profile: ops
provider: deepseek
model: deepseek-v4-flash
---

# llm-radar — run() git 处理逻辑修复设计 v1.3

> 版本: v1.3 | 日期: 2026-08-15
> 作者: ops (hermes-1.2.0)
> 数据来源: llm-radar-collector.py 实际运行日志、服务器/本机 git 状态取证
> 变更: v1.0 → v1.1 确认项 A1 B1 C1 D2; v1.1 → v1.2 修复 review 4 项 🟡; v1.2 → v1.3 补 D2 rebase 冲突后 force-with-lease 路径(2026-08-15 服务器 5 ahead/10 behind 事件)

## 背景/动机

llm-radar 采集器运行于两端(本机 macOS + 服务器 Linux 7×24),cron 每天触发 `llm-radar-run.sh run`。run() 的 git 集成此前两次导致服务器卡死(7/14 rebase 卡死 27 天、8/12 冲突污染数据文件),v1.0-v1.2 已实现方案 D 全链路自愈(_sync_remote / _push_with_recovery / 冲突标记防护)。

2026-08-15 新事件:服务器 git 出现 5 ahead / 10 behind 分叉,连续多轮 run 的 auto-push 全部失败(数据 commit 成功但 push 被拒,累积 5 个未 push)。日志显示:

```
14:00:07 ⚠️ 远端分叉，本地优先，稍后 auto-push 收敛
14:02:15 ⚠️  push rejected，尝试收敛
14:02:19 ⚠️  pull --rebase 失败/冲突
14:02:19 ⚠️  检测到残留 rebase 状态，执行 git rebase --abort 清理
14:02:19 ℹ️  推送失败数据已存档到 dead-letter.json
```

## 根因分析

### 时间线还原(2026-08-15)

```
服务器 cron 14:00 run:
  _sync_remote(): 远端分叉 → 本地优先(正确, 数据写盘继续)
  采集 → 提取 → 合并 → _auto_push():
    push → rejected(远端有新 commit)
    pull --rebase → 冲突(本地 3de5ca3 等 auto-push 数据 commit 与远端数据冲突)
    → 进入 else 分支: abort + dead-letter
    → 未尝试 force-with-lease(设计 v1.2 D2 的缺口!)
  本地 commit 保留(数据不丢), push 失败, 累积未 push commit
```

### 根因(代码级)

`_push_with_recovery()` 的收敛链设计为:`push rejected → pull --rebase → 成功才 force-with-lease`。

问题:当 `pull --rebase` **冲突失败**(returncode != 0)时,直接走 else 分支 abort + dead-letter,**跳过了 force-with-lease**。

但 rebase 冲突恰恰是"本地确实领先(有未 push commit)+ 远端有新增"的典型信号——这正是 force-with-lease 应出场的场景:
- 本地有未 push 的 auto-push commit(领先)
- 远端有新增(behind)
- 双方都改了数据文件 → rebase 必然冲突
- force-with-lease 带 lease 保护:仅当远端引用未被他人更新时生效,不会覆盖他人新 push

设计 v1.2 D2 的原文是"尝试 2: rebase 成功后 force-with-lease",隐含假设 rebase 会成功;未覆盖"rebase 冲突但本地确实领先"的场景。

### 影响

- 服务器数据 commit 成功但 push 持续失败 → 未 push commit 累积(ahead 数增长)
- 每次 run 都重复此过程,git 分叉越拉越大
- 数据本身不丢(远端有本机 push 的更新版本),但服务器侧历史漂移、dead-letter 堆积
- 需人工介入收敛(reset --hard origin/main)

## 目标

1. auto-push 在 pull --rebase 冲突后**继续尝试 force-with-lease**(本地确实领先时收敛分叉)
2. force-with-lease 仅当 lease 检查通过时生效(不覆盖他人新 push)——保持安全边界
3. 全失败仍进 dead-letter,不抛异常(保持 v1.2 契约)
4. 绝不残留 rebase 状态(保持 v1.2 契约)

## 非目标

- 不改变 _sync_remote 的"分叉本地优先"策略(数据新鲜度优先,正确)
- 不改变单次采集/提取/合并业务逻辑
- 不引入新的 git 机制

## 方案设计

### D2 修订(仅改 _push_with_recovery 的失败分支)

原逻辑(v1.2):
```
push → 成功 return
push rejected → pull --rebase
  ├─ 成功 → force-with-lease → 成功 return / 失败 warning
  └─ 失败(冲突) → abort + dead-letter  [缺口: 未尝试 force-with-lease]
```

新逻辑(v1.3):
```
push → 成功 return
push rejected → pull --rebase
  ├─ 成功 → force-with-lease → 成功 return / 失败 warning → dead-letter
  └─ 失败(冲突) → abort 清理残留 → **尝试 force-with-lease**
       ├─ 成功 → 收敛分叉完成 return
       └─ 失败 → dead-letter
```

代码改动(collector.py _push_with_recovery else 分支):

```python
else:
    self._print_warn(f'pull --rebase 失败/冲突: {(r.stderr or "").strip()[:150]}')
    self._abort_rebase()
    # v1.3 补: rebase 冲突说明本地确实领先(有未 push commit) → 尝试 force-with-lease 收敛
    r3 = self._git_run('push', '--force-with-lease', 'origin', 'main', timeout=120)
    if r3.returncode == 0:
        self._print_ok('auto-push 完成（rebase 冲突后 force-with-lease 收敛）')
        return
    self._print_warn(f'force-with-lease push 失败(冲突分支): {(r3.stderr or "").strip()[:150]}')
```

### 安全性分析(force-with-lease 边界)

| 检查 | 结论 |
|------|------|
| lease 保护 | ✅ `--force-with-lease` 仅当远端 ref 未被他人更新时生效;若他人已 push,命令失败(不覆盖) |
| 双提交者场景 | 本机与服务器是唯二提交者;冲突窗口极小(6h 间隔);即便双 push 竞争,lease 保证至少一方成功 |
| 数据覆盖风险 | 本地 commit 是完整数据快照(含最新采集),覆盖远端旧数据快照是期望行为 |
| 与 v1.2 设计一致性 | v1.2 已在"rebase 成功后"使用 force-with-lease;v1.3 仅扩展到"rebase 冲突后",语义一致 |

## 实施范围

| 文件 | 改动 |
|------|------|
| llm-radar-collector.py | `_push_with_recovery()` else 分支: abort 后尝试 force-with-lease |

## 验收标准

1. 单元测试新增用例:rebase 冲突 → force-with-lease 成功 → 收敛完成(exit 0,无 dead-letter)
2. 单元测试:rebase 冲突 → force-with-lease 失败 → dead-letter(不抛异常)
3. 现有 12 个 gitflow 测试全部保持通过(不回归)
4. 真实场景:两端分叉时 run,auto-push 收敛成功,无 rebase 残留

## 风险评估

| 风险 | 等级 | 缓解 |
|------|------|------|
| force-with-lease 覆盖他人提交 | 低 | lease 保证仅当远端 ref 未变时生效;双提交者窗口极小 |
| rebase 冲突后 force 导致数据倒退 | 低 | 本地 commit 为最新采集快照,覆盖旧远端数据是期望行为 |
| 测试污染 git 历史 | 低 | _skip_push 守卫(已有)覆盖测试路径 |

## 已实施部分补设计(v1.0-v1.2 已落地, 本设计不重复)

- D1 _sync_remote: fetch + merge --ff-only,分叉本地优先,先清理残留 rebase
- D2 _push_with_recovery: push rejected → rebase 重试 → force-with-lease → dead-letter(本设计扩展其冲突分支)
- D3 _clean_conflict_file: 写盘冲突标记防护
- D4 本机 cron 每小时 + 6h 防抖;服务器 7/14/21
- 已提交:63de4b3/03ab565/0058fcb/3dbcb96/db8d792/5254ea4/81ddac2/cb82792

## 待确认清单

A. force-with-lease 在 rebase 冲突后的使用:
  A1 直接尝试(推荐——lease 提供安全边界)
  A2 先检查本地是否确实领先(git rev-list count)再尝试
  A3 本次不做

B. 测试覆盖:
  B1 新增 2 个单元测试(rebase冲突→force成功 / rebase冲突→force失败→dead-letter)(推荐)
  B2 仅改代码,测试靠真实场景观察
  B3 本次不做

## 元信息

| 项目 | 内容 |
|:-----|:------|
| 版本 | 1.3 |
| 最后更新 | 2026-08-15 |
| 作者 | hermes-1.2.0 |
| Session | ops/llm-radar-git-fix-v1.3 |
| Model | deepseek/deepseek-v4-flash |
