---
title: X 热点采集与分栏详情设计
topic: llm-radar
type: design
version: 1.3
date: 2026-08-26
author: hermes-1.2.0
tags: [llm-radar, twitter, x, selenium, frontend, split-view, search]
profile: ops
provider: deepseek
model: deepseek-v4-flash
---

# X 热点采集与分栏详情设计 v1.3

> 探讨确认(2026-08-26): CL-SEC20, 决策 D1 1A / D2 2C / D3 三账号 / D4 4B / D5 5A 锁定。
> v1.1 已实现并通过实现审计 (PASS 100/A); v1.2 评审 80/B → 本版修正 4 🟡 + 1 🟢。

## 修订记录

- v1.0 (2026-08-25) — 初版: 决策锁定 (Q1-Q11 + D1-D6)。
- v1.1 (2026-08-25) — 评审修正 5 项 (SEC-1/REA-1/REA-2/RIG-1/RIG-2) + 观察项 3 项。
- v1.2 (2026-08-26) — CL-SEC20 增强: 配置迁移 data/; 账号 1→10; forward; 30/24h 窗口; 全站搜索。
- v1.3 (2026-08-26) — 评审修正 4 🟡: REA-1 条数窗口回填语义统一; RIG-1 schema
  变更测试影响枚举; RIG-2 风控部分成功语义锁定; SEC-1 搜索高亮输出编码。
  观察项 O-1 forward XSS 专项断言。
  (评审: documents/reviews/x-hotspot-review-v1.2-20260826.md, 80/B CONDITIONAL)

---

## 1. 背景与目标

llm-radar X 热点功能 (CL-SEC19) 已上线。本版 (CL-SEC20) 增强:

1. 配置迁移至 data/, 账号扩展至 10 个 AI/LLM 领头人。
2. 转发 (retweet/quote) 采集, forward 字段展示原文。
3. 条数窗口: 每账号 ≥30 条, 24h 内超量不限。
4. 全站搜索 (Cmd+F 快捷键), 跨 tab 汇总。

约束 (继承):

- 纯抓取不调 LLM (0 token)。
- 采集失败不阻断主流程; 图片直引 pbs.twimg.com + 失败占位。
- 前端渲染全字段转义 (esc()/textContent, SEC-1), 含 forward 与搜索高亮。

## 2. 决策记录

### 2.1 v1.0/v1.1 已确认 (继承)

Q1-Q11 + D1-D6 (见 v1.1): 配置可编辑/2D 内容/独立 twitter.json/X热点 tab/
--attach CDP 登录态/cron 2×/day/7C 交互/8A 分栏/9A 范围/10B 图片/11A 抽屉。

### 2.2 v1.2/v1.3 新增 (CL-SEC20)

| # | 决策 | 内容 |
|:---|:---|:---|
| D1 | 条数窗口 | 1A: 每账号 ≥30 条; 24h 内 >30 条全保留; 废弃 36h (语义见 §3.4) |
| D2 | 转发处理 | 2C: retweet/quote 计入条数; forward = "by @{作者}: {原推文}" |
| D3 | 新增账号 | Jeff Dean (JeffDean) / Andrew Ng (AndrewYNg) / Andrej Karpathy (karpathy) |
| D4 | 搜索 | 4B: 全站 header-search 跨 tab 汇总 + Cmd+F 拦截聚焦 |
| D5 | 采集时长 | 5A: 滚动 3 次/账号保持, 接受 5-8min |

## 3. 采集器设计 (scripts/twitter-collector.py)

### 3.1 配置 twitter-targets.yaml (data/)

- 路径: `data/twitter-targets.yaml` (CONFIG_PATH 更新; .gitignore 无冲突, 入库)。
- 账号清单 (10 个): DHH/dhh, Boris Cherny/bcherny, Sam Altman/sama,
  Claude/claudeai, OpenClaw/openclaw, Nous Research/NousResearch,
  DeepSeek/deepseek_ai, Jeff Dean/JeffDean, Andrew Ng/AndrewYNg,
  Andrej Karpathy/karpathy。
- 字段规则: name/handle/url 必填, enabled 默认 true, max_tweets 默认 30。

### 3.2 CLI 签名 (继承)

默认 collect / --collect / --login / --dry-run / --attach。
退出码: 0=成功(含部分成功) / 1=抓取失败或配置错误 / 2=登录态失效。

### 3.3 登录态与 Chrome profile (继承)

- profile: ~/chrome-twitter-cdp (独立 Chrome, 人工登录一次)。
- cron 自动拉起: scripts/twitter-collector-cron.sh (D1A, 已验证)。
- 登录墙检测 → exit 2 + 人工恢复提示。

