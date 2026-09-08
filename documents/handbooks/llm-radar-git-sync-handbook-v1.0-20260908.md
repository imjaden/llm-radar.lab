---
author: hermes-v0.20.6(2026.8.27)
profile: dev
type: summary
date: 2026-09-08
---

# llm-radar git-sync handbook v1.0（双机同步与自愈）

> documents-consolidation phase-2 草稿（只写文件，未 commit）。素材全文（gitignored）：
> `cache/doc-consolidation/llm-radar-git-sync-extract.md`。
> 代码行号核实基准：2026-09-08 工作区 `llm-radar-collector.py`（~2779 行）——源文档写作时行号已漂移，正文一律标现行号。

## 一、定位

llm-radar.lab 双实例（本机 macOS + 阿里云 Linux 59.110.66.1）共用同一 remote（github.com:imjaden/llm-radar.lab，main 分支）定时双写。本手册覆盖由此产生的**同步与 git 自愈机制**：三次事故链、方案 D 全链自愈（git-flow-fix）、语义并集自动收敛（fork-converge, CL006）、force 决策反转史（push-anti-overwrite, v1.4）。

素材：18 份 = git-flow-fix 9 + fork-converge 8 + push-anti-overwrite 1（全部为 solutions/reviews 过程文档）。

## 二、功能概述

- **架构事实**：每次 run 整行重写 3 数据文件 `data/snapshot.json` + `overview.json` + `timestamp.json`（实证 8eee136/d0ad26e/7d0a990 均只动 3 文件）；`data/twitter.json` 独立 commit 亦 tracked。双机 git 身份不同（Mac `t <t@t.com>` / Linux `Jaden.Li <jaden.li@jaden.tech>`）。cron 平台分支见 §三。
- **自愈链现状（2026-09-08 终态，即 CL006 后）**：
  1. run() 顶部 `_sync_remote()` 只同步（fetch + merge --ff-only），分叉时调 `_converge_fork()` 收敛，失败回退「本地优先」warning；
  2. 数据写盘前 `_clean_conflict_file()` 防护冲突标记（`<<<<<<< HEAD` 等）；
  3. 末尾 `_auto_push()` 统一 commit+push；push 被拒 → `_push_with_recovery()` 收敛（rebase 成功→**普通 push**；rebase 冲突→abort 后 `_converge_fork()` 语义并集合并→普通 push）；
  4. 仍失败 → `_write_dead_letter()` 存档 + warning，不抛异常；
  5. **全程 0 处 force push**（含 rebase 成功分支——CL006 删除）。
- **force 决策反转链（手册时间线要点）**：git-flow-fix v1.3 (08-15) rebase 冲突后尝试 `--force-with-lease` → v1.4 (09-03, 074ac1b) rebase 冲突**禁 force**（dead-letter + 人工 merge，防覆盖）→ CL006 (09-06~07) **删除全部 force**，改普通 push + 语义并集 merge commit。
- **测试隔离**：`_skip_push` 守卫在 `_auto_push()` 与 `_converge_fork()` 方法顶部统一拦截（L682-683 / L607-608），防测试触发真实 git 写操作。

## 三、机制与指令说明

### 3.1 现行代码关键方法（code 核实，2026-09-08）

