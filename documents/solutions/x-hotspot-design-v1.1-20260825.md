---
title: X 热点采集与分栏详情设计
topic: llm-radar
type: design
version: 1.1
date: 2026-08-25
author: hermes-1.2.0
tags: [llm-radar, twitter, x, selenium, frontend, split-view]
profile: ops
provider: deepseek
model: deepseek-v4-flash
---

# X 热点采集与分栏详情设计 v1.1

> 探讨确认(2026-08-25): 1A 协议闭环, 决策 Q1-Q11 + D1-D6 全部锁定 (CL-SEC19)。
> 采集器与前端联动设计, 分两期实施节奏见 §9。

## 修订记录

- v1.0 (2026-08-25) — 初版: 决策锁定 (Q1-Q11 + D1-D6), 采集器/数据/前端/crontab/测试验收。
- v1.1 (2026-08-25) — 评审修正 5 项: SEC-1 XSS 输出编码; REA-1 twitter.json 入库链路;
  REA-2 cadence 实况与错峰; RIG-1 部分成功语义; RIG-2 CLI 签名。
  观察项 3 项一并处理: O-1 schema 时区统一; O-4 测试补 exit-2/挑战用例; O-6 country filter 语义。
  (评审: documents/reviews/x-hotspot-review-v1.0-20260825.md, 70/B CONDITIONAL)

---

## 1. 背景与目标

llm-radar 现有 7 源新闻采集 + 5 维实体展示, 缺人物社交动态维度:

- X (Twitter) 上 AI 领头人的实时发言是重要信号源, 现有新闻源不覆盖。
- 前端表格行点击仅做跳转/交叉链接, 无"详情分栏"阅读体验。

目标:

1. 通过 Selenium 登录态采集指定 X 人物最近 36h 资讯
   (文本/时间/链接/访问量/回复数/转推/点赞/图片 URL)。
2. 前端新增 "X热点" tab 复用表格, 点击行右分栏展示详情
   (参考 html-gen split-preview 形态)。

约束:

- 纯抓取不调 LLM (D2 2A), 0 token 成本。
- 采集失败不阻断主采集流程 (独立脚本独立退出码)。
- 图片直引 pbs.twimg.com, 失败占位 (D Q10 10B)。
- 前端渲染全字段转义 (SEC-1), 推文为攻击者可控数据类。

## 2. 决策记录(已确认)

| # | 决策 | 内容 |
|:---|:---|:---|
| Q1 | 人物名单 | 1C: 配置文件 twitter-targets.yaml 可编辑; 默认 Peter Steinberger (x.com/steipete) |
| Q2 | 采集内容 | 2D: 文本+时间+链接+指标(views/replies/retweets/likes)+图片 URL |
| Q3 | 数据落点 | 3B: 独立 data/twitter.json, 前端单独加载 |
| Q4 | 前端展示 | 4A: 新增 "X热点" tab |
| Q5 | 登录态 | 5A: 持久化 Chrome profile (user-data-dir), 人工登录一次 |
| Q6 | 采集节奏 | 6A: cron 每日 2 次 (防 X 风控的独立选择, 非"同 cadence"绑定) |
| Q7 | 交互触发 | 7C: 单击展开 + 行内按钮二选一 (移动端用按钮) |
| Q8 | 分栏形态 | 8A: 右侧分栏 (html-gen split-preview 式: header nav/close + body) |
| Q9 | 详情范围 | 9A: 仅 X热点 tab 资讯行 |
| Q10 | 图片处理 | 10B: 直接引用 pbs.twimg.com, 失败显示占位 |
| Q11 | 窄屏降级 | 11A: <1200px 分栏变全屏抽屉 (底部滑出) |
| D1 | 人物拼写 | 按 x.com/steipete 定: Peter Steinberger |
| D2 | 摘要 | 2A: 纯抓取原文, 不调 LLM |
| D3 | 代码位置 | 3A: 独立 scripts/twitter-collector.py |
| D4 | 保留策略 | 4A: 仅 36h 窗口内推文 (滚动裁剪) |
| D5 | 触发方式 | 5A: crontab 增加一行 (与 run 并列) |
| D6 | tab 命名 | 用 "X热点" |

