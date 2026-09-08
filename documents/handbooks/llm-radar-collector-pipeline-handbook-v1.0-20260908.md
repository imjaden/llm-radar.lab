---
author: hermes-v0.20.6(2026.8.27)
profile: dev
type: summary
date: 2026-09-08
---

# llm-radar collector-pipeline handbook v1.0（采集与数据流）

> documents-consolidation phase-2 草稿（只写文件，未 commit）。素材全文（gitignored）：
> `cache/doc-consolidation/llm-radar-collector-pipeline-extract.md`。
> 代码行号核实基准：2026-09-08 工作区 `llm-radar-collector.py`（2779 行）与 `scripts/twitter-collector.py`。

## 一、定位

本手册覆盖 llm-radar 两条采集 pipeline：**A 主采集**（`llm-radar-collector.py`，LLM 抽取 5 类实体情报）与 **B X 热点采集**（`scripts/twitter-collector.py`，Selenium 登录态纯抓取 0 token），含数据流架构、质量门禁、网络前置（FlClash 代理）。

素材：10 份 = data-flow 1 + x-hotspot 8（design 1 + review/audit 6 + verify 1）+ flclash-audit 1。

## 二、功能概述

### 2.1 Pipeline A 主采集（现状以 code 为准，data-flow v1.0 为 6 月末骨架）

主流程链：**Think → Fetch → Extract → Verify → Merge → Observe → Push**。

- 调度：`CRON_SCHEDULE`（code L2389）Darwin **每小时 `0 * * * *`** / Linux `0 7,14,21 * * *`；`_think` 6h 防抖 + 连续失败≥3 告警。启动器 `llm-radar-run.sh`（跨平台，加载 .env + conda）。
- Fetch：**6 源**（qbitai/jiqizhixin/infoq/36kr/github-trending/huggingface；TechCrunch 已移除——`# techcrunch REMOVED - Selenium page load timeout` L99）；Selenium 无头 + requests+BS4 fallback；FlClash 代理未运行则跳过 github-trending/huggingface（见 §3.3）。
- Extract：DeepSeek LLM（默认 **deepseek-chat**，L221-226，2026-08-10 因 v4-flash 长 prompt 空 content 变更；max_tokens 8192）按内联 prompt 抽 5 类实体（providers/people/tools/llms/hotspots）；重试 5→3（CL005）。
- Verify（`_verify` L1746-1796）：中位新鲜度 >168h（7 天）=issue、4 实体维度全 0=issue、**hotspots<3=warning**（CL005 由阻断降级）、空 URL>5/截断>0/裸域名>2=warning（方案 D 降级为不阻断 push）。
- Merge（`merge_entities`）：按 dimension 遍历 → id 精确 → name 精确 → 新增（>14 天新实体拒绝）→ `_fuzzy_name_dedup`（KNOWN_ALIASES/括号后缀剥离）→ `_apply_time_decay` → **留存 100+15 天滑动窗口** → changelog 过滤 → stats → `_save_snapshot` → `_auto_push`（partial=not quality_ok）。紧凑单行写盘（CL002）。
- 数据文件：`data/snapshot.json`（提交）+ `overview.json` + `timestamp.json`（提交）；`metrics.json`/`dead-letter.json`/fetch-cache 与日志在 **cache/**（cli-runtime-files v1.0，详见 cli-governance handbook）。
- 前端 6 tab（tools/llms/providers/people/hotspots/**xhotspots**）——前端渲染见 frontend handbook。

### 2.2 Pipeline B X 热点采集（x-hotspot, CL-SEC19 + CL-SEC20 终态 v1.3）

- 定位：X（Twitter）热点独立采集器，**纯抓取 0 LLM token**；独立 cron 错峰 `20 9,21 * * *`（避开主采集整点）；自带 commit+push（`git add data/twitter.json` 限定非 -A，commit 消息 `auto-push@llm-radar: update twitter ({N} changes)` L91）；采集失败不阻断主流程。
- CLI（code 实核 scripts/twitter-collector.py docstring L4-26 / parse_args L849-871）：默认 collect / `--collect` / `--login` / `--dry-run` / `--attach`（CDP 9222）；退出码 0=成功（含部分成功）/ 1=抓取失败或配置错 / 2=登录态失效；未知/多余参数 → USAGE + exit 1。
- 配置：`data/twitter-targets.yaml`（L78）；name/handle/url 必填（缺失→ConfigError L103-106）、enabled 默认 true、max_tweets 默认 30（<=0 回落 L83/L108-118）；**10 账号**：DHH, Boris Cherny, Sam Altman, Claude, OpenClaw, Nous Research, DeepSeek, Jeff Dean, Andrew Ng, Andrej Karpathy。
- 条数窗口（`apply_retention` L182-217，D1=1A）：`retention = "30/24h"`（L84/RETENTION_HOURS=24 L82）——(a) 24h 内 >30 → 全保留；(b) 24h 内 ≤30 → 24h 内全保留 + 24h 外倒序补足至 30；(c) 总 <30 → 全保留；边界 =30 / =24h 整点含等号；无 posted_at 或 >now+5min 丢弃。
- 数据 schema（`build_document` L389-400）：顶层 `generated_at`（UTC Z）/ `retention` "30/24h" / `targets[{name,handle,url,tweets[]}]` / `last_error`；tweet 字段 id/text/**forward**/posted_at/url/views/replies/retweets/likes/images；**字段缺失置 null 不省略键**；forward=`by @{作者}: {原推文}`（非转发 null）。
- 登录态：profile `~/chrome-twitter-cdp`（独立 Chrome，人工登录一次）；`scripts/twitter-collector-cron.sh` 检查 CDP 9222 → 未就绪自动拉起 → 轮询 ready ≤30s → `exec ... --attach`；ProfileLock pidfile（`.collector.lock`，os.kill(pid,0) 存活检查）；原子写盘 tmp+os.replace。
- 已知边界（用户决策 B）：**30 条/账号为理想目标，X 对 CDP attach 会话降级无限滚动（scrollHeight 不增长），实测 7-14 条/账号（总量 84-109）**，用户接受「24h 内全保留 + 首屏可达」——勿把 30 写作硬保证。

