---
author: hermes-v0.20.6(2026.8.27)
profile: dev
type: summary
date: 2026-09-08
---

# llm-radar frontend handbook v1.0（站点渲染/前端）

> documents-consolidation phase-2 草稿（只写文件，未 commit）。素材全文（gitignored）：
> `cache/doc-consolidation/llm-radar-frontend-extract.md`。
> 代码行号核实基准：2026-09-08 工作区 `index.html`（1333 行）——08-27 文档写作时行号经 CL002/CL003 增删整体前移，正文一律标现行号。

## 一、定位

本手册覆盖 GitHub Pages 单页站点 `index.html` 的渲染约定与前端演进闭环：emoji 渲染映射（v1.0 约定）+ X 热点弹框增强（CL001 x-preview）+ 页面加载优化（CL002 perf-optimize）+ 拷贝降级修复（CL003 copy-fix）。

素材：11 份 = emoji-mapping 1 + x-preview 3 + perf-optimize 4 + copy-fix 3。

## 二、功能概述

- **站点形态**：Vanilla JS 单页（无框架无 build step），Tailwind 样式（CL002 后为预编译 `static/tailwind.css` 入库，非 CDN）；**6 tab**（tools/llms/providers/people/hotspots/xhotspots，TABS L336 / tab-bar L211-217）；数据经 `snapshot.json`（5 维度）+ `twitter.json`（X 热点）独立加载，10min 自动刷新。
- **emoji 渲染**：`EMOJI_M`（L597，per-dim 专属映射）/ `DIM_EM`（L598，维度默认 providers 🏢 people 👤 tools 🔧 llms 🧠 hotspots 🔥）/ `entEmoji(dim,id)`（L599，llms 前缀回退 gpt-/claude-/gemini-/grok/deepseek/qwen/glm-/hunyuan/seed-… + 兜底 ❓）；热度 emoji `hl(s)`（L479，≥80/60/40/20 → 5..1）+ `he(l)`（L480，{5🔥 4🟠 3🟡 2🔵 1⚪}）+ `hotScore`（L531）。调用点：renderProviders L617 / renderPeople L645 / tools L674 / llms L711。
- **CL001 split-preview 弹框**：`.split-preview` 居中 720px（L57：fixed + top/left 50% + translate + max-width 92vw + max-height 80vh）；<1200px 抽屉降级 `transform:none`（L161）；按钮行 3 枚 `.sp-act` 🔗/👤/📋 + title（L305-308）；sp-title 序号（L1099：`该作者序号/总数 · 全局序号/总数`）；sp-meta（L1105：`@handle · fmtFull(t.posted_at)` 完整时间）；fmtFull L1013。
- **CL002 加载优化四项**：预编译 CSS（link L10，14,061B）去 CDN / 去 6 处 `?t=` 改 `{cache:'no-cache'}` 条件缓存（index 4 处 + changelog 2 处）/ snapshot compact 写盘（collector 侧，体积 -20.2%）/ `RENDER_CACHE` 渲染缓存（L344-345，`clearRenderCache()`）。
- **CL003 拷贝降级链**：`copyTweet`（L1133）→ `navigator.clipboard && navigator.clipboard.writeText` 判空（L1149）→ promise `.catch` → `copyTextFallback()`（L1156-1172：textarea 临时节点 + setAttribute('readonly') + top:-9999px + `document.execCommand('copy')`，0 innerHTML）；反馈 `feedback(ok)`：成功 '已拷贝 ✓' 1500ms / 失败 '拷贝失败' 2000ms 复原，orig='📋'（L1143）。

## 三、机制与指令说明

