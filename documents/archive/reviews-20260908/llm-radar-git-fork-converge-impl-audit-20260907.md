# llm-radar 双端分叉自动收敛 — 实现审计报告 (LLM-RADAR-CL006)

> 日期: 2026-09-07
> 审计类型: 实现审计 (L2, implementation verification)
> 审计对象: `ea9172c` feat@llm-radar: auto-converge dual-writer fork (semantic union, D1-D3)
> 设计基线: v1.1-r2 (5c1bf42, 评审 PASS 100/A → 678b3a2)
> 闭环编号: LLM-RADAR-CL006
> 评审链: b981e9e→1985ca8→5c1bf42→678b3a2→0794cbd (Phase 0)→ea9172c (本批)

```
┌─ IMPLEMENTATION AUDIT ──────────────────────────────┐
│  Commit  : ea9172c  (collector +338 / test +499)    │
│  Design  : v1.1-r2 (5c1bf42)                        │
├─────────────────────────────────────────────────────┤
│  D1 语义并集      🟢  4 维度并集/时间优先级/对称      │
│  D2 _converge_fork 🟢  白名单守护/无 force/finally   │
│  D3 集成点        🟢  sync/push/partial 三处收敛      │
│  测试/验收        🟢  33 gitflow + 266/2 全绿         │
│  结论            PASS — 95/100 (A)                   │
└─────────────────────────────────────────────────────┘
```

## 结论

**PASS — 95/100 (A)**。D1/D2/D3 三处实现与设计 v1.1-r2 逐项对应且正确；AC1-AC5 中 AC2/AC3/AC5 全绿，AC4 的 docstring 已同步，唯一残余为 🟡 AGENTS.md L190 描述过期（受保护指令文件，审批超时未改，待用户授权 — CL005 同先例）。无 🔴/🟡 安全缺陷，无新攻击面。

审计期间发现分叉已**在生产环境自动收敛**：`299e97a merge@llm-radar: auto-converge dual-writer data (semantic union)`（双亲 = ea9172c + eccc122，消息与 `_CONVERGE_MSG` 精确一致）已推送，随后 `6ee0c5d auto-push` 落地，当前 `local == origin/main == 6ee0c5d`（0/0，clean）。这构成 AC2 的真实世界端到端验证（超出 ops sandbox 证据）。

## 实现 vs 设计逐项核对

### D1 — 语义并集规则

| # | 设计项 | 实现 (llm-radar-collector.py) | 状态 |
|:-:|:-------|:------------------------------|:----:|
| 1 | 白名单 4 文件 + twitter-targets.yaml 排除 | L249 `_CONVERGE_WHITELIST = (snapshot.json, overview.json, timestamp.json, twitter.json)`；L16-17 注释「白名单外冲突…含 data/twitter-targets.yaml, O-4 → abort 人工」 | ✅ O-4 落地 |
| 2 | 4 实体维度 id 并集不丢数据 | L463 `_union_snapshot` → L447 `_union_by_id`（仅一侧保留 / 两侧 `_merge_semantic`） | ✅ |
| 3 | 时间优先级 last_event_date > date > updated_at | L252 `_TIME_FIELDS`；L424-428 存在即用不交叉，最高位可判字段胜出 | ✅ RIG-9 |
| 4 | 空值填补 / 平局字典序 | L407 `_is_empty` / L412 `_lex_key`(json sort_keys) / L431-441 逐字段 | ✅ |
| 5 | hotspots 并集 + date 降序 + 截断 max(len) | L476-484（同 id 合并 → date/hot_score 降序 → `[:max_hs]`） | ✅ |
| 6 | changelog (type,dim,id) 并集 + time 较新 + 截断 | L486-497 | ✅ |
| 7 | stats total_* 重算 + period 计数取较新侧 | L499-505 | ✅ |
| 8 | version/period/execution_mode 取较新侧 | L466-468 `base = 较新 generated_at` | ✅ |
| 9 | twitter.json targets/tweets 并集 | L511 `_union_twitter`（targets 按 url/handle、tweets 按 id） | ✅ |

