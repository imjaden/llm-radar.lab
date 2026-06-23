# LLM Radar — 数据规范

> 用于指导 LLM 行业情报的采集、结构化、评分，输出 5 维度联动数据，驱动 llm-radar.lab.jaden.tech 前端渲染。

---

## 1. 目标

聚焦 LLM 行业热点，不求大而全。覆盖 5 个维度：

| 维度 | 关注点 |
|:---|:---|
| 工具 (Tools) | 推理框架、Agent 框架、RAG 工具、评测平台等 |
| 大模型 (LLMs) | 新模型发布、版本更新、Benchmark 表现、定价变化 |
| 厂商 (Providers) | 头部厂商动态、融资/并购、产品线布局 |
| 人物 (People) | 创始人/灵魂人物动向、跳槽、新项目 |
| 热点 (Hotspots) | 3-5 条近期最重要行业事件，含简报和关联实体 |

核心原则：
- 只收录近 30 天有实质动态的条目
- 每条必须有可追溯的信息来源（URL）
- 评分用于排序和行情感知，不做绝对排名

---

## 2. 输出格式

每次采集后输出 JSON，包含 5 个实体数组：

```json
{
  "providers": [{ "id", "name", "country", "hot_score", "last_event", ... }],
  "people": [{ "id", "name", "title", "influence_level", "hot_score", ... }],
  "tools": [{ "id", "name", "category", "hot_score", "last_update", ... }],
  "llms": [{ "id", "name", "provider_id", "tier", "hot_score", ... }],
  "hotspots": [{ "id", "title", "summary", "date", "url", "related_*", ... }],
  "changelog": [{ "type": "new|update", "dimension", "id", "summary", "date" }],
  "stats": { "total_*", "new_this_period", ... }
}
```

每条数据分为核心层（LLM 采集必填，轻量）和参考层（API 同步补充，如 models.dev 的定价、上下文窗口等）。热点维度包含关联实体 ID（related_providers、related_people、related_tools、related_llms），用于前端跨页签跳转。

---

## 3. 热度评分

采用 LLM 可直接执行的定性标准，不依赖外部量化 API：

| 等级 | 分值 | 判定条件 |
|:---|:---|:---|
| 🔥 爆热 | 80-100 | 多家媒体报道 + 社区大量讨论 + 官方重大公告 |
| 🟠 高热 | 60-79 | 本周 1-2 条重要新闻，社区有讨论 |
| 🟡 温热 | 40-59 | 近 2 周有动态但非焦点 |
| 🔵 平稳 | 20-39 | 近 1 个月有零星消息 |
| ⚪ 冷淡 | 0-19 | 无实质动态 |

人物维度额外按影响力分为：行业领袖、核心人物、活跃人物、新锐。

---

## 4. 数据留存

各维度数据保留最多 100 条。超出时：
1. 优先保留最近 15 天内有动态的条目
2. 若 15 天内数据仍超 100 条，按时间倒序保留最新 100 条
3. 过期数据自动归档至 archive/ 目录

---

## 5. 执行流程

```
Agent Loop: Think → Act → Verify → Observe

[Think]   间隔检查（<6h 跳过）、连续失败告警
[Act]     Selenium 无头浏览器抓取 7 源 → 提取 {title,url,date} + page_text
          → DeepSeek API（max_tokens=16000）提取实体 JSON
[Verify]  质量门禁：事件中位数新鲜度 < 7 天、热点 ≥ 3 条
[Act]     增量合并到 snapshot.json（去重、归档）
[Observe] 写 metrics.json（源健康、连续失败、运行历史）
[Act]     git commit + push（质量门禁未通过则跳过）
```

每次采集后自动生成 changelog（增量记录），前端从 snapshot.json 加载渲染。

---

## 6. 数据源

| 源 | 类型 | 抓取方式 | 用途 |
|:---|:---|:---|:---|
| 量子位 | 中文 AI 媒体 | Selenium 无头 | 国内大模型动态 |
| 机器之心 | 中文 AI 媒体 | Selenium 无头（懒加载滚动） | AI 研究与产业 |
| InfoQ | 中文技术媒体 | Selenium 无头（懒加载滚动） | AI 工程化实践 |
| 36氪 | 中文科技媒体 | Selenium 无头 | AI 融资与商业 |
| TechCrunch | 英文 AI 媒体 | Selenium 无头 | 国际大模型动态 |
| GitHub Trending | 开发者 | Selenium 无头 | 热门 AI 工具 |
| HuggingFace Papers | 研究 | Selenium 无头（懒加载滚动） | 最新论文 |

失败自动降级到 requests+BeautifulSoup（Selenium 不可用时备用）。

---

## 7. 环境要求

- Python ≥ 3.9
- 依赖：`pip3 install openai selenium webdriver-manager requests beautifulsoup4 prettytable`
- 需要 `DEEPSEEK_API_KEY` 环境变量或 `.env` 文件
- Chrome 浏览器（Selenium 无头模式驱动）
- Linux/macOS 系统（crontab 管理功能依赖）

---

*规范版本: 2.1 | 更新: 2026-06-23*
*基于 llm-radar-collector.py v1.0 实现*