### 3.4 抓取流程 (REA-1 修正)

1. 启动 Chrome (--attach 复用 9222 / 本地 profile headless)。
2. 打开 target.url, 等待 article 出现 (30s 超时)。
3. 首屏解析 → 滚动 3 次 × 2s 补抓 (v1.1 修复, 保留)。
4. 每条 tweet 提取 (解析纯函数化):
   - id/text/posted_at/url/views/replies/retweets/likes/images (继承);
   - forward (v1.2): retweet/quote 检测 → 外层 tweetText (可能空) +
     内层原推文 tweetText + 作者 (嵌套 article / 引用 href / 头像 alt 提取);
     forward 格式 `by @{作者}: {原推文文本}`; 非转发 → None。
5. **条数窗口 (D1 1A, 统一语义 — REA-1)**:
   - 抓取全部解析出的推文 (时间倒序);
   - 保留规则 (单账号):
     a. 24h 内推文 >30 条 → 全保留 (24h 内所有, 不截断);
     b. 24h 内推文 ≤30 条 → 保留全部 24h 内 + 24h 外按时间倒序补足至 30;
     c. 总推文 <30 条 → 全部保留;
   - 实现: 先按 posted_at 分 24h 内/外两组; 组内时间倒序;
     按规则组合后取前 N (N=max_tweets 或 24h 内全量, 取较大);
   - 边界: 恰好 30 条 → 全保留; 恰好 24h 边界 (now-24h 整点) 视为 24h 内。
6. 多账号循环: 10 账号, 每账号 ~30-60s, 总耗时接受 5-8min (D5 5A);
   账号间 2s 间隔 (风控)。

### 3.5 失败处理与退出码 (继承)

| 场景 | 写盘 | last_error | 退出码 |
|:---|:---|:---|:---|
| 全部成功 (≥1 target 有数据) | ✓ | 清空 | 0 |
| 部分成功 | ✓ | 记录失败 target | 0 |
| 全部失败 | ✗ | — | 1 |
| 登录态失效 | ✗ | — | 2 |

### 3.6 反爬与频率 (RIG-2 修正)

