# llm-radar 双端分叉自动收敛 — 复审报告 v1.1

> 日期: 2026-09-06
> 文件: documents/solutions/llm-radar-git-fork-converge-design-v1.1-20260906.md
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.lab
> 复审对象: 1985ca8 docs@llm-radar: git fork auto-converge design v1.1 fix RIG-1~6 (CL006)
> 上轮结论: v1.0 CONDITIONAL PASS 70/100 (B) — 6 🟡 (RIG-1~6) + 3 🟢 (O-1~3)
> review维度: 合理性 / 严格性 / 安全性
> closed_loop: LLM-RADAR-CL006
> 本轮: 仅评审，不 push

```
┌─ DESIGN RE-REVIEW ─────────────────────────────────┐
│  Document: llm-radar-git-fork-converge-design-v1.1 │
│  Version : v1.1                                     │
│  Commit  : 1985ca8                                  │
├─────────────────────────────────────────────────────┤
│  合理性   🟢 (根因/方案不变, v1.0 已代码级确认)      │
│  严格性   🟡 (6 RIG + 3 O 全修, 复评发现 3 新残余)  │
│  安全性   🟢 (v1.4 契约维持, 0 新攻击面)            │
│  结论     CONDITIONAL PASS — 85/100 (A 阈值线)      │
└─────────────────────────────────────────────────────┘
```

## 分叉实况复核 (2026-09-06)

- 本地 main = 1985ca8 (HEAD)，远端 origin/main = e01c6dd，merge-base = af48ced。
- `git rev-list --left-right --count origin/main...HEAD` = 3 / 5，即本地 ahead 5、远端 ahead 3。
- 设计 L41「本地 3 ahead / 远端 3 ahead」为 v1.0 评审时快照，现已增长（5/3）——设计 L95 已声明「执行前 fetch 以当时实况为准，不承诺固定 SHA」，RIG-3 修复对此类漂移已免疫。

## Fix Verification（逐项核对）

| # | v1.0 问题 | v1.1 修复 | 验证 |
|:-:|:----------|:----------|:----:|
| RIG-1 | overview.json 字段漂移（用 generated_at/错误计数键） | D1 改真实字段 `t` / `s.pr\|pe\|to\|ll\|ho` 重算 / `h` 并集去重按 d 降序 | ⚠️ 部分 — `t`/`s.*`/`p`/`h` 已改对（L119，实测 overview 键 `t`/`s`/`h` 一致），但遗漏 `v`/`r`/`rd` 三字段 → **RIG-7** |
| RIG-2 | 「复用 _merge_single」不成立 | 删除复用表述；定义 `_union_record()` 显式规则 + 单测 | ✅ L132 不复用声明 + 胜者规则三档（空值填补/时间胜出/字典序 tie-break）；`_merge_single` L1185 语义「new-wins+空填」描述准确 |
| RIG-3 | D0 硬编码 SHA/计数漂移 | 移除硬编码 SHA，改「fetch 后实况为准」+ 时间点快照 | ✅ L95 显式「执行前 fetch origin main 以当时实况为准」；L41/L108 均标注「评审实测」为时间点快照 |
| RIG-4 | docstring 未同步 | D3 两行显式纳入 `_sync_remote`/`_push_with_recovery` docstring | ✅ L172/L174 逐行列出；行号与源码实测一致（_sync_remote L271-297 / _push_with_recovery L349-387） |
| RIG-5 | partial 分支参数未锁定 | 锁定 partial push 失败走 `_converge_fork()` + dead-letter 映射 | ⚠️ 参数映射 ✅（`changelog_count:0`/`changelog_snapshot:[]` 与 `_write_dead_letter` L332-347 契约一致），但与 D2 脏工作区守护矛盾 → **RIG-8** |
| RIG-6 | 平局非确定 | tie-break 改 JSON 字典序（跨机确定），删「平局保留本地」 | ✅ L131 字典序 + Unicode 码点 + 数字转字符串；全文无「平局保留本地」残留（仅修订记录描述「已删」） |
| O-1 | hotspots 截断丢数据 | 目标 1 限定 4 实体维度；hotspots/changelog 声明有界截断例外 | ✅ L80/L133 声明到位 |
| O-2 | changelog 折叠 | 接受声明（display-only，每轮重生成） | ✅ L134 接受 |
| O-3 | docs scope 混用 | 维持 `@llm-radar` 现状说明 | ✅ L215 说明 |

## 新增发现（残余，需 v1.1-r2）

### 🟡 RIG-7 — overview.json 合并规则仍缺 3 字段 + `h` 截断未声明

D1 L119 overview.json 规则覆盖 `t`/`s.*`/`p`/`h`，但 `_write_overview`（collector.py L1358-1366）实际产出 **7 字段**：`v`（版本，恒 1）、`t`、`p`、`s`、`h`、`r`（质量门禁结果 `'success'/'failed'`）、`rd`（质量详情字符串）。D1 左侧括号枚举「顶层 t=生成时间 / s.*=计数 / h=头条」遗漏 `v`/`r`/`rd`。

- `r`/`rd` 非恒定值——跨端可能一侧 success 一侧 failed（质量门禁结果不同），未指定合并规则则并集后取值不确定，削弱「确定性/可审」承诺。
- 另 `h` 由 `_write_overview` 构造时 `[:3]`（L1356）仅 top-3，D1「并集去重保留两端头条」未声明最终截断到 3（并集最多 6 条 → 截 3）。

