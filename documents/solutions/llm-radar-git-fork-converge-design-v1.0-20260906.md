---
title: llm-radar 双端分叉自动收敛设计
topic: llm-radar
type: design
version: 1.0
date: 2026-09-06
author: hermes-personal
profile: personal
provider: deepseek
model: deepseek-v4-flash
tags: [llm-radar, git, dual-writer, converge, auto-push, cron]
closed_loop: LLM-RADAR-CL006
---

# llm-radar — 双端 Git 分叉自动收敛设计 v1.0

> 版本: v1.0 | 日期: 2026-09-06
> 闭环编号: LLM-RADAR-CL006
> 作者: hermes-personal（本会话，personal profile；llm-radar 历史设计文档多为 ops profile 产出，作者字段仅为溯源，不影响评审）
> 触发: 2026-09-06 daily-checker LLM Radar 自愈提醒——「Git 分叉 2 ahead / 2 behind，lr run --force 复验仍异常」

## 决策确认（澄清超时，默认采纳推荐项，评审可改）

| 项 | 决策 | 默认 |
|:---|:---|:---|
| A1 | 保留双机双写同一 main 分支，不做单写者改造 | ✅ |
| A2 | 收敛合并策略 = 语义并集（实体按 dimension+id 并集、同 id 取较新；汇总文件取 generated_at 较新侧并重算计数） | ✅ |
| A3 | 收敛触发 = 双保险（run() sync 检测到分叉即收敛 + push 被拒兜底收敛） | ✅ |
| A4 | 现状 2 ahead/2 behind 收敛（Phase 0）在评审 PASS 后由 ops 执行 | ✅ |

## 背景/动机

2026-09-06 daily-checker LLM Radar checkpoint 持续 warning：`Git 同步 2 ahead / 2 behind`。自愈 heal（llm-radar action=run，即 `lr run --force`，interval 360min）已尝试仍异常，提醒建议替代操作 `dk action llm-radar push`（=`lr auto-push`）——但两者在当前架构下都无法收敛（见根因）。

这不是新故障：collector.log 自 08-20 起同类「残留 rebase 状态 → abort → dead-letter」已出现 13+ 次（08-20 / 08-21×2 / 08-22 / 08-23 / 08-26 / 08-28×2 / 08-29 / 09-04×3 / 09-06×2），仓库历史上已有 3 次人工 merge 收敛（08-13、09-02、09-04 各留 `merge@llm-radar: reconcile fork` merge commit）。git 处理逻辑前序修复链 v1.0~v1.4（`documents/solutions/llm-radar-git-flow-fix-design-v1.2/1.3`、2026-09-03 push anti-overwrite audit 074ac1b）已覆盖 rebase 卡死、冲突污染、force 覆盖等事故，但**未消除双写架构下分叉的根本成因**，当前设计是「冲突即停、人工 merge」——安全但不自愈。

## 根因分析

### 架构根因：双实例双写同一 main 分支

- 采集器部署两地（features.md「跨平台执行」「平台感知调度 Darwin 每小时 / Linux 7,14,21 + 6h 防抖」；llm-radar-run.sh:14-16）：
  - Mac：`~/CodeSpace/llm-radar.lab`，crontab `40 * * * *`，git 身份 `t <t@t.com>`
  - 阿里云 Linux：`/home/admin/codespace/llm-radar.lab`，git 身份 `Jaden.Li <jaden.li@jaden.tech>`
- 同一 repo（github.com:imjaden/llm-radar.lab）main 分支，各自采集各自 auto-push。

### 写集根因：每次运行整体重写 3 个生成文件

git 层面每次 auto-push commit 只动 3 个文件（8eee136 / d0ad26e / 7d0a990 实证均如此）：

```
data/snapshot.json    （全量实体库，单文件紧凑 JSON，整行重写）
overview.json          （站点数据，整行重写）
timestamp.json         （运行状态/计数，整行重写）
```

两机任何时间窗内各自基于同一 base 运行 → 同文件同几行内容不同 → 3-way merge 必冲突。tracked 数据文件另含 `data/twitter.json`（twitter 采集独立 commit+push，双端若都启用同属风险，纳入收敛白名单覆盖）。

### 机制根因：冲突即 abort 的收敛死锁（v1.4 决策的残留缺口）

