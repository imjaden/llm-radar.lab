# X热点设计 v1.2 — review报告 v1.0

> 日期: 2026-08-26 (评审执行日)
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.lab
> 设计文档: documents/solutions/x-hotspot-design-v1.2-20260826.md (commit 82d8d1a)
> 前版: v1.1 (CL-SEC19, 实现审计 PASS 100/A)
> 决策: CL-SEC20 — D1 1A / D2 2C / D3 三账号 / D4 4B / D5 5A (已锁定)
> review者: Security Reviewer (IRIS) / hermes-1.2.0
> review维度: 合理性 / 严格性 / 安全性 / 继承一致性 (按治理规范 §6 + 3D + 100-base)

## 结论摘要

v1.2 是 v1.1 (PASS 100/A) 之上的功能增强, 架构方向正确、决策闭环完整、继承机制
(CLI/登录态/反爬/分栏/抽屉) 未被破坏。但 4 项 🟡 属设计级语义/影响分析缺口, 需要 ops
在进入 dev 前闭环:

1. **REA-1** — D1 条数窗口在 §3.4 与 §7.1 给出互相矛盾的回填语义 (核心新特性, 会导致 dev 实现分歧)。
2. **RIG-1** — `window_hours → retention` 的 schema 变更影响未完整枚举 (3 处测试硬编码断言会 break, §7.1 "写盘不变" 与事实不符)。
3. **RIG-2** — §3.6 风控语义 "跳过本轮" 与 "提前终止本轮" 并存, 10 账号部分成功的数据完整度未锁定。
4. **SEC-1** — 全站搜索的 "高亮" 为新增 innerHTML 注入面, 设计未约束输出编码 + 查询词转义。

另 5 项 🟢 观察 (不扣分, 随实现 prompt 落地)。

**评分: 80 / 100 (B) → ⏳ CONDITIONAL PASS。** 建议 ops 修 4 项 🟡 后 bump v1.3 重审。

## 数据验证

| # | 验证项 | 方法 | 结果 |
|:-:|:-------|:-----|:-----|
| 1 | 前端是否读 window_hours | grep index.html `window_hours`/`retention` | ✅ 0 命中 → 设计 §4 "前端无需读" 成立 |
| 2 | schema 断言硬编码 | read tests/test_twitter_collector.py | ⚠️ 3 处 `assert ...['window_hours'] == 36` (L317/340/513), §7.1 未提及 |
| 3 | 36h 相关函数 | grep collector.py `WINDOW_HOURS`/`window_hours` | ⚠️ `within_window`/`filter_window`/`build_document`/`fetch_target`/`truncate_tweets` 五处引用, 设计未给函数级改造映射 |
| 4 | max_tweets 当前默认 | read collector.py parse_config | ⚠️ 现默认 20 (L105/109/201), 设计改 30; twitter-targets.yaml 显式 `max_tweets: 20` |
| 5 | 风控语义 | read 设计 §3.6 + §8 | ⚠️ §3.6 "跳过本轮" vs "提前终止本轮" 并存; §8 用 "挑战跳过" |
| 6 | 搜索高亮注入面 | read 设计 §5.2 | ⚠️ "高亮" 未指定 textContent vs innerHTML, 查询词转义未声明 |
| 7 | esc() 现状 | read index.html L468-471 | ✅ esc() helper 存在, 已用于 searchIcon title |
| 8 | .gitignore 冲突 | read .gitignore | ✅ 无 `data/*.yaml` 忽略项, 设计 §3.1 "入库" 声明成立 |
| 9 | 前端现有搜索 | grep index.html `doSearch`/`header-search` | ✅ 0 命中, 仅 searchIcon (Bing 搜索图标), header-search 为净新增 |
| 10 | 退出码/CLI/分栏继承 | read collector.py CLI + index.html | ✅ 与 v1.1 一致, 未破坏 |

## 维度评估 (3D)

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 合理性 | 🟡 | 决策闭环完整、架构复用充分; 但 D1 回填语义在 §3.4/§7.1 自相矛盾 (REA-1); max_tweets 与 24h 全保留的关系未重定义 (O-4) |
| 严格性 | 🟡 | schema→测试影响未完整枚举 (RIG-1); 风控部分成功语义未锁定 (RIG-2); 30/24h 边界 (=30/=24h) 用例缺失 |
| 安全性 | 🟡 | 继承的 "全字段 esc()" 覆盖 forward (O-1); 但搜索高亮为新注入面未约束 (SEC-1) |
| 继承一致性 | 🟢 | CLI/登录态/反爬/分栏/抽屉/crontab 均标注继承且无矛盾 |

