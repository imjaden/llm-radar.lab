# X热点弹框体验+CI修复 设计 v1.1 — 评审报告

> 日期: 2026-08-27 (评审执行日)
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.lab
> 设计文档: documents/solutions/llm-radar-x-preview-design-v1.1-20260827.md (commit adf9b2a)
> 决策: llm-radar-CL001 — D1 A1 / D2 B1+E1 / D3 C2 / D4 D1 / D5 (二轮 B1+A1); 二轮 A1 B1 C1 D1
> 用户确认串: 一轮 "A1 B1 C2 D1 E1" + 二轮 "A1 B1 C1 D1"
> review者: ops/llm-radar-x-preview-review (hermes-1.2.0)
> review维度: 合理性 / 严格性 / 安全性 / 继承一致性 (3D + 100-base, 用户阈值 PASS ≥85/A)

## 结论摘要

设计 v1.1 与用户两轮确认串完全对应, 无遗漏无越界; 7 项重点审查中 6 项直接核验通过, 1 项发现
版本命名不一致 (RIG-1 🟡, 机械修复, 不阻塞 dev 启动):

- **§3.1 弹框居中 transform 闭环** ✅: 基线 translate(-50%,-50%) 与 <1200px 分支 transform:none 重置
  成对; 实测当前 index.html:172 分支确无 transform (残留偏移风险真实存在, 设计修复方向正确);
  .split-preview 无任何 transition/其他 transform (grep 确认), .show 仅切 display, 无 JS 定位,
  无遗漏偏移场景。
- **§3.2 按钮行** ✅: sp-act-link 复用 t.url https 白名单 (现状 1102-1104 同款逻辑); sp-act-profile
  用 tg.url — 实测 data/twitter.json 10 账号 url 全部 https:// 前缀 (设计"实测均有"声明属实);
  拷贝按钮沿 1166 ago.onclick 先例 (成功 1500ms 复原); SEC-1 无用户数据注入 HTML (textContent/
  静态 HTML + href 仅 https 白名单)。
- **§3.3 拷贝格式 C2** ✅: 模板完整 (作者/时间/正文/forward/指标/原文); null → "—" 与 num()
  (index.html:549) 一致; 空 text+空 forward 省略、url 缺失省略原文行均已显式声明; 示例渲染正确。
- **§3.4 序号语义** ✅: X_ITEMS = X_FLAT posted_at 降序 (1048-1051) 实测成立; V8 稳定排序
  (Chrome 70+/ES2019 起) → 同作者子集保持降序, indexOf 即位置; 与 spNav 同子集逻辑 (1113-1114)
  天然一致; totalInAuthor = tg.tweets.length (无过滤时, X tab 无 handle 级过滤); 全局序号 i+1
  与表格行序一致; fmtFull 复用 fmtMMDD padding 逻辑 + 补年份, null → "—" 继承守卫。
- **§3.5 CI** ✅: 根因链逐环实测 — test.yml:13 缺 pyyaml (与 AGENTS.md Dependencies 漂移);
  twitter-collector.py:37-40 yaml=None; :83-84 raise ConfigError; test_twitter_collector.py:763
  assert main==0; 本机预装 pyyaml 故本地不炸。修复: pip 列表补 pyyaml + `-m "not selenium"`
  (排除 test_html.py:263/315 两个真实 Chrome 渲染测试) + --ignore=test_selenium.py 双保险
  (其 6-7 行已有 GITHUB_ACTIONS skipif); twitter-collector 单测全 FakeDriver + fixture HTML
  (556 行注释"不需浏览器", grep 确认测试文件无 requests/webdriver/Chrome 调用), CI 保留执行合理。
- **§4/§6 测试影响与验证清单** ✅: test_html 仅扫 <script> 块 (CSS 改动不在检查范围) 声明准确;
  §6 四条验证可执行 (pytest / 本地 server 手工 / <1200px 抽屉 / CI 绿跑)。
- **决策对应** ✅: D1=A1 / D2=B1+E1 / D3=C2 / D4=D1 / D5=二轮 B1(pyyaml)+A1(排除); 二轮
  A1 B1 C1 D1 全部并入 v1.1 修订记录与 §3.5; 无遗漏无越界。

**评分: 95 / 100 (A) → ✅ PASS (≥85/A)。** 设计可进 dev。1 🟡 (版本命名, Bucket A 机械修复,
随 dev 首 commit 一并) + 4 🟢 观察项不阻塞。

## 逐项验证表 (7 项重点审查)

