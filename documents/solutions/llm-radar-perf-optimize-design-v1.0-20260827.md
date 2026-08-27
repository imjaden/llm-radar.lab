---
title: 页面加载速度与用户体验优化设计
topic: llm-radar
type: design
version: 1.0
date: 2026-08-27
author: hermes-1.2.0
tags: [llm-radar, frontend, performance, tailwind, cache, rendering]
profile: ops
provider: deepseek
model: deepseek-v4-flash
---

# 页面加载速度与用户体验优化设计 v1.0 (llm-radar-CL002)

> 探讨确认(2026-08-27): 决策 D1 A1+B1+C1+D1; 待决策 5 项确认 1A 2A 3A 4A 5A。
> 用户确认串: "A1+B1+C1+D1" + "1A 2A 3A 4A 5A"。
> 闭环: llm-radar-CL002 (新式编号, 续 CL001)。

## 修订记录

- v1.0 (2026-08-27) — 初版: 4 项优化决策锁定 (A1 预编译 CSS / B1 条件缓存 / C1 compact / D1 渲染缓存)。

---

## 1. 背景与目标

现状瓶颈 (实测):

| 瓶颈 | 现状 | 影响 |
|:---|:---|:---|
| Tailwind CDN | index.html:10 + changelog.html:10 引 cdn.tailwindcss.com 运行时 JIT 编译 (~300KB JS) | 每次加载浏览器编译, 首屏慢 |
| 缓存击穿 | 所有数据 fetch 带 `?t=Date.now()` (snapshot/twitter/overview) | 每次刷新/10min 自动刷新全量重下 ~385K (snapshot 316K + twitter 69K) |
| 数据体积 | snapshot.json 写盘 indent=2 (llm-radar-collector.py:1279/:1353) | 316K pretty; 传输/解析偏大 |
| 渲染重建 | renderTab (index.html:738-741) 每次切 tab 全量 `panel.innerHTML=renderers[tab]()` | 切 tab 重复 DOM 重建 + 重新搜索过滤 |

目标:

- 首屏/刷新提速: 去 CDN 运行时编译、避免全量重复下载。
- 保持核心约束: 线上无 build step (预编译产物入库); GitHub Pages 部署不变。
- 数据语义不变: 5 实体 tab 仍读 snapshot.json 单文件; xhotspots 仍独立 twitter.json。

## 2. 决策记录

| # | 决策 | 内容 |
|:---|:---|:---|
| D1 | 样式层 | A1+2A: Tailwind CLI 预编译 static/tailwind.css (minify) 入库; 去掉 CDN 标签与 config 内联; CSP 同步; dev 一次性构建, CI/线上不构建 |
| D2 | 缓存策略 | B1+3A: 去掉全部 `?t=Date.now()`; fetch 加 `{cache:'no-cache'}` 条件请求 (ETag/Last-Modified → 304 零传输); 10min 自动刷新保留 |
| D3 | 数据体积 | C1+4A: snapshot.json 写盘改 compact (indent=None); archive/history/metrics 保持 pretty 不动 |
| D4 | 渲染缓存 | D1+5A: 切 tab 缓存已渲染 panel; 数据刷新 (refreshData/loadTwitterData 成功) 后全部失效重渲染 |

## 3. 详细设计

### 3.1 样式层预编译 (D1/A1)

构建 (dev 一次性, 产物入库):

```bash
cd /Users/jadenli/CodeSpace/llm-radar.lab
# 1) 独立 tailwind.config.js (提取 index.html:12-21 内联 config: colors.cobalt/accent)
# 2) 构建输入 css (含 @tailwind base/components/utilities)
npx tailwindcss@3.4.17 -c tailwind.config.js -i cache/build/tailwind-input.css \
  -o static/tailwind.css --minify --content "index.html,changelog.html"
```

- 产物 static/tailwind.css 提交仓库 (预期 <30KB 压缩); 运行时仅 `<link rel="stylesheet">`。
- index.html:10 与 changelog.html:10 的 `<script src="https://cdn.tailwindcss.com">` +
  index.html:11-22 内联 tailwind.config → 替换为 `<link rel="stylesheet" href="static/tailwind.css">`。
- CSP (index.html:6-7 / changelog.html:7): `script-src` 移除 `cdn.tailwindcss.com`;
  `style-src` 保留 `'unsafe-inline'` (内联 <style> 块仍在) + `fonts.googleapis.com` 不动。