- **渲染安全基线**（SEC-1 系）：所有外部数据渲染走 `esc()`/textContent 或结构化 DOM（span 分片），0 innerHTML 注入面；链接 https 白名单 + rel=noopener noreferrer；图片 src 二次校验 + onerror 占位；CSP `img-src … https://pbs.twimg.com`。
- **全站搜索（CL001 D4=4B）**：header-search 防抖 ~200ms + Enter；跨 tab 计数汇总 + 跳转高亮；Cmd+F **+Ctrl+F** keydown 拦截（L968-978）；高亮用 TreeWalker + createTextNode + span.textContent（L937-967，0 innerHTML）。
- **渲染缓存复合 key**（renderTab L735-737）：`tab|filterMode|sourceFilter|JSON.stringify(sortState[tab])` 命中恢复 / 未命中写入；`refreshData`/`loadTwitterData` 成功或失败均 `clearRenderCache`（L446/L1027/L1031）；过滤/排序内嵌 renderer，计数每轮 filterItems 重算（L739-744）。
- **样式构建（CL002 后防漂移约定）**：新增 Tailwind 类须重构建提交——`npx tailwindcss@3.4.17 -c tailwind.config.js -i cache/build/tailwind-input.css -o static/tailwind.css --minify --content "index.html,changelog.html"`（产物 <30KB 预算，实测 13.7KB）。运行时仅 `<link>`；CSP script-src 无 cdn.tailwindcss.com。
- **测试区域截取技巧（CL003 RIG-001）**：断言 scope 到函数体——正则 `function copyTweet[\s\S]*?(?=\nfunction spNav)` 截取区域，防全文件子串假阳性（裸 `navigator.clipboard.writeText` 存在于 ago.onclick L1230，localhost 专用 secure context，范围外）。

## 四、用法示例

```bash
# 样式构建（新增类后必做；产物入库提交）
npx tailwindcss@3.4.17 -c tailwind.config.js -i cache/build/tailwind-input.css -o static/tailwind.css --minify --content "index.html,changelog.html"

# 手工验证（浏览器渲染不在 CI 覆盖内）
python3 -m http.server 8080                 # 打开 X 热点 tab 验证分栏/搜索/拷贝
python3 -m http.server 8080 --bind 0.0.0.0   # 非安全上下文验证：http://<局域网IP>:8080 → 拷贝走 execCommand 降级不报 TypeError

# 测试（三闭环后基线；test_html.py 三批用例 TestXHotspotFrontend + TestPerfOptimize + TestCopyTweetFallback）
python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q   # 215-219+ passed
python3 -m pytest tests/test_html.py::TestCopyTweetFallback -q   # 4 passed

# 冒烟（CL002 防回归）
grep -c 'cdn.tailwindcss.com' index.html    # 0
ls -lh static/tailwind.css                  # 14K
grep -n '?t=' index.html changelog.html     # 0 命中（页面级重定向用 URLSearchParams p.set('t',...) 非字面 ?t=）

git checkout -- data/snapshot.json overview.json timestamp.json   # 跑完全量后还原污染
```

## 五、关键决策（原文编号）

> 编号纪律：CL001/002/003 各自含「决策表 D1-Dn」+「确认串字母 A1/B1/…」+「残余 1A~5A」三轨编号，跨闭环撞名（一轮 B1=按钮行 vs 二轮 B1=CI pyyaml；CL002 残余 1A-5A 与 CL003 残余语义无关）——引用必须带闭环前缀。

### 族 A emoji-mapping（2026-07-13，现行约定，无编号体系）

- 规则条款：**id 精确匹配**（非 name——id 是数据管道稳定主键，不受 LLM 改名影响）；五维度默认 fallback（🏢👤🔧🧠🔥）；映射粒度按厂商分节、tools 按类别、llms 按系列前缀共用（GPT 🌀 / Claude 🧬 / Gemini 🔮 / DeepSeek 🐋 / 千问 🛒 等）；热度等级中文级名 爆热🔥/高热🟠/温热🟡/平稳🟢/冷淡⚪；维护约定（新增 24h 内补映射并同步 JS 常量 / 废弃标注日期保留 JS 条目 / 更名 id 不变无需操作 / **季度覆盖度检查**）；v1.0 覆盖 93 providers + 81 people + 99 tools + 82 llms。
- 与 code 漂移 [待核]：doc 常量名 EMOJI_MAP/entityEmoji vs code EMOJI_M/entEmoji；学术键名 tsinghua-university vs tsinghua；code 内嵌为压缩子集；季度覆盖度无落地工具。

### 族 B x-preview（LLM-RADAR-CL001，2026-08-27，新式闭环编号启用首例）