- cron 20 9,21 错峰; 滚动 3 次保守。
- **挑战检测 (统一语义)**: 单账号抓取中遇挑战 (cf-challenge/"Something
  went wrong") → 终止**该账号**, 记 error (部分成功语义, §3.5), 继续下一账号;
  连续 ≥2 账号遇挑战 → 提前终止本轮 (防风控升级), 已抓账号正常写盘;
  全部账号未抓成 → 全部失败不写盘 (exit 1)。
- 数据完整度: 部分成功时 last_error 记录失败账号与原因, 成功账号数据完整落盘。

## 4. 数据 schema (data/twitter.json) (RIG-1 修正)

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
- **schema 变更与测试影响 (RIG-1)**:
  - `window_hours` → `retention` (语义: "30/24h");
  - 受影响测试断言 (需同步更新, 不属"写盘不变"):
    a. tests/test_twitter_collector.py 中 window_hours 字段断言;
    b. tests/test_html.py 若读取 retention/window 相关;
    c. 设计 v1.2 §7.1 原"写盘不变"表述更正: schema 字段变更 → 写盘断言更新。
  - 前端不读 retention 字段, 无渲染影响。
- forward 非转发为 null; 转发且无外层文本时 text 为 null (渲染处理)。

## 5. 前端设计 (index.html)

### 5.1 X热点 tab (继承)

- tab id xhotspots, label "X热点"; 表格列: 时间/人物/摘要/指标。
- 摘要截断: 有 forward 时显示 `{text}\nforward: {forward}` 截断形式
  (text 为空则仅显示 forward 行)。
- 分栏全文: 同格式完整显示 (forward 行区分样式)。

### 5.2 全站搜索 (D4 4B, SEC-1 修正)

- header-search 输入框 (顶部工具条, 参考 html-gen table-actions-demo):
  - 输入即过滤 (防抖 ~200ms) + Enter 触发;
  - 当前 tab 表格行过滤 (匹配 name/文本/forward/人物/链接);
  - 跨 tab 汇总: 其他 tab 匹配计数 (如 "工具 3 · 模型 5"), 点击跳转+高亮;
  - 清空按钮 / Esc 清空恢复全表。
- Cmd+F 快捷键: keydown 拦截 (metaKey && key==='f') →
  preventDefault + 聚焦搜索框; 已聚焦时无操作。
- **高亮输出编码 (SEC-1)**: 匹配高亮用结构化 DOM 构建 (span 节点 +
  textContent 分片), 禁止 innerHTML 拼接; 查询词与匹配文本均按文本节点
  渲染; 若用字符串模板必须经 esc() 双转义 (查询词 + 片段)。
- 窄屏 (<1200px): 搜索框保留 (工具条可滚动)。

### 5.3 分栏详情 (继承, SEC-1)

- split-preview: header (nav/close) + body (全文/forward/指标 kv/图片)。
- 渲染: 全字段 esc()/textContent (forward 同); URL+图片 https 白名单; rel=noopener。

### 5.4 窄屏降级 (继承)

- <1200px: 分栏变全屏抽屉; 行内"详情"按钮显示。

## 6. crontab (继承)

```cron
20 9,21 * * * cd /Users/jadenli/CodeSpace/llm-radar.lab && bash scripts/twitter-collector-cron.sh >> data/twitter.log 2>&1 # llm-radar-twitter
```

- 采集时长 5-8min 在 9:20/21:20 窗口内完成 (主采集整点错开)。
- twitter.json 随 auto-push 入库 (REA-1 v1.1)。

## 7. 测试与验收

### 7.1 单元测试 (tests/test_twitter_collector.py 更新)

- 配置解析: data/ 路径 + 10 账号 + 缺字段容错。
- **条数窗口 (D1 1A, 统一语义)**, 用例:
  - 24h 内 >30 条 → 全保留;
  - 24h 内 ≤30 条 + 24h 外补足 → 总 30 条 (24h 内全保留, 24h 外倒序补);
  - 总 <30 条 → 全部保留;
  - 边界: 恰好 30 条 / 恰好 24h 整点。
- **forward 解析 (D2 2C)**: retweet/quote fixture → "by @author: 原文";
  非转发 → None; 无外层文本 → text None + forward 有值。
- **风控 (RIG-2)**: 单账号挑战 → 部分成功; 连续 2 账号挑战 → 提前终止。
- schema: retention 字段断言 (RIG-1, window_hours 移除后同步)。
- 原有: DOM 解析/写盘/退出码 (window_hours 断言更新为 retention)。

### 7.2 前端测试 (tests/test_html.py 更新)

- header-search 元素 + doSearch 函数 + Cmd+F 拦截逻辑;
- forward 渲染 (表格/分栏) + esc 覆盖;
- **forward XSS 专项 (O-1)**: forward 值含 `<img src=x onerror=...>` →
  渲染为纯文本 (无 img 执行), 断言 esc/textContent 生效;
- 搜索高亮: 查询词含 `<script>` → 高亮输出为文本节点 (SEC-1 防回归)。

### 7.3 验收标准

1. data/twitter-targets.yaml 生效 (10 账号), 旧根路径文件移除。
2. --attach 实测: ≥3 个代表性账号 (sama/karpathy/deepseek_ai), forward 字段
   正确 (转推带 by @作者), 条数 ≥30 或 24h 内全保留。
3. 全站搜索: 输入过滤当前 tab + 跨 tab 计数跳转 + Cmd+F 聚焦拦截 +
   高亮为文本 (注入查询词不执行)。
4. X热点 表格/分栏 forward 格式渲染正确 (含 XSS 用例)。
5. cron 自动拉起链路不变 (D1A 回归)。
6. pytest 非 selenium 全绿。

## 8. 风险与回退

| 风险 | 影响 | 缓解 |
|:---|:---|:---|
| 10 账号风控触发 | 部分账号无数据 | 账号间 2s 间隔; 单账号挑战跳过; 连续 2 账号提前终止 |
| 30 条滚动深度不足 | 条数 <30 | 首屏+3 次滚动实测; 不足时提高滚动次数 (不并发) |
| 转发 DOM 结构变化 | forward 缺失 | 多级 fallback; forward=None 不崩溃 |
| 搜索性能 (大 JSON) | 输入卡顿 | 防抖 200ms; 过滤在内存数组 |
| Cmd+F 覆盖原生查找 | 用户习惯冲突 | 已确认接受 (D4); 搜索框有清空/Esc 恢复 |
| 搜索高亮注入 | XSS | 结构化 DOM 构建 / 双转义 (SEC-1) |

## 9. 实施顺序 (dev)

1. 配置迁移 data/ + CONFIG_PATH + 10 账号 + 测试适配。
2. 条数窗口 30/24h (统一语义) + forward 解析 + 风控部分成功 + 单测。
3. 前端: header-search + doSearch + Cmd+F + 高亮转义 + forward 渲染 + test_html 扩展。
4. crontab/AGENTS.md 文档同步。
5. ops 实测: 多账号采集 + 搜索/快捷键 + 前端渲染 + pytest。

---

> 设计评审入口: documents/reviews/ (CL-SEC20 闭环)。
