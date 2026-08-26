---
title: X 热点采集与分栏详情设计
topic: llm-radar
type: design
version: 1.2
date: 2026-08-26
author: hermes-1.2.0
tags: [llm-radar, twitter, x, selenium, frontend, split-view, search]
profile: ops
provider: deepseek
model: deepseek-v4-flash
---

# X 热点采集与分栏详情设计 v1.2

> 探讨确认(2026-08-26): CL-SEC20, 决策 D1 1A / D2 2C / D3 三账号 / D4 4B / D5 5A 锁定。
> v1.1 已实现并通过实现审计 (PASS 100/A); 本版为功能增强。

## 修订记录

- v1.0 (2026-08-25) — 初版: 决策锁定 (Q1-Q11 + D1-D6), 采集器/数据/前端/crontab/测试验收。
- v1.1 (2026-08-25) — 评审修正 5 项: SEC-1 XSS; REA-1 入库链路; REA-2 cadence;
  RIG-1 部分成功语义; RIG-2 CLI 签名。观察项 O-1/O-4/O-6。
- v1.2 (2026-08-26) — CL-SEC20 增强: 配置迁移 data/; 账号 1→10; 转发 forward 字段
  (D2 2C); 条数窗口 30 条+24h 不限 (D1 1A, 废弃 36h); 全站搜索 Cmd+F (D4 4B);
  采集时长接受 5-8min (D5 5A)。

---

## 1. 背景与目标

llm-radar X 热点功能 (CL-SEC19) 已上线: 单账号 (steipete) 36h 窗口采集 +
X热点 tab 分栏详情。本版 (CL-SEC20) 增强:

1. 配置迁移至 data/, 账号扩展至 10 个 AI/LLM 领头人。
2. 转发 (retweet/quote) 采集, forward 字段展示原文。
3. 条数窗口: 每账号 ≥30 条, 24h 内超量不限。
4. 全站搜索 (Cmd+F 快捷键), 跨 tab 汇总。

约束 (继承 v1.1):

- 纯抓取不调 LLM (0 token)。
- 采集失败不阻断主流程; 图片直引 pbs.twimg.com + 失败占位。
- 前端渲染全字段转义 (esc(), SEC-1)。

## 2. 决策记录

### 2.1 v1.0/v1.1 已确认 (继承)

| # | 决策 | 内容 |
|:---|:---|:---|
| Q1 | 人物名单 | 1C: 配置文件可编辑; 默认 Peter Steinberger |
| Q2 | 采集内容 | 2D: 文本+时间+链接+指标+图片 URL |
| Q3 | 数据落点 | 3B: 独立 data/twitter.json 前端单独加载 |
| Q4 | 前端展示 | 4A: "X热点" tab |
| Q5 | 登录态 | 5A→--attach: CDP 复用独立 Chrome profile (~/chrome-twitter-cdp) 登录态 |
| Q6 | 采集节奏 | cron 每日 2 次 (防 X 风控) |
| Q7 | 交互触发 | 7C: 单击展开 + 行内按钮 |
| Q8 | 分栏形态 | 8A: 右侧分栏 (split-preview 式) |
| Q9 | 详情范围 | 9A: 仅 X热点 tab |
| Q10 | 图片处理 | 10B: 直引 pbs.twimg.com + 占位 |
| Q11 | 窄屏降级 | 11A: <1200px 全屏抽屉 |
| D1-D6 | v1.1 | steipete 拼写/纯抓取/独立脚本/保留策略/触发/命名 |

### 2.2 v1.2 新增 (CL-SEC20)

| # | 决策 | 内容 |
|:---|:---|:---|
| D1 | 条数窗口 | 1A: 每账号保留最近 30 条; 24h 内 >30 条全保留; 废弃 36h 窗口 |
| D2 | 转发处理 | 2C: retweet/quote 计入条数; forward 字段 = "by @{作者}: {原推文}" |
| D3 | 新增账号 | Jeff Dean (JeffDean) / Andrew Ng (AndrewYNg) / Andrej Karpathy (karpathy) |
| D4 | 搜索 | 4B: 全站 header-search 跨 tab 汇总 + Cmd+F 拦截聚焦 |
| D5 | 采集时长 | 5A: 滚动 3 次/账号保持, 接受 5-8min |

## 3. 采集器设计 (scripts/twitter-collector.py)

### 3.1 配置 twitter-targets.yaml (data/, CL-SEC20)

- 路径: `data/twitter-targets.yaml` (CONFIG_PATH 更新; .gitignore 已验证无冲突, 入库)。
- 账号清单 (10 个):