- 问题：split-preview 固定 420px 贴右上偏小；打开原文单文本链接无作者主页/拷贝；sp-title/sp-meta 重复展示；CI 因 PyYAML 未装全红。
- 决策表 **D1-D5**（一轮确认串 A1 B1 C2 D1 E1 + 二轮 A1 B1 C1 D1）：**D1=A1** 居中 720px 大弹窗（translate(-50%,-50%)，max-height 80vh；<1200px 补 transform:none）/ **D2=B1+E1** 三按钮行 🔗打开原文/👤作者主页/📋拷贝推广内容（emoji 零依赖）/ **D3=C2** 拷贝=完整推广素材（正文+forward+指标 kv+原文链接+作者+完整时间）/ **D4=D1** sp-title=「该作者序号/总数 · 全局序号/总数」、sp-meta=「@handle · YYYY-MM-DD HH:MM」/ **D5=B1(二轮)** test.yml pip 补 pyyaml + `-m "not selenium"` + `--ignore=tests/test_selenium.py`。
- 评审 95/A PASS（**RIG-1** 🟡：版本命名不一致——v1.0 文件名承载 v1.1 内容，由 dev 首 commit dd6ec52 git mv 修复；OBS-1~4 🟢 含 OBS-3 一轮/二轮 B1 撞名注记）→ 实现审计 eea7482 **100/100 (A) PASS**（SEC-1 专项零风险面；独立复跑 211+82+13=306 项；OBS-1 失败 2s 复原超出设计落地）。
- 设计观察项来源坑：O-1 序号/拷贝格式无自动化断言（JS 无单测框架）；O-2 clipboard API 非安全上下文不可用（CL003 根因）；O-3 workflow 依赖与 AGENTS.md 双处同步防漂移。

### 族 C perf-optimize（LLM-RADAR-CL002，2026-08-27）

- 现状瓶颈实测：Tailwind CDN 运行时 JIT ~300KB JS / 6 处 `?t=` 每次全量重下 ~385K / snapshot indent=2 316K / renderTab 每次全量重建。
- 决策表 **D1-D4 × 双轨确认**：**D1=A1+2A** Tailwind CLI 预编译 static/tailwind.css（minify）入库去 CDN，CSP 同步，dev 一次性构建 / **D2=B1+3A** 去 `?t=` 改 `{cache:'no-cache'}` 条件请求（304 零传输），10min 刷新保留 / **D3=C1+4A** snapshot 写盘 compact indent=None（archive/history/metrics 保持 pretty）/ **D4=D1+5A** renderTab 缓存已渲染 panel，数据刷新后失效重渲染。
- 评审 80/B CONDITIONAL（**RIG-1** `?t=` 枚举 3→实际 **6 处**（漏 init() 首屏 + changelog 2 处）/ **RIG-2** 缓存失效漏 filter/sort → 复合 key / **RIG-3** 写盘点误判：:1353 是周归档非 snapshot（snapshot 仅 1279 一处）/ **RIG-4** 漏 test_html.py:147 硬断言 '?t='）→ rereview v1.1 95/A PASS（+新 **N1** 🟡：冒烟 grep `.text-cobalt-500` 必挂——页面 0 使用，Tailwind JIT 不生成；改 `.text-cobalt-400`）→ 实现审计 8f008e7 **100/100 (A) PASS**（8 文件 107+/36-；体积 -20.2% 实测与估算一致；CDN 0 残留）。

### 族 D copy-fix（LLM-RADAR-CL003，2026-08-27）

- 问题：① 用户手工微调按钮纯图标化未入库 ② `Uncaught TypeError: Cannot read properties of undefined (reading 'writeText')`——navigator.clipboard 非安全上下文为 undefined，抛错发生在 promise catch 之前（CL001 OBS-2 只覆盖 promise 失败）。
- 决策表 **D1-D5**（确认 A1 B2+B3 C1 D1 + 残余 2A）：**D1=A1** 降级链 `navigator.clipboard?.writeText` 防御 + textarea/execCommand 兜底 / **D2=B2** 成功 '已拷贝 ✓' 1500ms 失败 '拷贝失败' 2000ms；orig '📋 拷贝'→'📋' / **D3=B3** 三按钮 title / **D4=C1+D1** 手工微调+修复同一 commit + test_html 断言 / **D5=2A** execCommand 按返回值 true/false 反馈。
- 评审 95/A PASS（**RIG-001** 🟡：断言防假阳性——若全文件子串 'navigator.clipboard.writeText' 会**修复前就变绿**（ago.onclick L1230 裸调用）；修法=函数体区域截取 + 兼容正则 `navigator\.clipboard(?:\.|\s*&&\s*navigator\.clipboard)\.writeText`）→ 实现审计 0013b84 **100/100 (A) PASS**（2 文件 78+/12-；4 用例 TestCopyTweetFallback；负断言 `"const orig = '📋 拷贝'" not in region` 锁定 D2 核心；'📋 拷贝' 零残留）。