### 2.3 网络前置（flclash, 2026-09-04）

`_is_flclash_running()`（code 两脚本同源，collector.py:44 / twitter-collector.py:44）：非 Darwin → return True（CI/Linux 不误伤）；`pgrep -f FlClash`（list-form，timeout 5）；异常 → False（fail-closed 保守）。collector 侧 `NEEDS_FLCLASH = {'github-trending','huggingface'}`（L979-985），单源运行仅命中该集才跳；twitter-collector 侧检测在 login/dry-run/空 targets 分支之后、cmd_collect 之前（L910-915），仅 collect/attach 需代理，未运行时提前 exit 1 避免无谓 Chrome 启动。

## 三、机制与指令说明

- **退出码四场景**（X 采集，`evaluate_results` L403）：全部成功（≥1 target 有数据）→ 写盘+清空 last_error+exit 0；部分成功 → 写盘+last_error 记失败 target+exit 0；全部失败或 0 条 → 不写盘+exit 1（保留上次数据）；登录墙 → exit 2 + 人工恢复提示。
- **风控三态**（cmd_collect L743-810，`challenge_streak`）：单账号遇挑战（cf-challenge/"Something went wrong"）→ 记 error continue（部分成功）；**连续 ≥2 账号遇挑战 → 提前终止本轮**（已抓正常写盘）；全部未抓成 → 不写盘 exit 1。
- **forward 解析**（parse_tweet_html L277-354 / `_extract_forward_author` L258-274）：retweet/quote 检测 → 内层=最后 tweetText、外层=第一（纯转推无外层 → text null）；作者三级 fallback：/status/ 链接 handle → 头像 alt → 'unknown'。
- **动态滚动**（fetch_target L610-640）：`max_scrolls = max(scrolls, 12)` + 达 max_tweets 提前停 + 连续 2 次无新增停（实测静态 ~11 → 动态 84-109 条）。
- **git 自愈集成**：twitter.json 走 `git add data/twitter.json` + 普通 push（`_git_run` L455，禁 shell）；与主采集 merge 链互不干扰，push 失败仅记 cron 日志下一轮自动重试（X-REV-2）。

## 四、用法示例

