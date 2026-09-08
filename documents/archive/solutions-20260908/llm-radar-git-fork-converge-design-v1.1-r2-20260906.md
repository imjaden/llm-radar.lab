---
title: llm-radar 双端分叉自动收敛设计
topic: llm-radar
type: design
version: 1.1-r2
date: 2026-09-06
author: hermes-personal
profile: personal
provider: deepseek
model: deepseek-v4-flash
tags: [llm-radar, git, dual-writer, converge, auto-push, cron]
closed_loop: LLM-RADAR-CL006
---

# llm-radar — 双端 Git 分叉自动收敛设计 v1.1-r2

> 版本: v1.1-r2 | 日期: 2026-09-06 | 闭环编号: LLM-RADAR-CL006
> 作者: hermes-personal（personal profile；llm-radar 历史设计文档多为 ops profile 产出，作者字段仅为溯源）
> 变更:
>   - v1.0 → v1.1 修复设计评审 6 🟡（RIG-1~6）+ 3 🟢 观察（见 v1.1 文件头）
>   - v1.1 → v1.1-r2 修复复评（documents/reviews/llm-radar-fork-converge-design-rereview-v1.1-20260906.md, CONDITIONAL PASS 85/100）3 新残余 🟡：
>     - RIG-7: overview.json 规则补全 7 字段（v/t/p/s/h/r/rd，源码 _write_overview L1358-1366 实证）
>     - RIG-8: partial→converge 与 D2 脏工作区守护矛盾解除（先 checkout 丢弃未提交的 snapshot/overview）
>     - RIG-9: 多时间字段优先级锁定 `last_event_date` > `date` > `updated_at` + 单测断言

## 决策确认（澄清超时，默认采纳推荐项，评审可改）

| 项 | 决策 | 默认 |
|:---|:---|:---|
| A1 | 保留双机双写同一 main 分支，不做单写者改造 | ✅ |
| A2 | 收敛合并策略 = 语义并集（4 实体维度按 id 并集；汇总文件取较新侧并重算计数） | ✅ |
| A3 | 收敛触发 = 双保险（run() sync 检测到分叉即收敛 + push 被拒兜底收敛） | ✅ |
| A4 | 现状分叉收敛（Phase 0）在评审 PASS 后由 ops 执行 | ✅ |

## 背景/动机

2026-09-06 daily-checker LLM Radar checkpoint 持续 warning：`Git 同步 N ahead / N behind`。heal（`lr run --force`，interval 360min）已尝试仍异常；`dk action llm-radar push`（=`lr auto-push`）同样无法收敛（见根因）。

慢性问题非新故障：collector.log 全量统计 110 次「远端分叉本地优先」+ 23 次「残留 rebase abort」+ 6 次 dead-letter + 5 次「双向分叉需人工 merge」（评审实测，08-20 起高频出现，09-04 单日 3 次）。git 处理前序修复链 v1.0~v1.4（git-flow-fix design v1.2/v1.3、2026-09-03 push anti-overwrite audit 074ac1b）已解决 rebase 卡死/冲突污染/force 覆盖事故，但未消除双写分叉根本成因；v1.4 决策「冲突即停、人工 merge」安全但不自愈。仓库已有 3 次人工 reconcile merge（9d6bd0f / b5de3fe / 3633cf4）。

## 根因分析

### 架构根因：双实例双写同一 main 分支

- 采集器部署两地（features.md「跨平台执行」「平台感知调度 Darwin 每小时 / Linux 7,14,21 + 6h 防抖」；llm-radar-run.sh:14-16）：
  - Mac：`~/CodeSpace/llm-radar.lab`，crontab `40 * * * *`，git 身份 `t <t@t.com>`
  - 阿里云 Linux：`/home/admin/codespace/llm-radar.lab`，git 身份 `Jaden.Li <jaden.li@jaden.tech>`

### 写集根因：每次运行整文件重写 3 个生成文件

git 层面每次 auto-push commit 只动 3 个 tracked 数据文件（评审实测多笔均如此）：

```
data/snapshot.json    全量实体库（providers/people/tools/llms + hotspots + changelog + stats），单文件紧凑 JSON 整行重写
overview.json         站点汇总（7 字段：v/t/p/s/h/r/rd，_write_overview L1358-1366），整行重写
timestamp.json        运行状态（generated_at/server/hostname/period/entity_count/...），整行重写
```