## 3. 采集器设计 (scripts/twitter-collector.py)

### 3.1 配置 twitter-targets.yaml (项目根)

```yaml
# X 采集目标名单 (可编辑, 增删人物后采集自动生效)
targets:
  - name: Peter Steinberger
    handle: steipete
    url: https://x.com/steipete
    enabled: true
    max_tweets: 20        # 单次采集该人物最多保留条数
```

- 缺失字段容错: name/handle/url 必填, enabled 默认 true, max_tweets 默认 20。
- 解析失败输出明确错误并 exit 1 (配置问题属于硬错误, 不应静默跳过)。

### 3.2 CLI 签名 (RIG-2)

```bash
python3 scripts/twitter-collector.py            # 默认 = collect
python3 scripts/twitter-collector.py --collect  # 显式采集 (等价默认)
python3 scripts/twitter-collector.py --login    # 有头模式打开登录页, 人工登录一次
python3 scripts/twitter-collector.py --dry-run  # 只解析配置+探测登录态, 不抓取不写盘
```

- 退出码: 0=成功 / 1=抓取失败 / 2=登录态失效 (与 §3.5 一致)。
- 未知子命令/flag → 打印用法并 exit 1。
- `TWITTER_PROFILE_DIR` 环境变量可覆盖 profile 路径 (测试用临时目录)。

### 3.3 登录态与 Chrome profile

- profile 目录: `cache/twitter-profile/` (gitignored, 不入库)。
- `--login`: 有头模式打开 https://x.com/login, 等待人工登录后关闭;
  登录态持久化在 profile。
- 采集默认 `headless=new` 复用 profile cookie。
- 登录态失效检测: 页面出现登录墙 (redirect login / "Sign in" 卡片) →
  采集终止, exit 2, 输出 `需要人工重新登录: python3 scripts/twitter-collector.py --login`。

### 3.4 抓取流程