| # | 审查项 | 验证方法 | 结果 |
|:-:|:-------|:---------|:----:|
| 1 | §3.1 transform 闭环 | read index.html:69/:172 + grep transform/transition + JS 定位面 | ✅ |
| 2 | §3.2 按钮行数据与安全 | read index.html:86-87/:316/:1102-1104 + 实测 twitter.json 10 账号 url | ✅ |
| 3 | §3.3 拷贝格式 C2 完整性 | 模板 vs num() (L549) vs schema null 面 | ✅ |
| 4 | §3.4 序号语义一致性 | read index.html:1048-1051/:1113-1114 + V8 稳定排序 + fmtMMDD | ✅ |
| 5 | §3.5 CI 边界清晰度 | read test.yml + twitter-collector.py:37-40/:83-84 + test_twitter_collector.py:556/:763 + test_html.py:263/:315 + test_selenium.py:6-7 | ✅ |
| 6 | §4/§6 可执行性 | 命令实跑前提核对 + 验证清单逐条推演 | ✅ |
| 7 | 决策对应完整性 | D1-D5 vs 两轮确认串逐项比对 | ✅ |

## 数据验证

| # | 验证项 | 方法 | 结果 |
|:-:|:-------|:-----|:-----|
| 1 | 设计文件存在 + 唯一 commit | git log --follow + git show --stat adf9b2a | ✅ 205 行新建, commit 主题 "design v1.1" |
| 2 | 工作区状态 | git status | ✅ clean; 1 未推送 commit (adf9b2a); 未 commit / 未 push (1A 约束) |
| 3 | test.yml 现状 | read .github/workflows/test.yml:13-14 | ✅ pip 列表确缺 pyyaml; 命令无排除, 与设计描述一致 |
| 4 | twitter-collector 根因链 | read scripts/twitter-collector.py:37-40/:83-84 | ✅ import yaml except → None; parse_config raise ConfigError |
| 5 | 测试断言位置 | read tests/test_twitter_collector.py:763 + :556 | ✅ assert main(['--collect'])==0; "不需浏览器" 注释 |
| 6 | selenium 测试面 | read tests/test_html.py:263/:315 + tests/test_selenium.py:6-7 | ✅ 2 个 @pytest.mark.selenium 真实 Chrome; skipif GITHUB_ACTIONS |
| 7 | twitter 单测无网络 | grep tests/test_twitter_collector.py requests/webdriver/Chrome( | ✅ 0 功能调用 (全 FakeDriver + fixture HTML) |
| 8 | 10 账号 url/handle/name | python3 读 data/twitter.json | ✅ 10 targets, https url 全有, handle/name 无 null; 109 tweets 无空 text/url/posted_at |
| 9 | sp-link 引用面 | grep index.html sp-link/sp-act | ✅ 仅 CSS 86-87 + HTML 316 + JS 1102-1104, 设计替换面完整覆盖 |
| 10 | 版本一致性 | 设计 frontmatter vs 标题 vs 文件名 vs commit | ⚠️ frontmatter version:1.0 + 文件名 -v1.0- vs 内容/标题/commit v1.1 → RIG-1 |

## 维度评估 (3D)

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 合理性 | 🟢 | 居中弹框/三按钮/完整素材/序号+完整时间 与确认串逐项对应; 数据面 (url/handle) 有实测支撑 |
| 严格性 | 🟢 | transform 残留风险被显式识别 (index.html:172 现缺 transform:none, 修复正确); CI 排除/保留边界有源码级论证; 拷贝 null/空行/缺行处理齐全 |
| 安全性 | 🟢 | SEC-1 继承: textContent/静态 HTML、href 仅 https 白名单、双保险; 无新注入面 |
| 继承一致性 | 🟢 | 继承 <1200px 抽屉行为、clipboard 先例 (1166)、num()/fmtMMDD 复用; 无矛盾 |

## 发现项

### RIG-1 🟡 — 设计文档版本命名不一致 (Bucket A, 机械修复)

- **问题**: 设计文档 frontmatter `version: 1.0` + 文件名 `-v1.0-20260827.md`,但文档标题/修订记录/
  commit 主题均为 v1.1 (v1.1 已并入二轮澄清)。仓库先例 (x-hotspot b9b025d) 版本提升用
  `git mv` 同步文件名; 本设计文件以 v1.0 名承载 v1.1 内容创建 (git log --follow 仅 adf9b2a 一个
  commit, 205 行一步到位)。
- **影响**: 追踪链断裂 — 未来引用者按文件名会误读为 v1.0 内容; 本次 review prompt 也需人工
  标注 "(v1.1)" 才能对齐。
- **修复 (✅ 已随 llm-radar-CL001 dev 首 commit dd6ec52 落地)**: 设计文件已 git mv 至
  `documents/solutions/llm-radar-x-preview-design-v1.1-20260827.md`,frontmatter `version: 1.1`,
  本报告设计文档路径引用已同步 v1.1。

### 观察项 (🟢, 不扣分, 随实现落地)

| # | Severity | 事项 | 说明 |
|---|----------|------|------|
| OBS-1 | 🟢 | sp-act-copy 失败反馈无复原 | 设计仅定义成功路径 1500ms 复原; "拷贝失败" 会停留到下次打开。建议失败也 2s 复原 (低成本) |
| OBS-2 | 🟢 | CI 保留 test_cli.py, 本地验证 ignore 之 | 新 CI 命令未 ignore test_cli.py, 本地命令 ignore; 设计 §3.5 边界表未提及 test_cli。属 pre-existing 不对称, 首次 CI 绿跑需顺带确认 test_cli 通过 |
| OBS-3 | 🟢 | D5 中 "B1" 标签跨轮同名不同义 | D5 的 B1 是二轮 B1 (pyyaml 一并修复), 与一轮 B1 (按钮行) 撞名; 头部确认串已区分, 建议决策表加注 "(二轮)" |
| OBS-4 | 🟢 | 拷贝模板 name/handle null 未定义 | schema 必填 + 实测无 null, 低风险; 若防御可写 "(@handle)" 缺失降级 |

## 评分

| 级别 | 数量 | 扣分 |
|:-----|:-----|:-----|
| 🔴 HIGH | 0 | 0 |
| 🟡 MEDIUM | 1 (RIG-1) | -5 |
| 🟢 LOW (观察) | 4 (OBS-1~4) | 0 |

**得分: 100 − 5 = 95 / 100 → A → PASS (≥85/A)**

## 结论

**✅ PASS (95/100, A) — 设计 v1.1 可进 dev。** 无 🔴, 1 🟡 (版本命名, Bucket A 机械修复),
4 🟢 观察。RIG-1 随 dev 首 commit 一并修正即可, 不阻塞实现启动。

## 实现验收清单 (dev 侧, PASS 后执行)

**核心变更:**

1. **index.html:69** `.split-preview` 基线 CSS → `position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); width:720px; max-width:92vw; max-height:80vh;` (其余样式保留)。
2. **index.html:172** `<1200px` 分支 `.split-preview` 规则补 `transform:none;` (防抽屉被 translate 向左上偏移半个自身)。
3. **index.html:86-87 + :316** `.sp-link` 单链接 → `.sp-actions` 容器 + 3 枚 `.sp-act` 按钮 (🔗 打开原文 / 👤 作者主页 / 📋 拷贝); 新增 `.sp-actions/.sp-act` CSS (display:none 默认 + show 显示)。
4. **index.html openSplitPreview (~1080-1108)**:
   - sp-title (1084) → `${posInAuthor}/${totalInAuthor} · ${i+1}/${X_ITEMS.length}` (同 targetIndex 子集 indexOf+1 / 子集长度 · 渲染索引+1 / X_ITEMS 总数)。
   - sp-meta (1090) → `@${tg.handle} · ${fmtFull(t.posted_at)}`。
   - sp-link 块 (1102-1104) → 三按钮逻辑: sp-act-link (t.url https 白名单), sp-act-profile (tg.url https 白名单), sp-act-copy (每次打开重绑 onclick → copyTweet(f))。
5. **新增函数**: `fmtFull(iso)` → "YYYY-MM-DD HH:MM" 本地 (复用 fmtMMDD L1003-1009 padding + 补年份, 继承 null → "—" 守卫); `copyTweet(f)` → C2 纯文本组装 + navigator.clipboard.writeText + 成功 "已拷贝 ✓" 1500ms 复原 + 失败 catch "拷贝失败"。
6. **.github/workflows/test.yml:13** pip 列表尾追加 `pyyaml`; **:14** 命令改 `python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_selenium.py -v --tb=short`。
7. **RIG-1 (Bucket A)**: `git mv` 设计文件至 `-v1.1-20260827.md` + frontmatter `version: 1.1`。

**验证清单 (dev 提交前):**

1. `python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q` 全绿 (AGENTS.md 机制 2/3)。
2. 本地 `python3 -m http.server 8080` → X 热点 tab → 点行/详情按钮: 弹框居中 720px、三按钮行、拷贝粘贴含 正文+指标+链接、作者主页打开 https://x.com/<handle>、sp-title 序号抽样核对表格行序、sp-meta 完整本地时间。
3. 窗口 <1200px: 底部抽屉无偏移 (transform 重置生效)。
4. `git push` 后 CI 绿: twitter-collector 用例不再报 PyYAML; 顺带确认 test_cli 通过 (OBS-2)。
5. RIG-1: 设计文件已改名 -v1.1- + frontmatter version: 1.1。

---

*报告: documents/reviews/llm-radar-x-preview-review-v1.0-20260827.md | 结论: ✅ PASS 95/100 (A) | RIG-1 🟡 版本命名 (Bucket A) + OBS-1~4 🟢 | 未 commit / 未 push (1A 约束)*
