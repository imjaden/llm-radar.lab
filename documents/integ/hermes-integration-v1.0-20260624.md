# LLM-Radar Hermes 集成方案

> 通过 Hermes Agent 的 MCP (Model Context Protocol) 能力，为 LLM-Radar 接入第二条数据管道。
> 与 Agent Loop 定时采集并行，Hermes MCP 提供按需的、对话驱动的数据写入能力。

---

## 1. 架构总览

```text
┌─────────────────────────────────────────────────────────────────────┐
│                    LLM-Radar Dual Pipeline                          │
│                                                                     │
│  ┌─────────────────────────┐    ┌─────────────────────────────────┐ │
│  │  Pipeline A: Agent Loop │    │  Pipeline B: Hermes (MCP)       │ │
│  │  (scheduled collector)  │    │  (on-demand write)              │ │
│  │                         │    │                                 │ │
│  │  crontab 9:00/21:00     │    │  last30days skill               │ │
│  │       → fetch 7 sources │    │  blogwatcher RSS                │ │
│  │       → DeepSeek extract│    │  tavily-search                  │ │
│  │       → _verify quality │    │       │                         │ │
│  │       → merge snapshot  │    │       ▼                         │ │
│  │       → auto-push       │    │  Middle layer (5-dim JSON)      │ │
│  └─────────────────────────┘    │       │                         │ │
│                                 │       ▼                         │ │
│                                 │  MCP Server (llm-radar-mcp-     │ │
│                                 │  server.py)                     │ │
│                                 │  → auth → quality gate → merge  │ │
│                                 └─────────────────────────────────┘ │
│                                           │                         │
│                                           ▼                         │
│                               ┌────────────────────────┐            │
│                               │  data/snapshot.json    │            │
│                               │  (shared storage)      │            │
│                               └────────────────────────┘            │
│                                           │                         │
│                                           ▼                         │
│                               index.html / changelog.html           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. 可用 Skills 清单

### 2.1 `last30days`（推荐主通道）

| 属性 | 值 |
|:---|:---|
| 名称 | `last30days` |
| 版本 | 3.3.2 |
| 数据源 | Reddit, X/Twitter, YouTube, TikTok, Hacker News, Polymarket, GitHub, Web |
| 触发方式 | 对话中直接调用 `last30days <topic>` |
| 输出 | 结构化帖子列表（标题、摘要、链接、互动数、时间） |
| 安装 | 已内置（openclaw 市场） |
| API Key | `SCRAPECREATORS_API_KEY`（可选，无 key 也可用部分源） |
| 主页 | https://github.com/mvanhorn/last30days-skill |

**使用示例：**
```
用户: last30days LLM industry news this week
Agent: 返回 8 源聚合的 LLM 热点帖子列表
```

### 2.2 `blogwatcher`（RSS 持续监控）

| 属性 | 值 |
|:---|:---|
| 名称 | `blogwatcher` |
| 数据源 | RSS/Atom feeds（可自定） |
| 触发方式 | `blogwatcher-cli scan` → `blogwatcher-cli articles` |
| 安装 | `go install github.com/JulienTant/blogwatcher-cli/cmd/blogwatcher-cli@latest` |
| API Key | 无需 |
| 主页 | https://github.com/JulienTant/blogwatcher-cli |

**推荐订阅源（blogwatcher 支持 RSS 自动发现，直接添加首页即可）：**

```bash
blogwatcher-cli add "量子位" https://www.qbitai.com
blogwatcher-cli add "机器之心" https://www.jiqizhixin.com
blogwatcher-cli add "InfoQ AI" https://www.infoq.cn/topic/AI
blogwatcher-cli add "TechCrunch AI" https://techcrunch.com/category/artificial-intelligence/
blogwatcher-cli add "GitHub Trending" https://github.com/trending
blogwatcher-cli add "HuggingFace Papers" https://huggingface.co/papers
```

### 2.3 `tavily-search`（轻量搜索）

| 属性 | 值 |
|:---|:---|
| 名称 | `tavily-search` |
| 数据源 | Web 搜索（LLM 优化） |
| 触发方式 | 对话中 `tavily-search <query>` |
| API Key | `TAVILY_API_KEY` |
| 特点 | 响应快、结果精炼、自带摘要 |

---

## 3. 中间层：Skills → MCP 数据转换逻辑

Hermes Agent 在对话中执行以下步骤将 SKILL 输出转为 MCP 写入：

### 3.1 标准处理流程

```
Step 1: 用户触发
  "帮我看看最近 LLM 圈有什么大事，记到仪表盘上"

