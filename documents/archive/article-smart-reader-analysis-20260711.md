# article-smart-reader 功能分析报告

> 分析日期：2026-07-11
> 对比对象：article-smart-reader（Hermes Skill） vs steipete-summarize（Node CLI + Chrome Ext）

---

## 一、功能对比：article-smart-reader vs steipete-summarize

| 维度 | article-smart-reader（Hermes Skill） | steipete-summarize（Node CLI + 浏览器扩展） |
|:---|:---|:---|
| **定位** | 中文文章深度智读 + 知识管理 | 多格式内容快速摘要（英/中） |
| **输入** | 在线文章 URL | URL / YouTube / 本地文件 / 音视频 / PDF / RSS |
| **核心流程** | 抓取→Markdown→智读分析报告（step1+step2） | 获取→交由 AI 模型摘要输出 |
| **输出** | 结构化中文智读报告（观点/坑点/话术/行动建议/关键词/关联推荐） | Markdown 摘要 / JSON 诊断 / 纯文本 |
| **存储** | `~/Documents/10-DataDrived/web2md/` 按文章独立目录 + `web2md_index.json` 索引 | 无持久化存储（流式输出） |
| **管理功能** | `web2md list/search/info/edit/remove`、文章库查询、断点续传 | 无 |
| **媒体支持** | 纯文章（web 页面） | 视频/音频/PDF/RSS/网页，自动检测类型 |
| **AI 后端** | LLM（配置化多模型优先级切换） | Claude / Codex / Gemini / Ollama 等自由切换 |
| **快速模式** | `web_extract` 替代 Selenium，规避长流程依赖 | npx 零安装即用 |
| **Chrome 扩展** | 无 | Chrome Side Panel + Firefox Sidebar |
| **批量能力** | 有（progress.json 断点续传，分类+标签机制） | 单次输入 |
| **语言** | 中文为主（分析框架、输出模板） | 英文为主 |
| **项目路径** | Hermes skill（SKILL.md + references） | `~/CodeSpace/steipete-summarize/`（Node 项目，⭐6.4k） |

### 核心差异

- **article-smart-reader** = 文章深度消化 + 知识管理（侧重读透、存档、关联检索）
- **steipete-summarize** = 快速内容摘要工具（侧重快、广、多格式、即时获取）

---

## 二、英文词汇学习功能完善方案

**目标：** 在智读过程中自动提取英文生词，打标签、归档、复习提醒。

### A. 智读管线加一层「词汇提取」

在现有的 `step2-analyze`（智读分析报告）之后插入 `step3-vocab`：

```
step1 抓取原文 → step2 智读分析 → step3 词汇提取
                                    ↓
                            产出词汇清单
```

词汇提取逻辑：
- 从 step1（原文 Markdown）中扫描非中文段落
- 识别低频/技术性英文词汇（用词频表过滤掉基础词）
- 输出格式：

```json
{
  "word": "conformance suite",
  "context": "A language-independent test suite with a million assertions...",
  "translation": "一致性测试套件",
  "frequency": "high" | "medium" | "low",
  "category": "AI/测试" | "编程" | "通用",
  "article_id": "260518-7640711227311768100"
}
```

### B. 词汇存储：独立词汇索引

新增 `web2md_vocab_index.json`：

```json
{
  "words": {
    "conformance suite": {
      "translations": ["一致性测试套件"],
      "articles": [
        {"article_id": "xxx", "title": "Bun Rust Rewrite", "date": "2026-07-08"}
      ],
      "category": "AI/测试",
      "last_seen": "2026-07-08"
    }
  },
  "stats": {
    "total_words": 120,
    "by_category": {"AI/测试": 45, "编程": 50, "通用": 25}
  }
}
```

### C. 新增命令

| 命令 | 功能 |
|:---|:---|
| `web2md vocab <article_id>` | 提取指定文章的生词 |
| `web2md vocab-list [category]` | 列出所有生词/按分类筛选 |
| `web2md vocab-review` | 输出今日复习清单（按 last_seen 排序） |
| `web2md vocab-export [format]` | 导出为 Anki CSV / Quizlet 格式 |

### D. 复习提醒

在智读报告末尾追加复习板块：

```markdown
### 📖 本文生词（N 个）
| 单词 | 翻译 | 行业频率 | 分类 |
|:---|:---|:---:|:---|
| conformance suite | 一致性测试套件 | 🔥 高频 | AI/测试 |
```

---

## 三、关联分析最新 LLM 主题资讯的完善方案

**目标：** 让 article-smart-reader 能自动识别文章是否涉及 LLM 行业话题，并与已有的 `news-summary/` 和 `llm-radar` 数据联动。

### A. 文章 Topic 分类

