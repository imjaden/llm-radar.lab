---
title: X 热点弹框体验增强与 CI 依赖修复设计
topic: llm-radar
type: design
version: 1.1
date: 2026-08-27
author: hermes-1.2.0
tags: [llm-radar, x, frontend, split-preview, clipboard, github-actions]
profile: ops
provider: deepseek
model: deepseek-v4-flash
---

# X 热点弹框体验增强与 CI 依赖修复设计 v1.1

> 探讨确认(2026-08-27): 决策 D1 A1 / D2 B1+E1 / D3 C2 / D4 D1 / D5 锁定。
> 用户确认串: "A1 B1 C2 D1 E1" + 追加 GitHub Action 报错分析请求;二轮澄清
> "CI 只测部分功能,浏览器相关仅本地" 确认串: "A1 B1 C1 D1"。
> 闭环: llm-radar-CL001 (新式编号启用首例, draft 绑定即永久启用)。

## 修订记录

- v1.0 (2026-08-27) — 初版: X 热点弹框体验 4 项决策 + CI pyyaml 依赖修复。
- v1.1 (2026-08-27) — 二轮澄清并入: CI 测试范围显式排除浏览器相关
  (A1: `-m "not selenium"` + `--ignore=tests/test_selenium.py`);pyyaml 修复一并
  (B1);本地验证命令集保持现状 (C1);前端弹框与 CI 修复同一设计同一轮
  review→dev (D1)。

---

## 1. 背景与目标

X 热点 tab 的 split-preview 分栏详情(X 热点采集 CL-SEC19/20 已上线)存在 3 个体验问题:

1. 弹框固定 420px 宽、贴右上角,偏小且不在视野中心。
2. "打开原文"是单个文本链接,无作者主页/拷贝能力。
3. sp-title 与 sp-meta 重复展示作者+时间,无位置序号信息。

同时 GitHub Actions CI 全红: `TestMainPaths.test_empty_targets_writes_empty` 等
twitter-collector 测试因 PyYAML 未安装而失败。

约束 (继承):

- 无 build step,Vanilla JS + Tailwind CDN;前端渲染全字段转义 (esc()/textContent, SEC-1)。
- <1200px 响应式: 分栏变全屏底部抽屉 (§5.5),该分支行为不变,仅需防 transform 残留。
- 图片直引 pbs.twimg.com + onerror 占位;协议白名单 https:// 二次校验 (SEC-1 双保险)。

## 2. 决策记录

| # | 决策 | 内容 |
|:---|:---|:---|
| D1 | 弹框尺寸/位置 | A1: 居中大弹窗 — width 720px, top/left 50% + translate(-50%,-50%), max-height 80vh;<1200px 分支补 transform:none |
| D2 | 按钮清单/样式 | B1+E1: body 底部图标按钮行 3 枚 — 🔗 打开原文 / 👤 作者主页 / 📋 拷贝推广内容 (emoji, 零依赖) |
| D3 | 拷贝内容格式 | C2: 完整推广素材 — 正文+forward+指标 kv+原文链接+作者+完整时间 |
| D4 | 标题/元信息 | D1: sp-title = "该作者序号/总数 · 全局序号/总数"; sp-meta = "@handle · YYYY-MM-DD HH:MM(本地完整时间)" |
| D5 | CI 修复 | B1(二轮): test.yml pip install 补 pyyaml + 测试命令显式排除浏览器相关(A1 细则见 §3.5) |

## 3. 详细设计

### 3.1 弹框尺寸与位置 (D1)

index.html:69 `.split-preview` 修改:

```css
.split-preview { position:fixed; top:50%; left:50%; transform:translate(-50%,-50%);
                 width:720px; max-width:92vw; max-height:80vh; ... 其余不变 }
```

index.html:172 `<1200px` 分支补 transform 重置(陷阱: 若不重置,底部抽屉会被
translate(-50%,-50%) 向左上偏移半个自身尺寸):