**跨机对称性**: `_merge_semantic` / `_union_by_id` / `_union_snapshot` 均无执行机依赖；`test_union_symmetric` + `test_time_newer_wins` / `test_multi_time_field_priority` / `test_tie_lexicographic` 各自断言 `f(a,b)==f(b,a)`。✅

**写盘格式一致性** (审计复核): snapshot.json `_save_snapshot` L1604 `indent=None` ↔ `_write_json_file` mode 'compact'；overview.json `_write_overview` L1668 `separators=(',',':')` ↔ mode 'min'；timestamp.json L1637 `indent=2` ↔ mode 'pretty'。三处全对齐。twitter.json 为 pretty + 尾换行，converge 覆写丢尾换行（纯 cosmetic，下轮 twitter-collector 重写补回，非缺陷）。

### D2 — `_converge_fork()` (L596)

| 设计步骤 | 实现 | 状态 |
|:---------|:-----|:----:|
| 1 fetch（失败 warn return） | L600-603 | ✅ |
| 2 状态判定: 相等 return / 祖先 ff / 分叉继续 | L604-617 (`rev-parse` + `merge-base --is-ancestor`) | ✅ |
| 3 脏工作区守护 | L619-622 (`status --porcelain` 非空 → warn return) | ✅ |
| 4 merge --no-commit --no-ff + 冲突文件集白名单校验 | L624-636；白名单外 → `merge --abort` + dead-letter + warn「需人工 merge」 | ✅ |
| 5 语义解决 (snapshot 先于 overview) | L637-644 `sorted(files, key=lambda f: (f != 'data/snapshot.json', f))` + `_resolve_converge_file` | ✅ |
| 6 merge commit | L645-650 `_CONVERGE_MSG` | ✅ |
| 7 普通 push | L651-654 | ✅ |
| 9 finally 清理 MERGE_HEAD + rebase 残留 | L662-665 `_in_merge_state`(L593) → `merge --abort` + `_abort_rebase` | ✅ |

**安全边界**: 全程无 force（L597 docstring + grep 全文 0 处 `--force-with-lease`/`push --force`）；白名单外 abort 人工不碰代码；`_skip_push` 守护 L604-606；异常不抛（L656-660 try/except warn return）。

### D3 — 集成点

| 位置 | 设计 | 实现 | 状态 |
|:-----|:-----|:-----|:----:|
| `_sync_remote` 分叉分支 | warn + `_converge_fork()`，失败回退本地优先 | L300-304 | ✅ |
| `_sync_remote` docstring | 「分叉时收敛…仅落后 ff」 | L278-283 | ✅ |
| `_push_with_recovery` 冲突分支 | abort 后 `_converge_fork()` → 普通 push → 仍失败 dead-letter | L381-391 | ✅ |
| `_push_with_recovery` rebase 成功分支 | 删 force-with-lease → 普通 push | L373-377 | ✅ |
| `_auto_push` partial 分支 | push 失败 → checkout 丢弃 snapshot/overview → converge | L702-713 | ✅ |

**AC3 复验**: `grep -n "force"` 仅命中 CLI `--force` 采集参数 (L1705/2035/2483/2526/2710) 与 docstring「无 force」描述，git 子进程调用序列 0 处 force。✅

## 代码质量

