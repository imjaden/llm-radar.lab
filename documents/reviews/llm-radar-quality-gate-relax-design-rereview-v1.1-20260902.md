# LLM-RADAR-CL005 质量门禁放宽与重试优化设计 — 复审报告 v1.1

> 日期: 2026-09-02 (复审执行日)
> 设计文档: documents/solutions/llm-radar-quality-gate-relax-design-v1.0-20260902.md (内部 version 1.1, commit ba76927)
> 上轮评审: documents/reviews/llm-radar-quality-gate-relax-design-review-v1.0-20260902.md (80/100 B, CONDITIONAL PASS)
> review者: review/llm-radar-quality-gate-relax-design-rereview (hermes-1.2.0)
> review维度: 合理性 / 严格性 / 安全性 (3D + 100-base, PASS 阈值 ≥85/A)

## 结论摘要

v1.0 的 4 🟡 阻塞项 (REA-1 / RIG-1 / RIG-2 / RIG-3) 全部闭合, SEC-001 取舍已显式声明。复审新发现 1 🟡 (N1, 并入实现验收清单, 不阻塞) + 3 ℹ️:

- **N1 🟡**: §6 验证清单第 3 项冒烟 "计时 LLM 阶段 ≤200s" 与 §3.1/§5 重ground 216s 矛盾 —
  RIG-3 放宽未同步到 §6。§3.1 "≤200s 非承诺" / §5 O-1 "≤200s 非目标" 均已声明, 但 §6 项 3
  仍将 "≤200s" 作为冒烟门限, 照单执行必挂 (216s > 200s)。修复: 改 "计时 LLM 阶段 <300s"
  或 "记录 LLM 阶段耗时 (预期 ~216s)"。属验证清单细节, 不改变构建规格, 并入实现验收清单。
- N2 ℹ️: 背景 §2 根因 #2 "重试 5 次 × ~40s" 的 ~40s 与 54s/次 重ground 不一致 (narrative, 可选修)。
- N3 ℹ️: D2 决策记录 "压到 ~200s" 略乐观 (216s 属 "约 200s", 波浪号可辩护, 可选统一)。
- N4 ℹ️: §3.1 未列 L776/L778 注释 "5 次重试" 与 _verify docstring L1422-1423 "热点数量"
  的同步 (实施时随代码一并更新, 设计不强制)。

**评分: 95 / 100 (A) → ✅ PASS (≥85/A)。** 设计可进 dev; N1 修法明确, 并入实现验收清单
(dev 实施时 §6 冒烟按修正门槛执行), 不阻塞。commit 报告 + review-log + .review-level.yaml, 不 push。

## 修复核验表 (上轮 4 🟡 + SEC-001 → v1.1)

