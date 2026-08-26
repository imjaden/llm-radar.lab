# X 热点采集与分栏详情 — re-review报告 v1.1

> 日期: 2026-08-26 (复审执行日; 设计文档自述日期 2026-08-25)
> 文件: documents/solutions/x-hotspot-design-v1.1-20260825.md
> 上轮评审: documents/reviews/x-hotspot-review-v1.0-20260825.md (70/B CONDITIONAL)
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.lab
> 设计 commit: 7238949 (docs@design: X热点设计 v1.1 评审修正, CL-SEC19)
> review维度: 合理性 / 严格性 / 安全性 + 治理合规 (复审)
> review者: Security Reviewer (IRIS) / hermes-1.2.0

## 结论摘要

v1.0 的 1 🔴 (SEC-1) + 4 🟡 (REA-1 / REA-2 / RIG-1 / RIG-2) **全部修复落地** (git diff 实改, 非仅追加声明), 3 个观察项 (O-1 / O-4 / O-6) 一并处理, O-7 / O-10 被 §5.3 修复顺带解决。新发现 3 项 🟢 观察 (X-REV-1 ~ X-REV-3), 均为表述/实现注记级, 不阻塞。

按 100-base 复审评分: v1.0 扣分项全部回补 → **100/100 (A) → ✅ PASS**。

设计可进入 dev; 实现 prompt 已生成 (cache/review-prep/prompt-x-hotspot-impl-20260826.md), 验收清单 6 项见该文件及本文 §结论。

## Fix Verification (逐项核对)

### 安全性 (SEC)