1. 启动 Chrome (profile + headless), 打开 target.url。
2. 等待主时间线加载 (`article[data-testid="tweet"]` 出现, 超时 30s)。
3. 滚动加载: 默认 3 次, 每次间隔 2s (保守, 防反爬)。
4. 对每条 tweet 提取 (解析函数纯函数化, 便于单测):
   - id: 状态链接 path 尾段 `/status/{id}`
   - text: `[data-testid="tweetText"]` 文本 (无则整卡文本)
   - posted_at: `time` 元素 `datetime` ISO 属性
   - url: `a[href*="/status/"]` 的 href (规范化为 https://x.com/{handle}/status/{id})
   - views: action bar `aria-label` 匹配 `N views|views` (或 `N 次查看`), 正则提取数字
   - replies/retweets/likes: 底部按钮 `aria-label` (如 `12 replies, 3 reposts, 45 likes`), 逐项正则
   - images: `img[src*="pbs.twimg.com/media/"]` 的 src 列表
5. 多级 fallback: 任一字段缺失置 null, 记 warn 不崩溃。
6. 指标文本 locale 差异: 英文优先, 中文兜底; 解析失败字段置 null。

### 3.5 失败处理与退出码 (RIG-1)

| 场景 | 写盘 | last_error | 退出码 |
|:---|:---|:---|:---|
| 全部成功 (≥1 target 有数据) | ✓ 重写 | 清空 | 0 |
| 部分成功 (部分 target 失败) | ✓ 重写 (含成功 target 数据) | 记录失败 target + 原因 | 0 |
| 全部失败 | ✗ 不写盘 (保留上次) | 不入盘 (仅 stderr 输出) | 1 |
| 登录态失效 | ✗ | — | 2 |

- last_error 仅在写盘时更新; 全失败场景不落盘, 失败原因见 stderr + cron 日志。
- 全失败保留上次 twitter.json (前端仍可显示旧数据, 不破版)。

### 3.6 反爬与频率 (REA-2)

- 采集频率: cron 每日 2 次 (9:20 与 21:20 错峰, 见 §6), 这是防 X 风控的
  独立选择, 不与主采集 cadence 绑定 (主采集实测为每小时)。
- 滚动次数保守 (默认 3 次)。
- 检测验证挑战 (cf-challenge / "Something went wrong") → 跳过本轮,
  输出提示, 不重试轰炸。
- 36h 窗口 × 12h 间隔: 相邻两轮重叠 12h, 单轮失败被次轮完全覆盖。

## 4. 数据 schema (data/twitter.json)

```json
{
  "generated_at": "2026-08-25T01:00:00Z",
  "window_hours": 36,
  "targets": [
    {
      "name": "Peter Steinberger",
      "handle": "steipete",
      "url": "https://x.com/steipete",
      "tweets": [
        {
          "id": "123456789",
          "text": "推文全文",
          "posted_at": "2026-08-25T00:30:00Z",
          "url": "https://x.com/steipete/status/123456789",
          "views": 12345,
          "replies": 12,
          "retweets": 34,
          "likes": 567,
          "images": ["https://pbs.twimg.com/media/xxx.jpg"]
        }
      ]
    }
  ],
  "last_error": null
}
```

- 时间统一 UTC (Z) 存储 (O-1); 前端展示本地化 (MM-DD HH:MM)。
- 字段缺失用 null, 不省略键 (前端渲染稳定)。
- 入库: 采集器自带 commit+push (REA-1, 见 §6), 随 GitHub Pages 部署。

## 5. 前端设计 (index.html)

### 5.1 X热点 tab

- 新 tab id `xhotspots`, label "X热点", 默认不激活 (默认仍 llms)。
- 数据加载: `fetch('data/twitter.json?t=' + ts)`, 失败 console.warn
  回退空态 (`[llm-radar] twitter.json load failed:`) 不阻断页面。
- tab 计数: 渲染后更新 (与现有 5 tab 同机制)。

### 5.2 表格渲染 renderXHotspots() (SEC-1)

- 新增 `esc()` helper: 转义 `& < > " ' \``; 渲染路径全字段强制转义。
  (建议顺带回填既有渲染点: renderHotspotPanel 等 innerHTML 直插点 —
  现有 5 tab 同源同类风险, 实施时一并收敛。)
- 复用 `.data-table`: 列 = 时间 / 人物 / 推文摘要 (截断) / 指标 (views/replies/likes)。
- 时间显示 MM-DD HH:MM (UTC → 本地); 推文文本截断 + 全文在分栏。
- 源 filter chips 扩展 "X" (按 handle/url 域名过滤)。
- 国家过滤对 X tab 不适用 (tweet 无 country 字段, O-6): X tab 内国家
  chips 隐藏或置灰, 仅源 chips 生效。
- 指标为 null 显示 `—`。

### 5.3 分栏详情 (split-preview 式, SEC-1)

- 结构参考 html-gen demos/hermes-profile-skills-list.html:
  - `.wrapper.split-mode` 容器状态
  - `.split-preview`: header (上一/下一 nav + 关闭) + body
  - body: 推文全文 / 指标 kv 卡片 / 图片列表
- 交互: 单击行 或 行内"详情"按钮 → openSplitPreview(当前 tweet 索引);
  nav 上一/下一条同人物内切换。
- 关闭: header 关闭按钮 / 点击空白 / Esc。
- 仅 X热点 tab 生效 (9A), 其他 tab 行行为不变。
- 安全: 全文/指标经 esc() 转义; URL 渲染协议白名单 (https://) +
  `target="_blank" rel="noopener"`; images src 前端二次校验 https:// 前缀
  (采集侧已过滤 pbs.twimg.com, 双保险)。

### 5.4 图片处理

- `<img src="https://pbs.twimg.com/media/...">` 直引 (10B)。
- onerror → 替换为占位块 (`图片加载失败`), 不破版。
- 多图横排滚动, 单图完整显示。
- src 仅接受 https:// 前缀 (双保险, SEC-1)。

### 5.5 窄屏降级 (<1200px)

- `.split-preview` 变为 fixed 全屏抽屉 (底部滑出, 高度 ~85vh)。
- 行内"详情"按钮在窄屏显示 (7C), 单击行仍可用。

## 6. crontab 变更 (Mac 本机) (REA-1/REA-2)

```cron
20 9,21 * * * cd /Users/jadenli/CodeSpace/llm-radar.lab && python3 scripts/twitter-collector.py >> data/twitter.log 2>&1 # llm-radar-twitter
```

- 时刻 `20 9,21` 错峰: 避开主采集整点 (:00), 防止双 Chrome 实例资源竞争
  与主采集 `git add -A` 抓取写入中的 twitter.json (REA-2)。
- 采集成功后自带 commit + push (REA-1):
  `auto-push@llm-radar: update twitter (N changes)`; push 失败记录
  last_error 不重试轰炸 (下一轮自动再试)。
- 不调 LLM, 无需 .env。
- Linux 服务器默认不启用 (无人工登录态; 若后续需要, 由部署方
  在服务器上单独 --login 一次并加入其 crontab)。

## 7. 测试与验收

### 7.1 单元测试 (tests/test_twitter_collector.py 新增)

- 配置解析: 正常/缺字段/空文件/非法 yaml。
- 36h 窗口过滤: 注入假 tweets (窗口内/外/边界), 断言裁剪正确。
- max_tweets 截断: 时间倒序取前 N。
- DOM 解析: 注入 fixture HTML 片段 (文本/时间/指标/图片), 断言提取字段。
- twitter.json 写盘: schema 字段完整 + null 缺省 + UTC 时间格式。
- 退出码映射 (O-4): exit-2 登录墙检测 / 挑战检测 / 全失败不写盘 /
  部分成功写盘 + last_error。

### 7.2 前端测试 (tests/test_html.py 扩展)

- 断言 "X热点" tab 存在 + renderXHotspots 函数 + split-preview 元素/类
  + esc() helper 存在。
- 按既有规则: 只扫 `<script>` 块, 排除 `<style>` 块。

### 7.3 验收标准

1. `--login` 可打开登录页; 人工登录后 `--collect` 实测抓取 steipete 36h 推文。
2. data/twitter.json 生成且 schema 合规 (generated_at UTC / targets / tweets)。
3. 36h 过滤正确 (注入旧推文被裁剪); 全失败保留旧文件 + exit 1。
4. 前端 X热点 tab 渲染 (转义生效) + 单击分栏 + nav 切换 + 关闭; 窄屏抽屉降级。
5. Mac crontab 接入 (20 9,21 错峰), 手动触发一次实测成功 + 自带 push 生效。
6. pytest 相关用例通过 (非 selenium 集合)。

## 8. 风险与回退

| 风险 | 影响 | 缓解 |
|:---|:---|:---|
| X DOM/选择器变化 | 字段提取失败 | 多级 fallback + 字段级 warn; 解析纯函数化易修 |
| 登录态失效 | 采集全部失败 | exit 2 + 明确提示 --login; 人工 1 分钟恢复 |
| 反爬 (403/挑战页) | 本轮无数据 | 检测跳过本轮, 不重试轰炸; 频率保守 (2×/day) |
| 图片防盗链 403 | 图片不显示 | 占位块, 不破版 (已接受 10B) |
| 指标 locale 差异 | views/replies 缺失 | 正则多语言兜底, 缺失显示 — |
| stored XSS | 恶意推文注入页面 | esc() 全字段转义 + URL/图片协议白名单 (SEC-1) |
| 入库链路断裂 | Pages 数据陈旧 | 采集器自带 commit+push; last_error 可见 |

## 9. 实施顺序 (dev)

1. twitter-targets.yaml + 配置解析 (含单测)。
2. twitter-collector.py: --login / --collect / --dry-run / 抓取 / 解析 /
   36h 过滤 / 写 twitter.json / commit+push。
3. 单测: 配置/过滤/解析/写盘/退出码 (test_twitter_collector.py)。
4. 前端: esc() helper + X热点 tab + 表格 + 分栏 + 抽屉 + chips (index.html)。
5. test_html.py 扩展 (tab/分栏/esc 断言)。
6. Mac crontab 接入 (20 9,21 错峰)。
7. ops 实测: 人工登录 + 采集 + 前端渲染 + pytest。

---

> 设计评审入口: documents/reviews/ (CL-SEC19 闭环)。
