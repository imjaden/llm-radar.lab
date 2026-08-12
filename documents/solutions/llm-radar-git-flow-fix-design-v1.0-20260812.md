---
title: llm-radar git 处理逻辑修复设计
topic: llm-radar
type: design
version: 1.0
date: 2026-08-12
author: hermes-1.2.0
tags: [llm-radar, git, cron, data-collection]
profile: ops
provider: deepseek
model: deepseek-v4-flash
---

# llm-radar — run() git 处理逻辑修复设计

> 版本: v1.0 | 日期: 2026-08-12
> 作者: ops (hermes-1.2.0)
> 数据来源: llm-radar-collector.py 实际运行日志、服务器/本机 git 状态取证

## 背景/动机

llm-radar 的采集器在两端运行(本机 macOS + 服务器 Linux 7×24),cron 每天 7/14/21 点触发 `llm-radar-run.sh run`。`run()` 的 git 集成存在设计性竞争,导致服务器两次卡死在 interactive rebase 状态:

- 2026-07-14:服务器 rebase 卡死,detached HEAD 持续 27 天,数据冻结(7/28 后 snapshot 停更)
- 2026-08-12:服务器 07:00 cron run 再次卡死,冲突标记污染 timestamp.json/snapshot.json,auto-push 失败,当轮 68 实体成果丢失

两次是同一类根因:run 开头的 `git pull --rebase` 在"本地有未提交数据写盘 + 远端有分叉提交"时必然冲突,而冲突后代码没有 abort 兜底,rebase 状态残留导致后续所有 git 操作失败。

## 根因分析

### 时间线还原(2026-08-12)

```
8/11 21:04  服务器 cron run → auto-push 98e08dd (60 changes) → 服务器本地 HEAD
8/11 21:04  本机 cron run  → auto-push 8297883 (64 changes) → 推送远端
8/12 07:00  服务器 cron run:
              run() 开头 git pull --rebase 拉取远端 8297883
              服务器本地 HEAD=98e08dd 与远端 8297883 分叉(同一时刻各自 auto-push)
              rebase 98e08dd onto 8297883 → snapshot.json/timestamp.json/overview.json 冲突
              → 卡死在 rebase, 无 abort 兜底
              run 继续执行, 冲突标记文件被当作正常数据写盘
              auto-push 失败 → 当轮 68 实体成果丢失
```

### 根因链(代码级)

1. **两机同时 auto-push 产生分叉**:本机与服务器 cron 时间重叠(21:00 同时触发),各自 commit+push,远端出现两个并列的 auto-push commit,无冲突处理机制
2. **run() 开头 `git pull --rebase` 无冲突兜底**:`_ensure_remote_sync()`(或等价逻辑)直接调 `git pull --rebase`,冲突时既不 `--abort` 也不跳过,rebase-merge 状态残留
3. **冲突后 run 继续执行**:git pull 失败仅打印告警(日志显示 "git pull 跳过"),不终止 run;后续 `_write_snapshot` 把冲突标记当作正常 JSON 写入数据文件
4. **auto-push 无冲突恢复**:`_auto_push()` push 失败(rejected)后无 retry/pull/abort 恢复逻辑,且 `git add -A` 会把冲突文件一起提交

### 影响

- 服务器数据冻结(7/14:27 天;8/12:当轮丢失)
- 冲突标记进入数据文件,前端解析失败
- 需要人工介入(abort + reset),不可自愈

## 目标

1. run() 的 git 处理在任何冲突/失败情况下都能自愈,绝不残留 rebase 状态
2. 采集数据新鲜度优先:git 同步失败不阻断采集,不阻断写盘
3. auto-push 失败可重试,重试仍失败则记录 dead-letter 而非抛异常
4. 两端并发 auto-push 的分叉能被自动收敛(以远端为权威或保留本地并重试)

## 非目标

