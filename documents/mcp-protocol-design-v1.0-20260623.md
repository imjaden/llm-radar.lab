# LLM-Radar MCP 协议设计

> 通过 MCP (Model Context Protocol) 协议，为 Hermes Agent 提供向 LLM-Radar 写入情报数据的标准接口。
> 与 Agent Loop 采集并行，MCP 是外部数据接入通道，Agent Loop 是内部采集引擎。

---

## 1. 架构

```text
Hermes Agent (LLM News SKILL)
        │
        │  JSON-RPC 2.0 over stdio
        │
        ▼
┌───────────────────────────────────────┐
│  MCP Server (llm-radar-mcp-server.py) │
│                                       │
│  1. Auth (API Key)                    │
│  2. Data quality check                │
│  3. Merge to snapshot.json            │
└───────────────────────────────────────┘
        │
        ▼
data/snapshot.json  ← shared with Agent Loop
```

---

## 2. 传输与协议

- **传输方式**：Stdio（Hermes 启动子进程，通过 stdin/stdout 通信）
- **协议版本**：MCP 2025-03-26
- **消息格式**：JSON-RPC 2.0，每行一条 JSON（`\n` 分隔）

---

## 3. 工具（Tools）

### 3.1 `submit_entities`

MCP 工具名：`mcp_llm_radar_submit_entities`

向 LLM-Radar 提交 5 维度情报数据。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|:---|:---|:---:|:---|
| `api_key` | string | ✅ | 鉴权密钥 |
| `providers` | array | ❌ | 厂商实体列表 |
| `people` | array | ❌ | 人物实体列表 |
| `tools` | array | ❌ | 工具实体列表 |
| `llms` | array | ❌ | 大模型实体列表 |
| `hotspots` | array | ❌ | 热点事件列表 |

每个维度实体字段与 `snapshot.json` 规范一致（见 llm-radar-prompt.md）。

**数据质量检验（拒绝条件，任一满足即拒绝）：**

| 检查项 | 条件 | 说明 |
|:---|:---|:---|
| 必填字段缺失 | `name` 为空 | 所有类型实体必须有 name |
| 置信度过低 | `confidence == "low"` | LLM 自身不确定的数据不写入 |
| 日期不合理 | `date/last_event_date` > 当前日期 + 1 天 | 未来日期拒绝 |
| 无实质动态 | 所有数组均为空 | 拒绝空提交 |
| 热点无日期 | `hotspots[].date` 缺失 | 热点必须带日期 |

**返回：**

```json
{
  "status": "accepted|rejected|partial",
  "accepted": { "providers": 3, "people": 0, "tools": 1, "llms": 2, "hotspots": 5 },
  "rejected": { "providers": 1, "people": 0, "tools": 0, "llms": 0, "hotspots": 0 },
  "rejected_reasons": [{ "id": "xxx", "reason": "confidence is low" }],
  "merge_result": { "new": 3, "updated": 5 },
  "snapshot_totals": { "providers": 72, "people": 54, "tools": 78, "llms": 77, "hotspots": 100 }
}
```

### 3.2 `health_check`

MCP 工具名：`mcp_llm_radar_health_check`

返回服务器状态。

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|:---|:---|:---:|:---|
| `api_key` | string | ✅ | 鉴权密钥 |

**返回：**

```json
{
  "status": "ok",
  "version": "1.0",
  "snapshot": "data/snapshot.json",
  "total_entities": 381,
  "last_updated": "2026-06-23T13:12:34"
}
```

---

## 4. 鉴权

- 默认 API Key：`llm-radar-mcp-2026`
- 通过 `LLM_RADAR_MCP_KEY` 环境变量自定义
- Hermes Agent 配置时通过 `env` 传入：

```yaml
# ~/.hermes/config.yaml
mcp_servers:
  llm-radar:
    command: "python3"
    args: ["/path/to/llm-radar.jaden.tech/llm-radar-mcp-server.py"]
    env:
      LLM_RADAR_MCP_KEY: "llm-radar-mcp-2026"
```

---

## 5. Hermes Agent 配置

### 5.1 添加 MCP Server

```yaml
# ~/.hermes/config.yaml
mcp_servers:
  llm-radar:
    command: "python3"
    args: ["/Users/jadenli/CodeSpace/llm-radar.jaden.tech/llm-radar-mcp-server.py"]
    env:
      LLM_RADAR_MCP_KEY: "llm-radar-mcp-2026"
```

### 5.2 交互示例

用户在 Hermes Agent 中说：

> "帮我查一下最近 LLM 资讯，把 DeepSeek 的最新动态提交到 LLM-Radar"

LLM 资讯 SKILL 会：
1. 抓取 LLM 相关资讯
2. 整理为 5 维度 JSON 数据
3. 调用 `mcp_llm_radar_submit_entities` 提交
4. 向用户返回提交结果

---

## 6. 数据流全景

```text
┌──────────────────────────────────────────────────────────────┐
│                    Data Entry                                │
│                                                              │
│   Agent Loop (scheduled)      MCP (external write)           │
│   crontab 9:00/21:00          Hermes Agent SKILL             │
│        │                            │                        │
│        ▼                            ▼                        │
│   fetch_all()                submit_entities()               │
│        │                            │                        │
│        ▼                            ▼                        │
│   extract_entities()         Quality check                   │
│   (DeepSeek API)              (confidence/date/required)     │
│        │                            │                        │
│        ▼                            ▼                        │
│   _verify()                   Quality gate → reject low      │
│        │                            │                        │
│        └───────────┬────────────────┘                        │
│                    ▼                                         │
│             merge_entities()                                 │
│             (dedup / merge / archive)                        │
│                    │                                         │
│                    ▼                                         │
│             snapshot.json                                    │
│                    │                                         │
│                    ▼                                         │
│             index.html / changelog.html                      │
└──────────────────────────────────────────────────────────────┘
```

---

## 7. 实现文件

| 文件 | 说明 |
|:---|:---|
| `llm-radar-mcp-server.py` | MCP Server 实现（JSON-RPC 2.0 over stdio） |
| `scripts/mcp-protocol-demo.py` | 手工验证脚本（模拟 Hermes Agent 调用 MCP Server） |

---

## 8. 安全边界

- API Key 不写死在代码中，通过环境变量 `LLM_RADAR_MCP_KEY` 注入
- 质量检验拒绝低置信度和不完整数据，防止污染 snapshot
- MCP Server 只监听 stdio（本地子进程），不开放网络端口，无外部攻击面
- Hermes Agent 的 env 过滤机制自动屏蔽非白名单环境变量

---

*版本: 1.0 | 更新: 2026-06-23*
