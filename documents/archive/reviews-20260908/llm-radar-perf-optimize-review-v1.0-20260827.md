# 页面加载速度与用户体验优化 设计 v1.0 — 评审报告

> 日期: 2026-08-27 (评审执行日)
> 项目路径: ~/CodeSpace/llm-radar.lab
> 设计文档: documents/solutions/llm-radar-perf-optimize-design-v1.0-20260827.md (commit 138f62d)
> 决策: LLM-RADAR-CL002 — D1 A1+2A / D2 B1+3A / D3 C1+4A / D4 D1+5A; 编号 1A=LLM-RADAR-CL002
> 用户确认串: "A1+B1+C1+D1" + "1A 2A 3A 4A 5A"
> review者: ops/llm-radar-perf-optimize-review (hermes-1.2.0)
> review维度: 合理性 / 严格性 / 安全性 (3D + 100-base, 用户阈值 PASS ≥85/A)

## 结论摘要

架构方向正确、四项决策与两轮确认串完全对应 (D1-D4 × 9 项无遗漏无越界)、核心机制
(A1 预编译 / B1 304 条件请求 / C1 compact / D1 渲染缓存) 均成立。但发现 4 项 🟡 问题,
其中 3 项为**枚举/盘点遗漏** (按字面实施会破坏决策意图), 1 项为**状态陈旧语义缺陷**:

- **RIG-1 🟡**: B1 的 `?t=` 枚举不全 — 设计列 3 处, 实际 5 处 (漏 index.html:1282 init()
  初始 snapshot 加载 + changelog.html:157/:166 两处)。按字面实施, 首屏 316K 仍全量下载,
  B1 核心目标在首屏路径落空, 与 D2 "去掉全部" 不符。
- **RIG-2 🟡**: D4 缓存失效条件遗漏 filter/sort 交互 — 过滤/排序在 renderer 内部
  (renderLLMs:696 `sortData(filterItems(...))` 等 6 处), setFilter/toggleSource/toggleSort
  触发 renderTab 时缓存命中 → 面板行不更新, 与 tc- 计数 (每次重算) 不一致。
  设计"只缓存基础渲染, 不缓存过滤状态"的语义模型不成立。
- **RIG-3 🟡**: C1 写盘点误判 — :1353 是 `_archive_snapshot` 写 `data/history/{week}.json`
  (周归档, 实测 2026-W32/33/34 存在), **不是** snapshot.json 写点 (snapshot.json 仅 1279
  一处); §1 现状表与 §3.3 与 D3 "archive/history 保持 pretty" 直接矛盾。
- **RIG-4 🟡**: §4 测试影响遗漏 — tests/test_html.py:147 `test_twitter_fetch_warn`
  硬断言 `'data/twitter.json?t=' + Date.now()`, B1 落地后该用例必挂; §4 仅核对缩进断言。

**评分: 80 / 100 (B) → ⏳ CONDITIONAL PASS (<85/A)。** 4 🟡 待修正 → 回 ops 修复设计
bump v1.1 重审; 不生成实现 prompt; 未 commit / 未 push (1A 约束)。

## 逐项验证表 (7 项重点审查)

| # | 审查项 | 验证方法 | 结果 |
|:-:|:-------|:---------|:----:|
| 1 | §3.1 A1 预编译 | read index.html:6-22 / changelog.html:6-16 + grep cdn.tailwindcss + static/ 目录 + node/npx 可用性 | ✅ |
| 2 | §3.2 B1 条件缓存 | grep `?t=` 全量 + fetch 调用面 + 304 语义推演 (GH Pages ETag / http.server If-Modified-Since) | ⚠️ RIG-1 |
| 3 | §3.3 C1 snapshot compact | grep json.dump 10 处 + read collector.py:1274-1373 逐点归属 | ⚠️ RIG-3 |
| 4 | §3.4 D1 渲染缓存 | read renderTab:738-751 + renderers (696 等) + setFilter/toggleSource/toggleSort/doSearch 调用面 | ⚠️ RIG-2 |
| 5 | §4 测试影响 | grep tests/ `?t=`/indent/tailwind/cdn + read test_html.py:144-148 | ⚠️ RIG-4 |
| 6 | §6 验证清单可执行性 | 5 项逐条推演 + node v26/npx 11.16 实测 | ✅ (O-2 阶段注记) |
| 7 | 决策对应完整性 | D1-D4 × 确认串 9 项逐项比对 (A1/B1/C1/D1 + 1A-5A) | ✅ |