两机在时间窗内基于同一 base 各自运行 → 同文件同几行内容不同 → 3-way merge 必冲突。tracked 数据文件另含 `data/twitter.json`（twitter 采集独立 commit+push）与 `data/twitter-targets.yaml`（配置），前者纳入收敛白名单。

### 机制根因：冲突即 abort 的收敛死锁（v1.4 决策的残留缺口）

当前 git 收敛链（`llm-radar-collector.py`）：

- `_sync_remote()` (L271)：run 前置 fetch + `merge --ff-only`；分叉分支仅 warn「远端分叉，本地优先，稍后 auto-push 收敛」（L293-295），不收敛
- `_auto_push()` (L389) → `_push_with_recovery()` (L349)：push 被拒 → `pull --rebase`；rebase 冲突 → `rebase --abort` + dead-letter + 人工 merge（L372-382，v1.4 2026-09-03 决策：禁 force 防任一 clone 覆盖另一端）

后果：任一 clone 在 sync 未能 ff 时基于旧 base 采集提交（典型诱因：Mac 夜间休眠后首个 run、sync fetch 瞬时失败），与另一端已 push 的 commit 形成分叉；此后两侧各自「本地优先」堆 commit → push 每轮被拒 → rebase 冲突 → abort → dead-letter。分叉只增不减且只能人工 merge。heal 每 6h `lr run --force` 反而再叠本地 commit，形成提醒循环。

### 安全现状

数据无丢失：每侧本地 commit 完整（push 仅被拒）；失败变更存档 data/dead-letter.json；冲突范围 = 3 生成 JSON + 潜在 twitter.json，无源码参与（评审实证）。rebase 均安全 abort，无残留状态。

## 目标

1. 双端分叉自动收敛：任一 clone 检测到分叉即自动语义合并并推送；**4 实体维度（providers/people/tools/llms）不丢任一端数据**（并集），全程无 force push
2. 收敛后不复发：双写正常交错，分叉自限（最多多一个 merge commit）
3. 保持 v1.0~v1.4 安全契约：不覆盖远端数据、不留 rebase/merge 残留态、失败降级 dead-letter + 可人工、不阻断采集
4. heal 可自愈：`lr run --force`（含 0 新数据场景）能清分叉 → checkpoint 复验转 ok

## 非目标

- 不做单写者架构改造（A1）
- 不改采集/提取/合并业务逻辑、不改 cron 调度、不改 daily-checker heal 配置
- 不引入新 git 机制（仅 merge commit，不用 force；rebase 仅保留为 push 前尝试）

## 方案设计

### D0（Phase 0，一次性，评审 PASS 后由 ops 执行）：现状分叉收敛

目标：将本地 main（评审时含 docs/audit 链，当前 5 ahead）与 origin/main（服务器链，当前 3 ahead）语义合并推回。**执行前 `git fetch origin main` 以当时实况为准**（ahead/behind 数随两侧 cron 持续变化，本文档不承诺固定 SHA；若执行时任一侧已自动/人工收敛，跳过或按实际分叉处理并在审计说明）。

流程（ops 执行，产出合并审计）：
1. 备份：`mkdir -p /tmp/cl006-phase0-backup && cp data/snapshot.json overview.json timestamp.json data/dead-letter.json /tmp/cl006-phase0-backup/`
2. `git fetch origin main`
3. `git merge origin/main --no-commit --no-ff`
4. 预期冲突仅在数据白名单文件（D1 表）；冲突解决 = 语义并集（用一次性 /tmp 脚本按 D1 规则重写冲突文件并 `git add`，脚本不入库）
5. 若冲突出现在白名单以外（源码/文档/配置）→ 停止 `git merge --abort`，升级人工（不应发生：评审实证两侧 commit 均只动 3 数据文件）
6. `git commit`（merge commit，双亲 = 本地 HEAD + origin/main）：`merge@llm-radar: reconcile fork — semantic union (CL006 Phase 0)`
7. `git push`
8. 验证：
   - `git status` 干净；`git log --oneline -4`；`git ls-remote origin main` == 本地 HEAD
   - `lr status --json` Git 同步转 ok
   - 4 实体维度计数 ≥ max(合并前两侧各自计数)（评审实测 providers union=101：local 100 / remote 100 / local_only 1 / remote_only 1 → 并集 101 是并集正确性直接证据）
   - overview.json `s.*` 与合并后 snapshot 各维度 len 一致（重算，非取任一侧）；站点页面数据正常