| # | v1.0 问题 | v1.1 修复位置 | 验证 |
|:-:|:----------|:--------------|:----:|
| SEC-1 | 🔴 X热点渲染路径未指定输出编码 → stored XSS | §5.2 L193 esc() helper + 全字段强制转义; §5.3 L213-215 URL 协议白名单 (https://) + target=_blank rel=noopener + images src 二次校验; §5.4 L222 src 仅 https 前缀; §8 风险表 stored XSS 行 | ✅ esc() 字符集明确 (`& < > " ' \` `), 转义范围覆盖表格+分栏全文/指标; 白名单+noopener+图片二次校验齐全; 既有渲染点回填已注明为实施时建议 (§5.2) |

### 合理性 (REA)

| # | v1.0 问题 | v1.1 修复位置 | 验证 |
|:-:|:----------|:--------------|:----:|
| REA-1 | 🟡 twitter.json 入库链路未闭环 | §4 L180 采集器自带 commit+push (见 §6); §6 L237-239 commit+push + 失败策略; §8 风险表"入库链路断裂"行 | ✅ commit 消息 `auto-push@llm-radar: update twitter (N changes)` 与项目约定一致; push 失败记 last_error 不重试轰炸、下一轮自动再试, 陈旧可见性闭环 |
| REA-2 | 🟡 cadence 前提与实况不符 + 同刻并发 | §2 Q6 L59 独立选择非"同 cadence"; §3.6 L141-142 明确 2×/day 为防 X 风控独立选择 + 主采集实测每小时; §6 L232/235 cron `20 9,21` 错峰避开 :00 | ✅ 三处一致声明"独立选择"; cron 时刻为 `20 9,21` (09:20/21:20), 避开主采集整点, 防双 Chrome + git add 竞争; 仅 §3.6 表述残留"9:21 与 21:21" (见 X-REV-1, 无功能影响) |

### 严格性 (RIG)

| # | v1.0 问题 | v1.1 修复位置 | 验证 |
|:-:|:----------|:--------------|:----:|
| RIG-1 | 🟡 部分成功语义与 last_error 持久化矛盾 | §3.5 L129-137 四场景表 | ✅ 全部成功(≥1 target 有数据)→写盘+清空 last_error+exit 0; 部分成功→写盘(含成功 target)+last_error 记失败 target+exit 0; 全失败→不写盘保留上次+不入盘(仅 stderr)+exit 1; 登录失效→exit 2; "last_error 仅在写盘时更新"显式声明, 四行无矛盾 |
| RIG-2 | 🟡 CLI 签名未定义 | §3.2 L89-100 签名块 | ✅ 默认 collect / --collect / --login / --dry-run 四形态; 退出码 0/1/2 与 §3.5 一致; 未知参数 exit 1; TWITTER_PROFILE_DIR 可覆盖 |

### 观察项 (O)

| # | v1.0 问题 | v1.1 修复位置 | 验证 |
|:-:|:----------|:--------------|:----:|
| O-1 | 时区 +08:00 与 Z 混用 | §4 L152/163/178 统一 UTC (Z) | ✅ 全文 grep `+08:00` = 0 命中; generated_at / posted_at 均为 Z; 前端本地化 (MM-DD HH:MM) 已注明 |
| O-4 | 缺退出码用例 | §7.1 L253-254 | ✅ 退出码映射用例: exit-2 登录墙 / 挑战检测 / 全失败不写盘 / 部分成功写盘+last_error |
| O-6 | country filter 语义未定义 | §5.2 L199-200 | ✅ X tab 无 country 字段 → 国家 chips 隐藏/置灰, 仅源 chips 生效 |
| O-7 | URL 前端二次校验 | §5.3 L214 / §5.4 L222 | ✅ 顺带解决 |
| O-10 | rel=noopener | §5.3 L214 | ✅ 顺带解决 |

## 新增附注 (🟢)

- **X-REV-1** — §3.6 L141 表述残留: "9:21 与 21:21 错峰" vs §6 cron 行 `20 9,21` (09:20/21:20)。cron 行为无歧义且三处 (§6/§7.3/§9) 一致, 无功能影响; 建议把 §3.6 改为 "9:20 与 21:20"。
- **X-REV-2** — push 失败记录 last_error 的写入时机未定义: 写盘完成后 push 失败, 按 §3.5 "last_error 仅在写盘时更新" 该记录无法落盘。建议实现时: `git add` 范围限定 data/twitter.json (勿用 git add -A 顺带); push 失败仅记 cron 日志/本地注记, 下一轮自动重试 (可复用主采集 _push_with_recovery 的 rebase→force-with-lease 思路, 本机 cron 场景从简)。
- **X-REV-3** — twitter-targets.yaml 需 YAML 解析, 但 AGENTS.md 依赖清单未声明 PyYAML (环境已装, tasks/al-scanner.py 在用, 无运行缺口); 实施时同步补声明。
- **v1.0 未处理观察项** (不阻塞, 并入实现注记): O-2 (36h 窗口容差 now+5min), O-3 (tweet id 去重), O-5 (--login 与 cron 并发 → profile 锁), O-8 (AGENTS.md 同步), O-9 (健康度入 metrics.json, 后续迭代), O-11 (--login 完成判定), O-12 (空 targets/全 disabled 行为), O-13 (主采集 cron 指向 jaden.tech vs lab, ops 核对)。

## 数据验证

| # | 验证项 | 方法 | 结果 |
|:-:|:-------|:-----|:-----|
| 1 | v1.1 修复 commit 存在 | git log 7238949 | ✅ `docs@design: X热点设计 v1.1 评审修正 (CL-SEC19)` — type@scope 合规 |
| 2 | v1.1 实改非仅追加 | git show --stat 7238949 | ✅ 设计文件 rename + 126 行变更; 修复声明均有正文支撑, 无"声明未落地"项 |
| 3 | 文档命名/frontmatter | head 设计文档 | ✅ x-hotspot-design-v1.1-20260825.md kebab-case; frontmatter version 1.1 = 文件名; type: design; profile: ops; 修订记录含 v0→v1.1 双向 |
| 4 | SEC-1 转义字符集 | 读 §5.2/5.3/5.4 | ✅ esc() 字符集 `& < > " ' \` ` + 白名单 + noopener + 图片二次校验 |
| 5 | REA-1 入库链路 | 读 §4/§6 | ✅ commit+push + last_error 失败策略 + §8 风险行同步 |
| 6 | REA-2 cron 时刻 | 读 §2 Q6/§3.6/§6 | ✅ `20 9,21` (09:20/21:20) 三处一致; §3.6 表述残留见 X-REV-1 |
| 7 | RIG-1 四场景表 | 读 §3.5 | ✅ 四行无矛盾, last_error 写盘条件显式 |
| 8 | RIG-2 CLI 签名 | 读 §3.2 | ✅ 四形态 + 退出码映射 + 未知参数 exit 1 |
| 9 | O-1 时区 | grep +08:00 设计文档 | ✅ 0 命中; schema 全 Z |
| 10 | O-4 测试用例 | 读 §7.1 | ✅ 退出码映射用例齐 |
| 11 | O-6 country filter | 读 §5.2 | ✅ 国家 chips 隐藏/置灰声明 |
| 12 | YAML 依赖 | grep -rn "import yaml" *.py | ⚠️ 仅 tasks/al-scanner.py 在用 PyYAML; AGENTS.md 依赖清单无声明 → X-REV-3 |
| 13 | 数据文件 gitignore | cat .gitignore | ✅ cache/ + data/*.log 覆盖 profile 与 twitter.log; data/twitter.json 不入 ignore → 随 commit+push 入库 |
| 14 | 残留"同 cadence"表述 | grep 设计文档 | ✅ Q6/§3.6 均已改为"独立选择"; 无残留 |

## 评分

v1.0: 100 − 15 (1 🔴 SEC-1) − 20 (4 🟡 REA-1/REA-2/RIG-1/RIG-2) = **70/B**。
v1.1 复审: 全部 🔴🟡 扣分项回补 → 基数回到 100; 新发现 0 🔴 / 0 🟡 / 3 🟢 (X-REV-1~3, 记录不扣分)。

| 级别 | 数量 | 扣分 |
|:-----|:-----|:-----|
| 🔴 HIGH | 0 | 0 |
| 🟡 MEDIUM | 0 | 0 |
| 🟢 LOW | 3 (X-REV-1~3) + 8 (O-2/3/5/8/9/11/12/13 挂账) | 0 |

得分: **100 / 100 → A**

## 结论

**✅ PASS (100/100, A)** — v1.0 的 5 项修正 + 3 项观察全部核验通过, 新发现均为 🟢 观察级, 不阻塞。

**设计 PASS, 可进入 dev。** 实现验收清单:

1. `--dry-run` 解析配置+探测登录态, exit 0 / 2; `--login` 人工登录一次后 `--collect` 实测抓取 steipete 36h 推文。
2. data/twitter.json schema 合规 (generated_at UTC Z / targets / tweets, 缺失键用 null)。
3. 36h 过滤/截断正确; 全失败保留旧文件 + exit 1; 部分成功写盘 + last_error; 登录墙 exit 2。
4. 前端 X热点 tab 渲染 (esc 转义生效) + 单击分栏 + nav 切换 + 关闭; 窄屏抽屉降级; X 源 chip 生效; 国家 chips 在 X tab 隐藏/置灰。
5. Mac crontab 接入 `20 9,21` 错峰, 手动触发一次 + 自带 commit+push 生效。
6. pytest 非 selenium 集合通过 (含 test_twitter_collector.py 新增退出码用例 + test_html.py 扩展)。

实现注记 (实施时落实): X-REV-1~3 + O-2/O-3/O-5/O-8/O-9/O-11/O-12/O-13, 详见 cache/review-prep/prompt-x-hotspot-impl-20260826.md。

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | X-REV-1: §3.6 "9:21/21:21" → "9:20/21:20" (与 cron 行一致) | 严格性 🟢 |
| □ | X-REV-2: push 失败 last_error 写入时机 + git add 范围限定 twitter.json | 合理性 🟢 |
| □ | X-REV-3: AGENTS.md 依赖补 PyYAML | 治理 🟢 |
| □ | O-2: 36h 窗口过滤容差明确 (now+5min) | 严格性 🟢 |
| □ | O-3: 单次抓取内 tweet id 去重 (滚动防重复) | 严格性 🟢 |
| □ | O-5: --login 与 cron 并发 → profile 互斥/锁检测 | 合理性 🟢 |
| □ | O-8: AGENTS.md 同步 (scripts/twitter-collector.py、6 tab、data/twitter.json、twitter-targets.yaml) | 治理 🟢 |
| □ | O-9: 健康度入 metrics.json / lr status → 后续迭代 OBS | 合理性 🟢 |
| □ | O-11: --login 完成判定 (cookie/profile 轮询或用户关窗) | 严格性 🟢 |
| □ | O-12: 空 targets/全 disabled → 写空文件 exit 0 + 提示 | 严格性 🟢 |
| □ | O-13: 主采集 cron 指向 jaden.tech vs lab → ops 核对 | 合理性 🟢 |

---

*报告: documents/reviews/x-hotspot-rereview-v1.1-20260826.md | 结论: ✅ PASS 100/100 (A) | 实现 prompt: ✅ 已生成 (cache/review-prep/prompt-x-hotspot-impl-20260826.md)*
