---
title: X 热点采集与分栏详情设计
topic: llm-radar
type: design
version: 1.0
date: 2026-08-25
author: hermes-1.2.0
tags: [llm-radar, twitter, x, selenium, frontend, split-view]
profile: ops
provider: deepseek
model: deepseek-v4-flash
---

# X 热点采集与分栏详情设计 v1.0

> 探讨确认(2026-08-25): 1A 协议闭环, 决策 Q1-Q11 + D1-D6 全部锁定 (CL-SEC19)。
> 采集器与前端联动设计, 分两期实施节奏见 §9。

## 修订记录

- v1.0 (2026-08-25) — 初版: 决策锁定 (Q1-Q11 + D1-D6), 采集器/数据/前端/crontab/测试验收。

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

## 2. 决策记录(已确认)

| # | 决策 | 内容 |
|:---|:---|:---|
| Q1 | 人物名单 | 1C: 配置文件 twitter-targets.yaml 可编辑; 默认 Peter Steinberger (x.com/steipete) |
| Q2 | 采集内容 | 2D: 文本+时间+链接+指标(views/replies/retweets/likes)+图片 URL |
| Q3 | 数据落点 | 3B: 独立 data/twitter.json, 前端单独加载 |
| Q4 | 前端展示 | 4A: 新增 "X热点" tab |
| Q5 | 登录态 | 5A: 持久化 Chrome profile (user-data-dir), 人工登录一次 |
| Q6 | 采集节奏 | 6A: 与主采集同 cadence (cron 每日 2 次) |
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

### 3.2 登录态与 Chrome profile

- profile 目录: `cache/twitter-profile/` (gitignored, 不入库)。
- 子命令 `--login`: 有头模式打开 https://x.com/login, 等待人工登录后
  关闭; 登录态持久化在 profile。
- 采集默认 `headless=new` 复用 profile cookie。
- 环境变量 `TWITTER_PROFILE_DIR` 可覆盖 profile 路径 (测试用临时目录)。
- 登录态失效检测: 页面出现登录墙 (redirect login / "Sign in" 卡片) →
  采集终止, exit 2, 输出 `需要人工重新登录: python3 scripts/twitter-collector.py --login`。

### 3.3 抓取流程

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

### 3.4 36h 窗口与裁剪

- 过滤: `posted_at >= now - 36h` 且 <= now (容忍时钟偏差 5min)。
- 单人物按 max_tweets 截断 (时间倒序取前 N)。
- data/twitter.json 每次全量重写 (只含窗口内数据, 滚动裁剪)。

### 3.5 失败处理与退出码

| 退出码 | 含义 |
|:---|:---|
| 0 | 成功 (即使 0 条新推文, 数据文件照常更新 generated_at) |
| 1 | 抓取失败 (网络/Selenium 异常/解析崩溃) |
| 2 | 登录态失效 (需人工 --login) |

- 失败不写坏文件: 仅在成功/部分成功时重写 twitter.json。
- last_error 记录最近一次失败原因 (供前端/人工排查)。

### 3.6 反爬与频率

- 频率与主采集一致 (cron 9:00/21:00), 不触发高频风控。
- 滚动次数保守 (默认 3 次)。
- 检测验证挑战 (cf-challenge / "Something went wrong") → 跳过本轮,
  输出提示, 不重试轰炸。

## 4. 数据 schema (data/twitter.json)