| 方法/常量 | 位置 | 行为 |
|---|---|---|
| `_CONVERGE_WHITELIST` | L252 | `(snapshot.json, overview.json, timestamp.json, twitter.json)`；注释明示白名单外（含 twitter-targets.yaml, O-4）冲突 → abort 人工 |
| `_CONVERGE_MSG` | L253 | merge commit 消息 `merge@llm-radar: auto-converge dual-writer data (semantic union)` |
| `_TIME_FIELDS` | L255 | 时间字段优先级 `last_event_date` > `date` > `updated_at`（存在即用，不交叉比较） |
| `_git_run(*args)` | L257 | git 子进程统一封装，list-form，禁 shell=True，不抛异常 |
| `_has_rebase_state()` / `_abort_rebase()` | L267 / L274 | 检测并清理 `.git/rebase-merge`/`rebase-apply` 残留 |
| `_sync_remote()` | L280 | pre-run fetch → merge-base 判定 → ff-only / 分叉（warn + converge）/ fetch 失败 warning 本地优先 |
| `_clean_conflict_file()` | L311 | tracked → `git checkout --theirs <file>`；untracked → os.remove；失败 warning 直接覆盖写 |
| `_write_dead_letter()` | L344 | 推送失败存档（changelog 截断、限最近 10 条） |
| `_push_with_recovery()` | L361 | rejected → pull --rebase 成功→普通 push；冲突→abort→converge→普通 push；失败 dead-letter |
| `_merge_semantic` / `_union_by_id` / `_union_snapshot` | L420 / L450 / L466 | 4 实体维度按 id 并集；同 id 字段级：空值填补 → 时间较新侧胜出 → JSON 字典序 tie-break；base = 较新 generated_at |
| `_union_twitter` | L514 | targets 按 url/handle、tweets 按 id 并集 |
| `_in_merge_state()` / `_converge_fork()` | L596 / L599 | merge 状态检测 / 自动收敛（9 步流程，见 3.2） |
| `_auto_push()` | L680 | 顶部 `_skip_push` 守卫 → git add -A + commit → push（含 partial 分支：质量失败也收敛/兜底） |
| `CRON_SCHEDULE` | L2389 | `'0 * * * *' if platform.system() == 'Darwin' else '0 7,14,21 * * *'` |

### 3.2 `_converge_fork()` 九步流程（设计 v1.1-r2 定稿，impl 对照全 ✅）

1 fetch（L600-603）→ 2 状态判定：HEAD==origin/main 直接 return / 祖先则 ff / 分叉继续（L604-617）→ 3 脏工作区守护：`git status --porcelain` 非空 → warn return（L619-622）→ 4 merge --no-commit --no-ff + 白名单校验：冲突文件集全 ∈ 白名单才继续，否则 `merge --abort` + dead-letter + warn「需人工 merge」（L624-636）→ 5 语义解决（snapshot 先于 overview 排序键；L637-644）→ 6 merge commit `_CONVERGE_MSG`（L645-650）→ 7 普通 push（L651-654，无 force）→ finally 清理 merge/rebase 残留（L662-665）。

集成点 5 处：`_sync_remote` 分叉分支 L300-304 / `_sync_remote` docstring L278-283 / `_push_with_recovery` 冲突分支 L381-391 / rebase 成功分支 L373-377（原 force-with-lease 改普通 push）/ `_auto_push` partial 分支 L702-713（push 失败 → 先 `git checkout -- data/snapshot.json overview.json` 丢弃质量失败数据 → clean → converge，RIG-8）。

### 3.3 D0（Phase 0）人工收敛流程（历史/一次性，ops 执行）

备份 /tmp → fetch → `git merge origin/main --no-commit --no-ff` → 语义并集解决（一次性 /tmp 脚本不入库）→ 白名单外冲突 `git merge --abort` 升级人工 → commit → push → 验证（`lr status --json` Git 同步 ok；4 实体维度计数 ≥ max 两侧）。历史 3 次人工 reconcile merge：**9d6bd0f / b5de3fe / 3633cf4**（后者为 CL005 分叉 merge 审计对象）。

## 四、用法示例

```bash
# 分叉计数（判定 ahead/behind，CL006 各轮评审实测口径）
git rev-list --left-right --count origin/main...HEAD

# 数据采集 + 收敛（heal 入口，= daily-checker action run；绕过 6h 节流）
lr run --force

# 仅 push 数据（= dk action llm-radar push）
lr auto-push

# 定时任务状态
lr crontab --status

# git 自愈单测族（CL006 后 33 用例；全量 266 passed / 2 skipped / 0 failed）
python3 -m pytest tests/test_gitflow.py -q
python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_selenium.py -q

# 生产实证观察点：merge commit 消息与 _CONVERGE_MSG 精确一致（实测 299e97a，双亲 ea9172c + eccc122）
git log --oneline --merges -3
```