当前 git 收敛链（`llm-radar-collector.py`）：

- `_sync_remote()` (L271)：run 前置 fetch + `merge --ff-only`；**分叉分支仅 warn「远端分叉，本地优先，稍后 auto-push 收敛」，不收敛**（L293-295）
- `_auto_push()` (L389) → `_push_with_recovery()` (L349)：push 被拒 → `pull --rebase`；**rebase 冲突 → `rebase --abort` + dead-letter + 提示人工 merge（L372-382，v1.4 2026-09-03 决策：禁 force，防任一 clone 覆盖另一端）**

后果：一旦两侧在各自 base 上各产生 ≥1 个数据 commit（典型诱因：Mac 夜间休眠、晨起首个 forced run 在 sync 未能 ff 时基于旧 base 采集提交；或 sync fetch 瞬时失败），分叉即形成；此后任一侧 run 都「本地优先」继续堆本地 commit，push 每次被拒 → rebase 冲突 → abort → dead-letter。**分叉只能人工 merge 解除，且会持续增长**（本机 08:30、14:41 各叠 1 个；服务器 03:01、11:01 各 push 1 个 → 2 ahead / 2 behind）。

heal 循环：checkpoint 把 git 分叉映射 warning → heal 每 6h `lr run --force` → 又叠本地 commit → 复验仍分叉 → 提醒。`lr auto-push` 无 merge 逻辑，同样无法收敛。

### 安全现状

- 数据无丢失：每侧本地 commit 完整（push 仅被拒未丢）；失败变更存档 data/dead-letter.json（仅 gitignore，不入库）；两侧数据在各自 snapshot 中。
- 冲突范围 = 3 个生成 JSON + 潜在 twitter.json，无源码参与（实证 diff）。rebase 均安全 abort，无残留状态。

## 目标

1. 双端分叉自动收敛：任一 clone 检测到分叉即自动语义合并并推送，无需人工；不丢任一端数据（并集），全程无 force push
2. 收敛后不复发：后续双写正常交错，分叉自限（最多多一个 merge commit）
3. 保持 v1.0~v1.4 安全契约：不覆盖远端数据、不留 rebase/merge 残留态、失败降级 dead-letter + 可人工、不阻断采集
4. heal 可自愈：`lr run --force`（含 0 新数据场景）能清分叉 → checkpoint 复验转 ok

## 非目标

- 不做单写者架构改造（A1）
- 不改采集/提取/合并业务逻辑、不改 cron 调度、不改 daily-checker heal 配置（自动收敛后现有 heal 即自愈）
- 不引入新 git 机制（仅用 merge commit，不用 force/rebase 收敛）

## 方案设计

### D0（Phase 0，一次性，评审 PASS 后由 ops 执行）：现状分叉收敛

目标：将当前本地 main（含 8eee136、7d0a990 及本文档 commit）与 origin/main（d0ad26e、08cae7d）语义合并推回。

流程（ops 执行，产出合并审计）：
1. 备份：`cp data/snapshot.json overview.json timestamp.json /tmp/cl006-phase0-backup/`（含 data/dead-letter.json）
2. `git fetch origin main`
3. `git merge origin/main --no-commit --no-ff`
4. 预期冲突仅在 3 个数据文件；冲突解决 = 语义并集（规则同 D1，用一次性 /tmp 脚本按 D1 规则重写 3 文件并 `git add`）
5. 若冲突出现在数据白名单以外（源码/文档）→ 停止，`git merge --abort`，升级人工（不应发生，实证两侧均只动数据文件）
6. `git commit`（merge commit）：`merge@llm-radar: reconcile fork — semantic union (CL006 Phase 0)`
7. `git push`
8. 验证：`git status` 干净；`git log --oneline -3`；`git ls-remote origin main` == 本地 HEAD；`lr status --json` Git 同步转 ok；4 实体维度计数 ≥ max(合并前两侧各自计数)（实测当前 providers 各 100 但 local-only 1 / remote-only 1 → 并集应为 101，是并集正确性的直接证据）；overview/timestamp 计数一致
9. 写合并审计报告（documents/reviews/llm-radar-fork-converge-phase0-YYYYMMDD.md，audit@review 类产物由 review 或 ops 落盘）

### D1：语义合并规则（核心）

定义数据白名单（自动收敛仅处理这些文件，均 tracked 且由采集器生成）：