- 不改变采集/提取/合并的业务逻辑
- 不引入 git worktree/子模块等复杂机制
- 不解决"两机采集时间重叠导致重复数据"问题(数据合并去重已有逻辑,超出本设计范围)
- 不处理服务器与本机的数据一致性策略(以 git 远端为唯一权威,两端 pull 对齐即可)

## 方案设计

### 方案对比

| 方案 | 做法 | 优点 | 缺点 | 结论 |
|------|------|------|------|------|
| A | run 开头 git pull --rebase 失败时 abort 并继续 | 改动小 | 无法收敛分叉,auto-push 仍可能失败 | 不充分 |
| B | run 先 commit 本地数据再 pull --rebase | 数据先落库 | 未解决分叉冲突,rebase 仍可能冲突 | 不充分 |
| C | pull 改为 fetch + merge --no-edit,冲突 abort 继续 | 避免 rebase 残留 | merge 冲突仍可能,auto-push 仍可能 rejected | 不充分 |
| **D** | **git 同步重构:pre-run fetch 快进 + auto-push 冲突自愈闭环** | 全链路自愈,分叉可收敛 | 改动中等 | ✅ 采用 |

### 方案 D 详细设计

#### D1. pre-run 同步(`_sync_remote()` 替换现 pull --rebase 逻辑)

```
输入: 无
流程:
1. git fetch origin main
2. 判断分叉状态:
   - git merge-base --is-ancestor HEAD origin/main → 本地可快进 → git merge --ff-only origin/main
   - 否则(分叉): 保持本地 HEAD 不动, 记 warning "远端分叉, 本地优先, 稍后 auto-push 收敛"
3. 任何 git 命令失败 → 仅 warning, 不 abort run
异常兜底:
   - 若检测到 .git/rebase-merge 或 .git/rebase-apply 残留 → git rebase --abort 先清理
输出: 无(不阻断采集)
```

要点:
- 用 `fetch + merge --ff-only` 替代 `pull --rebase`:快进不会冲突,失败即跳过
- 分叉时**本地优先**:不强行 rebase 远端,保留本地最新采集结果,交给 auto-push 环节收敛
- 每次进入先清理残留 rebase 状态(自愈 7/14 与 8/12 的现场)

#### D2. auto-push 冲突自愈(`_auto_push()` 改造)

```
输入: changelog 变更
流程:
1. git add -A && git commit(沿用现逻辑, 冲突文件先 checkout --theirs 清理标记)
2. git push origin main
   - 成功 → 完成
   - 失败(rejected):
     a. 尝试 1: git pull --rebase(远端有新增)
        - 冲突 → git rebase --abort, 回到本地 commit, 记 warning
     b. 尝试 2: git push --force-with-lease origin main
        - 仅当本地确实领先且远端被证明陈旧时使用(force-with-lease 安全检查)
     c. 仍失败 → 写入 data/dead-letter.json, 记 warning, 不抛异常
3. 结束时检查 git status, 若残留 rebase-merge → git rebase --abort(自愈兜底)
```

要点:
- push rejected 时先尝试普通 rebase,冲突则 abort(绝不残留)
- `--force-with-lease` 作为收敛分叉的最终手段(有 lease 保护,不会覆盖他人新 push)
- 全部失败进 dead-letter,与现有 push 失败机制一致

#### D3. 数据文件冲突标记防护(`_write_snapshot`/`_write_timestamp`/`_write_overview`)

```
写盘前检查: 若目标文件内容包含冲突标记(<<<<<<< HEAD / ======= / >>>>>>>),
          先 git checkout --theirs <file> 清理, 再写入
```

要点:
- 防止 8/12 那种"冲突标记文件被当正常数据写盘"的二次污染
- checkout --theirs 取远端版本为基,本地 run 的合并结果会完整覆盖(数据以本机新采集为准)

#### D4. 本机 cron 频率调整(配合 D1,独立决策项)

```
crontab: 0 * * * *(每小时)+ 保留 _think 6h 防抖
```

