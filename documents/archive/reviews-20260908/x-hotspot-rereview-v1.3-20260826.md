# X热点设计 v1.3 — 复审报告

> 日期: 2026-08-26 (评审执行日)
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.lab
> 设计文档: documents/solutions/x-hotspot-design-v1.3-20260826.md (commit b9b025d)
> 前轮评审: documents/reviews/x-hotspot-review-v1.2-20260826.md (80/B CONDITIONAL)
> 决策: CL-SEC20 — D1 1A / D2 2C / D3 三账号 / D4 4B / D5 5A (已锁定)
> review者: Security Reviewer (IRIS) / hermes-1.2.0
> review维度: 合理性 / 严格性 / 安全性 / 继承一致性 (按治理规范 §6 + 3D + 100-base)

## 结论摘要

v1.3 针对 v1.2 评审的 4 🟡 + 1 🟢 (O-1) 逐项闭环, 全部核验通过:

- **REA-1** (条数窗口回填语义矛盾) → ✅ 全修: §3.4 步骤5 统一为三规则 (24h 内 >30 全保留 / ≤30 补足至 30 / 总 <30 全保留) + 边界 (=30 / =24h 整点), §7.1 用例同步。
- **RIG-2** (风控语义矛盾) → ✅ 全修: §3.6 统一为 单账号挑战→记 error 继续 / 连续 ≥2 账号→提前终止(已抓写盘) / 全部未抓成→exit 1, 语义自洽。
- **SEC-1** (搜索高亮注入面) → ✅ 全修: §5.2 结构化 DOM (span + textContent 分片) 禁 innerHTML, 查询词+片段按文本节点渲染, 双转义 fallback; §7.2 补 `<script>` 注入用例。
- **O-1** (forward XSS 专项断言) → ✅ 全修: §7.2 `<img onerror>` → 纯文本渲染断言。
- **RIG-1** (schema 变更影响未枚举) → ✅ 主修: §4 `window_hours→retention` + 3 处测试断言影响枚举 + 更正 "写盘不变" 表述。⚠️ 残余 🟢: 函数级改造映射 + 断言方法级命名 + max_tweets 20→30 断言影响未枚举 (并入 impl prompt, 不阻塞)。

**评分: 100 / 100 (A) → ✅ PASS。** 设计可进 dev。残余 🟢 项随实现 prompt / 验收清单落地, 不阻塞。

## 逐项验证表 (上轮发现 → 修法 → 验证)

| 发现 | v1.3 修法位置 | 验证结论 | 结果 |
|:---|:---|:---|:---:|
| REA-1 🟡 条数窗口回填语义矛盾 | §3.4 步骤5 三规则 + 边界; §7.1 用例 | §3.4 (a/b/c 三规则) 与 §7.1 (四条用例) 语义一致, 无矛盾; 边界 =30/=24h 整点已显式声明 | ✅ |
| RIG-1 🟡 schema 变更影响未枚举 | §4 retention + 测试断言影响; 更正 "写盘不变" | §4 列 test_twitter_collector.py window_hours 断言 / test_html.py / 写盘断言更新三处, "写盘不变" 已更正; 残余: 函数映射 + 方法级命名未列 | ⚠️✅ |
| RIG-2 🟡 风控语义矛盾 | §3.6 统一三态 + 数据完整度 | 单账号跳过→部分成功 / 连续≥2 提前终止(已抓写盘) / 全未抓成 exit1 三态自洽, 与 §3.5 四场景兼容 | ✅ |
| SEC-1 🟡 搜索高亮注入面 | §5.2 编码约束; §7.2 注入用例 | 结构化 DOM (span+textContent) 禁 innerHTML + 双转义 fallback; §7.2 `<script>` 查询用例 | ✅ |
| O-1 🟢 forward XSS 专项断言 | §7.2 | forward 含 `<img onerror>` → 纯文本渲染断言 (无 img 执行) | ✅ |

## 数据验证

| # | 验证项 | 方法 | 结果 |
|:-:|:-------|:-----|:-----|
| 1 | 三处 window_hours 断言存在 | read tests/test_twitter_collector.py | ✅ L317 `assert doc['window_hours']==36` / L340 `assert data['window_hours']==36` / L513 `assert written.get('window_hours')==36` — 与设计 §4 "3 处" 一致 |
| 2 | 前端不读 retention | grep index.html window_hours/retention | ✅ 0 命中 → §4 "前端不读 retention 字段" 成立 |
| 3 | 36h 函数引用现状 | read scripts/twitter-collector.py | ✅ WINDOW_HOURS=36 五处引用 (within_window L161 / filter_window L179 / build_document L331 / fetch_target L518 / truncate_tweets L201); build_document 键 `window_hours` (L336); 待 v1.3 实现改造 |
| 4 | 风控现状 | read cmd_collect L682-697 | ✅ 现 ChallengeError → "跳过本轮" continue (无提前终止); v1.3 设计描述待实现语义, 非现状矛盾 |
| 5 | max_tweets 默认现状 | read parse_config L105-109 | ⚠️ 现默认 20; 设计 §3.1 改 30; test 中 `assert cfg[0]['max_tweets']==20` (L63/L83) 会 break → RIG-1 残余 |
| 6 | 提交内容 | git show --stat b9b025d | ✅ v1.2→v1.3 rename + 263 insertions, 修复声明有正文支撑 (非仅追加) |
| 7 | 工作区 | git status | ✅ clean; 未 commit / 未 push (1A 约束) |