| 文件 | 语义 | 合并规则 |
|:---|:---|:---|
| data/snapshot.json | 实体库（providers/people/tools/llms + hotspots + changelog + stats） | 见下 |
| overview.json | 站点汇总 | 取 generated_at 较新侧，实体计数以合并后 snapshot 重算 |
| timestamp.json | 运行状态 | 取 generated_at 较新侧；server/hostname/period 保留该侧原值 |
| data/twitter.json | X 热点 | 按记录 id（或 url）并集去重，同 id 取较新 |
| data/twitter-targets.yaml | 配置 | 非本设计合并对象（配置变更走人工，极少双写） |

snapshot 并集规则（确定性，评审可审）：
- providers / people / tools / llms：按记录 `id` 并集
  - 仅一侧有 → 保留该侧记录（另一侧新发现实体不丢）
  - 两侧都有 → 字段级合并：逐字段取非空较新值；冲突字段以 `last_event_date`（或记录级更新依据字段，people/tools/llms 用 id 相同的记录里时间戳字段）较新一侧胜出；平局保留本地
  - 实现复用 collector 现有 `_merge_single()`（L1185，语义同：新值优先、空值填补）——两记录互为 old/new 各跑一次合并后取并
- hotspots：按 `id` 并集 → 按 date 降序 → 截断至 max(len(local), len(remote))（保两端热点，超容丢弃最旧）
- changelog：按 (type, dimension, id) 并集，同键取 time 较新者；截断至较大一侧长度（纯展示）
- stats：total_* 由合并后各维度 len 重算；new/updated/removed_this_period 取 generated_at 较新一侧
- version/period/execution_mode：取 generated_at 较新一侧

### D2：`_converge_fork()`（新方法，自动收敛核心）

位置：`llm-radar-collector.py`，与 `_push_with_recovery` 平级。流程：

```
1. git fetch origin main（失败 → warn return，不阻断）
2. 状态判定：
   - HEAD == origin/main → 无需收敛，return
   - HEAD 是 origin/main 祖先（仅落后）→ merge --ff-only（复用现有路径）→ return
   - 否则 → 分叉，继续
3. git merge origin/main --no-commit --no-ff
   - 若 merge 因冲突中止：检查冲突文件集
     - 全部 ∈ 数据白名单 → 进入 4（语义解决）
     - 含白名单外文件 → git merge --abort + dead-letter + warn「需人工 merge」，return（绝不动代码冲突）
4. 语义解决：按 D1 读工作区冲突版本与两侧 blob（HEAD / origin/main），产出并集内容覆写白名单文件，git add 这些文件
5. git commit（自动生成 merge commit，双亲 = HEAD + origin/main）
   消息: merge@llm-radar: auto-converge dual-writer data (semantic union)
6. git push（merge 后为 fast-forward 语义，普通 push）
7. 成功 → print_ok（含各维度计数）；失败 → dead-letter + warn
8. finally：检查并清理任何残留 merge/rebase 状态（git status 非 merge 中），保持与 v1.4 相同的自清理契约
```

安全边界（与 v1.4 精神一致并强化）：
- 全程无 force push（删除 rebase 成功后多余的 `--force-with-lease`，见 D3）
- 数据白名单外冲突一律 abort + 人工，不自动解决
- 工作区有未提交改动时不启动（调用点保证 clean；另加守护检查）
- 任何异常不抛（沿用 try/except warn 风格），不阻断采集主流程

### D3：集成点（改动最小化）

| 位置 | 现状 | 改为 |
|:---|:---|:---|
| `_sync_remote()` L293-295 分叉分支 | warn「远端分叉，本地优先，稍后 auto-push 收敛」 | warn + 调 `_converge_fork()`；收敛失败才回退「本地优先」（数据新鲜度优先仅作兜底） |
| `_push_with_recovery()` L372-382 rebase 冲突分支 | abort + dead-letter + 人工 | abort 后调 `_converge_fork()` → 成功则再普通 push；仍失败才 dead-letter + 人工提示 |
| `_push_with_recovery()` L366-371 rebase 成功分支 | `push --force-with-lease` | 普通 `push`（rebase 成功 = 本地已含远端，普通 push 即 ff；force-with-lease 属多余风险面，删除） |
| `_auto_push()` partial 分支 L411 | 裸 `git push` 无恢复 | 复用 `_push_with_recovery` 失败语义（质量门禁失败路径也走收敛兜底；改动小，评审确认是否纳入，默认纳入） |

