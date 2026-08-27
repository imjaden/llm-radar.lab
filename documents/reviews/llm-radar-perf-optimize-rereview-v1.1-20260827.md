# 页面加载速度与用户体验优化 设计 v1.1 — 复审报告

> 日期: 2026-08-27 (复审执行日)
> 项目路径: ~/CodeSpace/llm-radar.lab
> 设计文档: documents/solutions/llm-radar-perf-optimize-design-v1.1-20260827.md (commit 4c98e52)
> 上轮评审: documents/reviews/llm-radar-perf-optimize-review-v1.0-20260827.md (80/100 B, CONDITIONAL PASS)
> 决策: llm-radar-CL002 — D1 A1+2A / D2 B1+3A / D3 C1+4A / D4 D1+5A
> review者: ops/llm-radar-perf-optimize-rereview (hermes-1.2.0)
> review维度: 合理性 / 严格性 / 安全性 (3D + 100-base, 用户阈值 PASS ≥85/A)

## 结论摘要

v1.0 的 4 🟡 (RIG-1~4) 全部修复,证据充分,无残留;2 项顺带观察 (O-1 changelog
重定向 / O-4 边缘缓存窗口) 落地。复审新发现 1 🟡 + 2 🟢:

- **N1 🟡**: §6 验证清单第 3 项冒烟 grep `.text-cobalt-500` — 页面实际 0 使用
  (grep index/changelog 仅 `text-cobalt-300`×4 + `text-cobalt-400`×6); Tailwind CLI
  JIT 只生成 content 扫描到的类 → 预编译产物**必不含** cobalt-500 (config 有定义但
  页面未用同样不生成),照单执行必挂,且无法达成"防 --content 解析遗漏"目的。
  修复: 改 `.text-cobalt-400` (config 定义 + 页面使用,产物必生成) 或删该项。
- N2 🟢: "共 5 处 `?t=`" 数字应为 6 处 (4 index + 2 changelog); 上轮 RIG-1 "实际
  5 处" 亦应为 6 (3 列 + 3 漏 = 6)。枚举完整,无实施影响,纯精度。
- N3 🟢: §6 项 3 "(O-3)" 与项 5 "(O-2 阶段注记)" 引用上轮评审观察项编号,与 v1.1
  §5 观察项重排后 O-1~O-4 (O-2=新增类重构建, O-3=RENDER_CACHE 内存) 冲突,建议
  改指代文字。

**评分: 95 / 100 (A) → ✅ PASS (≥85/A)。** 设计可进 dev;N1 修法明确,并入实现
验收清单 (dev 实施时 §6 冒烟按修正类名执行),不阻塞。未 commit / 未 push (1A 约束)。

## 修复核验表 (上轮 4 🟡 + 2 观察 → v1.1)

| # | v1.0 Finding | Status | 证据 (v1.1 位置 + 独立验证) |
|:--|:-------------|:------:|:---------------------------|
| RIG-1 | B1 `?t=` 枚举不全 | ✅ | §3.2 枚举 6 个位置 (index 452/1027/1235/1282 + changelog 157/166) = grep 全量 6 处 100% 一致,与 D2 "去掉全部" 对齐;页面级 timestamp 重定向 (index 337-345 / changelog 12-15) 显式标注不动,实际读取确认二机制可区分;统一 `{cache:'no-cache'}` 语义 (ETag/Last-Modified → 304 零传输) 成立。仅"共 5 处"数字应为 6 (→ N2 🟢) |
| RIG-2 | D4 缓存失效漏 filter/sort | ✅ | §3.4 复合 key `${tab}\|filterMode\|sourceFilter\|JSON.stringify(sortState[tab])` 覆盖 renderer 内部全部状态 (renderLLMs:696 `sortData(filterItems(...))` 等 6 处,均核验);数据刷新 (refreshData/loadTwitterData 成功) 置空;计数 (renderTab:743-749) 每轮重算与行一致;搜索 doSearch:867 → applySearchFilter 每轮重跑,独立于缓存 — 语义自洽,无陈旧路径 |
| RIG-3 | C1 写盘点误判 history | ✅ | §1+§3.3 只列 1279 `_save_snapshot` → data/snapshot.json (SNAPSHOT_PATH L44);:1353 `_archive_snapshot` → data/history/{week}.json 保持 pretty,与 D3 一致;keep-pretty 列表 (327/674/1312/1372/1700/2041) + overview 1343 已 compact,逐点 grep 归属核验无遗漏 |
| RIG-4 | §4 测试影响漏 ?t= 断言 | ✅ | §4 明确列出 tests/test_html.py:147 `test_twitter_fetch_warn` 硬断言 `'data/twitter.json?t=' + Date.now()`;断言同步方案 (fetch 无 `?t=` + `{cache:'no-cache'}` 存在 + console.warn:148 回退保留) 与用例意图 (独立加载失败不阻断页面) 一致 |
| O-1 | changelog 重定向补注 | ✅ | §3.2 补 changelog.html:12-15 标注不动;实际读取确认 changelog 同款页面重定向 IIFE 存在 |
| O-4 | GH Pages 边缘缓存窗口 | ✅ | §3.2 注记 ~10min 窗口 + 10min 自动刷新自愈 |