```css
.split-preview { top:auto; bottom:0; left:0; right:0; width:100%; max-width:100%;
                 max-height:85vh; border-radius:12px 12px 0 0; transform:none; }
```

影响面: 纯 CSS 属性修改,无 JS 逻辑变化;sp-nav/sp-close/sp-metrics 等子元素样式不动。

### 3.2 按钮行 (D2)

HTML (index.html:316 替换 `sp-link` 单链接):

```html
<div class="sp-actions">
  <a class="sp-act" id="sp-act-link" href="#" target="_blank" rel="noopener noreferrer">🔗 打开原文</a>
  <a class="sp-act" id="sp-act-profile" href="#" target="_blank" rel="noopener noreferrer">👤 作者主页</a>
  <button class="sp-act" id="sp-act-copy" type="button">📋 拷贝</button>
</div>
```

CSS (替换/新增,继承 sp-link 的 display:none 默认 + show 时显示):

```css
.sp-actions { display:flex; gap:8px; margin-top:12px; flex-wrap:wrap; }
.sp-act { display:none; padding:4px 12px; border-radius:8px; font-size:0.75rem;
          cursor:pointer; background:#16161f; border:1px solid #4f46e5; color:#818cf8;
          text-decoration:none; align-items:center; gap:4px; }
.sp-act:hover { color:#facc15; border-color:#facc15; background:rgba(79,70,229,0.15); }
```

JS openSplitPreview 内 (1102-1104 逻辑扩展):

- `sp-act-link`: t.url 匹配 /^https:\/\// → 显示 + href,否则 display:none(继承现状)。
- `sp-act-profile`: tg.url 匹配 /^https:\/\// → 显示 + href(数据已有: twitter.json target.url =
  https://x.com/<handle>,实测 10 账号均有),否则 display:none。
- `sp-act-copy`: 每次打开重绑 onclick = () => copyTweet(f);执行成功后按钮文字
  "已拷贝 ✓" 1500ms 复原(沿用 index.html:1166 ago.onclick 先例);失败 catch → "拷贝失败"。
- 安全: 按钮文字用 textContent/静态 HTML(无用户数据注入);href 仅经 https 白名单。

### 3.3 拷贝内容格式 (D3)

copyTweet(f) 组装纯文本(仅 textContent,无 HTML):

```
@{handle} ({name})
{YYYY-MM-DD HH:MM 本地}
{text}
forward: {forward}        ← 仅当 t.forward 非空
浏览 {views} · 回复 {replies} · 转推 {retweets} · 点赞 {likes}   ← null → —
原文: {url}               ← 仅当 t.url 存在
```

- 空 text 且空 forward → 正文行省略,防空行噪音。
- null 指标 → "—" 与表格一致;url 缺失 → 省略"原文"行。
- 实现: navigator.clipboard.writeText;失败降级按钮反馈,不弹 alert(避免打断)。

示例(实际渲染效果):

```
@dhh (DHH)
2026-08-26 16:40
PSA: My X mentions are out of control...
浏览 1908 · 回复 3 · 转推 1 · 点赞 32
原文: https://x.com/dhh/status/2092532552523235423
```

### 3.4 标题/元信息序号 (D4)

- 新增 `fmtFull(iso)` → "YYYY-MM-DD HH:MM"(本地,复用 fmtMMDD 的 padding 逻辑,补年份)。
- sp-title.textContent = `${posInAuthor}/${totalInAuthor} · ${i+1}/${X_ITEMS.length}`
  - posInAuthor: X_ITEMS 中同 targetIndex 子集内当前项位置+1。X_ITEMS 按 posted_at
    全局降序,V8 sort 稳定 → 同作者子集保持降序,indexOf 即位置。
  - totalInAuthor: 同 targetIndex 子集长度(与 tg.tweets.length 一致,无过滤时)。
  - i+1: 全局序号 = 当前渲染索引+1;X_ITEMS.length: 全局总数(与表格行数一致)。