Step 2: Hermes Agent 调用 SKILL 获取原始数据
  last30days LLM industry
  → 返回帖子列表 [{title, url, date, summary, source, engagement}]

Step 3: Agent 整理为 5 维度 JSON
  从帖子列表中提取:
  - providers: 厂商名称、事件、热度
  - people: 人物动向、跳槽、发言
  - tools: 新工具发布、版本更新
  - llms: 新模型、Benchmark、定价
  - hotspots: 3-5 条最重要事件（含摘要、日期、关联实体）
  * 实体字段规范见 `llm-radar-prompt.md` §2

Step 4: 调用 MCP 写入
  mcp_llm_radar_submit_entities(
    api_key="llm-radar-mcp-2026",
    providers=[...],
    people=[...],
    tools=[...],
    llms=[...],
    hotspots=[...]
  )

Step 5: 向用户报告结果
  "已提交 2 条厂商、1 个人物、3 条热点到 LLM-Radar 仪表盘"
```

### 3.2 JSON 格式规范（与 Agent Loop 输出一致）

```json
{
  "api_key": "llm-radar-mcp-2026",
  "providers": [
    {
      "id": "anthropic",
      "name": "Anthropic",
      "country": "美国",
      "hot_score": 90,
      "hot_level": "爆热",
      "last_event": "事件描述",
      "last_event_date": "2026-06-23",
      "last_event_url": "https://...",
      "confidence": "high"
    }
  ],
  "people": [
    {
      "id": "dario-amodei",
      "name": "Dario Amodei",
      "title": "CEO",
      "employer_id": "anthropic",
      "influence_level": "行业领袖",
      "hot_score": 85,
      "recent_activity": "动态描述",
      "recent_activity_date": "2026-06-23",
      "confidence": "high"
    }
  ],
  "tools": [
    {
      "id": "cursor",
      "name": "Cursor",
      "category": "AI 编程工具",
      "hot_score": 95,
      "last_update": "被 SpaceX 收购",
      "last_update_date": "2026-06-23",
      "confidence": "high"
    }
  ],
  "llms": [
    {
      "id": "claude-fable-5",
      "name": "Claude Fable 5",
      "provider_id": "anthropic",
      "type": "文本",
      "tier": "旗舰",
      "hot_score": 95,
      "last_event": "发布三天遭下架",
      "last_event_date": "2026-06-23",
      "confidence": "high"
    }
  ],
  "hotspots": [
    {
      "id": "anthropic-fable5-ban",
      "title": "Anthropic 发布 Claude Fable 5 三天后遭美国政府临时下架",
      "summary": "特朗普政府对 Anthropic 最新模型采取行动",
      "date": "2026-06-23",
      "source": "综合",
      "url": "https://techcrunch.com/2026/06/21/...",
      "related_providers": ["anthropic"],
      "related_people": ["dario-amodei"],
      "related_llms": ["claude-fable-5"],
      "confidence": "high"
    }
  ]
}
```

### 3.3 质量要求

| 字段 | 要求 |
|:---|:---|
| `id` | 英文小写+连字符格式 |
| `confidence` | 无法确认的信息标记 `low`（会被 MCP Server 拒绝） |
| 日期 | `YYYY-MM-DD` 格式，不可在未来 |
| 热点 | 必须包含 `date`、`title`、`summary` |
| URL | 完整链接，不确定则留空字符串 |

---

## 4. Hermes 配置

### 4.1 注册 MCP Server

在 `~/.hermes/config.yaml` 中添加：

```yaml
mcp_servers:
  llm-radar:
    command: "python3"
    args: ["/Users/jadenli/CodeSpace/llm-radar.jaden.tech/llm-radar-mcp-server.py"]
    env:
      LLM_RADAR_MCP_KEY: "llm-radar-mcp-2026"
