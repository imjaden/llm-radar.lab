# X热点采集与分栏详情 — 实现审计报告 v1.0

> 日期: 2026-08-26 (实现审计执行日)
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.lab
> 设计文档: documents/solutions/x-hotspot-design-v1.1-20260825.md
> 复审报告: documents/reviews/x-hotspot-rereview-v1.1-20260826.md (PASS 100/A)
> draft 登记: cache/draft/TODO-20260825.md (CL-SEC19)
> review者: Security Reviewer (IRIS) / hermes-1.2.0
> review维度: 设计 vs 实现一致性 / 测试质量 / 治理合规 / 安全性 / 运维闭环

## 结论摘要

CL-SEC19 (X 热点采集 + 分栏详情) 已按设计 v1.1 完整实现并推送 (origin/main == HEAD,
0 未推送)。采集器 / 前端 / 测试 / AGENTS.md / cron 包装脚本五类产物全部落地, 与设计
逐项一致; pytest 复跑 **184 passed** (与 ops 核查结论一致); 无 🔴 / 🟡 发现, 3 项 🟢
注记 (记录不扣分)。注记项 (Q5 决策 5A 受阻 → --attach 补偿方案) 已确认可接受, 不 bump
设计。

**评分: 100 / 100 (A) → ✅ PASS。CL-SEC19 闭环完成。**

## 维度评估

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 1. 设计 vs 实现一致性 | 🟢 | CLI 签名/退出码四场景/schema UTC/esc()/分栏/抽屉/chips/crontab 全落地; --attach 为已确认注记项 |
| 2. 测试质量 | 🟢 | 单测 (配置/36h/截断/DOM/写盘/退出码映射/O-12) + 前端断言 (tab/分栏/esc/chips/https guard) 齐全; 184 passed 可复跑 |
| 3. 治理合规 | 🟢 | commit type@scope 全合规; AGENTS.md 同步 (PyYAML 补声明); §3.6 表述修正 (X-REV-1); console 前缀/CSS 无引号/esc 落实 |
| 4. 安全性 | 🟢 | esc() 全字段转义 + textContent + URL/https 白名单 + CSP img-src; 无敏感入库; profile 登录态 gitignored |
| 5. 运维闭环 | 🟢 | cron 包装自动拉起 (D1A); profile pidfile 互斥 (O-5); 幂等 (去重+原子写盘); attach 失败友好提示 (D4) |

## 1. 设计 vs 实现一致性 (逐项)

### CLI 签名 (§3.2, RIG-2) ✅

| 设计 | 实现 (scripts/twitter-collector.py) | 验证 |
|:-----|:-----------------------------------|:----:|
| 默认 = collect | `parse_args([]) → {'mode':'collect'}` (L734-735) | ✅ |
| --collect | L740-741 | ✅ |
| --login (有头登录) | L742-743 → cmd_login | ✅ |
| --dry-run (解析+探测, 不写盘) | L744-745 → cmd_dry_run | ✅ |
| 退出码 0/1/2 | parse_args/main/evaluate_results 全链 | ✅ |
| 未知参数 → 用法 + exit 1 | L748-750; 多余参数 L751-753 | ✅ |
| TWITTER_PROFILE_DIR 覆盖 | L765 | ✅ |
| **--attach (注记项新增)** | L746-747, L793-795 (TWITTER_CDP_PORT 默认 9222) | ✅ 注记 |

### 数据 schema (§4) ✅

- `generated_at` UTC Z (`utc_now_str` L148-150), `window_hours`=36, `targets[{name,handle,url,tweets[]}]`, `last_error` — 与 §4 完全一致。
- tweet 字段: id/text/posted_at/url/views/replies/retweets/likes/images — 缺失置 null 不省略键 (parse_tweet_html L239-241)。
- 实测 data/twitter.json (25 行): `generated_at=2026-08-26T05:04:13Z`, 全字段 Z, `images:null` — schema 合规。

### 失败处理四场景 (§3.5, RIG-1) ✅

