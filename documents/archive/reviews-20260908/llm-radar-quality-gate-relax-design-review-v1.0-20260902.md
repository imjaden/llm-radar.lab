# LLM-RADAR-CL005 质量门禁放宽与重试优化设计 — review报告 v1.0

> 日期: 2026-09-02
> 文件: documents/solutions/llm-radar-quality-gate-relax-design-v1.0-20260902.md
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.lab
> 待 push commit: 961d666 (设计文档; 本评审仅新增评审产物, 不 push)
> review维度: 合理性 / 严格性 / 安全性

## 数据验证

| 验证项 | 方法 | 结果 |
|:-------|:-----|:-----|
| §3.1 重试行号 L776-796 | read_file llm-radar-collector.py L760-840 | 已确认: `for retry_i in range(1, 6)` @ L779; 4 处日志计数 L780 `重试 {retry_i}/5` / L784 `重试 {retry_i}/3 LLM 调用失败` / L788 `重试 {retry_i}/5 返回空内容` / L794 `已重试 3 次` |
| §3.1 方法名 `_extract_entities` | grep 'def .*extract_entities' | ❌ 漂移: 实际为 `extract_entities` (L681), 无 `_extract_entities` 方法 |
| §3.2 _verify L1419-1463 | read_file L1400-1490 | 已确认: `if not entities: return ['实体提取为空']` @ L1428; 热点阻断 @ L1447-1449; 新鲜度阻断 @ L1442-1445 (median>168h) |
| §3.3 checks L1894-1899 | read_file L1860-1922 | 已确认: checks 4 项 @ L1894-1899; `dims` 含 hotspots @ L1886, `entity_value` 已含热点数 (5 维度 join) @ L1889 |
| status_str 主状态因子 | read_file L1857-1863 | 实际 = `not snapshot` + `freshness` + `consec_fails>=3` + `quality_status(last_run_status)` + `git_status`; **"实体数" 非 status_str 因子** (仅影响 checks 显示) |
| merge_entities quality_ok 链路 | grep quality_ok/_verify/merge_entities | 已确认: run L1748-1764 → `merge_entities(entities, quality_ok=...)` L951/1141/1155 → `_write_timestamp` L1283/1302 → `_auto_push(partial=not quality_ok)` L1155 |
| _auto_push partial 语义 | read_file L372-430 | partial=True 仅 push timestamp.json (last_run_status='failed'); 正常模式 changelog 空/无变更 → skip push (L402-408) |
| run() 实体 None 拦截 | read_file L1738-1742 | `if not entities: return False` @ L1739 先于 `_verify` 调用 (L1748) |
| test_status.py::test_ok_checks | read_file tests/test_status.py L92-106 | 已确认 labels 断言 = `['数据日期','实体数','质量门禁','Git 同步']` — 需加 '热点数' |
| test_status.py::test_warning_quality_failed | read_file L165-177 | 语义不变 (timestamp failed→warning, 与热点无关) |
| test_timestamp.py::test_status_success_when_no_issues | read_file tests/test_timestamp.py L57-67 | 不变 (调 merge_entities 不调 _verify) |
| _verify 直接单测现状 | grep '_verify' tests/ | 0 命中 — 当前无 _verify 直接单测, §4 新增 2 用例为首批 |
| test_extract.py 无 retry 断言 | grep 'retry|range(1,' tests/ | test_extract.py 0 命中 — §4 "不变" 成立 |
| review-log 位置 | read review-log.md head | 固定项目根 `review-log.md` (非 documents/reviews/) |

## 合理性评估

✅ REA-0 根因覆盖完整。三层根因 (3 源降级 / LLM 重试超时 / 热点 0 门禁失败死循环) 分别由 D1/D2/D5+D6 覆盖, 另加 D3 (daily-checker 600s 兜底) 与 D4 (存量恢复), 决策闭环。

🟡 REA-1 — "实体 0 判定" 维度口径与位置描述不精确。

- 位置: §3.2 "另加实体数检查：5 维度实体总数为 0 → issues" + "实体 0（全源失败）仍阻断: _verify 开头 if not entities 保持"
- 问题: (a) "5 维度" 与 D5/D7 的 "实体 0（全源失败）" 口径冲突 — 采集器代码中 "实体" 恒为 4 维度 `['providers','people','tools','llms']` (见 `_verify` 新鲜度循环 L1433、`_observe` 实体统计 L1666), 不含 hotspots。若实现按 "5 维度" (含 hotspots) 判定, 则 "仅提取 3 热点 + 0 实体" 会被判为通过并 push, 违背 D5 "实体 0 → fail"。(b) 位置误述 — 真正的 "全源失败 (entities=None)" 拦截在 run() L1739 `if not entities: return False`, 而非 `_verify` 开头; `_verify` 的 `if not entities` (L1428) 只防御直接调用传 None, 在 run() 路径中是死代码。新检查实际针对的是 "LLM 返回全空数组的 dict" (truthy dict, L1739 放行) 这一场景。
- 建议: §3.2 明确实体数检查表达式为 `sum(len(entities.get(d, [])) for d in ['providers','people','tools','llms']) == 0` (4 维度, 排除 hotspots), 并更正 "实体 0 拦截" 的位置描述 (run L1739 拦 None + _verify 新检查拦空 dict)。

## 严格性评估

🟡 RIG-1 — §3.1 日志文案改动不完整 (4 处只列 1 处)。