| # | v1.0 Finding | Status | 证据 (v1.1 位置 + 独立验证) |
|:--|:-------------|:------:|:---------------------------|
| REA-1 | 实体0判定维度口径 (5维度) + 拦截位置误述 | ✅ | §3.2 明确 4 实体维度表达式 `sum(len(entities.get(d, [])) for d in ['providers','people','tools','llms'])` (排除 hotspots) + 分层拦截: run L1739 `if not entities: return False` 拦 None + `_verify` 新检查拦 "LLM 返回全空数组的 dict" (truthy dict 绕过 L1739) + L1428 `if not entities: return ['实体提取为空']` 防御保留。源码独立核验: L1739 确为 `if not entities: return False` (先于 _verify 调用 L1748); L1428 确为 `return ['实体提取为空']`; L1433 新鲜度循环确为 4 维度 `['providers','people','tools','llms']` (排除 hotspots)。公式排除 hotspots 正确, 位置描述与源码一致, 无遗漏。|
| RIG-1 | 重试日志 4 处计数只列 1 处 | ✅ | §3.1 列出全部 4 处目标值 + 循环改动: L780 `重试 {retry_i}/5`→`/3`; L788 `重试 {retry_i}/5 返回空内容`→`/3`; L784 `重试 {retry_i}/3 LLM 调用失败` 与 L794 `已重试 3 次` 当前已是 `/3`/`3 次` (既有漂移: 5 次重试下就已错标, 本次改动恰好使其变正确); L779 `range(1,6)`→`range(1,4)`。grep 全量复核 (collector 全文件 `重试|/5|/3|range(1,|已重试`): 重试块硬编码计数恰为 L780/L784/L788/L794 四处 + L779 循环一处, 无第 5 处遗漏; tests/ 无 retry 计数断言。4 处全覆盖, 漂移标注准确。|
| RIG-2 | status_str 因子枚举误述 (漏 quality_status/git_status) | ✅ | §3.3 更正为 5 项: `not snapshot`(快照缺失) / `freshness`(last_run_at 年龄) / `consec_fails>=3` / `quality_status`(timestamp.json last_run_status) / `git_status`(ahead/behind), 不受 checks 项(含新增"热点数")影响。源码独立核验 L1857-1863: critical = `not snapshot or freshness=='critical' or consec_fails>=3`; warning = `freshness=='warning' or quality_status=='warning' or git_status=='warning'`; 恰好 5 项, 与 §3.3 枚举一一对应。"实体数"确非因子 (L1896 `{'label':'实体数',...,'status':'info'}` 硬编码 'info')。结论 (热点数不影响主 status) 仍成立。|
| RIG-3 | 耗时估算 ~40s/次 vs 实测 54s/次; O-1 "≤200s" 余量不足 | ✅ | §3.1 重ground: 根因 #2 实测 324s / 6 次调用 ≈ 54s/次; D2 后 4 次调用 (1 首次 + 3 重试) ≈ 216s, 总耗时 <300s (主目标); "≤200s" 非承诺, D3 600s 为硬兜底。算术独立核验: 324/6 = 54 ✓; 4 × 54 = 216 ✓; 6 次调用 = 1 首次 + `range(1,6)` 5 重试 ✓ (与源码 L779 一致)。§5 O-1 "≤200s 非目标" ✓ 不再承诺 ≤200s。①估算与实测一致 ②O-1 不承诺 ≤200s — 双点均达标。|
| SEC-001 (ℹ️) | 实体>0 无下限, 单条垃圾实体可过门禁 (非安全漏洞) | ✅ | §3.3 "已知取舍 (SEC-001)" 声明 (单条新鲜垃圾实体可过门禁, 当前 3 健康源 ~50 实体风险低, 新鲜度优先质量为代价) + §5 O-1b 观察项。取舍已显式声明, 上轮建议 (补声明) 落地。|

## 新发现 (复审扫描)

| # | Severity | Title | 说明 | 建议 |
|:-:|:--------:|:------|:-----|:-----|
| N1 | 🟡 | §6 冒烟 "计时 LLM 阶段 ≤200s" 未同步放宽 | §6 项 3 冒烟将 "≤200s" 作为 LLM 阶段门限, 但 §3.1/§5 已重ground 216s 且声明 "≤200s 非承诺/非目标"; 照单执行必挂 (216>200), 与 RIG-3 修复意图自相矛盾。属验证清单细节, 非构建规格缺陷 | §6 项 3 改 "计时 LLM 阶段 <300s" 或 "记录 LLM 阶段耗时 (预期 ~216s)"; 并入实现验收清单 |
| N2 | ℹ️ | 背景 "× ~40s" 与 54s/次 不一致 | §2 根因 #2 "重试 5 次 × ~40s, LLM 阶段 324s" — ~40s/次 × 6 次 = 240s ≠ 324s; §3.1 已重ground 54s/次, 背景 ~40s 为遗留旧值 | 可选: 背景 "~40s" 改 "~54s/次" 或删 (narrative) |
| N3 | ℹ️ | D2 决策 "压到 ~200s" 略乐观 | 决策记录 D2 "LLM 阶段压到 ~200s" vs 重ground 216s; 波浪号 "约 200s" 可辩护 (216 在 ~8% 内), 但与 §3.1 216s 精确值不完全一致 | 可选: D2 改 "压到 ~216s" 或保留 (波浪号宽容) |
| N4 | ℹ️ | 代码注释/docstring 同步未列入 | §3.1 改 `range(1,6)→range(1,4)` 后, L776 注释 "重试最多 5 次" 与 L778 "改为 5 次重试" 变陈旧; §3.2 移除热点阻断后, _verify docstring L1422-1423 "仍阻断的硬指标: 新鲜度、热点数量" 变陈旧。设计未列, 实施者易漏 | 实施时随代码一并更新注释/docstring (非设计规格, 不强制入 §3) |