- 内联手写 CSS (<style> 块 ~90 行) 全部保留, 不受影响。
- 已知: `bg-surface-900` (index.html:185/:221) 未在 tailwind.config 定义, CDN Play 下同样
  不生成 (行为一致), 不扩范围 → O-1。

### 3.2 条件缓存 (D2/B1)

- 删除 3 处 `?t=Date.now()`: loadOverview (1235), refreshData (452), loadTwitterData (1027)。
- fetch 改 `fetch(url, {cache:'no-cache'})`: 每次发条件请求, ETag/Last-Modified 命中 → 304
  零传输; 数据更新 → 200 新内容。GitHub Pages 静态文件返回 ETag; 本地 python http.server
  支持 If-Modified-Since → 304 同样生效。
- 10min 自动刷新 / 手动刷新按钮逻辑保留 (仅去除 ?t=)。
- 页面级缓存击穿 (index.html:331-340 timestamp 重定向) 不动 — 属页面刷新机制, 与数据缓存无关。

### 3.3 snapshot compact (D3/C1)

- llm-radar-collector.py:1279 与 :1353: `json.dump(snapshot, f, ensure_ascii=False, indent=2)`
  → `indent=None` (compact)。
- 仅 snapshot.json; archive (1372) / metrics (1700/2041) / fetch-cache (674) / dead-letter (327)
  / timestamp (1312) 保持 pretty 不动 (人工可读性保留)。
- overview.json (1343) 已是 compact, 不动。
- 估算: 316K → ~250K (-20%)。changelog.html 读 snapshot 渲染, JSON 解析与缩进无关 → 兼容。

### 3.4 渲染缓存 (D4/D1)

- 新增 `const RENDER_CACHE = {};`
- renderTab (738): `if (RENDER_CACHE[tab]) panel.innerHTML = RENDER_CACHE[tab];
  else { panel.innerHTML = renderers[tab](); RENDER_CACHE[tab] = panel.innerHTML; }`
- 失效: refreshData 成功 (snapshot 更新) 与 loadTwitterData 成功 (twitter 更新) 后
  `Object.keys(RENDER_CACHE).forEach(k => delete RENDER_CACHE[k])` (或直接置空对象)。
- applySearchFilter / updateSearchSummary 每次仍执行 (只缓存基础渲染, 不缓存过滤/高亮状态,
  避免与搜索状态交互复杂化)。
- 切 tab 从"重建 DOM"变"恢复缓存 HTML" → 显著提速; 数据刷新后自动回退为重建。

## 4. 测试影响

- index.html/changelog.html 改动 → 机制 2/3:
  `python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q`
- collector 写盘改动 → `python3 -m pytest tests/test_gitflow.py -q` + 全量回归;
  核对 test_html/test_timestamp 等是否断言 snapshot 缩进 (预期无 — JSON 解析不依赖缩进)。
- 可选新增 test_html 断言: (a) index.html/changelog.html 无 `cdn.tailwindcss.com` 引用;
  (b) 存在 `<link rel="stylesheet" href="static/tailwind.css">`。 → dev 落地, 防回归。
- CI: 测试命令不变 (CL001 已定型)。

## 5. 观察项

- O-1: bg-surface-900 未在 config — CDN 与 CLI 行为一致 (现状即无效类), 不扩范围; 若后续
  要 header 底色, 在 tailwind.config.js 补 surface 色。
- O-2: 未来 index.html 新增 Tailwind 类需重构建并提交 static/tailwind.css (防漂移: 治理项,
  建议 AGENTS.md 记录构建命令)。
- O-3: RENDER_CACHE 内存: 6 tab HTML 总量 <200KB, 可接受; 不引入淘汰策略。

## 6. 验证清单 (dev 阶段)

1. `python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q` 全绿。
2. 本地 `python3 -m http.server 8080` + 浏览器网络面板:
   - 无 cdn.tailwindcss.com 请求 (样式正常, 对比截图无回归)。
   - 首次加载 200; 二次刷新 snapshot/twitter → 304 (或 200 但传输 0 字节)。
   - 切 tab 流畅; 数据刷新后表格更新 (缓存失效生效)。
3. `ls -lh static/tailwind.css` < 30KB。
4. snapshot.json 重新生成后体积下降 (~250K); 页面渲染数据无缺失。
5. `git push` 后 CI 绿跑 (机制 2/3 命令在 CI 同样通过)。