9. 合并审计报告落盘（documents/reviews/llm-radar-fork-converge-phase0-YYYYMMDD.md）

### D1：语义合并规则（核心）

数据白名单（自动收敛仅处理这些 tracked 生成文件；白名单外冲突一律 abort 人工）：

| 文件 | 语义 | 合并规则 |
|:---|:---|:---|
| data/snapshot.json | 实体库 | 见下 |
| overview.json | 站点汇总（7 字段：`v`=schema 版本恒 1、`t`=生成时间、`p`=周期、`s`=各维度计数、`h`=top3 头条、`r`=质量门禁结果 success/failed、`rd`=质量详情） | 结构跟随 `t` 较新侧：`v` 任一侧（恒 1）；`t`/`p`/`r`/`rd` 取较新侧；`s` 由合并后 snapshot 各维度 len 按 _write_overview 同款统计重算；`h` 由合并后 snapshot hotspots 按 (date, hot_score) 降序取 top3 重算（非并集） |
| timestamp.json | 运行状态（generated_at/server/hostname/period/entity_count/...） | generated_at 较新侧整体胜出（server/hostname 保留该侧原值）；entity_count 若与合并后 snapshot 不一致由下轮 run 归正（display-only） |
| data/twitter.json | X 热点 | 按记录 id（或 url）并集去重，同 id 取较新 |
| data/twitter-targets.yaml | 配置 | 非本设计合并对象（配置变更走人工，极少双写） |

snapshot 并集规则（确定性，评审可审）：

- **4 实体维度（providers/people/tools/llms）：按记录 `id` 并集 —— 数据不丢的唯一性保证（目标 1）**
  - 仅一侧有 → 保留（另一侧新发现实体不丢）
  - 两侧都有（同 id）→ 字段级合并，**胜者判定规则**：
    1. 逐字段比较；任一侧字段为空/缺失 → 取非空侧（空值填补）
    2. 两侧均非空且不等：若记录含时间类字段，按**固定优先级取最高位可判字段**判定较新侧——`last_event_date` > `date` > `updated_at`（RIG-9：updated_at 仅为无语义日期字段的 fallback；优先级字段存在即用，不存在才降级下一档；多字段同时存在时按优先级取最高位，不交叉比较）
    3. 无时间字段、或按规则 2 判为平（同值/均无）→ 逐字段取 JSON 字典序较大值（字符串按 Unicode 码点比较；数字先转字符串）——**跨机确定性**（不依赖执行机/merge 方向，任何 clone 收敛结果一致）
  - 不复用 `_merge_single()`（L1185，其语义是「参数序 new-wins + 空值填补」，与上述「时间/字典序胜出」不同）；D2 实现内置独立辅助 `_union_record(remote_rec, local_rec)`，规则如上，单测覆盖（含多时间字段冲突断言）
- **hotspots：按 `id` 并集 → 按 date 降序 → 截断至 max(len(local), len(remote))**——display-only 例外声明（O-1）：并集可能 > 单侧上限（评审实测 union=92 > 90），截断按日期丢弃最旧；hotspots 为展示性热点榜单、由 run 定期按源重生成，允许有界丢弃，不属于「不丢数据」保证范围
- **changelog：按 (type, dimension, id) 并集，同键取 time 较新者；截断至 max(len(local), len(remote))**——display-only；同 id 同 type 多次 update 被折叠（O-2，接受：changelog 展示最近期事件，且每轮 run 重新生成）
- **stats：total_***（含 total_hotspots）由合并后各维度/hotspots len 重算；new/updated/removed_this_period 取 generated_at 较新侧
- **version / period / execution_mode：取 generated_at 较新侧**

### D2：`_converge_fork()`（新方法，自动收敛核心）

位置：`llm-radar-collector.py`，与 `_push_with_recovery` 平级。流程：

