# X热点 v1.3 — 实现审计报告 v1.1

> 日期: 2026-08-26 (实现审计执行日)
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.lab
> 设计文档: documents/solutions/x-hotspot-design-v1.3-20260826.md
> 复审报告: documents/reviews/x-hotspot-rereview-v1.3-20260826.md (PASS 100/A)
> draft 登记: cache/draft/TODO-20260826.md (CL-SEC20)
> review者: Security Reviewer (IRIS) / hermes-1.2.0
> review维度: 设计 vs 实现一致性 / 测试质量 / 治理合规 / 安全性 / 运维闭环

## 结论摘要

CL-SEC20 (X热点 v1.3 增强: 配置迁移 data/ + 10 账号 / forward 采集 / 30-24h 条数窗口 /
全站搜索 + Cmd+F) 已按设计 v1.3 完整实现并推送 (origin/main == HEAD, 0 未推送)。采集器 /
前端 / 测试 / AGENTS.md 四类产物全部落地, 与设计逐项一致; 上轮 v1.2 评审的 4 🟡 +
O-1 🟢 全部闭环, 复审残余 6 🟢 中 4 项随实现落地 (RIG-1 函数改造 / O-2 forward 作者
fallback / O-3 ctrlKey / O-4 max_tweets 参数化); pytest 复跑 **211 passed** (与 ops 核查
一致); 无 🔴 / 🟡 发现, 4 项 🟢 注记 (记录不扣分)。注记项 (D1 1A 条数目标偏差 / 依赖约束 /
push 时机) 已确认可接受, 不 bump 设计。

**评分: 100 / 100 (A) → ✅ PASS。CL-SEC20 闭环完成。**

## 维度评估

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 1. 设计 vs 实现一致性 | 🟢 | 配置迁移/10 账号/forward 格式/条数窗口三规则/风控三态/retention schema/全站搜索/Cmd+F/高亮结构化 DOM 全落地; 动态滚动为已确认注记项 (设计 §8 风险预案) |
| 2. 测试质量 | 🟢 | 条数窗口三规则+边界/forward 解析/风控三态/schema 变更/搜索/Cmd+F/XSS 专项断言齐全; 211 passed 可复跑 |
| 3. 治理合规 | 🟢 | commit type@scope 全合规; AGENTS.md 同步 (data/ 路径 + retention + 搜索); 前端规范 (console 前缀/CSS 无引号) 落实 |
| 4. 安全性 | 🟢 | esc() 全字段 + textContent + URL/https 白名单 + CSP; 搜索高亮结构化 DOM 禁 innerHTML; forward XSS 专项断言; 无敏感入库; git add 限定; subprocess list-form |
| 5. 运维闭环 | 🟢 | cron 自动拉起回归 (D1A); attach 失败友好提示; push 收敛 (git add data/twitter.json 限定); ProfileLock 互斥 |

## 1. 设计 vs 实现一致性 (逐项)

### 配置迁移 (§3.1) ✅

| 设计 | 实现 (scripts/twitter-collector.py) | 验证 |
|:-----|:-----------------------------------|:----:|
| 路径 data/twitter-targets.yaml | `CONFIG_PATH = PROJECT_ROOT / 'data' / 'twitter-targets.yaml'` (L44) | ✅ |
| 旧根路径文件移除 | git show ff7f3a1: `twitter-targets.yaml` 删除 9 行, `data/twitter-targets.yaml` 新增 34 行 | ✅ |
| name/handle/url 必填 | parse_config L103-106 (缺失/非字符串 → ConfigError) | ✅ |
| enabled 默认 true, max_tweets 默认 30 | L108-118; `max_tweets <= 0 → DEFAULT_MAX_TWEETS` (30) | ✅ |
| 10 账号清单 | data/twitter-targets.yaml 实测 10 目标, handle 集 = {dhh, bcherny, sama, claudeai, openclaw, NousResearch, deepseek_ai, JeffDean, AndrewYNg, karpathy} | ✅ |

### 条数窗口 (D1 1A, §3.4 步骤5, REA-1 三规则) ✅

`apply_retention` (L182-217) 与设计三规则逐项一致:

| 规则 | 设计 | 实现 | 单测 |
|:-----|:-----|:-----|:-----|
| a. 24h 内 >30 → 全保留 | 不截断 | `len(inner) > n → return inner` | test_rule_a_inner_gt_max_all_kept |
| b. 24h 内 ≤30 → 外倒序补足至 30 | 内全保留 + 外补 | `inner + outer[:n-len(inner)]` | test_rule_b_inner_le_max_fill_outer |
| c. 总 <30 → 全部保留 | 全保留 | `len(inner)+len(outer) <= n → inner+outer` | test_rule_c_total_lt_max_all_kept |
| 边界 =30 | 全保留 | 规则 c (=n 边界) | test_boundary_exact_max |
| 边界 =24h 整点 | 视为 24h 内 | `lower <= dt` (含等号) | test_boundary_exact_24h_edge |
| per-account max_tweets override | O-4 残余 | `n = max(1, int(max_tweets))` 参数化 | test_max_tweets_override |

- 未来超容差 (>now+5min) 丢弃 (L206-208); 无 posted_at 丢弃 (L201-202)。
- `within_window` 保留为通用窗口 helper (window_hours 参数默认 RETENTION_HOURS=24), 非残留 36h。

### forward 解析 (D2 2C, §3.4 步骤4) ✅

- `parse_tweet_html` (L277-354): retweet (socialContext + repost/repost 语义) / quote
  (tweetText ≥2) 检测 → 内层 = 最后 tweetText, 外层 = 第一 (纯转推无外层 → None);
  forward 格式 `by @{作者}: {原推文}` (L321); 非转发 → forward=None (L322 else 分支)。