```bash
# Pipeline A
cd ~/CodeSpace/llm-radar.lab && python3 llm-radar-collector.py run          # 手动全量（或 run <source>）
llm-radar-run.sh >> data/collector.log 2>&1                                   # crontab 实际执行形态（迁移后日志在 cache/logs/）

# Pipeline B
python3 scripts/twitter-collector.py --dry-run                                # 预检，exit 0
python3 scripts/twitter-collector.py --login                                  # 人工登录一次（~/chrome-twitter-cdp）
python3 scripts/twitter-collector.py --attach                                 # 真实采集（CDP 9222，cron 自动拉起）
bash scripts/twitter-collector-cron.sh                                        # cron 包装：自拉起 Chrome + attach
TWITTER_CDP_PORT=9299 python3 scripts/twitter-collector.py --attach           # 失败提示「无法连接调试 Chrome ... 请先启动 cron.sh」

# cron 预期两行（verify F1 实况）
# 0 * * * * ... ./llm-radar-run.sh run >> ... # llm-radar-collector
# 20 9,21 * * * ... bash scripts/twitter-collector-cron.sh >> data/twitter.log 2>&1 # llm-radar-twitter

# 测试（x-hotspot 全链后基线）
python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q   # 211+ passed（CL-SEC20）
git checkout -- data/snapshot.json overview.json timestamp.json               # 跑完全量后还原污染

# 数据检查
python3 -c "import json;d=json.load(open('data/twitter.json'));print(d['retention'], d['generated_at'], len(d['targets']))"
```

## 五、关键决策（原文编号）

> 编号纪律：x-hotspot 族每份评审报告内编号局部唯一（O-1/REA-1/RIG-1/SEC-1 跨报告语义不同），D 编号分代际——引用须带报告名/代际（如「CL-SEC20 D1=1A」）。

### A data-flow（2026-06-22，现行架构骨架，无编号体系）

- 主流程链、100+15 天留存、changelog/stats/dead-letter、双机采集 + GitHub Pages（`llm-radar.lab.jaden.tech`）为仍有效的架构决策（§节引用）。
- **过期字段（以 code 为准）**：cadence 0 9,21 → Darwin 每小时；7 源含 TechCrunch → 6 源；collector 1111 → 2779 行；5 tab → 6 tab；模型 deepseek-v4-flash 自相矛盾 → deepseek-chat；llm-news-prompt.md 已不存在（prompt 内联 extract_entities L1021-1056）；data/ 运行时文件 → cache/ 布局。

### B x-hotspot 族

**CL-SEC19（v1.0→v1.1，2026-08-25）**：继承决策 **Q1-Q11**（含 **Q7→7C** 交互 / **Q8→8A** 分栏 / **Q9→9A** 范围 / **Q10→10B** 图片 / **Q11→11A** 抽屉）+ 代际 **D1-D6**；约束：纯抓取 0 token、失败不阻断主流程、图片直引 pbs.twimg.com + CSP。
- review v1.0（70/B CONDITIONAL，1 🔴 + 4 🟡 + O-1~13）：**SEC-1** 🔴 渲染未指定输出编码（stored XSS）→ esc() helper（`& < > " ' \``）+ 全字段转义 + URL https 白名单 + rel=noopener；**REA-1** twitter.json 入库链路未闭环（采集器无 commit/push）→ 自带 commit+push（消息 `auto-push@llm-radar: update twitter (N changes)`，失败记 last_error 不重试轰炸）；**REA-2** cadence 与实况不符（实测主采集每小时）→ cron `20 9,21` 错峰；**RIG-1** 部分成功 vs last_error 持久化矛盾 → 四场景表（「last_error 仅在写盘时更新」）；**RIG-2** CLI 签名未定义 → 签名块（默认 collect/--collect/--login/--dry-run + 退出码 0/1/2）。
- rereview v1.1（100/A PASS）+ X-REV-1~3（表述残留 / push 失败策略：git add 限定 twitter.json / PyYAML 依赖声明）；impl-audit v1.0（**100/100 (A) PASS**，184 passed）；注记项：**Q5 决策 5A 自动化登录受阻 → `--attach` 补偿**（Chrome 151 禁止默认 profile 远程调试 → `--user-data-dir=$HOME/chrome-twitter-cdp`）。

**CL-SEC20（v1.2→v1.3，2026-08-26）**：决策表 **D1=1A** 条数窗口 30/24h（废弃 36h）/ **D2=2C** 转发（retweet/quote 计入，forward=`by @{作者}: {原推文}`）/ **D3** 新增 Jeff Dean/Andrew Ng/Andrej Karpathy → 10 账号 / **D4=4B** 全站 header-search 跨 tab 汇总 + Cmd+F 拦截聚焦 / **D5=5A** 滚动 3 次/账号接受 5-8min。配置迁 `data/twitter-targets.yaml`。
- review v1.2（80/B CONDITIONAL）：**REA-1** 回填语义矛盾 → 三规则收敛（见 §2.2）；**RIG-1** `window_hours → retention` 影响未枚举（3 处测试断言 + 5 函数引用）；**RIG-2** 风控「跳过 vs 提前终止」并存 → 三态（§2.2/§3）；**SEC-1** 搜索高亮新增 innerHTML 注入面 → 结构化 DOM（span+textContent，0 innerHTML）。观察 O-1（forward XSS 专项断言）/O-3（Cmd+F 补 Ctrl+F）/O-4（max_tweets floor vs cap）/O-5（steipete 移除无归档说明）。
- rereview v1.3（100/A PASS，残余 🟢 O-5/D3 基数/IMPL-OBS-4 遗留）→ impl-audit v1.1（族最新审计，见 §六 终审）。