## 数据验证

| # | 验证项 | 方法 | 结果 |
|:-:|:-------|:-----|:-----|
| 1 | 设计文件 + commit | git log --oneline -3 | ✅ 138f62d 为 HEAD, design v1.0 主题合规, 工作区 clean |
| 2 | CDN/config/CSP 现状 | read index.html:6-22 + changelog.html:6-16 | ✅ 双文件 :10 CDN script + :6-7 CSP script-src 含 cdn.tailwindcss.com; index.html:12-21 内联 config (cobalt/accent); changelog.html **无** 内联 config (设计"+ config"表述仅限 index, 正确) |
| 3 | bg-surface-900 | read index.html:185/:221 | ✅ 与设计行号一致; 未在 config 定义 → CLI 与 CDN Play 均不生成, O-1 边界成立 |
| 4 | ?t= 全量盘点 | grep index.html + changelog.html fetch( | ⚠️ index 4 处 (452/1027/1235/1282) + changelog 2 处 (157/166) = **5 处数据 fetch 带 ?t=**, 设计仅列 3 → RIG-1 |
| 5 | timestamp 重定向 | read index.html:336-345 + changelog.html:12-15 | ✅ 机制识别正确 (实际行号 337-345, 设计写 331-340 含注释块偏移, 无功能影响); changelog 同款重定向未提及 → O-1 |
| 6 | json.dump 写点归属 | grep json.dump + read collector.py:1274-1373 | ⚠️ 1279=_save_snapshot→data/snapshot.json (SNAPSHOT_PATH L44); **1353=_archive_snapshot→data/history/{week}.json** → RIG-3; 其余 keep-pretty 列表 (327/674/1312/1372/1700/2041) 与 overview 1343 已 compact 均核验正确 |
| 7 | renderers 状态内嵌 | read renderLLMs:696 + grep filterItems/sortState 调用面 | ⚠️ renderHotspots:576 / renderProviders:610 / renderPeople:637 / renderTools:665 / renderLLMs:696 / renderXHotspots:1058-1062 全在 renderer 内部应用 filterMode+sourceFilter+sortState → RIG-2 |
| 8 | filter/sort/search 触发器 | read setFilter:383-387 / toggleSource:406-410 / toggleSort:568-571 / doSearch:864-868 / switchTab:753-765 | ✅ doSearch→applySearchFilter 每次重跑, 搜索无陈旧 (设计声明成立); 过滤/排序 3 处未失效 → RIG-2 |
| 9 | 测试断言盘点 | grep tests/ `?t=`/indent/tailwind/cdn + read test_html.py:144-148 | ⚠️ test_html.py:147 硬断言 `?t=` → RIG-4; 缩进断言 0 命中 (设计 §4 "预期无" 正确); conftest.py:46 为 fixture 写 sample, test_overview:83-90 断言 overview compact (不受影响) |
| 10 | 体积/环境事实 | ls -lh data/*.json + node/npx --version | ✅ snapshot 316K / twitter 69K / overview 408B 与设计一致; node v26.0.0 + npx 11.16.0 → 构建命令可执行; .gitignore 覆盖 cache/ + *.log, static/tailwind.css 可入库 |
| 11 | changelog 兼容性 | read changelog.html:166 | ✅ fetch snapshot.json → JSON.parse, 与缩进无关 (C1 兼容声明成立) |

## 维度评估 (3D)

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 合理性 | 🟡 | 决策闭环完整、9 项确认完全映射; A1 预编译/CSP 收紧/双页面覆盖方向正确; B1 "去掉全部" 与枚举 3 处不符 (RIG-1) |
| 严格性 | 🟡 | D4 失效条件遗漏 filter/sort 交互 (RIG-2); C1 写盘点误判 history 为 snapshot (RIG-3); §4 测试影响盘点缺 ?t= 断言 (RIG-4) |
| 安全性 | 🟢 | 去 CDN 收窄第三方 JS 面; CSP script-src 收紧方向正确; RENDER_CACHE 缓存既有 renderer 输出, 不引入新数据注入路径, 沿用 esc()/textContent 体系 |

## 发现项

### RIG-1 🟡 — B1 `?t=` 枚举不全: 设计列 3 处, 实际 5 处 (含首屏 init)

- **问题**: §3.2 "删除 3 处 `?t=Date.now()`: loadOverview (1235), refreshData (452),
  loadTwitterData (1027)" — 漏 3 处: **index.html:1282 init() 初始 snapshot 加载** +
  **changelog.html:157 (overview.json) / :166 (snapshot.json)**。D2 决策声明 "去掉全部
  `?t=Date.now()`" 与 §3.2 枚举矛盾。
- **影响**: 按字面实施, 首屏 (init) 仍带 cache-busting → 316K snapshot 每次全量下载,
  本次优化最重要的"首屏提速"目标落空; changelog 页面 (同样 316K) 不受益。
- **修复**: §3.2 枚举改 5 处 (index 452/1027/1235/1282 + changelog 157/166), 统一改
  `fetch(url, {cache:'no-cache'})`; changelog 的页面级 ?t= 重定向 (157/166 是数据 fetch)
  与 O-1 的页面重定向 (12-15) 区分标注。

### RIG-2 🟡 — D4 缓存失效条件遗漏 filter/sort 交互 → 陈旧面板 + 计数不一致

- **问题**: 过滤/排序内嵌于 renderer: renderLLMs:696 `sortData(filterItems(DATA.llms),
  'llms', s.col, s.dir)` (s=sortState.llms), 同型 renderHotspots:576 /
  renderProviders:610 / renderPeople:637 / renderTools:665 / renderXHotspots:1058-1062。
  setFilter (386) / toggleSource (409) / toggleSort (571) 均触发 renderTab → RENDER_CACHE
  命中时面板行保持旧过滤/排序; 而 tc- 计数 (743-748) 每次经 filterItems 重算 → 计数与行
  不一致。设计声称"只缓存基础渲染, 不缓存过滤/高亮状态"的语义模型不成立 — 过滤/排序在
  "基础渲染"内部。搜索 (doSearch:867 → applySearchFilter:918 每次重跑) 无此问题。
- **影响**: 切 tab 后切换国家/来源过滤或点列排序 → 面板无响应 (仅计数变), 可见 UX 回归,
  与本优化"体验"目标相悖。
- **修复**: 二选一 (设计需显式): 方案 A (推荐, 保留大部分收益): RENDER_CACHE key 复合
  `${tab}|${filterMode}|${sourceFilter}|${JSON.stringify(sortState[tab])}`; 方案 B (最简):
  setFilter / toggleSource / toggleSort 内 `delete RENDER_CACHE[activeTab]` (或整体置空)。

### RIG-3 🟡 — C1 写盘点误判: :1353 是 history 周归档, 非 snapshot.json

- **问题**: §1 现状表 "snapshot.json 写盘 indent=2 (llm-radar-collector.py:1279/:1353)"
  与 §3.3 "1279 与 :1353 → indent=None" 均把 1353 当 snapshot 写点; 实际 **1353 是
  `_archive_snapshot` → data/history/{week}.json** (周快照归档, 实测 2026-W32/33/34 存在),
  snapshot.json (SNAPSHOT_PATH=collector.py:44) 唯一写点是 1279 `_save_snapshot`。
- **影响**: 与 D3 决策 "archive/history/metrics 保持 pretty 不动" 直接矛盾; §3.3 keep-pretty
  列表列了 archive (1372) 却未列 history (1353), 内部不一致。按字面实施会把周归档 compact,
  破坏归档人工可读性意图 (功能无损, 但违反自身决策)。
- **修复**: §1 现状表 + §3.3 只列 1279; 1353 (history) 保持 pretty, 与 archive (1372) 同理。
  D3 决策本身正确, 无需改。

### RIG-4 🟡 — §4 测试影响遗漏: test_html.py:147 硬断言 `?t=`, B1 落地必挂

- **问题**: tests/test_html.py:147 `test_twitter_fetch_warn`:
  `assert "'data/twitter.json?t=' + Date.now()" in js`。§4 仅核对"是否断言 snapshot 缩进
  (预期无)", 未盘点 `?t=` 断言; 实测 grep tests/ `?t=` 唯一命中即此处。
- **影响**: dev 按 B1 删除 ?t= 后该用例失败; 不知情者可能误改断言意图或误判实现错误。
- **修复**: §4 明确列出 :147; 断言同步改为 `fetch('data/twitter.json'` + `{cache:'no-cache'}`
  存在 + console.warn 回退保留 (用例意图不变: 独立加载失败不阻断页面)。

### 观察项 (🟢, 不扣分)

| # | Severity | 事项 | 说明 |
|---|----------|------|------|
| O-1 | 🟢 | changelog.html:12-15 也有页面级 timestamp 重定向 | §3.2 仅列 index.html:331-340 (实际 337-345); changelog 同款机制未提及, 同属"不动"范围, 无功能影响, 建议补一句 |
| O-2 | 🟢 | §6 验证项 5 "git push 后 CI 绿跑" 阶段归属 | dev 无 push 权限 (push 仅 review profile), 该项实际在 review push 后执行; 建议标注阶段 |
| O-3 | 🟢 | 构建命令 `--content "index.html,changelog.html"` 解析依赖 | tailwind CLI v3 支持逗号分隔, 但 content 放 tailwind.config.js 更稳; 建议 §6 增构建产物冒烟 grep 关键类 (如 `.text-cobalt-500` / `.max-w-\[1400px\]`), 防 --content 解析遗漏导致静默缺样式 |
| O-4 | 🟢 | GH Pages 边缘缓存窗口 | `cache:'no-cache'` 仅约束浏览器; 数据更新后边缘 (~10min) 窗口内刷新可能仍拿旧文件; 10min 自动刷新自愈, 建议文档注明边界。本地 http.server If-Modified-Since → 304 语义核验成立 |

## 评分

| 级别 | 数量 | 扣分 |
|:-----|:-----|:-----|
| 🔴 HIGH | 0 | 0 |
| 🟡 MEDIUM | 4 (RIG-1~4) | -20 |
| 🟢 LOW (观察) | 4 (O-1~4) | 0 |

**得分: 100 − 20 = 80 / 100 → B → CONDITIONAL PASS (<85/A)**

## 结论

**⏳ CONDITIONAL PASS (80/100, B) — 设计 v1.0 待修正, 不可直接进 dev。** 无 🔴, 4 🟡
(RIG-1 ?t= 枚举 / RIG-2 缓存失效 / RIG-3 写盘点 / RIG-4 测试断言), 4 🟢 观察。

架构与决策方向正确, 但 4 项中 3 项属"按字面实施即偏离决策意图"的盘点缺陷, 1 项属可
复现的交互陈旧 bug — 均须在设计中显式修正后 bump v1.1 重审。

## 待修正项 (回 ops, 设计 v1.1)

1. **§3.2**: `?t=` 枚举 3 → 5 处 (补 index.html:1282 init + changelog.html:157/:166), 与 D2 "去掉全部" 对齐。
2. **§3.4**: RENDER_CACHE 失效条件补 filter/sort — 明确采用复合 key (推荐) 或 setFilter/toggleSource/toggleSort 置空。
3. **§1 + §3.3**: 写盘点只列 1279 (_save_snapshot → snapshot.json); :1353 (history 周归档) 保持 pretty, 与 D3 一致。
4. **§4**: 补 tests/test_html.py:147 `?t=` 断言影响 + 同步更新断言 (fetch 无 ?t= + {cache:'no-cache'} + console.warn 保留)。
5. **(顺带, O-1/O-3)**: changelog 页面重定向补注; §6 增构建产物冒烟 grep 关键类。

---

*报告: documents/reviews/llm-radar-perf-optimize-review-v1.0-20260827.md | 结论: ⏳ CONDITIONAL PASS 80/100 (B) | RIG-1~4 🟡 待修 + O-1~4 🟢 | 未 commit / 未 push (1A 约束)*