## 维度评估 (3D)

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 合理性 | 🟢 | REA-1 实体0判定口径 (4 实体维度排除 hotspots) + 分层拦截 (run L1739 拦 None / _verify 新检查拦空 dict / L1428 防御) 三层闭合, 与源码事实一致, "仅 3 热点 + 0 实体" 误判通过场景被正确封堵 |
| 严格性 | 🟢 | RIG-1 重试块 4 处计数 + 1 处循环全盘点无遗漏; RIG-2 status_str 5 因子枚举与 L1857-1863 精确对应; RIG-3 耗时重ground 算术自洽 (324/6=54, 4×54=216); 唯 N1 为验证清单门槛残留, 非机制缺陷 |
| 安全性 | 🟢 | 无安全发现。变更属质量门禁参数 + 重试次数调整, 不引入新依赖/注入面/认证边界; SEC-001 数据完整性取舍已显式声明 (新鲜度优先质量为代价), 残余风险低 (3 健康源稳定 ~50 实体) |

## 评分明细

```
基准分: 100
  REA-1 / RIG-1 / RIG-2 / RIG-3  ✅ 修复 (不计分)
  SEC-001                         ✅ 声明 (不计分)
  N1 🟡 -5  §6 冒烟 "≤200s" 与 216s 重ground 矛盾 (验证清单门槛残留, 并入 impl)
  N2~N4 ℹ️    不计分
────────────────────────
得分: 95 → A → ✅ PASS
```

## 结论

**✅ PASS — 95/100 (A)。** 上轮 4 🟡 阻塞项 + SEC-001 全部闭环, 设计 v1.1 与源码事实
(L1739 拦 None / L1428 防御 / L1433 4 维度 / L1857-1863 5 因子 / L1896 实体数 status='info' /
重试块 L779-794 四处计数) 逐项一致。新 N1 🟡 修法明确且仅影响 §6 验证命令门槛 (并入实现
验收清单), N2~N4 ℹ️ 不阻塞。

设计 PASS, 可进 dev。

## 实现验收清单 (dev 阶段, 照此执行)

核心变更:
1. **D2 重试 5→3** (§3.1): `llm-radar-collector.py` L779 `range(1,6)`→`range(1,4)`;
   L780 `/5`→`/3`; L788 `/5`→`/3`; L784 `/3` / L794 `3 次` 不动 (既有漂移变正确);
   顺带更新 L776/L778 注释 "5 次重试"→"3 次重试" (N4)。
2. **D5 质量门禁放宽** (§3.2): `_verify` 移除热点阻断 (L1447-1449 移出 issues, 记入
   `self._quality_warnings`); 新增实体 0 检查 `sum(len(entities.get(d,[])) for d in
   ['providers','people','tools','llms']) == 0` → issues; L1428 `if not entities` 防御保留;
   顺带更新 docstring L1422-1423 (N4)。
3. **D6 热点数 checks 附加** (§3.3): `status()` checks 增加第 5 项
   `{'label':'热点数','value':'<n> 条','status':'warning' if n<3 else 'info'}`;
   主 status_str (L1857-1863) 不动。
4. **D3 daily-checker 配合** (§3.4): 本仓库仅打印需求 prompt 转交, 不改跨项目代码。

测试同步 (§4):
- `tests/test_status.py::test_ok_checks` L96 labels 断言加 '热点数' (→ 5 项);
- 新增 `test_verify_hotspots_zero_but_entities_ok` / `test_verify_all_empty_fails` /
  `test_status_hotspot_warning_check` (建议落点 tests/test_verify.py, 上轮 O-2)。

实现文件:
- llm-radar-collector.py (L779-794 retry / L1419-1463 _verify / L1894-1899 checks)
- tests/test_status.py (:96 labels)
- tests/test_verify.py (新, 3 用例)

参考:
- 设计方案: documents/solutions/llm-radar-quality-gate-relax-design-v1.0-20260902.md (v1.1)
- 评审报告: documents/reviews/llm-radar-quality-gate-relax-design-review-v1.0-20260902.md (上轮)
- 复审报告: documents/reviews/llm-radar-quality-gate-relax-design-rereview-v1.1-20260902.md (本轮)

遗留问题 (不阻塞):
- N1 (P1): §6 项 3 冒烟 "计时 LLM 阶段 ≤200s" → 改 "<300s" 或 "记录耗时 (预期 ~216s)"
- N2/N3 ℹ️: 背景 "~40s" / D2 "~200s" 可选统一 (随 v1.2 或实施时顺手)
- N4 ℹ️: L776/L778 注释 + _verify docstring 随代码一并更新

---

*报告: documents/reviews/llm-radar-quality-gate-relax-design-rereview-v1.1-20260902.md | 结论: ✅ PASS 95/100 (A) | REA-1/RIG-1/RIG-2/RIG-3 ✅ 全修 + SEC-001 ✅ + N1 🟡 (并入 impl) + N2~N4 ℹ️ | commit 报告, 不 push*
