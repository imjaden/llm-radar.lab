# P7 AGENTS.md gate 口径对齐审计 — 报告 v1.0

- **日期**: 2026-09-09
- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2
- **范围**: commit 7fab719 `docs@agentsync: AGENTS.md gate 口径对齐 CL005 + wrapper 表述修正 (DOC-3/SEC-1/GOV-1)`
- **Verdict**: ✅ PASS — 100/100 (A)
- **findings_total**: 0 / **findings_open**: 0

## 结论

单文件文档提交 (AGENTS.md, 6+/6-)，将质量门禁与 wrapper 两处表述对齐到源码实况，
并关闭 CL005 实现审计遗留的 DOC-3（AGENTS.md 待用户改）。五条审计项全部通过，无安全发现。

## 审计项核验

| # | 审计项 | 结果 |
|---|--------|------|
| 1 | diff 范围与回执一致：仅 AGENTS.md, 6+/6-；无 -A；无其他文件 | ✅ |
| 2 | 口径对源码：`_verify` L1746-1796 / partial L1481-1482+L680-717 / wrapper L78-80 | ✅ |
| 3 | 表述无歧义、无与 AGENTS 其他段冲突（L191/L54/L196 未动且准确） | ✅ |
| 4 | 工作树 clean；ahead 仅 7fab719（无 auto-converge 插入） | ✅ |
| 5 | 验收登记 review-log/.review-level + push origin main（ls-remote 核验） | ✅ |

## 逐项实证

### 1. diff 范围

- `git show 7fab719 --stat`: `AGENTS.md | 12 ++++++------`, 1 file changed, 6 insertions(+), 6 deletions(-)。
- `git show 7fab719 --name-status`: 仅 `M AGENTS.md`。无 -A 混入，无其他文件。

### 2. 口径对源码

`_verify()` 硬阻断（llm-radar-collector.py L1746-1796）：

- `if not entities: return ['实体提取为空']` (L1756-1757) → entities empty 阻断 ✅
- `entity_count == 0 → '实体提取为空（4 维度全 0）'` (L1776-1778) → 4 实体维度全 0 阻断 ✅
- `median_age > 168 → '事件中位数新鲜度 > 168h'` (L1772-1773) → 中位数 >168h 阻断 ✅
- `len(hotspots) < 3 → warnings.append` (L1780-1782) → 热点 <3 仅 warning ✅
- URL 质量 (L1783-1790) + key_people (L1792-1794) → 均 warnings ✅

与 AGENTS.md L145/L146 逐字对应。

partial 模式（L1481-1482 + `_auto_push` L680-717）：

- `self._auto_push(changelog, partial=not quality_ok)` (L1482) ✅
- partial 分支仅 `git add timestamp.json` + commit + push (L689-704)；`CalledProcessError` → `checkout -- data/snapshot.json overview.json` (L710-711) → `_converge_fork()` (L712) → dead-letter (L715)。
- 注释 `CL006 v1.1-r2 (RIG-5/8)` (L706)，与 `_converge_fork` docstring `D2, CL006 v1.1-r2` (L600) 一致。
- 与 AGENTS.md L147「commits and pushes ONLY timestamp.json … discard quality-failed artifacts → `_converge_fork`」逐字对应。

wrapper 实况（cache/system-command/llm-radar-wrapper.sh）：

- `~/.local/bin/{llm-radar,lr}` 均为 symlink → `cache/system-command/llm-radar-wrapper.sh`（实测 `ls -la` 双软链一致）。
- L78-80 = `.env` 加载段：`PROJECT_ROOT` 定位 + `[ -f "$PROJECT_ROOT/.env" ] && set -a && source "$PROJECT_ROOT/.env" && set +a`，位于 `exec $interpreter ...` (L101) 之前 →「exec 前加载 .env」准确。
- `cache/` 整目录 gitignored（.gitignore:15），`git check-ignore` 命中 wrapper 路径。
- 仓库内无 wrapper 模板：`git ls-files` 无 `.tmpl`；`cache/cli-registry/` 空目录。SEC-1「曾标 wrapper.sh.tmpl 实为 .env 误副本，已删」与 review-log CL005 wrapper 审计 (sha256 相同、审计中删除) 一致。
- GOV-1「.env 段为手工 patch，install.py 再生成即丢失」与 review-log GOV-1 口径一致（install.py 为外部 cli-registry 工具组件，仓库内无此文件，`.cli-registry.yaml` 无 .env 字段）。

### 3. 表述无歧义/无冲突

- L191（Git 主路径：`_sync_remote` + `_push_with_recovery` 正常模式）未改动，与新 L147（partial 模式）分属不同路径，无冲突。
- L54（Linux `env.conda` py3.12→llm-radar）未改动且准确（.cli-registry.yaml 注释同源）。
- L196（`llm-radar-run.sh` Sources .env）未改动且准确。
- L83「事件新鲜度中位数 < 7 天 + 实体 > 0」与 L145「> 168h 阻断」口径一致；L86「partial 仅推 timestamp.json」与 L147 一致。

### 4. 工作树 / ahead

- `git status`: nothing to commit, working tree clean。
- `git ls-remote origin main` = `098fa7c`（7fab719 的父）；`git rev-parse HEAD` = `7fab719` → ahead 1 / behind 0，无 auto-converge 插入。

### 5. 交付

- review-log.md 追加 PASS 条目；.review-level.yaml 追加 review_history 条目，并关闭 CL005 实现审计遗留 DOC-3（findings_open 1→0）。
- push origin main 后 `git ls-remote` 核验。

## 结论

PASS — 100/100 (A)。文档口径与源码逐行对齐，无安全发现，可推送。
