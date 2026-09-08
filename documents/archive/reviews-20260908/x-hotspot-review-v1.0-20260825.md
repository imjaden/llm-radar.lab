# X 热点采集与分栏详情 — review报告 v1.0

> 日期: 2026-08-25
> 文件: documents/solutions/x-hotspot-design-v1.0-20260825.md
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.lab
> 设计 commit: 29045ed (docs@design, CL-SEC19)
> draft 登记: cache/draft/TODO-20260825.md (闭环 CL-SEC19, 状态 READY)
> review维度: 合理性 / 严格性 / 安全性 + 治理合规
> review者: Security Reviewer (IRIS) / hermes-1.2.0

## 结论摘要

架构方向正确, 决策 Q1-Q11 + D1-D6 闭环完整, 采集/前端/crontab 联动设计整体成熟。
但存在 1 个 🔴 安全缺口 (新渲染路径未指定输出编码, 推文文本为攻击者直接可控数据类) +
4 个 🟡 规格缺口 (入库链路未闭环 / cadence 前提与实况不符 / 部分成功语义矛盾 / CLI 签名未定义),
按 100-base 评分 70/B → **⏳ CONDITIONAL PASS**。

修正项由 ops 修后 bump v1.1 重审; 🔴 阻塞 dev 启动, 未生成实现 prompt。

## 数据验证

| # | 验证项 | 方法 | 结果 |
|:-:|:-------|:-----|:-----|
| 1 | 设计 commit 存在 | git log 29045ed | ✅ `docs@design: X热点采集与分栏详情设计 v1.0 (CL-SEC19)` — type@scope 合规 |
| 2 | 文档命名/frontmatter | head 设计文档 | ✅ x-hotspot-design-v1.0-20260825.md kebab-case 无点无下划线; frontmatter version 1.0 = 文件名; type: design; profile: ops; 修订记录完整 |
| 3 | draft 登记 | cat cache/draft/TODO-20260825.md | ✅ 闭环 CL-SEC19, 状态 READY |
| 4 | cache/ gitignore 覆盖登录 profile | .gitignore | ✅ `cache/` 整目录忽略 → cache/twitter-profile/ 不入库; `data/*.log` 覆盖 twitter.log |
| 5 | twitter-targets.yaml 不被忽略 | .gitignore grep | ✅ 无匹配 → 配置文件随 git 入库, 无敏感信息 |
| 6 | 主采集 cadence 实况 | crontab -l + collector.py:2048 | ⚠️ 本机主采集为**每小时** `0 * * * *` (Darwin `CRON_SCHEDULE`), 非设计所称"每日 2 次同 cadence"; AGENTS.md "09:00/21:00" 为陈旧表述 → REA-2 |
| 7 | auto-push 机制 | collector.py:371-429 | ✅ 正常模式 `git add -A` (L407) 可顺带 sweep twitter.json; 质量门禁失败走 partial 仅推 timestamp.json (L1154) → twitter.json 在 Pages 上可无限期陈旧 → REA-1 |
| 8 | 前端 escape 能力 | grep index.html escape/sanitize | ❌ 0 个 escape helper; 全部 innerHTML 直插 (renderHotspotPanel L732-737, renderTab L660) → SEC-1 |
| 9 | country filter 机制 | index.html L296-298 | ✅ Han script 检测 (name) + `country === '中国'`; X tab 的 tweet 无 country 字段, "国家过滤沿用"语义未定义 → O-6 |
| 10 | scripts/ 独立脚本先例 | ls scripts/ | ✅ 已有 5 个独立脚本 (llm-radar-health/mcp-server 等) → 3A 与单文件原则边界清晰 |
| 11 | 36h 窗口 vs 2×/day cadence | 计算 | ✅ 12h 间隔 × 36h 窗口 → 相邻两轮重叠 12h, 单轮失败被次轮完全覆盖; 两连败才有缺口; 窗口匹配 |
| 12 | 测试覆盖点 | 设计 §7.1 | ⚠️ 覆盖 config/window/truncation/DOM/write; 缺 exit-2 登录墙检测/挑战检测/退出码映射用例 → O-4 |
| 13 | 主 cron 路径指向 | crontab -l | ⚠️ 主采集 cron 指向 llm-radar.jaden.tech, 当前 checkout 为 llm-radar.lab → O-13 (非设计缺陷, ops 核对) |
| 14 | schema 时区格式 | 设计 §4 | ⚠️ generated_at `+08:00` vs posted_at `Z` 混用 → O-1 |

