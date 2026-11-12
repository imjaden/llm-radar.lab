# 转交 · `hm loop verify` 不落盘步骤件 ⇒ 「done 但无复盘」的系统性缺口

生成于 2026-11-12，from llm-radar.lab → hermes-manager（`hm` CLI / 1A 看板）。

## 1. 现象（本仓实测）

`hm loop verify <编号>` 只做两件事：把 draft 的 `- [ ]` 勾成 `- [x]`、重刷 `TODO-handoff.md` 机器段。
**它不生成 6 步 JSON，也不生成 retro 文档**。结果是一批条目处在
「台账 `✅ [6/6]`、`evidence_state=claimed`，实物 0 件」的状态：

```
$ ls cache/closed-loop | grep -E "CL01[3-7]"      # 空（一条都没有）
$ hm loop artifacts LLM-RADAR-CL014 --global
  ① 报告/产物 ❌   ② review-log ❌   ③ .review-level ❌   ④ 步骤 JSON 0/6
```

`CL007–CL017` 共 11 条**全部如此**。看板判据（`scripts/web-console/anomaly.py:178-184`）是
`"[6/6]" in progress` + `require_retro` + `retro_path` 空/文件不存在 ⇒ `doc-missing`（critical）；
而 `retro_path` 只有在 `_resolve_in_project()` 能拿到**closed-loop 步骤 JSON** 时才可能算出
（`lib_loop.py:2917 _enrich_item_detail` → `_compute_steps` → `_resolve_retro_md`）。
⇒ 无 JSON 的条目**必然**被判 doc-missing，且窗口一滑就会一条条被点名。

## 2. 影响

- 看板每轮都会重新报同一批历史条目（本次工单点到 `CL017` / `CL009`，只是它们最近更新）。
- 走「直改源码 + verify」这条快捷路径的条目**天生不再产出实物**，积压只会增长。

## 3. 建议（任选，A 与 B 不冲突）

- **A｜verify 增加落盘出口（推荐）**：`hm loop verify <编号> [--retro <md 路径>] [--steps-json <dir>]`。
  给了就校验并落盘；没给则在 verify 末尾打印一行提示
  `⚠️ 未提供 retro，看板会标 doc-missing`。不改变现有行为（无参数时零写入）。
- **B｜语义侧区分「声明」与「实物」**：`kind: direct-fix`（或类似标记）的条目在看板上按
  `require_retro=false` 处理，或把 `[6/6]` 的进度列改标 `[6/6 声明]` —— 让「有代码没文档」不再冒充「闭环完成」。
- **C｜最小兜底**：`hm loop verify` 自动生成 retro 骨架（`.json` + `.md`，字段含 `loop/step/date/chain/learnings/pending`，
  chain 取该编号最近的提交），内容由人补；看板即可正常通过，同时留痕「这是自动骨架」。

## 4. llm-radar 侧已做的补救（本次，不动别的仓）

- 为 `CL007–CL017` 补了 11 对 retro（`cache/closed-loop/20261112-llm-radar-ops-LLM-RADAR-CL0xx-retro.{json,md}`），
  内容按各自提交链 + 测试 + 真机证据写，链上 `commit`/`evidence` 字段齐全。
- 为 `CL009` / `CL017` 另补 5 个步骤 JSON（design / design-review / dev-impl / ops-check / impl-audit），
  并各写一篇可读复盘：`documents/reviews/llm-radar-cl00X-…-retro-v1.0-20261112.md`。
- 结果：`hm loop artifacts` 对这两条 ① ✅ / ④ 6/6；`hm loop list --done --global --json` 的 `retro_path` 非空。

## 5. 本仓流程侧的临时约定（等 A/B 落地后可撤）

凡「直改源码型」条目，在 `hm loop verify` 之前先落一对 retro 到 `cache/closed-loop/`，
再跑 verify —— 否则看板次日会点名。该约定已写进 `TODO-handoff.md §2`。