修复（各一行）：`v` 取任一侧（恒 1）；`r`/`rd` 随 `t` 取较新侧；`h` 补「并集去重按 d 降序截断至 3」。影响面 display-only，下轮 run 归正，但为规格完整性应补。

### 🟡 RIG-8 — partial→converge (D3 L176) 与 D2 步骤 3 脏工作区守护矛盾

RIG-5 修复声明 partial push 失败 → `_converge_fork()` 兜底。但实测 partial 模式运行顺序：

1. run() 始终写盘 `_save_snapshot`（L1164）+ `_write_overview`（L1168）；
2. `_auto_push(partial=True)`（L395-416）仅 `git add timestamp.json` + commit + push，snapshot.json / overview.json **保持未提交 dirty**；
3. push 失败触发 `_converge_fork()` → D2 步骤 3「工作区有未提交改动 → warn return」**直接拦截**。

后果：partial 分支的「push 失败兜底收敛」实为 no-op（除非该场景工作区恰干净，而 partial 模式恰不干净）。分叉仍会在下一轮 `_sync_remote` 收敛（自愈不破坏，仅推迟一轮），但设计描述的 partial 兜底路径不成立，D2/D3 两节互相矛盾，实现者照字面落地会得到死代码。

修复：D3 L176 注明 partial 触发收敛前须先处理 dirty snapshot/overview（如 `git checkout -- snapshot.json overview.json` 丢弃本轮未提交数据——该数据未 push、下轮重生成，丢弃无损），或显式声明该兜底仅在干净工作区生效、否则延后一轮由 `_sync_remote` 收敛。

### 🟡 RIG-9 — D1 规则 2「时间较新侧胜出」未指定多时间字段优先级

D1 L130 胜者规则列出时间类字段 `last_event_date / updated_at / date`「任一存在」，但 providers 记录同时含 `last_event_date` + `updated_at`（实测 snapshot 字段列表），hotspots 含 `date` + `updated_at`。当两侧这些字段对「哪侧更新」判断相悖时（A 侧 last_event_date 新但 updated_at 旧、B 侧反之），「较新侧」无定义 → 跨机结果不确定，削弱 RIG-6 确立的确定性。

且 `updated_at` 是 run 时间戳（非事件时间），用于「新数据胜」语义易误：两侧同 id 同数据仅 run 时刻不同，`updated_at` 不同会误导「较新侧」判定（虽同值无害，但叠加字段差异时方向可能错误）。

修复：显式优先级 `last_event_date` > `date` > `updated_at`（`updated_at` 仅作无语义日期的 fallback），单测补「多时间字段冲突」断言。

## 安全事项

🟢 与 v1.4 安全契约一致性维持（复评要点 2）：

- 全程无 force push（D2 L162）；D3 L175 删 rebase 成功后 `--force-with-lease` 改普通 push，与 v1.0 SEC-1 结论一致（rebase 成功 = 本地已含远端，ff 即可）。
- 白名单外冲突 abort 人工、异常不抛不阻断采集、finally 清理残留态（D2 L158/L164），延续 v1.4 边界。
- 0 注入面：`_converge_fork` 走 `_git_run` list-form、固定 merge 消息、JSON 读写无代码执行（v1.0 SEC-3 结论不变）。
- RIG-7/8/9 均非安全缺陷，无新攻击面、无凭据暴露、无提权面。

## 评分

v1.0 扣分项（RIG-1~6 共 -30）已全部修复 → base 归 100。复评仅减新增项：

| 发现 | 严重度 | 扣分 |
|:-----|:------:|:----:|
| RIG-7 overview.json 缺 v/r/rd + h 截断 | 🟡 | -5 |
| RIG-8 partial→converge 与脏工作区守护矛盾 | 🟡 | -5 |
| RIG-9 时间字段优先级未定 | 🟡 | -5 |
| 合计 | | **-15** |

得分: **85 / 100** → 恰在 A 阈值线，但因含 3 个未决 🟡（需 v1.1-r2 收敛）判 CONDITIONAL PASS。

## 结论

**CONDITIONAL PASS (85/100)**

v1.0 的 6 🟡 (RIG-1~6) + 3 🟢 (O-1~3) 已逐项修复且修复质量整体到位（字段名改对、_union_record 规则独立、字典序 tie-break 消除跨机非确定、docstring/partial 映射逐行锁定、行号与源码实测一致）。安全契约与 v1.4 一致性维持，无新安全缺陷。

复评发现 3 个新 🟡 残余（RIG-7/8/9）：均为规格精度/一致性缺口（非结构性缺陷、非安全缺陷），但 RIG-8 是 D2/D3 两节的真实矛盾、RIG-7/RIG-9 削弱「确定性/可审」承诺，需 ops 出 v1.1-r2 一并收敛后复审转 PASS。三者均可各 1~2 行修复，不推翻设计。

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | RIG-7：D1 overview 规则补 `v`（任一侧/恒1）、`r`/`rd`（随 `t` 取较新侧）、`h` 截断至 3 | 严格性 🟡 |
| □ | RIG-8：D3 partial→converge 注明先处理 dirty snapshot/overview（checkout 丢弃或声明延后一轮） | 严格性 🟡 |
| □ | RIG-9：D1 规则 2 明确时间字段优先级 last_event_date > date > updated_at + 单测补多时间字段冲突 | 严格性 🟡 |