- sp-meta.textContent = `@${tg.handle} · ${fmtFull(t.posted_at)}`;posted_at 空 → "—"。

改动点: 1084 行 sp-title、1090 行 sp-meta;新增 fmtFull;序号计算在 openSplitPreview 内
一次完成(无需新状态)。

### 3.5 CI 修复与测试范围 (D5)

根因(已对照源码确认):

1. .github/workflows/test.yml:13 依赖安装列表:
   `pip install pytest openai requests beautifulsoup4 selenium webdriver-manager prettytable`
   **缺 pyyaml**(AGENTS.md Dependencies 含 pyyaml,workflow 与文档漂移)。
2. scripts/twitter-collector.py:37-40 `import yaml` 失败 → yaml=None;
   :83-84 parse_config 直接 `raise ConfigError('PyYAML 未安装: pip3 install pyyaml')`;
   main 捕获 ConfigError → exit 1。
3. tests/test_twitter_collector.py:763 断言 `main(['--collect']) == 0` → 1 != 0 失败。
   报错仅展示 1 例,实际所有走 parse_config 的用例(空配置/缺字段/10 账号等)全红。
4. 本地不炸: 本机 Python 已预装 pyyaml;CI 为干净环境,只装 workflow 所列依赖。

修复(A1+B1 确认):

1. test.yml:13 行尾追加 `pyyaml`(与 AGENTS.md Dependencies 对齐)。
2. test.yml:14 测试命令改为显式排除浏览器相关(CI 只测部分功能):
   ```yaml
   - run: python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_selenium.py -v --tb=short
   ```
   理由与边界:
   - test_html.py 两个 @pytest.mark.selenium 渲染测试(macOS runner 自带 Chrome,
     实际会真跑 localhost 页面)→ `-m "not selenium"` 排除,仅本地执行。
   - test_selenium.py 已有 `GITHUB_ACTIONS==true` skipif,`--ignore` 双保险。
   - twitter-collector 单元测试全部 FakeDriver + fixture HTML(556 行注释"不需浏览器"),
     **不访问 twitter**,在 CI 正常执行(纯逻辑验证,正是"部分功能"的保留部分)。
   - 采集脚本运行本身(需 Selenium+登录态)本就不在 CI 执行,无变化。
3. 本地验证命令集(AGENTS.md 机制 2/3)保持现状 (C1):
   `python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q`

## 4. 测试影响

- index.html 改动 → 按 AGENTS.md 机制 2/3,dev 提交前必须跑:
  `python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q`
- test_html.py 仅扫 <script> 块语法(CSS 改动不属其检查范围);JS 无单测框架,
  fmtFull/copyText 行为靠 Selenium 渲染补充验证(观察项 O-1)。
- CI workflow 改动 → 无测试文件影响,下次 push 由 CI 自身验证(twitter-collector 用例转绿)。

## 5. 观察项

- O-1: 序号/拷贝格式是否加自动化断言 — 现 JS 无单测框架,保持 test_html 语法检查 +
  Selenium 手工验证,记观察。
- O-2: clipboard API 在非安全上下文 (http:// 非 localhost) 不可用 — 本部署为 GitHub
  Pages https,无碍;失败 catch 按钮反馈兜底。
- O-3: workflow 依赖列表与 AGENTS.md Dependencies 双处同步,防再次漂移(本次即漂移根因)。

## 6. dev 阶段验证清单

1. `python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q` 全绿。
2. 本地 `python3 -m http.server 8080` → X 热点 tab → 点行/详情按钮:
   - 弹框居中、宽 720px、正文可读。
   - 按钮行 3 枚;拷贝后粘贴含 正文+指标+链接;作者主页打开 https://x.com/<handle>。
   - sp-title 序号正确(抽样核对表格行序);sp-meta 完整时间。
3. 窗口 <1200px: 底部抽屉无偏移(transform 重置生效)。
4. `git push` 后 CI 绿(twitter-collector 用例不再报 PyYAML)。