- 位置: §3.1 "日志文案 `重试 {retry_i}/5` → `/3`"
- 问题: 重试块实际有 4 处硬编码计数 — L780 `/5`、L784 `/3`、L788 `/5`、L794 `已重试 3 次`。设计只列了 1 处 (L780)。且 L784/L794 在当前代码中已是 `/3`/`3 次` (与 `range(1,6)` 5 次重试不一致的既有漂移, 设计未指出)。实现者照单改 L780 会漏掉 L788 的 `/5`, 残留 "重试 1/5" 误导日志。
- 建议: §3.1 列出全部 4 处目标值 (L780 `/5`→`/3`, L788 `/5`→`/3`, L784/L794 已是 `/3`/`3 次` 无需改), 并标注既有漂移 (当前 5 次重试下 L784/L794 就已错标为 /3, 本次改动恰好使其变正确)。

🟡 RIG-2 — §3.3 "主 status 仅由新鲜度 + 连续失败 + 实体数决定" 与源码不符。

- 位置: §3.3 "注意" 段
- 问题: 源码 L1857-1863 status_str 实际由 5 项决定 — `not snapshot`(快照缺失) / `freshness`(last_run_at 年龄) / `consec_fails>=3` / `quality_status`(timestamp.json 的 last_run_status) / `git_status`(ahead/behind)。"实体数" 不是 status_str 因子 (仅影响 checks 的 `实体数` 项显示, status 恒为 'info')。结论 (热点数不影响主 status) 仍正确, 但推理前提的枚举不准确, 属 现状评估 误述。
- 建议: 更正为 "主 status 仅由 快照缺失/新鲜度/连续失败/质量门禁(last_run_status)/git 分叉 决定, 不受 checks 项(含热点数)影响"。

🟡 RIG-3 — §3.1 耗时估算与实测证据不一致, O-1 "≤200s" 目标余量不足。

- 位置: §3.1 "预期: 重试 3 次 × ~40s = 120s + 首次 40s ≈ 160s, LLM 阶段 <200s" + §5 O-1 "LLM 阶段耗时 ≤200s"
- 问题: 根因 #2 实测 "LLM 阶段 324s" 对应 6 次调用 (1 首次 + 5 重试) ≈ 54s/次, 与 "~40s/次" 不符。按 54s/次, D2 后 4 次调用 ≈ 216s, 仍 <300s (主目标达成), 但 "<200s" 与 O-1 "≤200s" 大概率不达标 (O-1 是设计自设的验收观测项)。
- 建议: 重ground 估算 (或将 O-1 放宽为 "≤240s" 或 "总耗时 <300s"), 明确 D3 (600s timeout) 才是硬兜底, 而非依赖 "<200s" 的乐观估计。

## 安全事项

🟢 无安全发现。本变更属数据采集质量门禁参数调整, 不引入新依赖、新注入面、认证边界或敏感数据流。

ℹ️ SEC-001 — 门禁放宽的残余数据完整性风险 (非安全漏洞)。D5 将硬阻断降为 "实体>0 即 push", 意味着一次 LLM 幻觉出 1 条新鲜垃圾实体 (含近期 date) 也会通过 (新鲜度 median<7天 + 实体非空 均满足)。当前 3 健康源稳定产出 ~50 实体, 实际风险低, 但设计未显式声明该取舍 (以新鲜度为优先, 以质量为代价)。建议在 §5 观察项补一条 "实体>0 阈值无下限, 单条新鲜垃圾实体可过门禁" 作为已知取舍。

## 评分

| Severity | 数量 | 扣分 |
|:---------|:----:|:----:|
| 🔴 阻断 | 0 | 0 |
| 🟡 观察 | 4 | -20 |
| ℹ️ 提示 | 6 | 0 |

得分: 80 / 100 → Rating: B

## 结论

⏳ CONDITIONAL PASS — 80/100 (B)

设计决策 (D1-D7) 正确、根因覆盖完整、源码行号锚点全部命中, 机制 (实体>0 即 push 断死循环) 可行。但存在 4 处严格性/合理性规格缺陷 (REA-1 / RIG-1 / RIG-2 / RIG-3), 均属 "文档规格不精确、实现者会猜错" 的级别, 需在进入实现前修正后复评。

## 待确认清单 (阻塞项)

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | REA-1: §3.2 明确实体数检查为 4 实体维度 (排除 hotspots) + 更正 "实体 0 拦截" 位置描述 | 合理性 🟡 |
| □ | RIG-1: §3.1 列出全部 4 处重试日志计数的目标值 + 标注 L784/L794 既有漂移 | 严格性 🟡 |
| □ | RIG-2: §3.3 更正 status_str 因子枚举 (快照缺失/新鲜度/连续失败/质量门禁status/git分叉) | 严格性 🟡 |
| □ | RIG-3: §3.1 重ground 耗时估算, 放宽 O-1 "≤200s" 或明确 D3 600s 为硬兜底 | 严格性 🟡 |

非阻塞提示 (ℹ️, 不阻断):

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | O-1: §3.4 daily-checker.py:68 为跨项目锚点 (本仓库不可验证); D3 非严格必需 (兜底), 确认落地节奏 | 提示 |
| □ | O-2: §4 新增 3 用例指定落点文件 (建议 tests/test_verify.py) | 提示 |
| □ | O-3: §3.3 "热点数" check 读 snapshot.json 存量而非本次 run 提取数, 确认意图 | 提示 |
| □ | O-4: status "实体数" value 已含热点数, 新增 "热点数" check 部分冗余, 确认展示不冲突 | 提示 |
| □ | O-5: D5 "实体>0→push" 实为 "实体>0 且 changelog 非空→push" (全过期/无变更仍 skip) | 提示 |
| □ | O-6: §3.1 方法名 `_extract_entities` → `extract_entities` (L681) | 提示 |