| 场景 | 写盘 | last_error | 退出码 | 实现 (evaluate_results L311-326) |
|:-----|:----:|:----------:|:------:|:-----|
| 全部成功 (≥1 target 有数据) | ✓ | 清空 | 0 | `ok → (True, build_last_error(failed), 0)` |
| 部分成功 | ✓ (含成功 target) | 记失败 target+原因 | 0 | `build_last_error(failed)` |
| 全部失败 / 全部无数据 | ✗ (保留上次) | 不入盘 | 1 | `(False, None, 1)` |
| 登录态失效 | ✗ | — | 2 | `login_wall → (False, None, 2)` |

四行无矛盾, "全部成功但 0 条窗口内推文" 由 `ok` 为空 → exit 1 (对应设计 "(≥1 target 有数据)" 限定, 单测 test_all_empty_no_write 固化)。

### 前端 (§5) ✅

- X热点 tab (`data-tab="xhotspots"` L213) + 默认仍 llms; 独立加载 `data/twitter.json?t=` (L857) 失败 `console.warn('[llm-radar] ...')` 回退空态不阻断 (L864)。
- renderXHotspots 表格: 时间 MM-DD HH:MM (fmtMMDD UTC→本地) / 人物 / 摘要截断 120 字符 / 指标 (views/replies/likes, null 显示 `—`)。
- esc() helper (L468-471) 转义 `& < > " ' \``, 并回填既有渲染点 renderHotspotPanel/chip/eventCell/smartEventCell/renderHotspots (SEC-1 顺带收敛)。
- 分栏 split-preview (L288-302): header 上一/下一/关闭 + body 全文/指标 kv/图片/原文链接; 单击行 (onclick) + 行内"详情"按钮 (stopPropagation); 同人物内 nav 循环 (spNav); 关闭三途径 (按钮/点击空白 backdrop/Esc); `<1200px` 变底部抽屉 (media query L165)。
- 源 chips 扩展 X (精确匹配防单字母误伤, 测试断言 `{name:'X', url:'https://x.com'}`); 国家 chips 在 X tab 置灰 (L741 `tab==='xhotspots'`)。
- CSP 同步加白 `img-src ... https://pbs.twimg.com` (L7)。

### crontab (§6) ✅

- 包装脚本 `scripts/twitter-collector-cron.sh` (已 tracked): 检查 CDP 9222 就绪 → 未就绪自动拉起独立 profile Chrome (`--user-data-dir=$HOME/chrome-twitter-cdp`) → 轮询 ready (≤30s) → `exec python3 scripts/twitter-collector.py --attach`。对应 D1A 注记。

## 2. 测试质量

- **tests/test_twitter_collector.py** (531 行): 配置解析 11 用例 (正常/缺可选/disabled/max_tweets=0/缺必填/全空/空文件/非法 yaml/targets 非 list/项非 dict/max_tweets 非整数); 36h 窗口 9 用例 (内/外/边界 36h/未来容差/超容差/缺时间/非法时间/组合/时区归一 O-2); 去重 (O-3) + 截断 4 用例; DOM 解析 11 用例 (全字段/缺失 null/空 html/url 归一/@handle strip/整卡 fallback/中文 views/中文指标/0 views 保留/offset 时区/非法时间); 写盘 schema 4 用例 (键完整/UTC Z/roundtrip null 键); 退出码映射 6 用例 (全成/部分/全败/全空/login-wall/build_last_error); 挑战+登录墙 FakeDriver 6 用例; CLI args 7 用例; main 路径 5 用例 (O-12 空配置写空文件 exit 0 用 monkeypatch 隔离 git/写盘)。
- **tests/test_html.py** 扩展 TestXHotspotFrontend (11 断言): tab 存在/render 函数/split-preview 元素/esc 字符集完整/既有渲染点回填/X 源 chip/国家置灰/images https guard/twitter fetch warn/null 指标 `—`。遵循"只扫 `<script>` 块排除 `<style>` 块"规则。
- **复跑证据**: `python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q` → **184 passed, 2 deselected** (与 ops 核查一致); 单跑 twitter+html → 80 passed。测试污染 (snapshot/overview/timestamp) 已 git checkout 还原, 工作区 clean。

## 3. 治理合规