## 新发现 (复审第三轮扫描)

| # | Severity | Title | 说明 | 建议 |
|:-:|:--------:|:------|:-----|:-----|
| N1 | 🟡 | §6 冒烟 grep `.text-cobalt-500` 必挂 | 页面 0 使用 cobalt-500 (grep index/changelog 仅 300/400); Tailwind JIT 只生成 content 扫描到的类 → 产物必不含 cobalt-500; 照 §6 项 3 执行该子项必然 0 命中, 且无法达成防静默缺样式目的 | 改 `.text-cobalt-400` (config 定义 + 页面 6 处使用, 产物必生成) 或删该项; 并入实现验收清单 |
| N2 | 🟢 | "共 5 处 `?t=`" 数字 | 实际 6 个位置 (4 index + 2 changelog); 上轮 RIG-1 "实际 5 处" 亦应为 6 (历史遗留, 本轮不追溯) | v1.2 顺手改 "6 处" (或 "6 个位置") |
| N3 | 🟢 | §6 观察项编号引用错位 | 项 3 "(O-3)" / 项 5 "(O-2 阶段注记)" 引用上轮评审 O 编号, 与 §5 重排后 O-1~O-4 冲突 (§5 O-2=新增类重构建, O-3=RENDER_CACHE 内存) | 改指代文字 (如 "上轮 O-3 建议") 或随 v1.2 统一 |

## 维度评估 (3D)

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 合理性 | 🟢 | 四项决策与确认串 9 项完全对应; RIG-1/3 枚举盘点缺陷已闭环, D2/D3 语义与实施面一致; O-4 边缘窗口边界诚实注记 |
| 严格性 | 🟢 | RIG-2 复合 key 覆盖全部 renderer 内嵌状态, 失效路径 (过滤/排序/数据刷新) 无遗漏; RIG-4 测试影响精确到用例行; 新 N1 为验证清单示例类选择错误, 非机制缺陷 |
| 安全性 | 🟢 | 去 CDN 收窄第三方 JS 面 (script-src 移除 cdn.tailwindcss.com, style-src 保留 'unsafe-inline' 因内联 <style> 保留, 均与现状核验一致); RENDER_CACHE 复用既有 renderer 输出, 无新数据注入路径, 沿用 esc()/textContent 体系 |

## 评分明细

```
基准分: 100
  RIG-1~4  ✅ 修复 (不计分)
  O-1/O-4  ✅ 落地 (不计分)
  N1       🟡 -5  §6 冒烟 grep .text-cobalt-500 类不存在/必挂 (验证项设计错误)
  N2/N3    🟢  不计分
────────────────────────
得分: 95 → A → ✅ PASS
```

## 结论

**✅ PASS — 95/100 (A)。** 上轮 4 🟡 + 2 观察全部闭环,设计 v1.1 与源码事实
(grep ?t= / json.dump 归属 / renderer 状态面 / test_html 断言) 逐项一致;新 N1 🟡
修法明确且仅影响验证命令示例 (并入实现验收清单),N2/N3 🟢 不阻塞。

