# llm-radar 双端分叉自动收敛 — review报告 v1.0

> 日期: 2026-09-06
> 文件: documents/solutions/llm-radar-git-fork-converge-design-v1.0-20260906.md
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.lab
> 待 push commit: b981e9e docs@llm-radar: git fork auto-converge design v1.0 (CL006)（本轮仅评审，不 push）
> review维度: 合理性 / 严格性 / 安全性
> closed_loop: LLM-RADAR-CL006

```
┌─ DESIGN REVIEW ────────────────────────────────────┐
│  Document: llm-radar-git-fork-converge-design-v1.0 │
│  Version : v1.0                                     │
│  Commit  : b981e9e                                  │
├─────────────────────────────────────────────────────┤
│  合理性   🟢 (根因代码级成立, 方案方向正确)          │
│  严格性   🟡 (6 个遗漏/矛盾)                        │
│  安全性   🟢 (无缺陷; v1.4 意图保留并强化)          │
│  结论     CONDITIONAL PASS — 70/100 (B)             │
└─────────────────────────────────────────────────────┘
```

## 数据验证

| 验证项 | 方法 | 结果 |
|:-------|:-----|:-----|
| 分叉拓扑：两侧独立链均起于 af48ced | `git fetch origin main` + `git merge-base HEAD origin/main` | ✅ merge-base = af48ced；本地 ahead 3（8eee136→7d0a990→b981e9e）、远端 ahead 3（d0ad26e→08cae7d→e01c6dd） |
| 每次 auto-push 只动 3 个生成文件 | `git show <sha> --stat`（8eee136/7d0a990/d0ad26e/e01c6dd） | ✅ 4 笔均仅 snapshot.json + overview.json + timestamp.json |
| 实体记录含 `id`（并集规则前提） | 读 data/snapshot.json 结构 | ✅ providers/people/tools/llms/hotspots 均含 `id`；changelog 含 `type/dimension/id/time`；stats 含 `total_*/new_this_period/updated_this_period/removed_this_period` |
| 真实并集佐证：providers 应=101 | 对比本地 vs `git show origin/main:data/snapshot.json` 的 id 并集 | ✅ 实测 local=100 / remote=100 / union=**101** / local_only=1 / remote_only=1（与设计 L101 完全一致） |
| hotspots 并集实况 | 同上 | ⚠️ union=**92** > max(local=90, remote=90)，按 D1 截断会丢 2 条一端独有热点（见 RIG/观察） |
| overview.json 字段名 | 读 overview.json 结构 | ⚠️ 时间字段为 `t`（无 `generated_at`）；计数键 `s.pr/pe/to/ll/ho`；头条热点 `h`（见 RIG-1） |
| timestamp.json 字段 | 读 timestamp.json | ✅ `generated_at`/`server`/`hostname`/`period`/`version` 均存在，D1 规则成立 |
| 平台感知调度 | grep features.md | ✅ L82-83「跨平台执行 llm-radar-run.sh」「平台感知调度 Darwin 每小时 / Linux 7,14,21（6h 防抖）」 |
| 分叉死锁证据 | grep data/collector.log | ✅ 全量 110 次「远端分叉本地优先」+ 23 次「残留 rebase 状态」+ 6 次「dead-letter」+ 5 次「双向数据分叉需人工 merge」；设计「13+ 次」为保守低估 |
| git 身份 | `git log -1 --format` per commit | ✅ Mac = `t <t@t.com>`、服务器 = `Jaden.Li <jaden.li@jaden.tech>` |
| v1.4「禁 force」决策 | `git show 074ac1b --stat` | ✅ 「disable force-with-lease on rebase conflict (CL005 fork prevention v1.4)」 |
| anti-overwrite 3 用例存在 | grep tests/test_gitflow.py | ✅ `test_rejected_rebase_force_lease`(L82) / `test_rejected_rebase_conflict_dead_letter`(L99) / `test_rebase_conflict_no_force_dead_letter`(L135)，D3 需改写语义 |
| `_sync_remote` 调用点 | grep llm-radar-collector.py | ✅ 唯一 caller = run() L1745（先于 `_think` L1748 节流），heal `run --force` 0 新数据可清分叉（目标4成立） |
| force-with-lease 仅存一处 | grep `force-with-lease` | ✅ 仅 L367（rebase 成功分支，D3 删除目标）；删除后 AC3「grep 无 force」可达成 |
| 历史人工 merge 收敛 | `git log --merges` | ✅ 9d6bd0f / b5de3fe / 3633cf4 三次「reconcile fork」merge commit |
| 命名/commit 合规 | 文件名 + frontmatter + commit | ✅ 文件名 kebab-case 无点无下划线；frontmatter v1.0 与文件名一致；commit `docs@llm-radar:` type@scope（观察 O-3 记录 scope 混用） |

## 合理性评估

| # | 项 | 结果 |
|:-:|:---|:-----|
| REA-1 | 根因分析（双实例双写 + 整文件重写 + 冲突即 abort 死锁） | ✅ 代码级成立，证据链完整（见数据验证） |
| REA-2 | 方案选型（语义并集替代 force/rebase 收敛） | ✅ 并集可交换、可幂等，方向上消除「覆盖」而非「规避」；与 v1.4 禁 force 精神一致且更强 |
| REA-3 | 非目标（不做单写者/不改调度/不改业务逻辑） | ✅ 守界良好，D3 改动全部落在 git 层，未侵入 fetch/extract/merge 业务 |
| REA-4 | 目标4「heal 自愈」可达性 | ✅ `_sync_remote` 在 `_think` 节流前收敛，`run --force` 0 新数据场景可清分叉 |