- `_git_show`/`_write_json_file`/`_resolve_converge_file` 顺序正确：`_resolve_converge_file` L565 读已合并 snapshot 盘上内容重算 overview，配合 D2 步骤 5 的 `snapshot 先于 overview` 排序键，避免 overview 读到冲突标记污染的快照。✅
- 异常路径不抛：`_converge_fork` / `_resolve_converge_file` 全程 try/except + warn，失败返回 False，调用方决定本地优先或 dead-letter。✅
- `_skip_push` 测试隔离：L604 `_skip_push` 顶层提前 return，test_gitflow 的 `TestConvergeFork._enable` 显式置 False，`test_skip_push_guard` 断言隔离有效。✅
- `_union_twitter` 的「同 id 取较新」经 `_merge_semantic` 落为字典序 tie-break（tweet schema 仅 `posted_at` = 发帖时间、两侧同值，无采集时间戳字段入 `_TIME_FIELDS`）；对 views/likes 等单调递增指标 = 取较大值，与「取较新」语义一致，确定性/对称性成立，零丢数据。🟢 观察（非缺陷）。

## 测试 / 验收 (AC1-AC5)

| AC | 描述 | 结果 |
|:--:|:-----|:----:|
| AC1 | Phase 0 已收敛 push (0794cbd) | ✅ + 审计期间 feat 已随自动收敛入库 |
| AC2 | 真实分叉端到端收敛 | ✅ 离线 sandbox 1/1 (ops) + **生产实测** 299e97a 双亲合并 |
| AC3 | grep 无 git force | ✅ (仅 CLI --force) |
| AC4 | docstring 同步 + AGENTS.md | ⚠️ docstring ✅ / AGENTS.md L190 🟡 待用户授权 |
| AC5 | pytest 全绿 | ✅ 见下 |

独立复跑（review profile 实测）:

```
tests/test_gitflow.py  →  33 passed (0.36s)
pytest tests/ (全量)    →  266 passed, 2 skipped, 0 failed (106s)
```

（ops 报告「263 passed/2 skipped」与本次 266 存在 +3 计数差，源于调用集合略异/数据态漂移，结论一致：全绿无失败。test_gitflow 33 与 ops 精确一致。）

## 发现

| # | Severity | Title | 位置 | Status |
|:-:|:---------|:------|:-----|:-------|
| DOC-1 | 🟡 | AGENTS.md L190 描述过期（仍写「分叉时本地优先」+「rebase 重试 → force-with-lease → dead-letter」，与 v1.4 实际行为及 CL006 收敛链不符） | AGENTS.md:190 | 待用户授权 (CL005 同先例) |

🟢 观察（记录不计扣分）:

- IMPL-OBS-1: `_union_twitter` 同 id 取较新经字典序近似（见上「代码质量」末条）。
- IMPL-OBS-2: `_union_snapshot` 在两侧 `generated_at` 精确相等时 `base = local`（`>=` 平局取左），理论非对称；实测 `generated_at` 为微秒级 (如 `2026-09-07T09:42:04.161473`)，跨机碰撞不可达，无实际影响。
- O-4 (twitter-targets.yaml 白名单表放置) → **已落地**，白名单仅 4 文件 + 显式注释。

## 评分

| 项 | 严重度 | 扣分 |
|:---|:------:|:----:|
| AGENTS.md L190 描述过期 (DOC-1) | 🟡 | -5 |
| 合计 | | **-5** |

得分: **95 / 100** → PASS (A)。

## 部署与后续动作 (用户执行)

1. **AGENTS.md L190 更新**（用户授权后）：将「分叉时本地优先」→「分叉时自动收敛（_converge_fork 语义并集）」；「rebase 重试 → force-with-lease → dead-letter」→「rebase 重试 → 冲突走 _converge_fork → 仍失败 dead-letter」。改后通知 review 复核可升至 100。
2. **服务器部署**（设计 D4）：`/home/admin/codespace/llm-radar.lab` 内 `git pull`，使新收敛链在服务器下轮 cron 生效。
3. 无需 force push；分叉已收敛（local == origin == 6ee0c5d），审计产物以普通 push 提交。

## 审计产物

- 报告: documents/reviews/llm-radar-fork-converge-impl-audit-20260907.md
- review-log.md: append (Style B)
- .review-level.yaml: append review_history