服务器侧部署/更新：`/home/admin/codespace/llm-radar.lab` 内 `git pull`（无需 force push）。

## 五、关键决策（原文编号）

### 族 A git-flow-fix（2026-08-12~15，v1.2/v1.3）

- 事故背景：2026-07-14 rebase 卡死 27 天；2026-08-12 冲突污染数据文件 + 当轮 68 实体丢失。根因链 4 级：两机同时 auto-push 分叉 → pull --rebase 无兜底 → run 继续把冲突标记当数据写盘 → auto-push 无恢复。
- 方案对比 A/B/C/D：A「pull --rebase 失败 abort 继续」/ B「先 commit 再 pull --rebase」/ C「fetch+merge --no-edit 冲突 abort」均不充分；**D「pre-run fetch 快进 + auto-push 冲突自愈闭环」✅ 采用**（2026-08-12 用户确认 **A1 B1 C1 D2**：A1 每小时+6h 防抖 / B1 fetch+merge/rebase/force-with-lease 链 / C1 三个写盘函数全加 / D2 仅靠真实 cron 周期观察）。
- **D1** `_sync_remote()` pre-run 同步（仅同步不 commit，REA-1 时序修正）；**D2** `_auto_push()`→`_push_with_recovery()` 冲突自愈；**D3** 写盘冲突标记防护（tracked→checkout --theirs / untracked→os.remove，RIG-1 修正）；**D4** cron `0 * * * *` 每小时 + 6h 防抖。run() 调用顺序（RIG-3 修正）：`_sync_remote` → 采集 → LLM → 质量门禁 → D3 写盘 → `_auto_push`。
- review 修正：**REA-1**（时序标注）/ **RIG-1**（untracked 分支）/ **RIG-2**（fetch 失败 warning 继续）/ **RIG-3**（调用顺序）→ 复审 100/100 PASS。
- **v1.3**（触发：08-15 服务器 5 ahead/10 behind 连续多轮失败）：**D2 修订**——rebase 冲突分支 abort 后尝试 `--force-with-lease`（lease 提供安全边界，确认 **A1**；A2 rev-list 预检否决；**B1** 新增 2 单测）。RIG-1：风险表改「两机并发时远端不旧，force-push 暂时丢失对方本轮新实体，下轮 _sync_remote + merge_entities 重新合并」。
- 终审（v1.3-rereview-v1.1, 2026-08-15）：**100/100 → Rating A → PASS**（0/0/0）；「实现与设计逐项对应，14/14 单测通过。v1.3 修复闭环完成」。

### 族 C push-anti-overwrite / v1.4（2026-09-03, commit 074ac1b）— 时序上先于 CL006

- 事故：服务器 clone rebase 冲突后 force-with-lease 推旧链 ad62fa8，抹掉 Mac 侧 CL005 全链（16 ahead/3 behind）。
- **漏洞本质**：`--force-with-lease` 仅校验「远端从 fetch 后未被再改」，**不校验 push 内容是否含远端 commit**；服务器 lease 基线一致 → 校验通过 → 推旧链 → 覆盖丢数据。
- 决策：else 分支（rebase 冲突）由「尝试 force-with-lease」改为「abort 清理 → dead-letter + 人工 merge」（`_print_err`「已停止 auto-push (防覆盖), 需人工 merge」）；rebase 成功分支 force-with-lease 保留（该路径 push 内容含远端，force 安全）。测试：3 用例更新/新增，`test_gitflow` 13 passed，全量 222 passed。
- 终审（push-anti-overwrite-audit）：**100/100 (A) → PASS**——「修复正确且最小化……彻底阻断了 rebase 冲突场景下的自动覆盖风险」。

### 族 B fork-converge（CL006, 2026-09-06~07, 闭环 LLM-RADAR-CL006）