```
1. git fetch origin main（失败 → warn return，不阻断）
2. 状态判定：
   - HEAD == origin/main → return
   - HEAD 是 origin/main 祖先（仅落后）→ merge --ff-only → return
   - 否则 → 分叉，继续
3. 守护：工作区有未提交改动（git status --porcelain 非空）→ warn return（调用点保证 clean；D3 partial 分支例外，见下）
4. git merge origin/main --no-commit --no-ff
   - merge 冲突时检查冲突文件集：
     - 全部 ∈ D1 白名单 → 进入 5
     - 含白名单外文件 → git merge --abort + dead-letter + warn「需人工 merge」，return（绝不动非数据文件）
5. 语义解决：按 D1 读工作区冲突版本与两侧 blob（HEAD:path / origin/main:path），产出并集内容覆写白名单文件，git add 这些文件
6. git commit（自动生成 merge commit，双亲 = HEAD + origin/main）
   消息: merge@llm-radar: auto-converge dual-writer data (semantic union)
7. git push（merge 后本地已含远端，普通 push 即 ff）
8. 成功 → print_ok（含各维度计数）；失败 → dead-letter + warn
9. finally：清理任何残留 merge/rebase 状态，保持 v1.4 自清理契约
```

安全边界：
- 全程无 force push
- 白名单外冲突 abort 人工，不自动解决
- 异常不抛（沿用 try/except warn 风格），不阻断采集主流程
- 并发安全：Mac 与服务器可能同时收敛 → 各自 fetch/merge 后 push，后者若再被拒则下一轮 run 的 sync 或 push 兜底再次收敛（merge 收敛幂等：并集可交换，重复收敛结果一致，最终收敛）

### D3：集成点（改动最小化，全部落在 git 层）

| 位置 | 现状 | 改为 |
|:---|:---|:---|
| `_sync_remote()` L293-295 分叉分支 | warn「远端分叉，本地优先，稍后 auto-push 收敛」 | warn + 调 `_converge_fork()`；收敛失败才回退「本地优先」（数据新鲜度优先仅作兜底） |
| `_sync_remote()` L272-275 docstring | 「仅同步，不 commit、不 push」 | 同步为「分叉时收敛（含 merge commit + push）；仅落后时 ff」 |
| `_push_with_recovery()` L372-382 rebase 冲突分支 | abort + dead-letter + 人工 | abort 后调 `_converge_fork()` → 成功则再普通 push；仍失败才 dead-letter + 人工提示 |
| `_push_with_recovery()` L350/L366-378 docstring/注释 | 描述 force-with-lease 链 | 同步为新链（rebase → 冲突收敛 merge；删除 force-with-lease 描述与调用） |
| `_push_with_recovery()` L366-371 rebase 成功分支 | `push --force-with-lease` | 普通 `push`（rebase 成功 = 本地已含远端，ff 即可；评审 SEC-1 确认安全且缩小 force 风险面） |
| `_auto_push()` partial 分支 L395-416 | 裸 `git push`，失败仅 print_err | **纳入收敛（RIG-5/8 锁定）**：partial 模式 run() 已写盘但未提交 snapshot.json/overview.json（L1164-1170，质量门禁失败数据），`git add` 仅 timestamp.json（L398-400）→ 收敛前**先 `git checkout -- data/snapshot.json overview.json` 丢弃这两个未提交生成文件**（未 push 的质量失败数据，下轮 run 重生成，丢弃无损——历史好数据仍在上一 commit），再走 `_converge_fork()`（此时工作区 clean，D2 步骤 3 守护放行）；dead-letter 无 changelog → `changelog_count: 0, changelog_snapshot: [], error: 'partial (quality-gate) push converge failed: <stderr>'` |

收敛调用点 = `_sync_remote`（run() L1745，先于 `_think` 节流 L1748）→ **run 因 6h 防抖跳过采集也会先清分叉** → heal `run --force` 0 新数据场景自愈（目标 4，评审 REA-4 实证成立）。

### D4：跨仓影响与文档同步

- daily-checker：**零改动**。heal action 保持 `lr run --force`；自动收敛落地后复验转 ok
- AGENTS.md L190 描述过期（仍写「rebase 重试 → --force-with-lease → dead-letter」，与 v1.4 实际行为及本设计均不符）→ 同步为新收敛链描述（连同 D3 docstring 一并）
- features.md：git 处理属内部机制，不加条目
- review-log.md / .review-level.yaml 由 review 按惯例追加（CL006）
- **服务器部署说明**：代码变更需同步到服务器 clone（`/home/admin/codespace/llm-radar.lab` 内 `git pull`）后下轮 cron 生效——由用户/运维执行或并入 Phase 1 实施说明（评审确认执行方，默认用户执行）