在智读分析报告（step2）头部增加 topic 字段：

```yaml
topics: ["LLM", "Agent", "Rust vs Zig"]
related_entities: [
  {"type": "provider", "name": "Anthropic"},
  {"type": "tool", "name": "Bun"},
  {"type": "person", "name": "Andrew Kelley"}
]
```

判断逻辑：
- 从文章内容提取关键词 → 匹配预定义 LLM 主题分类表
- 匹配命中 → 标记为 `topic: LLM-关联`
- 不命中 → 不标记，行为不变

### B. 关联查询：跨库搜索

新增命令 `web2md relate <keyword>`：

1. 搜索 `web2md_index.json` 看是否有已分析的文章匹配
2. 搜索 `llm-radar/data/snapshot.json` 的 providers/people/tools/hotspots
3. 搜索 `news-summary/*.md` 文件看是否有专题分析
4. 输出关联矩阵

### C. 联动数据源配置文件

新增 `~/.article-smart-reader/llm-context.json`：

```json
{
  "news_summary_dir": "~/Documents/JadenVault/news-summary/",
  "llm_radar_snapshot": "~/CodeSpace/llm-radar.jaden.tech/data/snapshot.json",
  "topic_classifier": {
    "large_model": ["大语言模型", "LLM", "GPT", "Claude", "Gemini", "Qwen"],
    "ai_agent": ["Agent", "AutoGPT", "OpenClaw", "Hermes", "MCP"],
    "ai_chip": ["芯片", "GPU", "Blackwell", "推理芯片"],
    "funding": ["融资", "收购", "IPO", "估值"],
    "programming": ["Zig", "Rust", "编译器", "重写"]
  }
}
```

---

## 四、头脑风暴：推荐行业资讯分析功能

按 ROI 排序：

### 🔥 P0 — 核心体验提升

**4.1 多来源交叉验证报告**
- 输入一个 URL 后，自动搜索 HN / X / Reddit / 36kr / InfoQ 的同主题文章
- 输出交叉验证报告：相同观点、冲突观点、独家信息
- 复用 `web-research-synthesis` skill 的工作流

**4.2 时效性标尺**
- 在智读报告头部加一行新鲜度指示：

```
📅 原文日期: 2026-07-08 (3 天前)
🔄 相关后续: Anthropic 回应 (07-09) | Andrew 反驳 (07-10)
⚠️ 此主题已有 2 篇后续，建议一并阅读
```

**4.3 一键生成 HTML 报告**
- 智读完成后自动调用 `research-doc-publish` skill → 暗色主题 HTML
- 不需用户手动触发

### 🔵 P1 — 知识沉淀

**4.4 观点演进追踪**
- 同一话题的多篇文章，追踪观点变化（如 Bun Zig→Rust 事件的三方视角）
- 输出观点时间线：

```
06-23 Jarred: 宣布 Rust 分支实验
07-08 Jarred: 发布「Bun in Rust」博客
07-10 Andrew: 「My Thoughts on the Bun Rust Rewrite」反驳
```

**4.5 技术雷达自动生成**
- 每月自动聚合 `news-summary/` 下的所有分析，生成月度技术雷达
- 包含：趋势、冲突、预测兑现情况

### 🟢 P2 — 效率工具

**4.6 Slack 级摘要**
- `web2md tl;dr <URL>` — 输出 3 句话极简摘要（300 字以内）
- 区别于完整智读报告（step2 的深度分析）

**4.7 阅读优先级队列**
- `web2md priority` — 对文章库按热度/时间/来源加权排序
- 输出今日推荐阅读 Top 5

**4.8 文章退化检测**
- 扫描已分析文章原文链接，检测是否已失效（404/被删）
- 输出失联文章清单

### ⚪ P3 — 中长期

**4.9 代码提取**
- 自动提取文章中的代码片段，按语言分类，存入代码片段库
- `web2md code <article_id> [--lang python]`

**4.10 简报订阅**
- 周期性扫描 `llm-radar` 的热点，自动触发智读分析
- 结合 cron job → 每日推送「今日 AI 行业简报」

---

### 推荐优先实施

| 优先级 | 功能 | 预计工作量 |
|:---:|:---|:---:|
| P0 | 4.1 交叉验证 + 4.2 时效性标尺 | 低（复用现有 skill） |
| P1 | 4.4 观点演进 + 英文词汇提取 | 中（新增 step3+索引） |
| P2 | 4.6 tl;dr 摘要 + 4.7 阅读优先级 | 低（新增命令） |
| P3 | 4.8 文章退化 + 4.10 简报订阅 | 中（cron + 失效检测） |

---

*分析由 IRIS (byHermes) 自动生成*
