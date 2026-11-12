# 转交 · `hm loop exempt` 子串 glob 误判（阻塞 CL-SEC11 豁免）

生成于 2026-11-12，from llm-radar.lab → hermes-manager（`hm` CLI）。

## 1. 现象

按 `documents/handoff/20261112-to-llm-radar-stale-loops-triage.md` §3 执行第一条：

```
hm loop exempt CL-SEC11 --reason "…" --evidence e4f11c1
```

返回：

```
❌ 编号 CL-SEC11 在多个仓命中（hermes-manager、llm-radar）⇒ 请用带项目前缀的编号
❌ 编号定位不到项目: CL-SEC11（需 <项目>-CL<编号> 形态, 或该仓闭环目录里有此编号产物）
```

带前缀的三种写法全部同样失败（`LLM-RADAR-CL-SEC11` / `llm-radar-CL-SEC11` / `LLM-RADAR-SEC11` —— 前两者被大写归一成同串）。

## 2. 根因（读 `scripts/lib_loop.py`，只读）

1. `_project_for_number()` 只认 `_RE_NUM_PROJ = ^([A-Z][A-Z0-9-]*)-CL\d{3,}$` —— **`CL\d{3,}` 要求 3 位以上数字**，`CL-SEC11` 的 `SEC11` 是 2 位，任何加前缀的写法都落不到前缀判定，只能走闭环目录扫描。
2. 扫描用 `_number_artifact_candidates()` → `_RE_ID_TAIL` 取尾段核心 `SEC11`，再用 `glob(f"*{c}*.json")` 匹配。**子串匹配** ⇒ hermes-manager 自己的 `cache/closed-loop/20260822-hermes-manager-ops-SEC118-*.json` 也被 `*SEC11*.json` 命中，于是「两仓都命中」被判成歧义。
3. 该「多仓命中即拒绝」是 fail-closed 的**正确**设计（不猜），但触发条件是误报：`SEC11` 是 `SEC118` 的前缀。

llm-radar 侧真实产物（唯一真源）：`cache/closed-loop/20260823-llm-radar-ops-CL-SEC11-{design-review,design-rereview,dev-impl,converge-audit,converge-tail-recheck}.json`。

## 3. 影响

`CL-SEC11`（llm-radar，`stale_kind=missing-artifacts`，证据 `e4f11c1` = `audit@review: … LR-SEC-015/016 Resolved (CL-SEC11)`）**无法豁免**，停滞台账停在 1 条。同日 `LLM-RADAR-CL006` 已用 `8ee4e8a` 豁免成功（该编号 3 位，不受影响）。

## 4. 建议修法（hermes-manager 侧，任选其一）

- **A（推荐）**：`_number_artifacts()` 的 glob 改成**边界匹配**：文件名段必须以候选编号结尾或后接 `-`，例如
  `glob(f"*{c}-*.json")` ∪ `glob(f"*{c}.json")`，再对 stem 做 `re.search(rf"(^|[-_]){re.escape(c)}($|[-_])", stem)` 回验。
- **B**：命中多仓时，若某仓命中的文件 stem 里候选编号只作为更长编号的前缀（如 `SEC11` ⊂ `SEC118`），降权/剔除该命中再判定。
- **C（兜底）**：`hm loop exempt` 增加显式 `--project <title>` 覆盖解析（绕过编号推断）。

## 5. llm-radar 侧当前处置

- 未改动 hermes-manager 任何文件；`CL-SEC11` 保持 `stale`，在 `cache/draft/TODO-20261112.md` 登记为 `BLOCKED / kind: cross-repo`。
- 修好后本仓只需一条命令收口：

```bash
cd ~/CodeSpace/llm-radar.lab
hm loop exempt CL-SEC11 \
  --reason "历史任务（2026-08 批次）：方案、ops 核查、复盘件未落盘，工作已并入主干（e4f11c1）" \
  --evidence e4f11c1
```