- 触发：2026-09-06 daily-checker 报「Git 分叉 2 ahead/2 behind，lr run --force 复验仍异常」。根因三层：架构（双实例双写同一 main）/ 写集（每次整行重写 3 文件）/ 机制（v1.4 残留缺口：冲突即停不自愈）。
- 决策确认 **A1~A4**：A1 保留双机双写同一 main（不做单写者改造）/ A2 收敛=语义并集 / A3 触发=双保险（run sync 检测 + push 被拒兜底）/ A4 现状分叉 Phase 0 收敛在评审 PASS 后由 ops 执行。
- 设计模块：**D0** Phase 0 现状收敛（ops，备份 + 一次性脚本语义并集）；**D1** 语义合并规则（数据白名单 4 文件；providers/people/tools/llms 按 id 并集；同 id 逐字段取非空较新值，冲突以较新时间侧胜出，tie-break JSON 字典序；hotspots 并集后按 date 降序截断至 max 两侧；changelog 按 (type,dimension,id) 并集截断；stats 重算）；**D2** `_converge_fork()`（见 §3.2，安全边界：全程无 force、白名单外 abort 人工、脏工作区不启动）；**D3** 集成点 3+（含删除全部 force）；**D4** 跨仓（daily-checker 零改动、AGENTS.md 同步、服务器部署）。
- 评审链三审：v1.0 CONDITIONAL PASS 70/100（**RIG-1~6** + O-1~3，union=101 实证基线、hotspots union=92>90 截断例外）→ v1.1 修复 RIG-1~6（RIG-1 overview 7 字段 / RIG-2 `_union_record` 字段级规则 / RIG-3 去硬编码 / RIG-4 docstring 同步 / RIG-5 partial 纳入 / RIG-6 字典序 tie-break）85/100（新 **RIG-7** overview 缺 v/r/rd、**RIG-8** partial 脏守护矛盾、**RIG-9** 多时间字段优先级未定义）→ v1.1-r2 修复 **100/100 PASS (A)**（+观察 **O-4** twitter-targets.yaml 白名单表内但非合并对象，需注明「白名单外—冲突 abort 人工」）。
- 实现审计（ea9172c, 2026-09-07）：D1/D2/D3 逐项对应 ✅；AC1-AC5 中 AC2 含**生产自动收敛实证 299e97a merge commit**（消息与 `_CONVERGE_MSG` 精确一致），终态 local == origin/main == 6ee0c5d (0/0 clean)；唯一 🟡 **DOC-1** AGENTS.md L190 描述过期（受保护指令文件，待用户授权）。**95/100 → PASS (A)**。🟢 **IMPL-OBS-1/2**（twitter 同 id 字典序近似无损；generated_at 平局取左理论非对称实测不可达）。
- CL005 fork-merge-audit（09-02, merge 3633cf4）：冲突解决数据新鲜度优先（21:02 > 18:42 取远端），代码零回退，98/100 (A)。

## 六、已知坑

1. **v1.3 教训**：rebase 冲突后 force-with-lease 在双 clone 场景可致数据覆盖——lease 不校验 push 内容含远端 commit（C 族 074ac1b 修复，后 CL006 全去 force）。现行终态无 force，勿回退。
2. **冲突标记当数据写盘**：若 run 在 rebase 残留态继续执行，`<<<<<<< HEAD` 会被当数据写入 snapshot；D3 防护已覆盖三个写盘函数，改动须保持。
3. **数据 commit 成功但 push 持续失败** → ahead 增长、分叉拉大、dead-letter 堆积（旧 v1.2 缺口）；现行收敛链已覆盖，但 dead-letter 出现「双向分叉」字样时应人工 merge（勿 force）。
4. **Mac crontab 分针记载不一致**：A 族文档记 `0 * * * *`（0 分），B 族 fork-converge 记 `40 * * * *`（40 分），0→40 变更未见文档记载 [待核]；Linux 侧 `0 7,14,21 * * *`（0 分）。查证以 `lr crontab --list` 实况为准。
5. **行号漂移**：源文档引用的方法行号随 CL006 增量（collector +338）整体后移；本文一律标 2026-09-08 现行号。
6. **项目路径两种写法**：A 族 review 文件头写 `~/CodeSpace/llm-radar.jaden.tech`，B/C 族写 `llm-radar.lab`——同仓库历史更名所致，引用以 llm-radar.lab 为准（Q3/引用清理范围）。
7. **测试隔离**：`temp_snapshot` fixture 只隔离 snapshot/data_dir，`_write_timestamp`/`_write_overview` 仍写真实根文件——跑完全量 pytest 后 `git checkout -- timestamp.json overview.json data/snapshot.json` 还原。