```yaml
targets:
  - {name: DHH, handle: dhh, url: https://x.com/dhh}
  - {name: Boris Cherny, handle: bcherny, url: https://x.com/bcherny}
  - {name: Sam Altman, handle: sama, url: https://x.com/sama}
  - {name: Claude, handle: claudeai, url: https://x.com/claudeai}
  - {name: OpenClaw, handle: openclaw, url: https://x.com/openclaw}
  - {name: Nous Research, handle: NousResearch, url: https://x.com/NousResearch}
  - {name: DeepSeek, handle: deepseek_ai, url: https://x.com/deepseek_ai}
  - {name: Jeff Dean, handle: JeffDean, url: https://x.com/JeffDean}
  - {name: Andrew Ng, handle: AndrewYNg, url: https://x.com/AndrewYNg}
  - {name: Andrej Karpathy, handle: karpathy, url: https://x.com/karpathy}
```

- 字段规则不变: name/handle/url 必填, enabled 默认 true, max_tweets 默认 30 (v1.2 起)。

### 3.2 CLI 签名 (继承 v1.1)

```bash
python3 scripts/twitter-collector.py            # 默认 collect
python3 scripts/twitter-collector.py --collect  # 显式采集
python3 scripts/twitter-collector.py --login    # 有头登录
python3 scripts/twitter-collector.py --dry-run  # 配置+登录态探测
python3 scripts/twitter-collector.py --attach   # CDP attach 采集 (cron 默认)
```

退出码: 0=成功(含部分成功) / 1=抓取失败或配置错误 / 2=登录态失效。

### 3.3 登录态与 Chrome profile (继承 v1.1)

- profile: ~/chrome-twitter-cdp (独立 Chrome, 人工登录一次)。
- cron 自动拉起: scripts/twitter-collector-cron.sh (D1A, 已验证)。
- 登录墙检测 → exit 2 + 人工恢复提示。

### 3.4 抓取流程 (CL-SEC20 变更)

1. 启动 Chrome (--attach 复用 9222 / 本地 profile headless)。
2. 打开 target.url, 等待 article 出现 (30s 超时)。
3. **首屏解析 → 滚动 3 次 × 2s 补抓** (v1.1 修复, 保留)。
4. 对每条 tweet 提取 (解析纯函数化):
   - id/text/posted_at/url/views/replies/retweets/likes/images (继承)
   - **forward (新增)**: 检测 retweet/quote 结构 —
     外层 tweetText (可能空) + 内层原推文 tweetText;
     原推文作者从嵌套 article/引用的 `a[href*="/{author}/status/"]` 或
     头像 alt 提取; forward 格式 `by @{作者}: {原推文文本}`;
     非转发 → forward=None。
5. **条数窗口 (D1 1A, 废弃 36h)**:
   - 每账号保留最近 max_tweets=30 条 (时间倒序截断);
   - 若 24h 内推文 >30 条 → 全保留 (不截断);
   - 实现: 先按 24h 过滤 → 若 >30 全保留; 否则取最近 30 条;
   - twitter.json 的 window_hours 字段改为 `retention: "30/24h"` 语义。
6. 多账号循环: 10 账号, 每账号 ~30-60s, 总耗时接受 5-8min (D5 5A)。

### 3.5 失败处理与退出码 (继承 v1.1)

| 场景 | 写盘 | last_error | 退出码 |
|:---|:---|:---|:---|
| 全部成功 (≥1 target 有数据) | ✓ | 清空 | 0 |
| 部分成功 | ✓ | 记录失败 target | 0 |
| 全部失败 | ✗ | — | 1 |
| 登录态失效 | ✗ | — | 2 |

### 3.6 反爬与频率 (继承 v1.1)

- cron 20 9,21 错峰; 滚动 3 次保守; 挑战检测跳过本轮。
- 10 账号连续抓取注意风控: 账号间 2s 间隔; 若遇挑战提前终止本轮
  (部分成功语义处理)。

## 4. 数据 schema (data/twitter.json)