- commit type@scope 全部合规: feat@twitter / test@twitter / feat@frontend / test@frontend / docs@llm-radar / fix@twitter, 均带 CL-SEC19 追踪, 与 AGENTS.md 约定一致。
- AGENTS.md 同步 (0faf43a): 依赖补 PyYAML (L66, X-REV-3 ✅) + X 采集结构 + crontab 说明。
- 设计 §3.6 表述修正 (X-REV-1 ✅): L141 已改为 "9:20 与 21:20", 与 cron `20 9,21` 三处一致, 无 "9:21/21:21" 残留。
- 前端规范: console 统一 `[llm-radar]` 前缀, 无残留 debug `console.log`/`console.debug`; CSS 属性无引号 (测试已覆盖)。
- 报告/复审记录命名 kebab-case; 本报告文件名 `x-hotspot-impl-audit-v1.0-20260826.md` 合规。

## 4. 安全性

- **esc() 全字段转义 (SEC-1) ✅**: 表格渲染 `esc(raw)`/`esc(tg.name)` (L891/894); 分栏全文/标题/元数据用 `textContent` 赋值 (L918-920, 天然免注入); 指标为 int 类型 (见 IMPL-OBS-2); 图片 `esc(src)` + `https://` 前缀 (L927-929); 原文链接 `link.href = t.url` 仅在 `/^https:\/\//` 通过后赋值 (L933) + HTML 侧 `rel="noopener noreferrer"` (L300)。
- **CSP 权威白名单**: `img-src 'self' data: https://pbs.twimg.com` (L7) — 即使前端 https 校验被绕过, 浏览器层面仍阻断非白名单域名图片 (见 IMPL-OBS-3)。
- **无敏感入库**: `git ls-files` 匹配 cookie/profile/token/credential/.env/secret/auth = 0 命中; 采集器无硬编码 key; twitter.json 为公开推文文本。
- **登录态 gitignored**: 默认 profile `cache/twitter-profile` 被 `cache/` 覆盖; 实际调试 profile `~/chrome-twitter-cdp` 在项目外; `data/*.log` 覆盖 twitter.log。登录态永不入库。
- **子进程安全**: `_git_run` list-form (`subprocess.run(['git', *args])`) 禁 shell=True; commit 消息 `COMMIT_MSG.format(tweet_count)` 入参为 int 无注入面; cron 包装脚本全部引号参数 + `set -u`, 无 eval/拼接。

## 5. 运维闭环

- **D1A 自动拉起**: cron 包装脚本自启调试 Chrome → 轮询 ready → --attach 采集 (已验证脚本 32 行完整)。
- **O-5 互斥**: ProfileLock pidfile (`.collector.lock`, 存活检查 os.kill(pid,0), 残留锁覆盖) 防 --login 与 cron 双 Chrome 竞争。
- **幂等**: 原子写盘 (tmp + os.replace, L352-355); 去重 (dedup_tweets O-3); push 失败仅记 stderr/cron 日志, 不重试轰炸, 下一轮自动重试 (X-REV-2 落实: `git add data/twitter.json` 限定范围, 非 `git add -A`)。
- **D4 友好提示**: attach 时 CDP 未就绪 → FetchError 输出 "无法连接调试 Chrome ... 请先启动 bash scripts/twitter-collector-cron.sh" (start_driver L462-466)。
- **全失败保留旧文件**: exit 1 不写盘, 前端仍显示上轮 twitter.json 不破版。

## 发现项

无 🔴 / 🟡。3 项 🟢 注记 (记录不扣分):

| # | Severity | Title | 说明 |
|:-:|:--------:|:------|:-----|
| IMPL-OBS-1 | 🟢 | 审计 prompt 所列 commit SHA 与仓库不符 (subjects 1:1 匹配) | 同 LR-SEC-017 类 (rebase 前记录残留): f24d307→04b7866, 3b82e19→df97905, b39f84f→67e427a, 5bc883c→c71537c, eeaf9d4→0faf43a, c770b35→958280f, 1635af7→275918d; 0a23913/23e3401 两后建 commit SHA 一致。按 subject 逐条映射核验无误, 无功能影响 |
| IMPL-OBS-2 | 🟢 | 指标字段 (views/replies/retweets/likes) 经 num() 直通渲染未 esc() | 采集器 `_num_from_label` 正则 `[\d,]+` → int(), 类型保证为整数, 非攻击者可控数据 (攻击者可控的 text 已全 esc); 属防御纵深注记, 非漏洞。若未来指标来源改为非解析字符串, 需同步 esc |
| IMPL-OBS-3 | 🟢 | 图片 src 前端仅校验 https:// 前缀, 非 pbs.twimg.com 锚定 | 采集器 selector `img[src*="pbs.twimg.com/media/"]` (子串) + 前端 `startsWith('https://')` 均非严格域名锚定; 但 CSP `img-src ... https://pbs.twimg.com` 为权威强制, 三层闭合无实际风险 |