```json
{
  "generated_at": "2026-08-25T09:00:00+08:00",
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
          "posted_at": "2026-08-25T08:30:00Z",
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

- 字段缺失用 null, 不省略键 (前端渲染稳定)。
- 入库: 随 GitHub Pages 部署 (同 snapshot.json 机制)。

## 5. 前端设计 (index.html)

### 5.1 X热点 tab

- 新 tab id `xhotspots`, label "X热点", 默认不激活 (默认仍 llms)。
- 数据加载: `fetch('data/twitter.json?t=' + ts)`, 失败 console.warn
  回退空态 (`[llm-radar] twitter.json load failed:`) 不阻断页面。
- tab 计数: 渲染后更新 (与现有 5 tab 同机制)。

### 5.2 表格渲染 renderXHotspots()

- 复用 `.data-table`: 列 = 时间 / 人物 / 推文摘要 (截断) / 指标 (views/replies/likes)。
- 时间显示 MM-DD HH:MM; 推文文本截断 + 全文在分栏。
- 源 filter chips 扩展 "X" (按 handle/url 域名过滤), 国家过滤沿用。
- 指标为 null 显示 `—`。

### 5.3 分栏详情 (split-preview 式)

- 结构参考 html-gen demos/hermes-profile-skills-list.html:
  - `.wrapper.split-mode` 容器状态
  - `.split-preview`: header (上一/下一 nav + 关闭) + body
  - body: 推文全文 / 指标 kv 卡片 / 图片列表
- 交互: 单击行 或 行内"详情"按钮 → openSplitPreview(当前 tweet 索引);
  nav 上一/下一条同人物内切换。
- 关闭: header 关闭按钮 / 点击空白 / Esc。
- 仅 X热点 tab 生效 (9A), 其他 tab 行行为不变。

### 5.4 图片处理

- `<img src="https://pbs.twimg.com/media/...">` 直引 (10B)。
- onerror → 替换为占位块 (`图片加载失败`), 不破版。
- 多图横排滚动, 单图完整显示。

### 5.5 窄屏降级 (<1200px)

- `.split-preview` 变为 fixed 全屏抽屉 (底部滑出, 高度 ~85vh)。
- 行内"详情"按钮在窄屏显示 (7C), 单击行仍可用。

## 6. crontab 变更 (Mac 本机)

```cron
0 9,21 * * * cd /Users/jadenli/CodeSpace/llm-radar.lab && python3 scripts/twitter-collector.py >> data/twitter.log 2>&1 # llm-radar-twitter
```

- 与主采集 (llm-radar-run.sh) 同 cadence 并列, 互不依赖。
- 不调 LLM, 无需 .env。
- Linux 服务器默认不启用 (无人工登录态; 若后续需要, 由部署方
  在服务器上单独 --login 一次并加入其 crontab)。

## 7. 测试与验收

### 7.1 单元测试 (tests/test_twitter_collector.py 新增)

- 配置解析: 正常/缺字段/空文件/非法 yaml。
- 36h 窗口过滤: 注入假 tweets (窗口内/外/边界), 断言裁剪正确。
- max_tweets 截断: 时间倒序取前 N。
- DOM 解析: 注入 fixture HTML 片段 (文本/时间/指标/图片), 断言提取字段。
- twitter.json 写盘: schema 字段完整 + null 缺省 + generated_at 格式。

### 7.2 前端测试 (tests/test_html.py 扩展)

- 断言 "X热点" tab 存在 + renderXHotspots 函数 + split-preview 元素/类。
- 按既有规则: 只扫 `<script>` 块, 排除 `<style>` 块。

### 7.3 验收标准

1. `--login` 可打开登录页; 人工登录后 `--collect` 实测抓取 steipete 36h 推文。
2. data/twitter.json 生成且 schema 合规 (generated_at/targets/tweets)。
3. 36h 过滤正确 (注入旧推文被裁剪)。
4. 前端 X热点 tab 渲染 + 单击分栏 + nav 切换 + 关闭; 窄屏抽屉降级。
5. Mac crontab 接入 (9:00/21:00), 手动触发一次实测成功。
6. pytest 相关用例通过 (非 selenium 集合)。

## 8. 风险与回退

| 风险 | 影响 | 缓解 |
|:---|:---|:---|
| X DOM/选择器变化 | 字段提取失败 | 多级 fallback + 字段级 warn; 解析纯函数化易修 |
| 登录态失效 | 采集全部失败 | exit 2 + 明确提示 --login; 人工 1 分钟恢复 |
| 反爬 (403/挑战页) | 本轮无数据 | 检测跳过本轮, 不重试轰炸; 频率保守 |
| 图片防盗链 403 | 图片不显示 | 占位块, 不破版 (已接受 10B) |
| 指标 locale 差异 | views/replies 缺失 | 正则多语言兜底, 缺失显示 — |

## 9. 实施顺序 (dev)

1. twitter-targets.yaml + 配置解析 (含单测)。
2. twitter-collector.py: --login / 抓取 / 解析 / 36h 过滤 / 写 twitter.json。
3. 单测: 配置/过滤/解析/写盘 (test_twitter_collector.py)。
4. 前端: X热点 tab + 表格 + 分栏 + 抽屉 + chips (index.html)。
5. test_html.py 扩展 (tab/分栏断言)。
6. Mac crontab 接入。
7. ops 实测: 人工登录 + 采集 + 前端渲染 + pytest。

---

> 设计评审入口: documents/reviews/ (CL-SEC19 闭环)。