收敛调用点在 run 流程 `_sync_remote`（L1745，先于 `_think` 节流判断）→ **即使 run 因 6h 防抖跳过采集，分叉也会被清除** → heal `lr run --force` 0 新数据场景同样自愈（满足目标 4）。

### D4：跨仓影响与文档同步

- daily-checker：**零改动**。heal action 保持 `lr run --force`；自动收敛落地后复验转 ok
- AGENTS.md L190 描述已过期（仍写「rebase 重试 → --force-with-lease → dead-letter」，v1.4 起实际为「冲突禁 force → dead-letter 人工」）→ 同步为新收敛链（CL005 审计已标记待改，一并处理）
- features.md：如无对应条目则不加（git 处理属内部机制）；review-log.md / .review-level.yaml 按惯例由 review 追加
- **服务器部署说明**：代码变更需同步到服务器 clone（`/home/admin/codespace/llm-radar.lab` 内 `git pull` + 重启/等待下轮 cron）——由用户/运维执行或并入 Phase 1 实施说明，评审确认执行方

### 测试与验收（AC）

单测（仓库 pytest 体系，现有 222+，其中 git-flow/anti-overwrite 3 用例需**改写语义**）：
1. D1 并集规则单测：构造两侧 snapshot（含 local-only / remote-only / 同 id 不同值 / hotspots / changelog）断言输出；**含真实数据回归**：用 origin/main 与本地当前 snapshot 跑合并，断言 4 维度计数 ≥ 两侧各自计数（实证 providers 101）
2. D2 分支测试（mock `_git_run`）：仅落后 ff / 分叉语义合并成功 / 白名单外冲突 → abort+dead-letter 不碰代码 / merge 失败降级 / 收敛后 push 失败降级 / 残留状态清理
3. D3 回归：`_sync_remote` fork 分支触发收敛；`_push_with_recovery` 冲突分支收敛而非死锁；无 force push 出现在任何 git 调用序列
4. 全量 pytest 回归（预期 222+ 用例，git-flow 相关断言同步更新）

实施后验收（ops verify 报告）：
- AC1 现状分叉已收敛（Phase 0），lr status Git 同步 ok
- AC2 任一 mock 分叉场景（测试）自动收敛且计数不降
- AC3 全 git 调用序列 grep 无 `force`（force-with-lease 移除）
- AC4 文档同步（AGENTS.md）已提交
- AC5 pytest 全绿

## 风险与回滚

- 收敛期间异常 → 每步 try/except + finally 清理，最坏 = 维持分叉现状（等价今日状态，无新损失）
- 语义合并 bug → 影响面仅 3 个数据文件，git 历史可回退（merge commit revert / reset --hard origin/main 前先备份）；实体库并集只增不减，最坏多冗余记录，下轮 run 归一
- 代码级冲突（白名单外）→ 明确 abort 人工，杜绝自动覆盖（延续 v1.4 边界）
- 服务器未及时拉新代码期间，旧代码仍可能产生一次 abort 死锁 → 由 Mac 侧新代码兜底收敛（双保险的单侧生效即可自愈），无数据风险

## Commit 计划

仓库：llm-radar.lab（daily-checker 无改动）。类型遵循本仓惯例（feat@llm-radar / docs@llm-radar / fix@llm-radar / merge@llm-radar / auto-push@llm-radar 见近期 log）：
1. `docs@llm-radar: git fork auto-converge design v1.0 (CL006)`（本文档）
2. `feat@llm-radar: auto-converge dual-writer fork (semantic union, D1-D3)`（含单测改写）
3. Phase 0 由 ops 执行后产出 `merge@llm-radar: reconcile fork — semantic union (CL006 Phase 0)`（如评审 PASS 时本地仍有分叉）；若评审期间任一侧已自动/人工收敛，则此步跳过并在审计说明
4. 评审产物（audit/review 报告 + review-log/.review-level.yaml 更新）由 review profile 按惯例落盘

提交策略：只 commit 不 push（llm-radar 与家族项目同规，push 由 review PASS 后执行；Phase 0 merge 的 push 亦在 PASS 后）。