设计 PASS,可进 dev。

## 实现验收清单 (dev 阶段, 照此执行)

核心变更:
1. **D1 样式预编译** (§3.1): 建 tailwind.config.js (提取 index.html:12-21 内联 config:
   colors.cobalt 400/500 + accent 400/500);`npx tailwindcss@3.4.17 -c tailwind.config.js
   -i cache/build/tailwind-input.css -o static/tailwind.css --minify --content
   "index.html,changelog.html"`;index.html:10 / changelog.html:10 CDN script 与内联
   config → `<link rel="stylesheet" href="static/tailwind.css">`;CSP (index.html:6-7 /
   changelog.html:6-7) script-src 移除 cdn.tailwindcss.com;内联 <style> 保留。
2. **D2 条件缓存** (§3.2): 删 6 处 `?t=Date.now()` (index 452/1027/1235/1282 +
   changelog 157/166) → `fetch(url, {cache:'no-cache'})`;页面级重定向
   (index 337-345 / changelog 12-15) **不动**;10min 自动刷新保留。
3. **D3 snapshot compact** (§3.3): collector.py:1279 `indent=2 → indent=None`;
   :1353 (history) / 327 / 674 / 1312 / 1372 / 1700 / 2041 keep-pretty **不动**。
4. **D4 渲染缓存** (§3.4): RENDER_CACHE 复合 key
   `${tab}|${filterMode||''}|${sourceFilter||''}|${JSON.stringify(sortState[tab]||null)}`;
   命中恢复 innerHTML, miss 渲染后写入;refreshData / loadTwitterData 成功后整体置空;
   renderTab 尾部计数与 applySearchFilter/updateSearchSummary 每轮仍执行。
5. **测试同步** (§4): test_html.py:147 断言改为 fetch 无 `?t=` + `{cache:'no-cache'}`
   存在 + console.warn:148 保留;可选新增断言 (a) 双文件无 cdn.tailwindcss.com
   (b) 存在 static/tailwind.css link。

实现文件:
- index.html (CDN/config/CSP/?t=×4/RENDER_CACHE)
- changelog.html (CDN/CSP/?t=×2)
- llm-radar-collector.py (1279 indent)
- tests/test_html.py (:147 断言)
- tailwind.config.js (新) + static/tailwind.css (新产物,入库)
- AGENTS.md (O-2: 记录构建命令,防类新增漂移)

参考:
- 设计方案: documents/solutions/llm-radar-perf-optimize-design-v1.1-20260827.md
- 评审报告: documents/reviews/llm-radar-perf-optimize-review-v1.0-20260827.md (上轮)
- 复审报告: documents/reviews/llm-radar-perf-optimize-rereview-v1.1-20260827.md (本轮)

遗留问题:
- N1 (P1): §6 项 3 冒烟 grep 改 `.text-cobalt-400` (或删),dev 执行验证清单时按修正执行
- N2/N3 🟢: 不阻塞,随 v1.2 或实施时顺手修正

验证 (§6 5 项, 第 3 项按 N1 修正):
1. `python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q` 全绿 (含 :147 更新断言)。
2. 本地 http.server + 网络面板: 无 cdn.tailwindcss.com 请求;二次刷新 snapshot/twitter → 304 (或 200 传输 0);切 tab 流畅;过滤/排序即时更新;数据刷新后表格更新。
3. `ls -lh static/tailwind.css` < 30KB;冒烟 grep `.text-cobalt-400` 与 `.max-w-\[1400px\]` 命中。
4. snapshot.json 重新生成后 ~250K;页面渲染无缺失。
5. CI 绿跑 (机制 2/3 命令,review push 后执行)。

---

*报告: documents/reviews/llm-radar-perf-optimize-rereview-v1.1-20260827.md | 结论: ✅ PASS 95/100 (A) | RIG-1~4 ✅ 全修 + O-1/O-4 ✅ + N1 🟡 (并入 impl) + N2/N3 🟢 | 未 commit / 未 push (1A 约束)*