### C flclash（2026-09-04, commit d73188b）

- 决策：采集前检测 FlClash 进程，未运行跳过两海外源 + X 采集提前 exit 1；非 Darwin return True（CI/Linux 直通）；fail-closed。OBS-1（两脚本重复实现，符合无 package 布局）/ OBS-2（跳过路径无独立单测，degraded-source 兜底低风险）。
- 终审：**PASS — 100/100 (A)**；+44/−0 两文件，222 passed。

## 六、已知坑

1. **编号串号**：O-1 在 review v1.0 = schema 时区混用，在 review v1.2/rereview v1.3 = forward XSS；REA-1 在 v1.0 = 入库链路，在 v1.2 = 回填语义；CL-SEC19 D1-D6 与 CL-SEC20 D1-D5 是两组不同决策——引用必须带报告/代际。
2. **30 条目标不可达**：X 对 CDP attach 降级无限滚动，实测 7-14 条/账号；勿把 D1 写成硬保证（用户决策 B 已接受）。
3. **data-flow 是 6 月末快照**：cadence/源清单/tab/行数/模型多字段过期；事实以本手册 code 锚点为准。
4. **verify/x-hotspot-verify-20260826 为 CL-SEC19 时点一次性指令**：A2 根路径 yaml+steipete、C1 `window_hours`/36h、E1 184 passed 均已过期（CL-SEC20 后 config 迁 data/ + 10 账号 + retention/30/24h + 211 passed）；复用需按 CL-SEC20 语义改写。
5. **行号漂移**：审计引用的实现行号随代码演进后移（如 parse_args L734-735→现 L849）；本文标 2026-09-08 现行号。
6. **登录态是人工资产**：`~/chrome-twitter-cdp` 独立 Chrome profile 登录一次；登录墙 exit 2 后需人工恢复（Cookie 过期会持续失败）。
7. **测试污染**：全量 pytest 后还原 `data/snapshot.json overview.json timestamp.json`（twitter 相关测试不碰主 snapshot，但 CLI 黑盒会触发写盘路径）。
8. **提示词「规则 7/8/9」编号在代码中无字面**：URL/时效/key_people 强制现由 `_verify` 硬门禁+警告承担（空 URL>5/截断>0/裸域>2/中位>168h）——引用旧 prompt 编号须说明来源。

## 七、参考文档

| 源文件（原位 documents/…） | 角色 | 处置 |
|---|---|---|
| pipeline/data-flow-v1.0-20260622.md | 现行架构说明（骨架） | **保留原位**（部分字段过期，事实以手册为准；归档与否见复核清单待核实项） |
| solutions/x-hotspot-design-v1.3-20260826.md | design 终版（CL-SEC20） | 已归档 → archive/solutions-20260908/ |
| reviews/x-hotspot-review-v1.0-20260825.md | CL-SEC19 评审 | 已归档 → archive/reviews-20260908/ |
| reviews/x-hotspot-impl-audit-v1.0-20260826.md | CL-SEC19 审计 | 已归档 → archive/reviews-20260908/ |
| reviews/x-hotspot-rereview-v1.1-20260826.md | CL-SEC19 复审 | 已归档 → archive/reviews-20260908/ |
| reviews/x-hotspot-review-v1.2-20260826.md | CL-SEC20 评审 | 已归档 → archive/reviews-20260908/ |
| reviews/x-hotspot-rereview-v1.3-20260826.md | CL-SEC20 复审 | 已归档 → archive/reviews-20260908/ |
| reviews/x-hotspot-impl-audit-v1.1-20260826.md | CL-SEC20 审计（族终审） | 已归档 → archive/reviews-20260908/ |
| verify/x-hotspot-verify-20260826.md | 一次性验证指令 | 已归档 → archive/theme-20260908/ |
| reviews/llm-radar-flclash-proxy-skip-audit-20260904.md | flclash 审计 | 已归档 → archive/reviews-20260908/ |

交叉引用：`cache/doc-consolidation/llm-radar-collector-pipeline-extract.md`（gitignored 提炼产物）；quality-gate/重试细节见 quality-loop handbook；X 热点前端渲染见 frontend handbook；运行时布局见 cli-governance handbook。
