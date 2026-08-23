---
title: llm-radar CLI 治理与全局注册设计
topic: llm-radar
type: design
version: 1.0
date: 2026-08-23
author: hermes-1.2.0
tags: [llm-radar, cli, governance, cli-registry, checkpoint]
profile: ops
provider: deepseek
model: deepseek-v4-flash
---

# llm-radar CLI 治理与全局注册设计 v1.0

> 探讨确认(2026-08-23): 1A 协议闭环, 决策 6+1 项全部锁定。
> 上游(dev 实施)先行, 下游 daily-checkin 接入后续单独推进。

---

## 1. 背景与问题

llm-radar 数据收集器目前只能 `python3 llm-radar-collector.py <cmd>` 调用:

- 无全局注册: 需记住绝对路径/脚本名, 与 hm/pc/daily-checker 等治理 CLI 不一致。
- CLI 不合治理规范: help 平铺无分组, 空入参 exit=1, positional help 无拦截, 无 --json。
- 无状态输出: daily-checkin 面板无法监控数据更新状态(七字段 checkpoint 协议接入缺前置)。

目标: 建立 hm-style 分组指令体系 + cli-registry 全局注册(`llm-radar` 主名 + `lr` 别名),
新增 `lr status --json`(checkpoint 协议), 提供 `lr run --force` 一键修复。

## 2. 决策记录(已确认)

| # | 决策 | 内容 |
|:---|:---|:---|
| D1 | 全局注册名 | `llm-radar` 主名 + `lr` 别名(cli-registry 注册, alias_list) |
| D2 | status 阈值 | 新鲜 <7h=ok / 7-48h=warning / >48h=critical(采纳 STALE_HOURS=7) |
| D3 | 修复动作 | 方案 B: 仅 `lr run --force`, 不做完整 repair 封装 |
| D4 | 实施顺序 | 先上游(dev 实施), 下游 checkpoint 接入后续单独推进 |
| D5 | STALE_HOURS | 常量可配, 对齐 health probe(scripts/llm-radar-health.py 的 STALE_HOURS=7) |
| D6 | force 语义 | `lr run --force` 在 cron 6h 节流下必须绕过(force 已内建 _think) |
| D7 | .cli-registry.yaml | 需入 git(参考 script-miner 先例) |

## 3. CLI 指令体系(hm-style 分组)

### 3.1 分组结构

```
📖 LLM Radar (llm-radar / lr) 使用说明

【采集执行】
  lr run [source] [--force]     — fetch+merge+push 一步(6h 节流, --force 绕过)
  lr fetch [source]             — 抓取 7 源(Selenium→requests 降级)
  lr merge                      — 从缓存提取实体并合并
  lr sources                    — 列出新闻源
  lr reset-health               — 重置源连续失败计数
  lr selenium-check             — 检查 Chrome/Driver 环境

【数据管理】
  lr status [--json]            — 数据新鲜度+质量门禁状态(新增)

【Git 集成】
  lr commit [msg]               — git add+commit
  lr auto-push                  — git add+commit+push

【定时任务】
  lr crontab --add|--remove|--list|--update|--status
  lr crontab help               — 子指令帮助

【其他】
  lr help                       — 本帮助
  lr <cmd> help                 — 各子指令帮助(拦截约定)
```

### 3.2 治理符合点

- 空入参 → 打印分组 help exit=0(现状 exit=1)。
- positional help 拦截: 带参子命令(fetch/run/commit/crontab)入口检查 `args[0].upper()=='HELP'`
  → 打印该命令用法 exit=0, 禁止当参数执行(对齐 pc magnet help 事故教训)。
- help 打印 hm-style 分组(【】分类), 不含危险指令或标 ⚠️。
- 全局注册后 `llm-radar help` 与 `lr help` 输出一致。

## 4. `lr status --json`(checkpoint 协议)

### 4.1 输出格式(七字段)