## 六、已知坑

1. **编号引用必须带闭环**：CL001-003 均三轨编号且跨轮撞名（一轮 B1 vs 二轮 B1）；emoji-mapping 无编号体系。
2. **emoji 三处口径不一致** [待核]：doc 热度平稳=🟢 vs code he() level 2=🔵；前端 hl 阈值 40/20 vs collector `_score_to_level` 30/10；tab 栏 llms 用 🤖（L213）vs DIM_EM.llms=🧠（L598）。
3. **emoji-mapping doc 与 code 漂移** [待核]：常量名/学术键名/覆盖条目数（code 压缩子集）；季度覆盖度检查无落地工具——改映射需双处同步。
4. **index.html 行号易漂移**：CL002/003 增删整体前移（.split-preview 69→57 等）；引用以 2026-09-08 现行号为准。
5. **新增 Tailwind 类必须重构建提交**（O-2 防漂移根因）；自定义色类（cobalt 400/500、accent 400/500）已入 config，CDN 时代未定义类不再可用。
6. **浏览器渲染不在 CI**（IMPL-OBS-2）：Selenium 测试靠 `-m "not selenium"` 排除 + GITHUB_ACTIONS skipif 双保险；渲染验证靠本地 http.server 手工。
7. **拷贝降级边界**：ago.onclick（L1230）仍有裸 `navigator.clipboard.writeText`（localhost 专用 secure context，范围外）；iOS Safari execCommand 需 setSelectionRange（O-3 未补，🟢 观察）。
8. **测试计数随用例演进**：215 → 216 → 219 passed 系 test_html 三批用例（TestXHotspotFrontend/TestPerfOptimize/TestCopyTweetFallback）累积，非矛盾。

## 七、参考文档

| 源文件（原位 documents/…） | 角色 | 处置 |
|---|---|---|
| emoji-mapping-v1.0-20260713.md | 现行 emoji 约定/映射表 | **保留原位**（documents/ 根；与手册并存，漂移见 §6-2/3） |
| solutions/llm-radar-x-preview-design-v1.1-20260827.md | CL001 design 终版 | 已归档 → archive/solutions-20260908/ |
| reviews/llm-radar-x-preview-review-v1.0-20260827.md | CL001 评审 | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-x-preview-impl-audit-v1.0-20260827.md | CL001 审计（族终审） | 已归档 → archive/reviews-20260908/ |
| solutions/llm-radar-perf-optimize-design-v1.1-20260827.md | CL002 design 终版 | 已归档 → archive/solutions-20260908/ |
| reviews/llm-radar-perf-optimize-review-v1.0-20260827.md | CL002 评审 | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-perf-optimize-rereview-v1.1-20260827.md | CL002 复审 | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-perf-optimize-impl-audit-v1.0-20260827.md | CL002 审计（族终审） | 已归档 → archive/reviews-20260908/ |
| solutions/llm-radar-copy-fix-design-v1.0-20260827.md | CL003 design 终版 | 已归档 → archive/solutions-20260908/ |
| reviews/llm-radar-copy-fix-review-v1.0-20260827.md | CL003 评审 | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-copy-fix-impl-audit-v1.0-20260827.md | CL003 审计（族终审） | 已归档 → archive/reviews-20260908/ |

交叉引用：`cache/doc-consolidation/llm-radar-frontend-extract.md`（gitignored 提炼产物）；X 热点采集端见 collector-pipeline handbook；热度等级数值口径（collector `_score_to_level`）与 git 自愈无关但同仓——口径对齐见 §6-2 [待核]。