合理性 🟢，无阻塞项。根因与方案均有实证支撑。

## 严格性评估

| # | 项 | 结果 |
|:-:|:---|:-----|
| RIG-1 | overview.json 合并规则字段漂移 | ❌ 见下 |
| RIG-2 | 「复用 `_merge_single`（语义同）」不成立 | ❌ 见下 |
| RIG-3 | D0 Phase 0 具体 SHA/计数已漂移 | ❌ 见下 |
| RIG-4 | `_sync_remote` 契约变更未同步 docstring | ❌ 见下 |
| RIG-5 | partial 分支复用 `_push_with_recovery` 参数映射未锁定 | ❌ 见下 |
| RIG-6 | 「平局保留本地」与「确定性（评审可审）」自相矛盾 | ❌ 见下 |

严格性 🟡 — 6 个遗漏/矛盾，均为可低成本修正的规格精度问题，无结构性缺陷。

## 安全事项

🟢 SEC-1 — 删除 rebase 成功后多余的 `--force-with-lease` 是安全的（确认项，非缺陷）

已验证：`pull --rebase` 成功 = 本地 HEAD 已含 origin/main 全部 commit，本地在此基础上叠加自身 commit，普通 `push` 即 fast-forward，无需 force。删除后缩小 force 风险面，AC3「全 git 调用序列 grep 无 force」可达成。**结论：安全，且是改进。**

🟢 SEC-2 — v1.4「防覆盖禁 force」意图被保留并强化

语义并集替代 force 后，收敛不覆盖任一端数据（并集只增不减），比 v1.4 的「冲突即停、人工 merge」更进一步实现自愈，安全性更强而非削弱。白名单外冲突 abort 人工的边界完整延续 v1.4。

🟢 SEC-3 — 无新攻击面

`_converge_fork` 全程 `_git_run` list-form（无 shell 拼接）、固定 merge commit 消息（无用户输入进入命令上下文）、语义合并读写 JSON 无代码执行、finally 清理残留态、异常不抛不阻断主流程。Phase 0 合并脚本为一次性 /tmp 脚本不入库。**0 注入面，0 凭据暴露，0 提权面。**

安全性 🟢，无 🔴 无 🟡。

## 评分

| 发现 | 严重度 | 扣分 |
|:-----|:------:|:----:|
| RIG-1 overview.json 字段漂移 | 🟡 | -5 |
| RIG-2 `_merge_single` 语义复用不准确 | 🟡 | -5 |
| RIG-3 D0 Phase 0 SHA/计数漂移 | 🟡 | -5 |
| RIG-4 `_sync_remote`/`_push_with_recovery` docstring 未同步 | 🟡 | -5 |
| RIG-5 partial 分支复用参数未锁定 | 🟡 | -5 |
| RIG-6 平局 tie-break 跨机非确定 | 🟡 | -5 |
| 合计 | | **-30** |

得分: **70 / 100** → Rating: **B**

## 结论

**CONDITIONAL PASS (B, 70/100)**

根因代码级成立、方案（语义并集替代 force）方向正确且安全契约强于 v1.4，非目标守界良好，测试/验收规划合理（anti-overwrite 3 用例改写语义方向正确，AC1~AC5 可验收）。阻塞项为 6 个 🟡 严格性缺口——均为规格精度/字段名/文档同步/开放决策类，可低成本在 v1.1 修复，无需推翻设计。修复后由 review 复评。

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | RIG-1：overview.json 合并规则改用真实字段（时间取 `t`；`s.pr/pe/to/ll/ho` 计数由合并后 snapshot 重算；`h` 头条热点明确取较新侧或重算） | 严格性 🟡 |
| □ | RIG-2：D1 字段级合并语义改为「逐字段取较新（按 last_event_date/updated_at）一侧 + 空值填补」，删除「复用 _merge_single」表述；明确「互为 old/new 各跑一次」的合并方式 | 严格性 🟡 |
| □ | RIG-3：D0 Phase 0 移除硬编码 SHA/「2 ahead/2 behind」，改为「执行时以 origin/main HEAD 为准」，或标注为时间点快照 | 严格性 🟡 |
| □ | RIG-4：同步 `_sync_remote`（L272-275「仅同步不 push」→ 分叉时收敛含 push）与 `_push_with_recovery`（L350/L376-378 force-with-lease 描述）docstring/注释 | 严格性 🟡 |
| □ | RIG-5：锁定 partial 分支是否复用 `_push_with_recovery` 及 changelog/dead-letter 参数映射（无 changelog 时 dead-letter 写什么） | 严格性 🟡 |
| □ | RIG-6：tie-break 改固定侧（建议「平局取 origin/main 侧」或字典序），消除跨机非确定性，兑现「确定性（评审可审）」 | 严格性 🟡 |
| □ | O-1：目标1「不丢任一端数据（并集）」限定于 4 实体维度；hotspots/changelog 声明为「并集 + 有界截断」例外（实测 hotspots union=92→截断 90） | 观察 🟢 |
| □ | O-2：changelog 并集键 (type,dimension,id) 会折叠同 id 同 type 的多次 update，确认是否接受（display-only） | 观察 🟢 |
| □ | O-3：design commit 用 `docs@llm-radar` 与早期 `docs@design`（CL-SEC19/20、CL005）混用，确认本仓统一 scope 或维持现状 | 观察 🟢 |