## 发现表

| # | Severity | 维度 | 标题 | 位置 | 状态 |
|:-:|:--------:|:----:|:-----|:-----|:----:|
| REA-1 | 🟡 | 合理性 | D1 条数窗口回填语义 §3.4 vs §7.1 矛盾 | §3.4 步骤5 / §7.1 | 待修 |
| RIG-1 | 🟡 | 严格性 | schema 变更影响未完整枚举 (3 处测试断言 break + "写盘不变" 错误) | §4 / §7.1 | 待修 |
| RIG-2 | 🟡 | 严格性 | 风控 "跳过本轮" vs "提前终止本轮" 语义矛盾 | §3.6 | 待修 |
| SEC-1 | 🟡 | 安全性 | 搜索 "高亮" innerHTML 注入面 + 查询词转义未约束 | §5.2 | 待修 |
| O-1 | 🟢 | 安全性 | forward 建议补 XSS payload 专项断言 (SEC-1 防回归) | §7.2 | 观察 |
| O-2 | 🟢 | 严格性 | forward 作者提取失败时降级粒度未定义 (丢整条 vs "by @unknown") | §3.4 步骤4 | 观察 |
| O-3 | 🟢 | 合理性 | Cmd+F 仅 metaKey, 未覆盖 ctrlKey (Windows/Linux 跨平台) | §5.2 | 观察 |
| O-4 | 🟢 | 严格性 | max_tweets 在 "24h 全保留" 下的语义 (floor vs cap) 未重定义 | §3.1 | 观察 |
| O-5 | 🟢 | 合理性 | steipete 从 10 人名单移除, 既有 twitter.json 数据滚动消失无归档说明 | §3.1 | 观察 |

## 详细发现

### REA-1 🟡 — D1 条数窗口回填语义自相矛盾 (合理性)

§3.4 步骤5 实现描述: "先按 24h 过滤 → 若 >30 全保留; 否则取最近 30 条"。
§7.1 测试规范: ">30 条跨 24h → 24h 内全保留 + 其余按最近 30 **补足**; <30 条 → 全部保留"。

两处对 "<30 时是否用 24h 外更早推文补足到 30" 给出相反描述:
- §3.4 的 "先…过滤…否则取最近 30 条" 易读为对 24h 过滤结果取 30 (无补足);
- §7.1 "其余按最近 30 补足" 明确要求跨 24h 补足 (有补足)。

"30 条保底" (floor) 与 "每账号保留最近 30 条" (cap) 两种表述并存且未 reconcile。
对核心新特性的实现会产生分歧: dev 可能实现为 `if len(within_24h) > 30: keep all; else: keep last 30 of within_24h` (错误地丢弃 24h 外更早推文)。

**修法建议 (单一精确语义)**: `retention = {posted_at ≥ now−24h 的全部} ∪ {24h 外按时间倒序的前 (30 − |24h 内|) 条}` (即 `max(30, 24h 全量)`), 并显式声明 =30 与 =24h 的边界 (inclusive/exclusive)。

### RIG-1 🟡 — schema 变更影响未完整枚举 (严格性)

`window_hours → retention` 会破坏 3 处硬编码测试断言, §7.1 未提及:
- `test_build_document_keys` (L316-317) / `test_write_document_roundtrip` (L340) / `test_all_disabled_writes_empty` (L513) 均断言 `['window_hours'] == 36`。

且 §7.1 "DOM 解析/写盘/退出码不变" 的 "写盘不变" 与事实不符: `build_document` 的顶层键由 `window_hours` 改为 `retention`。

"废弃 36h" 缺函数级改造映射: `within_window`/`filter_window` (36h 硬过滤) / `truncate_tweets` (max_tweets cap) / `build_document` (schema 键) / `fetch_target` (调用链) 五处均引用 `WINDOW_HOURS=36` 或 `max_tweets`, 其中 `within_window`/`filter_window` 的 "硬 36h 截止" 语义被 "30 保底 + 24h 全保留" 替换后, 这两个函数需重写或废弃。