## 合理性评估

| # | 项 | 结果 |
|:-:|:---|:-----|
| REA-1 | 🟡 **twitter.json 入库链路未闭环** — §4 "随 GitHub Pages 部署 (同 snapshot.json 机制)" 不成立: snapshot.json 由生成者 _auto_push 提交 (collector.py:371 `git add -A`), 而 twitter-collector 无任何 commit/push 步骤 (§6 crontab 行只有采集+日志); 只能靠主采集顺带 sweep, 主采集无变更或质量门禁失败 (partial 仅推 timestamp.json) 时 twitter.json 停留在本地, Pages 上不更新或无限期陈旧 | 修法: 采集器自带 commit+push (`auto-push@llm-radar: update twitter (N changes)` + `_push_with_recovery` 式重试), 或在 §6 显式声明 ride-along 语义 + 陈旧容忍策略 + 失败告警 |
| REA-2 | 🟡 **cadence 前提与实况不符 + 同刻并发** — 设计"与主采集同 cadence (cron 每日 2 次)"基于陈旧表述; 实测主采集每小时运行 (数据验证 #6)。且 twitter `0 9,21` 与主采集 :00 分钟并发: 双 Chrome 实例资源竞争 + 主采集 `git add -A` 可能抓取写入中的 twitter.json (open('w') 先截断后写, 部分文件入库) | 修法: 先核实现行主采集节奏; twitter 时刻错峰 (如 `20 9,21 * * *`), 并注明 2×/day 是防 X 风控的独立选择而非"同 cadence" |
| REA-3 | ✅ 36h 滚动窗口与 2×/day cadence 匹配 (数据验证 #11) | ✅ |
| REA-4 | ✅ Selenium 登录态方案可行: user-data-dir + 人工登录一次 + headless 复用 cookie 是标准模式; X 反爬/登录失效风险已声明并有 exit-2 + --login 提示 + 挑战跳过缓解 (§3.2/3.6/§8) | ✅ |
| REA-5 | ✅ 选择器多级 fallback 充分: 字段级 null + warn 不崩溃, 解析纯函数化易修; locale 差异中英兜底 | ✅ |
| REA-6 | ✅ scripts/ 独立脚本与单文件原则边界清晰 (已有 5 个先例); crontab 并列与主采集互不依赖, 无 .env/无 LLM | ✅ |
| REA-7 | ✅ 前端与 5 tab 机制一致: tab-btn/data-tab/renderTab renderers map + tc- 计数 + 缓存破坏 + localStorage 惯例均对齐; 分栏仅 X tab 生效 (9A) | ✅ |

## 严格性评估

| # | 项 | 结果 |
|:-:|:---|:-----|
| RIG-1 | 🟡 **部分成功语义与 last_error 持久化矛盾** — §3.5 同时声明"失败不写坏文件: 仅在成功/部分成功时重写"与"last_error 记录最近一次失败原因": 全失败 (exit 1) 时文件不重写 → last_error 无从落盘, 前端永远看不到失败原因; 多 target 部分成功时退出码/写盘策略未定义 | 修法: 定义 per-target 失败策略 (如: 部分成功 → 写盘 + last_error 记录失败 target + exit 0; 全部失败 → 不写盘 + exit 1), 并声明 last_error 仅在写盘时更新 |
| RIG-2 | 🟡 **CLI 签名未定义** — §3.2 定义 `--login`; §6 crontab 无参调用 (隐含默认 collect); §7.3 验收标准出现 `--collect` 但全文无 CLI 签名块, 默认行为/子命令/flag 无权威定义 | 修法: 增加 CLI 签名块 (默认 collect / `--login` / `--collect` / 可选 `--dry-run`) + 子命令与退出码映射 |
| RIG-3 | ✅ 退出码 0/1/2 语义清晰, 失败不写坏文件, exit 2 附人工恢复提示 | ✅ |
| RIG-4 | ✅ schema 完整: generated_at/window_hours/targets/tweets/last_error; 字段缺失用 null 不省略键 (前端渲染稳定) | ✅ |
| RIG-5 | ✅ 配置容错: name/handle/url 必填, enabled 默认 true, max_tweets 默认 20, 解析失败 exit 1 硬错误不静默 | ✅ |
| RIG-6 | ✅ 反爬: 挑战检测 (cf-challenge/"Something went wrong") 跳过本轮不重试轰炸; 登录墙检测 → exit 2; 滚动 3 次 × 2s 保守 | ✅ |
| RIG-7 | ✅ 单测基础面覆盖 config/window/truncation/DOM/write; 前端测试沿用只扫 script 块规则 (§7.2) | ✅ |

## 安全事项

🔴 SEC-1 — **X热点渲染路径未指定输出编码 (stored XSS)**

推文 text 是攻击者**直接可控**的数据类 (目标账号被攻破或刻意发布即可携带 `<img src=x onerror=...>` 载荷; X DOM 中 HTML 实体经 textContent 提取后还原为原始字符)。设计 §5.2/5.3 将"推文全文"经 innerHTML 模板直插 (与现有 index.html:732-737 同模式), 全文无 escape 指定; 现有 index.html 亦无任何 escape helper (数据验证 #8, grep 0 命中) → 恶意推文进入公开 GitHub Pages 站点即为 stored XSS。

修复建议:
1. 新增 `esc()` helper (`& < > " ' \``), renderXHotspots 表格 + split-preview body 全字段强制转义; 纯文本优先 textContent。
2. URL 渲染协议白名单 (https://) + `target="_blank" rel="noopener"`; images src 前端二次校验 https:// 前缀 (采集侧已过滤 pbs.twimg.com, 双保险)。
3. 建议顺带回填既有渲染点 (renderHotspotPanel 等) — OBS: 现有 5 tab 同源同类风险, 新功能引入时应一并收敛。

🟢 SEC-2 — 登录态隔离: cache/twitter-profile/ gitignored 不入库; 采集无 .env/无 API key 依赖; tweets 为公开数据, 无敏感信息入库。

🟢 SEC-3 — 图片直引 pbs.twimg.com 防盗链/追踪风险已在决策 10B 接受, onerror 占位不破版。

🟢 SEC-4 — 采集侧输入校验加分: img src 前缀过滤 + url 规范化 x.com/{handle}/status/{id}, 减少注入面。

🟢 SEC-5 — 无新增依赖/CDN/API key 暴露; 独立脚本权限面与主采集一致 (本机用户态 cron)。

## 治理合规

| # | 项 | 结果 |
|:-:|:---|:-----|
| GOV-1 | 文件名 v1.0 + frontmatter version: 1.0 + 修订记录三方一致, kebab-case | ✅ |
| GOV-2 | commit 29045ed `docs@design:` 格式合规, 主题含功能范围 | ✅ |
| GOV-3 | 决策 Q1-Q11 + D1-D6 全表锁定, 与 §1 目标 1:1 映射, 无编号漂移 | ✅ |
| GOV-4 | 验收标准 6 条可测 ("人工登录一次"属用户配合, 已知边界不误报) | ✅ |
| GOV-5 | draft 登记闭环 CL-SEC19 READY | ✅ |

## 评分

基数 100:

| 级别 | 数量 | 扣分 |
|:-----|:-----|:-----|
| 🔴 HIGH | 1 (SEC-1) | -15 |
| 🟡 MEDIUM | 4 (REA-1, REA-2, RIG-1, RIG-2) | -20 |
| 🟢 LOW | 13 (O-1 ~ O-13) | 0 (记录) |

得分: **70 / 100 → B**

## 结论

**⏳ CONDITIONAL PASS (70/B)** — 架构方向正确、决策闭环完整、采集方案可行, 但 🔴 SEC-1 (XSS 输出编码缺失) 阻塞 dev 启动, 另 4 个 🟡 规格缺口需在 v1.1 修正后重审。**未生成实现 prompt** (🔴 阻塞, 按 FAIL/COND 流程 ops 修后 bump v1.1 重审)。

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | **SEC-1**: 渲染路径输出编码 — 新增 esc() helper, renderXHotspots + split-preview 全字段转义; URL 协议白名单 + rel=noopener; images src 二次校验; 建议回填既有渲染点 | 安全性 🔴 |
| □ | **REA-1**: twitter.json 入库 — 采集器自带 commit+push, 或显式声明 ride-along 语义 + 陈旧容忍/告警 | 合理性 🟡 |
| □ | **REA-2**: cadence 核对 + 错峰 — 先核实现行主采集节奏 (实测每小时), twitter cron 避开 :00 (如 `20 9,21`) | 合理性 🟡 |
| □ | **RIG-1**: 部分成功策略 + last_error 写盘条件明确定义 (per-target 失败 → 写盘 + last_error + exit 0; 全失败 → 不写盘 + exit 1) | 严格性 🟡 |
| □ | **RIG-2**: CLI 签名块 — 默认 collect / --login / --collect / 退出码映射 | 严格性 🟡 |
| □ | O-1: 时区统一 UTC Z (generated_at +08:00 vs posted_at Z 混用) | 严格性 🟢 |
| □ | O-2: "<= now (容忍时钟偏差 5min)" 自相矛盾 → 明确 now+5min 容差 | 严格性 🟢 |
| □ | O-3: 单次抓取内按 tweet id 去重 (滚动防重复) | 严格性 🟢 |
| □ | O-4: 补 exit-2 登录墙/挑战检测/退出码映射单测 (核心运维路径) | 严格性 🟢 |
| □ | O-5: Chrome profile 并发锁 (--login 与 cron 同时运行 → SingletonLock) → 互斥/锁检测 | 合理性 🟢 |
| □ | O-6: 国家过滤对 X tab 语义未定义 (tweet 无 country) → 按文本 Han script 检测或声明不适用 | 合理性 🟢 |
| □ | O-7: 图片/链接 URL 前端二次校验 https:// 协议 | 安全性 🟢 |
| □ | O-8: AGENTS.md 同步 (scripts/twitter-collector.py、6 tab、data/twitter.json、twitter-targets.yaml) | 治理 🟢 |
| □ | O-9: twitter 采集健康度未入 metrics.json / lr status → 后续迭代 OBS | 合理性 🟢 |
| □ | O-10: 外部链接 target=_blank 需 rel="noopener" (现有惯例 index.html:600) | 安全性 🟢 |
| □ | O-11: --login "等待人工登录后关闭" 完成判定未定义 → 轮询 cookie/profile 或用户关窗触发 | 严格性 🟢 |
| □ | O-12: 空 targets/全 disabled 行为未定义 → 写空文件 exit 0 + 提示 | 严格性 🟢 |
| □ | O-13: 主采集 cron 仍指向 llm-radar.jaden.tech (当前 checkout 为 llm-radar.lab) → ops 核对主 cron 是否失效 | 合理性 🟢 |

---

*报告: documents/reviews/x-hotspot-review-v1.0-20260825.md | 结论: ⏳ CONDITIONAL PASS 70/B | 实现 prompt: 未生成 (🔴 SEC-1 阻塞, v1.1 重审后按流程生成)*