```json
{
  "id": "llm-radar",
  "label": "LLM Radar 数据更新",
  "status": "ok",
  "icon": "🟢",
  "message": "数据新鲜 2026-08-20 10:02 (1.0h 前)",
  "checks": [
    {"label": "数据日期", "value": "2026-08-20 10:02", "status": "ok"},
    {"label": "实体数", "value": "288 (100/43/100/45/47)", "status": "info"},
    {"label": "质量门禁", "value": "success", "status": "ok"},
    {"label": "Git 同步", "value": "0 ahead / 0 behind", "status": "ok"}
  ],
  "actions": [
    {"id": "run", "label": "立即采集+推送", "type": "shell", "cmd": "lr run --force"},
    {"id": "push", "label": "同步推送", "type": "shell", "cmd": "lr auto-push"},
    {"id": "repair", "label": "修复数据更新", "type": "shell", "cmd": "lr run --force"}
  ]
}
```

### 4.2 评估规则(四态)

| status | 条件 |
|:---|:---|
| ok | last_run_at < 7h 且质量门禁 success |
| warning | 7h-48h 或 git 分叉(非 0/0)或质量门禁 failed |
| critical | > 48h 或 snapshot 缺失或连续失败 ≥3 |
| info | checks 附属信息项(实体数/数据日期) |

### 4.3 数据源(全部只读, 不触发采集副作用)

- timestamp.json: last_run_at / last_run_status / entity_count。
- metrics.json: source_health 连续失败计数。
- git rev-list: 分叉检测(0 ahead / 0 behind 之外 → warning)。
- snapshot.json: 各维度实体数。

### 4.4 STALE_HOURS 常量

```python
STALE_HOURS = int(os.environ.get('LLM_RADAR_STALE_HOURS', '7'))
```

- 对齐 scripts/llm-radar-health.py 的 STALE_HOURS=7 语义。
- 48h 阈值 = STALE_HOURS * 7 近似(或独立 CRITICAL_HOURS = 48, 实施时二选一, 默认独立常量)。

## 5. 全局注册(cli-registry)

### 5.1 .cli-registry.yaml(入 git)

```yaml
bin_dir: ~/.local/bin
cache_dir: cache/system-command
python: python3

env:
  conda: py3.12

commands:
  - name: llm-radar
    script: llm-radar-collector.py
    description: "LLM 行业情报采集/数据管理"
    alias_list: [lr]
```

### 5.2 注册步骤

1. 项目根建 .cli-registry.yaml(入 git)。
2. 用 cli-registry install.py 生成 wrapper → ln -sf ~/.local/bin/llm-radar 和 lr。
3. wrapper 需处理: 项目根定位(PROJECT_ROOT 以脚本位置推导, 已内建)、
   .env 加载(参考 llm-radar-run.sh 的 set -a 模式)。
4. 验证: `llm-radar help` / `lr help` 输出一致且非 --version 误判。

## 6. 边界与不做

- ❌ 不做完整 repair 封装(决策 D3, 仅 run --force)。
- ❌ 不修改 mcp-server.py 的 CLI(那是独立入口, 不在本次范围)。
- ❌ 不做下游 daily-checkin 接入(决策 D4, 后续单独推进)。
- ❌ 不改 snapshot 数据 schema(仅 CLI 层)。
- ⚠️ 实施时注意: 数据文件为 cron 并行写入, 测试须隔离(temp_snapshot 需连 project_root 一起隔离)。

## 7. 变更清单

| 文件 | 改动 |
|:---|:---|
| llm-radar-collector.py | 分组 help / 空入参 exit=0 / positional help 拦截 / status 命令 / STALE_HOURS 常量 |
| .cli-registry.yaml | 新增(入 git) |
| tests/test_status.py | 新增: status 评估逻辑单测(四态 + 边界) |
| tests/test_cli.py | 更新/新增: help 分组 + positional 拦截 + 空入参 |
| AGENTS.md | CLI 指令表补充 lr 用法 |

## 8. 验收标准

1. `llm-radar help` 与 `lr help` 分组输出一致。
2. `lr status --json` 七字段齐全, status 仅四态, icon 匹配, message 无 emoji。
3. `lr status --json` 无 snapshot → critical 不抛异常。
4. `lr run --force` 绕过 6h 节流(实测或单测 mock)。
5. 空入参 exit=0 打印分组 help。
6. `lr crontab help` 显示用法 exit=0, 不执行任何副作用。
7. .cli-registry.yaml 入 git。
8. pytest 非 selenium 全量回归绿。

---

*版本: 1.0 | 更新: 2026-08-23*