- 每小时 cron + 6h 防抖 = 实际约 6-7h 采集一次(防抖吞掉中间触发)
- 解决 Mac 睡眠错过:7:00 错过,唤醒后下一个整点因距上次成功 >6h 会真正执行,错过窗口从"一天"缩到"几小时"
- 服务器保持 7/14/21(7×24 常开,无需每小时)

## 实施范围

| 文件 | 改动 |
|------|------|
| llm-radar-collector.py | 新增 `_sync_remote()`,改造 `_auto_push()`,写盘函数加冲突标记防护 |
| crontab(本机) | 改回每小时 |

## 验收标准

1. 服务器/本机 `run --force` 后 git status 干净,无 rebase 残留
2. 模拟两机分叉:本机手动制造分叉(本地 commit 后不 push),服务器 pull 远端后 run,验证不卡死且数据正常写盘
3. 冲突文件写盘防护:手工制造带冲突标记的 snapshot.json,run 后文件为合法 JSON
4. auto-push rejected 场景:远端有新增时 run,push 最终成功或进 dead-letter(不抛异常)
5. 本机 crontab 为每小时,服务器为 7/14/21

## 风险评估

| 风险 | 等级 | 缓解 |
|------|------|------|
| --force-with-lease 覆盖他人提交 | 低 | lease 保证仅当远端引用未变时生效;两端是同一 repo 仅两提交者,冲突窗口极小 |
| fetch 不 rebase 导致本地长期落后 | 低 | auto-push 环节 rebase 收敛;两端 run 频率低(6h),数据漂移可接受 |
| checkout --theirs 丢弃本地写盘 | 低 | 仅在检测到冲突标记时触发;正常路径不执行 |
| 每小时 cron 增加 API 调用 | 低 | 6h 防抖保证实际调用频率不变 |

## 已实施部分补设计(2026-08-10~12 修复记录)

本设计之前已完成的修复(与本设计同属"数据新鲜度恢复"范畴):

| 修复 | 说明 |
|------|------|
| chromedriver 151(本机) | Chrome 151 匹配,修复全部源 Selenium 失败 |
| max_tokens 16000→8192 | DeepSeek 长 prompt 空输出 |
| 默认模型 deepseek-chat | v4-flash 长 prompt 空 content,chat 稳定输出 |
| snapshot 无条件写盘 | 质量门禁失败也写盘(原 if quality_ok 守卫) |
| 门禁 URL/key_people 降级警告 | 空 URL/key_people 不再阻断 auto-push |
| prompt 兜底规则 | URL 禁止留空、key_people 推断 |
| 测试实体清理 | test-company/CLTest/IsolationTest |

这些已提交并通过验证(见 git log 63de4b3/03ab565/0058fcb/3dbcb96)。

## 待确认清单

A. 本机 cron 频率:
  A1 每小时 + 6h 防抖(推荐,错过窗口最小)
  A2 保持 7/14/21(依赖服务器兜底)
  A3 本次不做

B. auto-push 分叉收敛方式:
  B1 fetch/merge --ff-only + rejected 时 rebase,仍失败 force-with-lease(推荐)
  B2 只 rebase 重试,不用 force-with-lease(更保守)
  B3 本次不做

C. 冲突文件防护范围:
  C1 三个写盘函数都加(snapshot/timestamp/overview,推荐)
  C2 只加 snapshot(主数据文件)
  C3 本次不做

D. 实施后验证方式:
  D1 手动制造分叉+冲突标记场景验证(推荐)
  D2 仅靠真实 cron 周期观察
  D3 本次不做

## 元信息

| 项目 | 内容 |
|:-----|:------|
| 版本 | 1.0 |
| 最后更新 | 2026-08-12 |
| 作者 | hermes-1.2.0 |
| Session | ops/llm-radar-git-fix |
| Model | deepseek/deepseek-v4-flash |