### 注记项核验 (预知偏差, 已确认不 bump 设计)

| 注记项 | 核验结果 |
|:-------|:---------|
| Q5 决策 5A 自动化登录受阻 → --attach 补偿 | ✅ 已确认: `--attach` 模式 (cdp_port 复用独立 profile 登录态) 落地于 275918d (即 prompt 所列 1635af7 "首屏先抓再滚动" fix commit, 与首屏修复混入) + 0a23913 (D4 友好提示) + 23e3401 (D1A 包装脚本)。混入 fix commit 可接受 (ops 核查期直补) |
| Chrome 151 禁止默认 profile 远程调试 | ✅ 已确认: 调试 Chrome 用 `--user-data-dir=$HOME/chrome-twitter-cdp` 非默认目录 (cron 脚本 L9/18) |
| D1A wrapper 自动拉起 → --attach | ✅ 已确认: scripts/twitter-collector-cron.sh 完整实现 |

## 评分

| 级别 | 数量 | 扣分 |
|:-----|:-----|:-----|
| 🔴 HIGH | 0 | 0 |
| 🟡 MEDIUM | 0 | 0 |
| 🟢 LOW | 3 (IMPL-OBS-1~3, 记录不扣分) | 0 |

**得分: 100 / 100 → A**

## 结论

**✅ PASS (100/100, A)** — CL-SEC19 实现与设计 v1.1 完全一致, 测试 184 passed 复跑通过,
治理/安全/运维三维全绿, 无阻塞项。**X热点采集与分栏详情功能闭环完成。**

### 遗留注记项清单 (不阻塞, 后续迭代/ops)

1. **O-9** — X 采集健康度入 metrics.json / `lr status` 集成 (设计已挂账, 后续迭代 OBS)。
2. **O-13** — 主采集 cron 指向 jaden.tech vs lab 的核对 (ops 侧, 非本次代码范围)。
3. **已知边界** — 真实采集依赖调试 Chrome 常驻 (cron 自动拉起, ~/chrome-twitter-cdp 登录态);
   twitter.json 内容随时间滚动变化 (审计以 schema/字段完整为准, 不比对具体推文数)。

## 数据验证

| # | 验证项 | 方法 | 结果 |
|:-:|:-------|:-----|:-----|
| 1 | 实现 commit 全部推送 | git rev-parse HEAD origin/main | ✅ 6219fe1 双端一致, status clean |
| 2 | 设计 vs 实现一致性 | 读采集器 800 行 + index.html 相关段 + 测试 | ✅ 五维度全落地 |
| 3 | pytest 复跑 | `pytest tests/ -m "not selenium" --ignore=test_cli --ignore=test_selenium -q` | ✅ 184 passed, 2 deselected |
| 4 | twitter+html 单跑 | pytest 两文件 | ✅ 80 passed |
| 5 | schema 实测 | 读 data/twitter.json | ✅ 4 顶层键 + 9 tweet 字段全 Z, images null 合规 |
| 6 | 无敏感入库 | git ls-files 匹配敏感文件名 | ✅ 0 命中 |
| 7 | X-REV-1 §3.6 表述 | grep 设计文档 "9:21\|9:2" | ✅ 已改 "9:20 与 21:20", 无残留 |
| 8 | X-REV-3 PyYAML | grep AGENTS.md pyyaml | ✅ L66 已声明 |
| 9 | git add 范围限定 | 读 commit_and_push | ✅ `git add data/twitter.json` (非 -A) |
| 10 | 前端 debug 残留 | grep console.log/debug | ✅ 0 命中, 仅 console.warn 合规 |
| 11 | --attach 引入点 | git log -S "cdp_port"/"--attach" | ✅ 275918d (混入 fix commit, 注记确认) |
| 12 | cron 包装脚本 tracked | git ls-files | ✅ scripts/twitter-collector-cron.sh |

---

*报告: documents/reviews/x-hotspot-impl-audit-v1.0-20260826.md | 结论: ✅ PASS 100/100 (A) | CL-SEC19 闭环完成*