```json
{
  "generated_at": "2026-08-26T05:00:00Z",
  "retention": "30/24h",
  "targets": [
    {
      "name": "Sam Altman",
      "handle": "sama",
      "url": "https://x.com/sama",
      "tweets": [
        {
          "id": "123456789",
          "text": "推文全文或空",
          "forward": "by @openai: 被转发的原文",
          "posted_at": "2026-08-26T04:30:00Z",
          "url": "https://x.com/sama/status/123456789",
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

- 时间统一 UTC (Z); 字段缺失 null 不省略键。
- `window_hours` → `retention` (D1 1A 语义变更, 前端无需读, 兼容保留亦可)。
- forward 非转发为 null; 转发且无外层文本时 text 为 null (渲染处理)。

## 5. 前端设计 (index.html)

### 5.1 X热点 tab (继承 v1.1)

- tab id xhotspots, label "X热点"; 表格列: 时间/人物/摘要/指标。
- 摘要截断: 有 forward 时显示 `{text}\nforward: {forward}` 截断形式。
- 分栏全文: 同格式完整显示 (forward 行区分样式)。

### 5.2 全站搜索 (D4 4B, 新增)

- header-search 输入框 (顶部工具条, 参考 html-gen table-actions-demo):
  - 输入即过滤 (防抖 ~200ms) + Enter 触发;
  - 当前 tab 表格行过滤 (匹配 name/文本/forward/人物/链接);
  - 跨 tab 汇总: 其他 tab 匹配计数显示在搜索框旁
    (如 "工具 3 · 模型 5"), 点击计数跳转对应 tab 并高亮;
  - 清空按钮 / Esc 清空恢复全表。
- Cmd+F 快捷键: keydown 拦截 (metaKey && key==='f') →
  preventDefault + 聚焦搜索框; 二次 Cmd+F 无操作 (已聚焦)。
- 窄屏 (<1200px): 搜索框保留 (工具条可滚动)。

### 5.3 分栏详情 (继承 v1.1, SEC-1)

- split-preview: header (nav/close) + body (全文/forward/指标 kv/图片)。
- 渲染: 全字段 esc()/textContent; URL+图片 https 白名单; rel=noopener。

### 5.4 窄屏降级 (继承 v1.1)

- <1200px: 分栏变全屏抽屉; 行内"详情"按钮显示。

## 6. crontab (继承 v1.1)

```cron
20 9,21 * * * cd /Users/jadenli/CodeSpace/llm-radar.lab && bash scripts/twitter-collector-cron.sh >> data/twitter.log 2>&1 # llm-radar-twitter
```

- 采集时长 5-8min 在 9:20/21:20 窗口内可完成 (主采集整点错开)。
- 10 账号数据量增大, twitter.json 随 auto-push 入库 (REA-1)。

## 7. 测试与验收

### 7.1 单元测试 (tests/test_twitter_collector.py 更新)

- 配置解析: data/ 路径 + 10 账号 + 缺字段容错。
- **条数窗口 (D1 1A)**: 注入 >30 条 24h 内 → 全保留; >30 条跨 24h →
  24h 内全保留 + 其余按最近 30 补足; <30 条 → 全部保留。
- **forward 解析 (D2 2C)**: retweet/quote fixture HTML → forward 格式
  "by @author: 原文"; 非转发 → None; 无外层文本 → text None + forward 有值。
- 原有: 36h 过滤用例更新为 30/24h 语义; DOM 解析/写盘/退出码不变。
- 多账号: 部分失败 → last_error + 部分成功写盘。

### 7.2 前端测试 (tests/test_html.py 更新)

- header-search 元素 + doSearch 函数 + Cmd+F 拦截逻辑;
- forward 渲染 (表格/分栏) + esc 覆盖;
- 跨 tab 计数/跳转。

### 7.3 验收标准

1. data/twitter-targets.yaml 生效 (10 账号), 旧根路径文件移除。
2. --attach 实测: 10 账号采集 (或至少 3 个代表性账号), forward 字段
   正确 (转推带 by @作者), 条数 ≥30 或 24h 内全保留。
3. 全站搜索: 输入过滤当前 tab + 跨 tab 计数跳转 + Cmd+F 聚焦拦截。
4. X热点 表格/分栏 forward 格式渲染正确。
5. cron 自动拉起链路不变 (D1A 回归)。
6. pytest 非 selenium 全绿。

## 8. 风险与回退

| 风险 | 影响 | 缓解 |
|:---|:---|:---|
| 10 账号风控触发 | 部分账号无数据 | 账号间 2s 间隔; 挑战跳过; 部分成功语义 |
| 30 条滚动深度不足 | 条数 <30 | 首屏+3 次滚动实测; 不足时提高滚动次数 (不并发) |
| 转发 DOM 结构变化 | forward 缺失 | 多级 fallback; forward=None 不崩溃 |
| 搜索性能 (大 JSON) | 输入卡顿 | 防抖 200ms; 过滤在内存数组 |
| Cmd+F 覆盖原生查找 | 用户习惯冲突 | 已确认接受 (D4); 搜索框有清空/Esc 恢复 |

## 9. 实施顺序 (dev)

1. 配置迁移 data/ + CONFIG_PATH + 10 账号 + 测试适配。
2. 条数窗口 30/24h 逻辑 + forward 解析 + 单测。
3. 前端: header-search + doSearch + Cmd+F + forward 渲染 + test_html 扩展。
4. crontab/AGENTS.md 文档同步。
5. ops 实测: 多账号采集 + 搜索/快捷键 + 前端渲染 + pytest。

---

> 设计评审入口: documents/reviews/ (CL-SEC20 闭环)。