```

配置说明：
| 参数 | 值 | 说明 |
|:---|:---|:---|
| `command` | `python3` | 运行 MCP Server 的解释器 |
| `args` | 脚本路径 | 指向 `llm-radar-mcp-server.py` |
| `env.LLM_RADAR_MCP_KEY` | API Key | 与 MCP Server 鉴权一致 |
| 默认 Tool 命名 | `mcp_llm_radar_submit_entities` | Hermes 自动加 `mcp_{server}_{tool}` 前缀 |

### 4.2 验证配置

重启 Hermes Agent，观察启动日志：

```text
[MCP] Connecting to server 'llm-radar'...
[MCP] Server 'llm-radar' initialized: llm-radar-mcp v1.0
[MCP] Registered tools from llm-radar: [submit_entities, health_check]
```

在对话中测试：

```
用户: 调用 mcp_llm_radar_health_check 检查一下 LLM-Radar 状态
Agent: ✅ 状态正常，当前 390 条实体
```

---

## 5. 实施清单

### ✅ 已完成

- [x] `llm-radar-mcp-server.py` — MCP Server（JSON-RPC 2.0 over stdio）
- [x] 质量检验（5 项拒绝规则：必填字段、置信度、日期、空提交、鉴权）
- [x] `scripts/mcp-protocol-demo.py` — 测试脚本（5 TC 全部通过）
- [x] `documents/mcp-protocol-design-v1.0-20260623.md` — MCP 协议设计文档

### 📋 需手动操作

- [ ] 安装 `blogwatcher-cli`：`go install github.com/JulienTant/blogwatcher-cli/cmd/blogwatcher-cli@latest`
- [ ] 配置 `SCRAPECREATORS_API_KEY` 或 `TAVILY_API_KEY`（如需使用 last30days/tavily 完整功能）
- [ ] 编辑 `~/.hermes/config.yaml` 添加 MCP Server 配置
- [ ] 重启 Hermes Agent 使配置生效
- [ ] 首次测试：对话中调 `mcp_llm_radar_health_check`
- [ ] 完整测试：调 `last30days LLM news` → 整理 JSON → 调 `mcp_llm_radar_submit_entities`
- [ ] （可选）配置 blogwatcher RSS 订阅实现定时抓取

---

## 6. 数据管道对比

| 维度 | Agent Loop (Pipeline A) | Hermes MCP (Pipeline B) |
|:---|:---|:---|
| **触发方式** | crontab 定时 (9:00/21:00) | 对话驱动、按需触发 |
| **数据来源** | 7 个新闻源（量子位/机器之心等） | last30days / blogwatcher / tavily |
| **提取方式** | DeepSeek API 结构化提取 | Hermes Agent 自主整理 |
| **覆盖范围** | LLM 行业固定源 | 任意话题、任意源 |
| **质量门禁** | `_verify()` 新鲜度 + 热点数量 | MCP Server 5 项拒绝规则 |
| **延迟** | 定时（最长 12h 更新一次） | 实时（对话完成即写入） |
| **失败处理** | Selenium 降级 + 重试 | MCP error 返回给 Agent |
| **鉴权** | 无（本地脚本） | API Key 验证 |

两条管道共享同一份 `snapshot.json`，前端无感知。

---

## 7. 参考

| 文件 | 说明 |
|:---|:---|
| `llm-radar-mcp-server.py` | MCP Server 实现 |
| `scripts/mcp-protocol-demo.py` | MCP 协议测试脚本 |
| `documents/mcp-protocol-design-v1.0-20260623.md` | MCP 协议设计 |
| `documents/search-tips-v1.0-20260622.md` | 搜索技巧参考（用于构造查询） |
| `llm-radar-prompt.md` | 5 维度数据规范 |

---

*版本: 1.0 | 更新: 2026-06-24*