## 维度评估 (3D)

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 合理性 | 🟢 | D1 三规则单一语义 (REA-1); 决策闭环完整; 继承机制无破坏 |
| 严格性 | 🟢 | 条数窗口边界 (=30/=24h) 已覆盖; 风控三态锁定 (RIG-2); schema→测试影响已枚举 (RIG-1 主修) |
| 安全性 | 🟢 | 搜索高亮结构化 DOM 禁 innerHTML (SEC-1); forward XSS 专项断言 (O-1); 全字段 esc() 继承 |
| 继承一致性 | 🟢 | CLI/登录态/反爬/分栏/抽屉/crontab 均标注继承, 无矛盾 |

## 评分

| 级别 | 数量 | 扣分 |
|:-----|:-----|:-----|
| 🔴 HIGH | 0 | 0 |
| 🟡 MEDIUM | 0 | 0 |
| 🟢 LOW (残余观察) | 6 | 0 |

**得分: 100 − 0 = 100 / 100 → A (PASS)**

## 结论

**✅ PASS (100/100, A) — 设计 v1.3 可进 dev。** 上轮 4 🟡 + O-1 🟢 全部闭环
(3 🟡 全修 + RIG-1 主修), 无 🔴, 无新 🟡。残余 🟢 项不阻塞, 随实现 prompt / 验收清单落地。

### 残余观察项 (🟢, 并入 impl prompt, 不阻塞)

1. **RIG-1 残余**: §3.4 缺函数级改造映射 (within_window→24h 判定 / filter_window→apply_retention /
   truncate_tweets→floor 补足 / build_document 键名 window_hours→retention / fetch_target 调用链);
   §4 断言未命名到方法级 (test_build_document_keys L316-317 / test_write_document_roundtrip L340 /
   test_all_disabled_writes_empty L513) + TestWindowFilter 整类 36h 用例 + max_tweets 默认 20→30
   断言 (test_max_tweets_default / test_max_tweets_zero_falls_back) 未枚举。
2. **O-4 残余**: 规则 "补足至 30" 硬编码 vs 实现 "N=max_tweets" 未显式等价 — 建议将 "30" 写作
   "max_tweets (默认 30)", 避免 per-account override 时 floor 语义漂移。
3. **O-2 残余**: forward 作者提取失败降级粒度未定义 (丢整条 vs "by @unknown: 原文")。
4. **O-3 残余**: Cmd+F 仅 metaKey, 未覆盖 ctrlKey (Windows/Linux 跨平台)。
5. **O-5 残余**: steipete 从名单移除, 既有 twitter.json 数据滚动消失无归档/过渡说明。
6. **新 🟢**: §2.2 D3 "新增 3 账号" vs §3.1 10 账号清单基数未说明 (doc clarity)。

## 实现验收清单 (dev 侧, PASS 后执行)

1. 配置迁移 `data/twitter-targets.yaml` + CONFIG_PATH + 10 账号 + max_tweets 默认 30, 旧根路径文件移除。
2. 条数窗口 30/24h 三规则 + 边界 (=30/=24h 整点) + forward 解析 + 风控三态 (含连续 2 账号提前终止)。
3. 函数改造: within_window/filter_window/truncate_tweets/build_document (键 window_hours→retention) / fetch_target。
4. 前端: header-search + doSearch + Cmd+F 拦截 + 高亮结构化 DOM (textContent) + forward 渲染 + esc。
5. 测试同步更新: 3 处 window_hours 断言 → retention; TestWindowFilter 36h 用例 → 24h/30 用例;
   max_tweets 默认断言 20→30; 新增 forward XSS + 搜索高亮注入用例。
6. crontab/AGENTS.md 文档同步。
7. ops 实测: 多账号采集 + forward 正确 + 搜索/快捷键 + 前端渲染 + pytest 非 selenium 全绿。

---

*报告: documents/reviews/x-hotspot-rereview-v1.3-20260826.md | 结论: ✅ PASS 100/100 (A) | 上轮 4 🟡 + O-1 闭环, 残余 🟢 随 impl prompt 落地*