### 测试与验收

单测（仓库 pytest 体系，现有 222+；anti-overwrite 3 用例在 tests/test_gitflow.py L82/L99/L135，需改写语义）：
1. D1 并集规则单测：构造两侧 snapshot（local-only / remote-only / 同 id 不同值含时间 / **多时间字段冲突（last_event_date vs updated_at 相悖，断言 last_event_date 优先）** / 无时间 tie / hotspots / changelog / stats）断言输出；**真实数据回归**：用 origin/main 与本地 snapshot 跑合并，断言 4 维度计数 ≥ 两侧各自计数（providers =101）、hotspots 截断至 max=90、overview `s.*` 与合并后 len 一致
2. `_union_record` 确定性单测：同输入在「本地为左/右」两次调用结果一致（跨机确定性）；tie 走字典序
3. D2 分支测试（mock `_git_run`）：仅落后 ff / 分叉语义合并成功 / 白名单外冲突 abort 不碰代码 / merge 失败降级 / 收敛后 push 失败降级 / 残留状态清理 / 工作区 dirty 守护（含 partial 分支 checkout 后放行用例）
4. D3 回归：`_sync_remote` fork 分支触发收敛；`_push_with_recovery` 冲突分支收敛而非死锁；partial 分支失败先 checkout 再收敛；全 git 调用序列无 `force`
5. test_gitflow anti-overwrite 3 用例改写：断言冲突路径 → `_converge_fork` 而非 dead-letter-only；保留「无 force」断言
6. 全量 pytest 回归

实施后验收（ops verify 报告）：
- AC1 现状分叉已收敛（Phase 0），lr status Git 同步 ok
- AC2 任一 mock 分叉场景自动收敛且 4 维度计数不降
- AC3 全 git 调用序列 grep 无 `force`
- AC4 文档同步（AGENTS.md + docstring）已提交
- AC5 pytest 全绿（含改写用例）

## 风险与回滚

- 收敛异常 → 每步 try/except + finally 清理，最坏 = 维持分叉现状（等价今日状态，无新损失）
- 语义合并 bug → 影响面仅白名单数据文件，git 历史可回退；实体库并集只增不减，最坏冗余记录由下轮 run 归正
- 代码级冲突（白名单外）→ abort 人工，杜绝自动覆盖（延续 v1.4 边界）
- 服务器未及时拉新代码期间旧代码仍可能 abort 一次 → Mac 侧新代码兜底收敛（双保险单侧生效即自愈），无数据风险
- 双端同时收敛竞态 → 并集幂等可交换，后 push 者被拒后下轮再收敛，最终一致
- partial 分支 checkout 丢弃质量失败 run 的未提交数据 → 该数据未 push、下轮重生成，可接受（若需保留本地展示可先备份再丢弃，实施时打印 warn 注明）

## Commit 计划

仓库：llm-radar.lab（daily-checker 无改动）。commit scope 维持本仓近期主流 `@llm-radar`（O-3：与早期 docs@design 混用为历史，维持现状）：
1. `docs@llm-radar: git fork auto-converge design v1.0 (CL006)`（b981e9e，已提交）
2. `docs@llm-radar: git fork auto-converge design v1.1 fix RIG-1~6 (CL006)`（1985ca8，已提交）
3. `docs@llm-radar: git fork auto-converge design v1.1-r2 fix RIG-7~9 (CL006)`（本文档）
4. `feat@llm-radar: auto-converge dual-writer fork (semantic union, D1-D3)`（含单测改写，PASS 后实施）
5. Phase 0 由 ops 执行后产出 `merge@llm-radar: reconcile fork — semantic union (CL006 Phase 0)`（若执行时已无分叉则跳过并在审计说明）
6. 评审/审计产物（review-log、.review-level.yaml、documents/reviews/）由 review profile 按惯例落盘（audit@review:）

提交策略：只 commit 不 push；push 由 review PASS/审计后执行（Phase 0 的 merge+push 在复评 PASS 后由 ops 执行）。