- 作者提取 `_extract_forward_author` (L258-274): 最后 /status/ 链接 handle → 头像 alt
  ('X's profile picture' 显示名) → 'unknown' (O-2 fallback 三级)。
- 实测 data/twitter.json: `forward: "by @bcherny: Claude now has one memory ..."`,
  带评论转推 text 有值 + forward 有值, 格式正确。
- 单测: retweet/纯转推/quote/非转发/头像 alt fallback/unknown fallback/内层缺失 (L408-462)。

### 风控三态 (RIG-2, §3.6) ✅

`cmd_collect` (L743-810) `challenge_streak` 计数实现三态:

| 状态 | 设计 | 实现 | 单测 |
|:-----|:-----|:-----|:-----|
| 单账号挑战 | 记 error 继续下一账号 | L769-772 `challenge_streak+=1`, append error, continue | test_single_challenge_partial_success |
| 连续 ≥2 挑战 | 提前终止本轮 (已抓写盘) | L773-776 `challenge_streak>=2 → break` | test_two_consecutive_challenges_early_terminate |
| 全部未抓成 | exit 1 不写盘 | evaluate_results `not ok → (False, None, 1)` | test_partial_success_after_early_terminate |
| 非连续挑战 | 不提前终止 | 成功 target 归零 challenge_streak (L764) | test_challenge_then_success_no_early_terminate |

### 数据 schema (§4, RIG-1) ✅

- `window_hours` → `retention` (build_document L389-400): 顶层键 `generated_at / retention /
  targets / last_error`, `RETENTION = '30/24h'` (L50)。
- 实测 data/twitter.json: `keys=['generated_at','retention','targets','last_error']`,
  `retention='30/24h'`, `generated_at='2026-08-26T08:51:20Z'` (UTC Z), `last_error=None`。
- tweet 字段 id/text/forward/posted_at/url/views/replies/retweets/likes/images — 缺失 null
  不省略键 (parse_tweet_html L284-286)。
- 旧 36h 残留: 全库 grep `window_hours`/`WINDOW_HOURS`/`==36` 在 tests = 0 命中; collector
  仅 within_window 参数名 (默认 24) + 注释 + UA 字符串 "537.36" 误命中; 无 `filter_window`/
  `truncate_tweets`/`WINDOW_HOURS=36` 残留。
- 前端不读 retention (index.html grep retention/window_hours = 0), 与 §4 一致。

### 全站搜索 (D4 4B, §5.2, SEC-1) ✅

| 设计 | 实现 (index.html) | 验证 |
|:-----|:------------------|:----:|
| header-search 输入框 | id="header-search" + oninput/onkeydown (L847-858) | ✅ |
| 防抖 ~200ms | `setTimeout(doSearch, 200)` + clearTimeout (L848-849) | ✅ |
| 跨 tab 汇总计数 | updateSearchSummary textContent 构建 jump-btn (L890-911) | ✅ |
| Cmd+F 拦截聚焦 | `(e.metaKey || e.ctrlKey) && (e.key==='f'||'F')` → preventDefault + focus (L968-978) | ✅ |
| Ctrl+F 跨平台 (O-3) | `e.ctrlKey` 已覆盖 (复审残余 O-3 ✅ 落地) | ✅ |
| 高亮结构化 DOM 禁 innerHTML | highlightMatches: TreeWalker + createTextNode + span.textContent (L937-967), 无 innerHTML | ✅ |
| 查询词按文本节点 | `document.createTextNode(v.slice(i, idx))` + createDocumentFragment (L953-958) | ✅ |

### forward 渲染 (D2 2C, §5.1/5.3, O-1) ✅

- 摘要 `xSummaryText` (L1027-1034): `{text}\nforward: {forward}` 截断; text 空仅 forward 行。
- 表格: `esc(raw)` / `esc(title)` / `esc(tg.name)` (L1060-1061) — 摘要含 forward 全转义。
- 分栏: `sp-forward.textContent = 'forward: ' + t.forward` (L1089) + `sp-full-text.textContent`
  (L1087) — textContent 天然免注入 (O-1 落实)。
- 图片: `https://` 前缀二次校验 + esc(src) + onerror 占位 (L1097-1099); CSP `img-src
  ... https://pbs.twimg.com` 权威白名单。

### 动态滚动深度 (200513e, 设计 §8 风险预案) ✅

- `fetch_target` (L610-640): `max_scrolls = max(scrolls, 12)` + 达 max_tweets 提前停 +
  连续 2 次无新增停; 首屏先解析再滚动 (X 虚拟列表回收防护)。
- 实测提升: 静态 3 次 ~11 条 → 动态 84→109 条 (auto-push 两轮 84/109 changes 印证)。

## 2. 测试质量

- **tests/test_twitter_collector.py** (770 行): 配置解析 11 用例 (含 10 账号 real config +
  max_tweets 默认 30 + <=0 fallback); 24h 窗口 8 用例 (内/外/边界 24h 整点/未来容差/超容差/
  缺时间/非法时间/时区归一); 条数窗口三规则 + 边界 + override 8 用例; 去重; DOM 解析 10 用例;
  forward 解析 7 用例 (含 unknown/avatar alt fallback); 写盘 schema 4 用例 (retention 键);
  退出码映射 6 用例; 挑战/登录墙 FakeDriver 7 用例; 风控三态 4 用例; CLI args 7 用例; main 路径 6 用例。
- **tests/test_html.py** 扩展 TestSearchFeature (11 断言): header-search/doSearch/防抖/
  跨 tab 计数/Cmd+F+Ctrl+F 拦截/高亮禁 innerHTML/查询词文本节点/forward 摘要格式/分栏
  textContent/forward XSS 专项。遵循"只扫 `<script>` 块排除 `<style>` 块"规则。
- **复跑证据**: `python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py
  --ignore=tests/test_selenium.py -q` → **211 passed, 2 deselected** (与 ops 核查一致,
  184→211 因 CL-SEC20 新增用例)。测试污染 (snapshot/overview/timestamp) 待 git checkout 还原。

## 3. 治理合规

- commit type@scope 全部合规: docs@review / docs@design / feat@twitter / feat@frontend /
  test@frontend / docs@project / fix@twitter, 均带 CL-SEC20 追踪, 与 AGENTS.md 约定一致。
- AGENTS.md 同步 (b11812f): data/twitter-targets.yaml 路径 + retention + 全站搜索 + 国家
  filter X tab 语义, 10 行实改。
- 前端规范: console 统一 `[llm-radar]` 前缀, 无残留 debug log; CSS 属性无引号。
- 报告/复审记录命名 kebab-case; 本报告 `x-hotspot-impl-audit-v1.1-20260826.md` 合规
  (v1.1 因 CL-SEC19 实现审计为 v1.0)。

## 4. 安全性

- **esc() 全字段转义 (SEC-1) ✅**: 字符集 `& < > " ' \`` (L484-487); 表格 `esc(raw)`/
  `esc(tg.name)`; 分栏 `textContent` 赋值 (sp-full-text/sp-forward/sp-title/sp-meta)。
- **搜索高亮结构化 DOM (SEC-1) ✅**: highlightMatches 用 TreeWalker + createTextNode +
  span.textContent 构建, 函数体内 0 innerHTML; 查询词与匹配文本均按文本节点渲染, 注入查询词
  (`<script>`) 不执行。
- **forward XSS (O-1) ✅**: 分栏 forward 经 textContent (L1089); 表格摘要经 esc() (L1061);
  单测 test_forward_xss_text_only 固化 `<img onerror>` → 纯文本。
- **URL/https 白名单 ✅**: 图片 `startsWith('https://')` (L1097) + CSP img-src 权威;
  原文链接 `link.href` 仅在 `/^https:\/\//` 通过后赋值 (L1103)。
- **无敏感入库 ✅**: collector grep (api_key/token/secret/password/bearer/auth_token/AKIA/
  PRIVATE KEY) 仅命中 auth_token **cookie 名**检查 (非 token 值); 采集器 0 硬编码 key
  (纯抓取 0 LLM token); DEEPSEEK_API_KEY 在 .env (gitignored), 本脚本不读。
- **登录态 gitignored ✅**: 默认 profile `cache/twitter-profile` 被 `cache/` 覆盖; 调试
  profile `~/chrome-twitter-cdp` 在项目外; `data/*.log` 覆盖 twitter.log。
- **子进程安全 ✅**: `_git_run` list-form (`subprocess.run(['git', *args])`) 禁 shell=True;
  commit 消息入参为 int (tweet_count); cron 包装脚本全引号 + `set -u`, 无 eval。

## 5. 运维闭环

- **D1A 自动拉起回归**: scripts/twitter-collector-cron.sh (tracked) 检查 CDP 9222 就绪 →
  未就绪自动拉起独立 profile Chrome (`--user-data-dir=$HOME/chrome-twitter-cdp`) → 轮询 ready
  (≤30s) → `exec python3 scripts/twitter-collector.py --attach`。
- **attach 友好提示**: CDP 未就绪 → FetchError 输出 "无法连接调试 Chrome ... 请先启动 bash
  scripts/twitter-collector-cron.sh" (L523-527)。
- **push 收敛 (X-REV-2)**: `commit_and_push` `git add data/twitter.json` 限定 (L438, 非
  `-A`); push 失败仅记 stderr 不重试轰炸, 下一轮自动重试; "nothing to commit" 跳过 push。
- **互斥/幂等**: ProfileLock pidfile 防双 Chrome; 原子写盘 (tmp + os.replace); 去重 dedup_tweets;
  全失败 exit 1 不写盘保留旧文件。

## 发现项

无 🔴 / 🟡。4 项 🟢 注记 (记录不扣分):

| # | Severity | Title | 说明 |
|:-:|:--------:|:------|:-----|
| IMPL-OBS-1 | 🟢 | 审计 prompt 所列 commit SHA 与仓库不符 (subjects 1:1 匹配) | 同 LR-SEC-017 / v1.0 IMPL-OBS-1 类 (rebase 前记录残留): e06e442→2c11397, b9b025d→8b2a695, e9f7989→0d03458, 6186753→ff7f3a1, 371712d→6494a11, 893fc15→0b084cd, c2298de→b11812f (CL-SEC20); 10756bf→9ff4536, 0f9a764→dee96c2 (CL-SEC19 收尾); 200513e (ops 期动态滚动) SHA 一致。按 subject 逐条映射核验无误, 无功能影响 |
| IMPL-OBS-2 | 🟢 | 指标字段 (views/replies/retweets/likes) 经 num() 直通渲染未 esc() | 采集器 `_num_from_label` 正则 `[\d,]+` → int(), 类型保证为整数, 非攻击者可控 (攻击者可控 text/forward 已全 esc/textContent); 同 v1.0 IMPL-OBS-2 延续, 防御纵深注记非漏洞 |
| IMPL-OBS-3 | 🟢 | 复审残余 O-5 (steipete 移除无归档说明) + D3 名单基数 doc clarity 未显式落地 | 名单已正确迁移为 10 账号 (无 steipete), 既有 twitter.json 数据随 24h 滑动窗口自然滚动消失; 设计 §2.2 "新增 3 账号" vs §3.1 "10 账号" 基数未说明属文档清晰度, 无功能/安全影响 |
| IMPL-OBS-4 | 🟢 | searchIcon 注释/代码不符 (注释称 encodeURIComponent, 代码未调用) | L498 注释 "encodeURIComponent(q) 确保..." 但 L499 直接 `${q}` (仅 `name.replace(/"/g,'')` 去引号); pre-existing (8907a76), 不在 CL-SEC20 diff 范围; entity name 非直接攻击者可控 + title 已 esc(), 顺带记录 |

### 注记项核验 (预知偏差, 已确认不 bump 设计)

| 注记项 | 核验结果 |
|:-------|:---------|
| D1 1A 条数目标偏差 (用户决策 B) | ✅ 已确认: 实测 7-14 条/账号 (总量 84-109), 30 条目标因 X 对 CDP attach 会话降级无限滚动 (scrollHeight 不增长) 不可达; 动态滚动 200513e 已尽力 (max_scrolls 3→12 + no_new 提前停, 84→109 提升); 用户接受 "24h 内全保留 + 首屏可达"; 设计 §8 风险预案已触发并落地 |
| 依赖约束 | ✅ 已确认: 未引入新依赖 (undetected-chromedriver 方案被否, 用户选 B); 采集器仅 PyYAML + selenium (既有依赖) |
| push 时机 | ✅ 已确认: CL-SEC19 收尾项 (9ff4536/dee96c2) 由采集器 auto-push 顺带推送 (git push 推整个分支); origin 0/0 符合目标, 审计照常 |

## 评分

| 级别 | 数量 | 扣分 |
|:-----|:-----|:-----|
| 🔴 HIGH | 0 | 0 |
| 🟡 MEDIUM | 0 | 0 |
| 🟢 LOW | 4 (IMPL-OBS-1~4, 记录不扣分) | 0 |

**得分: 100 / 100 → A**

## 结论

**✅ PASS (100/100, A)** — CL-SEC20 实现与设计 v1.3 完全一致, 上轮 4 🟡 + O-1 全闭环,
测试 211 passed 复跑通过, 治理/安全/运维三维全绿, 无阻塞项。**X热点 v1.3 增强闭环完成。**

### 遗留注记项清单 (不阻塞, 后续迭代/ops)

1. **O-5 (steipete 归档说明)** — 名单迁移后既有数据滚动消失无显式归档/过渡说明 (IMPL-OBS-3);
   若需历史留痕, 后续补 documents/ 注记即可, 非阻塞。
2. **D3 名单基数 doc clarity** — 设计 §2.2 "新增 3 账号" vs §3.1 "10 账号" 基数未说明,
   文档清晰度问题, 后续设计迭代顺带修。
3. **searchIcon encodeURIComponent** — 注释/代码不符 (IMPL-OBS-4), pre-existing;
   建议后续顺带补 `encodeURIComponent(q)` 使注释与实际一致。
4. **已知边界** — 真实采集依赖调试 Chrome 常驻 (cron 自动拉起, ~/chrome-twitter-cdp 登录态);
   twitter.json 内容随时间滚动变化 (审计以 schema/字段完整/forward 格式为准, 不比对具体推文数);
   30 条目标受 X 降级限制 (注记项 1, 用户已确认)。

## 数据验证

| # | 验证项 | 方法 | 结果 |
|:-:|:-------|:-----|:-----|
| 1 | 实现 commit 全部推送 | git rev-parse HEAD origin/main; git status | ✅ 2899b06 双端一致, clean, 0 未推送 |
| 2 | 配置迁移 + 10 账号 | read data/twitter-targets.yaml + ls 旧路径 | ✅ data/ 生效, 根路径已移除, 10 目标 |
| 3 | retention schema | read data/twitter.json | ✅ 4 顶层键 + retention '30/24h' + UTC Z |
| 4 | forward 格式实测 | 读 data/twitter.json forward 样本 | ✅ "by @作者: 原文" 格式正确 |
| 5 | 36h 残留扫描 | grep collector/tests/index.html window_hours/WINDOW_HOURS/==36/filter_window/truncate_tweets | ✅ 0 功能残留 (仅参数名/注释/UA 误命中) |
| 6 | 条数窗口三规则 | read apply_retention + 8 单测 | ✅ 三规则 + 边界 + override 全对应 |
| 7 | 风控三态 | read cmd_collect challenge_streak + 4 单测 | ✅ 单/连续 2/非连续/部分成功全对应 |
| 8 | 搜索高亮禁 innerHTML | read highlightMatches (L937-967) | ✅ TreeWalker + textContent, 0 innerHTML |
| 9 | Cmd+F/Ctrl+F | read L968-978 | ✅ metaKey/ctrlKey 双覆盖 (O-3 落地) |
| 10 | forward XSS | read openSplitPreview L1086-1089 + 单测 | ✅ textContent 赋值, esc() 表格 |
| 11 | pytest 复跑 | `pytest -m "not selenium" --ignore=test_cli --ignore=test_selenium -q` | ✅ 211 passed, 2 deselected |
| 12 | 无敏感入库 | grep collector (api_key/token/secret/bearer/AKIA) | ✅ 0 命中 (仅 auth_token cookie 名) |
| 13 | git add 范围 | read commit_and_push L438 | ✅ `git add data/twitter.json` 限定 (非 -A) |
| 14 | cron 包装脚本 tracked | ls + cat scripts/twitter-collector-cron.sh | ✅ 完整实现 D1A 自动拉起 |
| 15 | 动态滚动 | read fetch_target L610-640 + auto-push 两轮 | ✅ max_scrolls 12 + no_new, 84→109 提升 |

---

*报告: documents/reviews/x-hotspot-impl-audit-v1.1-20260826.md | 结论: ✅ PASS 100/100 (A) | CL-SEC20 闭环完成*