## 七、参考文档

归档说明：18 份素材均为过程文档，已随 docs@archive（2026-09-08）移入 archive 桶，档案 = `documents/archive/{solutions,reviews}-20260908/`。Q3 改名项同批落地：reviews/ 4 份 `fork-converge-*` 补 `git-` 段 → `llm-radar-git-fork-converge-*`；`cl005-fork-merge-audit` 补 `git-` 段 → `llm-radar-cl005-git-fork-merge-audit-*`；`git-flow-fix-impl-v1.0` 迁 reviews 桶。

### 族 A git-flow-fix（9 份）

| 源文件（原位 documents/…） | 处置 |
|---|---|
| solutions/llm-radar-git-flow-fix-design-v1.2-20260812.md | 已归档 → archive/solutions-20260908/ |
| solutions/llm-radar-git-flow-fix-design-v1.3-20260815.md | 已归档 → archive/solutions-20260908/ |
| solutions/llm-radar-git-flow-fix-impl-v1.0-20260813.md（原存 solutions/，Q3 迁 reviews 桶） | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-git-flow-fix-review-v1.0-20260812.md | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-git-flow-fix-impl-audit-v1.0-20260813.md | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-git-flow-fix-ops-verify-v1.0-20260813.md | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-git-flow-fix-rereview-v1.2-20260812.md | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-git-flow-fix-v1.3-review-v1.0-20260815.md | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-git-flow-fix-v1.3-rereview-v1.1-20260815.md | 已归档 → archive/reviews-20260908/ |

### 族 B fork-converge（8 份）

| 源文件（原位 documents/…） | 处置 |
|---|---|
| solutions/llm-radar-git-fork-converge-design-v1.0-20260906.md | 已归档 → archive/solutions-20260908/ |
| solutions/llm-radar-git-fork-converge-design-v1.1-20260906.md | 已归档 → archive/solutions-20260908/ |
| solutions/llm-radar-git-fork-converge-design-v1.1-r2-20260906.md | 已归档 → archive/solutions-20260908/ |
| reviews/llm-radar-git-fork-converge-design-review-v1.0-20260906.md | 已归档 → archive/reviews-20260908/（Q3 改名：原 llm-radar-fork-converge-design-review-v1.0-20260906.md 补 git- 段） |
| reviews/llm-radar-git-fork-converge-design-rereview-v1.1-20260906.md | 已归档 → archive/reviews-20260908/（Q3 改名：同上补 git- 段） |
| reviews/llm-radar-git-fork-converge-design-rereview-v1.1-r2-20260906.md | 已归档 → archive/reviews-20260908/（Q3 改名：同上补 git- 段） |
| reviews/llm-radar-git-fork-converge-impl-audit-20260907.md | 已归档 → archive/reviews-20260908/（族 B 终审；Q3 改名：补 git- 段） |
| reviews/llm-radar-cl005-git-fork-merge-audit-20260902.md | 已归档 → archive/reviews-20260908/（Q3 改名：补 git- 段） |

### 族 C push-anti-overwrite（1 份）

| 源文件（原位 documents/…） | 处置 |
|---|---|
| reviews/llm-radar-push-anti-overwrite-audit-20260903.md | 已归档 → archive/reviews-20260908/ |

相关现行保留项（不归档）：`AGENTS.md`（仓库根，受保护指令文件；L190 描述需按 CL006 终态更新，待用户授权——DOC-1）、`cache/doc-consolidation/llm-radar-git-sync-extract.md`（gitignored 提炼产物）。