**修法建议**: §7.1 补 "schema 键变更: window_hours→retention, 同步更新 test_build_document_keys/test_write_document_roundtrip/test_all_disabled_writes_empty 三处断言"; §3.4 补函数级改造表 (within_window→within_24h / filter_window→apply_retention / truncate_tweets→并入 retention / build_document 键名)。

### RIG-2 🟡 — 风控语义 "跳过本轮" vs "提前终止本轮" (严格性)

§3.6 两行并存: "挑战检测跳过本轮" (继承) 与 "若遇挑战提前终止本轮 (部分成功语义处理)"。§8 风险表用 "挑战跳过"。
当前实现 `cmd_collect` 遇 `ChallengeError` → append error + **continue 下一 target** (跳过单账号)。而 "提前终止本轮" 会终止整批采集 (账号 #5 遇挑战 → #6-10 本轮无数据)。

对 10 账号部分成功语义 (决定采集数据完整度与 `last_error` 内容) 未锁定, 两处互相矛盾。

**修法建议**: 统一为 "挑战/风控 → 跳过该 target, continue 下一账号 (部分成功语义), 而非终止整批"; 如确需提前终止, 需在 §3.5 四场景表中新增该分支并定义 last_error 与退出码。

### SEC-1 🟡 — 搜索 "高亮" 为新增注入面 (安全性)

§5.2 "点击计数跳转对应 tab 并高亮" 是典型 innerHTML 注入点: 对攻击者可控的实体名/推文文本做字符串包裹高亮时, 若不先 esc() 再包裹, 会重演 SEC-1 类 stored XSS (本次注入向量是查询词 + 被高亮的攻击者可控文本)。
设计未指定: (a) 高亮实现 (textContent/CSS class vs innerHTML 字符串替换); (b) 查询词若回显 DOM 是否 esc()。

**修法建议**: §5.2 补 "高亮用 CSS class + textContent 赋值, 禁止 innerHTML 包裹匹配子串; 查询词回显一律 esc(); 追加 test_html 断言 (查询词含 `<img onerror>` 不注入)"。

## 评分

| 级别 | 数量 | 扣分 |
|:-----|:-----|:-----|
| 🔴 HIGH | 0 | 0 |
| 🟡 MEDIUM | 4 (REA-1 / RIG-1 / RIG-2 / SEC-1) | −20 |
| 🟢 LOW | 5 (O-1~O-5, 记录不扣分) | 0 |

**得分: 100 − 20 = 80 / 100 → B (CONDITIONAL PASS)**

## 结论

**⏳ CONDITIONAL PASS (80/100, B)** — 架构合理、继承一致、无 🔴; 但 4 项 🟡 属设计级
语义/影响分析缺口 (核心特性的回填语义矛盾、schema→测试影响遗漏、风控语义矛盾、搜索
注入面未约束), 需 ops 修正后 bump v1.3 重审。**不进入 dev。**

### 待修正项清单 (回 ops, bump v1.3)

1. **REA-1**: 统一 D1 条数窗口为单一精确语义 (见详细发现), §3.4/§7.1 对齐。
2. **RIG-1**: §7.1 补 schema 键变更 + 三处断言更新; §3.4 补函数级改造映射。
3. **RIG-2**: 统一 §3.6 风控语义 (跳过 vs 终止) 并在 §3.5 定义对应分支。
4. **SEC-1**: §5.2 补高亮 textContent/CSS class 约束 + 查询词转义 + test_html 断言。

### 观察项 (🟢, 随实现 prompt 落地, 不阻塞)

- O-1: forward 字段补 XSS payload 专项断言 (SEC-1 防回归)。
- O-2: forward 作者提取失败降级粒度 (丢整条 vs "by @unknown: 原文")。
- O-3: Cmd+F 补 ctrlKey (Windows/Linux 跨平台) 或显式声明仅 Mac。
- O-4: max_tweets 在 "24h 全保留" 下的语义 (floor vs cap) 需重定义。
- O-5: steipete 从名单移除, 既有 twitter.json 数据滚动消失, 建议加归档/过渡说明。

---

*报告: documents/reviews/x-hotspot-review-v1.2-20260826.md | 结论: ⏳ CONDITIONAL PASS 80/100 (B) | 待 ops 修 4 🟡 bump v1.3 重审*
