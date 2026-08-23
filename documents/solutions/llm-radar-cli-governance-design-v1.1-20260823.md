---
title: llm-radar CLI 治理与全局注册设计
topic: llm-radar
type: design
version: 1.1
date: 2026-08-23
author: hermes-1.2.0
tags: [llm-radar, cli, governance, cli-registry, checkpoint]
profile: ops
provider: deepseek
model: deepseek-v4-flash
---

# llm-radar CLI 治理与全局注册设计 v1.1

> 探讨确认(2026-08-23): 1A 协议闭环, 决策 6+1 项全部锁定。
> 上游(dev 实施)先行, 下游 daily-checkin 接入后续单独推进。

## 修订记录

- v1.1 (2026-08-23) — 评审修正 6 🟡 + 3 🟢: REA-11 文件名修正; RIG-1 锁定 CRITICAL_HOURS;
  RIG-2 wrapper .env 加载路径; RIG-3 install.py 模板耦合处理; RIG-4 测试隔离方案;
  RIG-5 连续失败级别锁定; RIG-6/7/9 timestamp 路径/分叉语义/文本输出定义。
  (评审: documents/reviews/llm-radar-cli-governance-review-v1.0-20260823.md, 70/B CONDITIONAL)

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
| critical | > 48h 或 snapshot 缺失或全局 consecutive_fails ≥3(run 级, 非 source_health 任一源) |
| info | checks 附属信息项(实体数/数据日期) |

### 4.3 数据源(全部只读, 不触发采集副作用)

- timestamp.json(项目根, 非 data/): last_run_at / last_run_status / entity_count。
- metrics.json: 全局 `consecutive_fails` 字段(run 级, 对齐 _think 语义)。
  ⚠️ 不采用 source_health.<src>.consecutive_fails —— 单源 37 连败是常态(被 fetch_all 自动跳过),
  若按任一源判定 status 将永久 critical, 面板失去区分度。
- git rev-list: 分叉检测(0 ahead / 0 behind 之外 → warning)。
  ⚠️ 基于本地 origin/main ref, 不主动 git fetch("全部只读"约束); 本地 ref 过期时 ahead/behind 可能不准,
  但 status 本身不触发网络副作用, 可接受并记录该语义。
- snapshot.json: 各维度实体数。

### 4.4 阈值常量(锁定)

```python
STALE_HOURS = int(os.environ.get('LLM_RADAR_STALE_HOURS', '7'))     # warning 阈值
CRITICAL_HOURS = int(os.environ.get('LLM_RADAR_CRITICAL_HOURS', '48'))  # critical 阈值
```

- STALE_HOURS 对齐 scripts/llm-radar-health.py 的 STALE_HOURS=7 语义。
- CRITICAL_HOURS 为独立常量 = 48(不采用 STALE_HOURS*7=49 的近似, 避免 48-49h 区间状态闪变)。

### 4.5 无 --json 时输出(文本)

`lr status`(无 --json)输出单行人类可读摘要, 对齐 dt-status 先例:
`LLM Radar: 数据新鲜 2026-08-20 10:02 (1.0h 前) | 质量 success | 0 ahead/0 behind`
(格式实施时以可读为准, 不含 emoji 前缀; --json 才是 checkpoint 消费格式。)

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

⚠️ install.py 模板耦合(RIG-3): cli-registry 原 wrapper.sh.tmpl 硬编码
`mkdir -p ~/CodeSpace/script-miner/cache/cli-registry; echo ... >> calls.log`
(script-miner 专用调用统计)。llm-radar 复用会写脏 script-miner 目录。
处理: fork 模板到项目内 `cache/cli-registry/wrapper.sh.tmpl`, 移除 calls.log 统计段
(或改写到本项目 cache/cli-registry/calls.log), 用 install.py --template 指向 fork 模板。


1. 项目根建 .cli-registry.yaml(入 git)。
2. 用 cli-registry install.py 生成 wrapper → ln -sf ~/.local/bin/llm-radar 和 lr。
3. wrapper 需处理: 项目根定位(PROJECT_ROOT 以脚本位置推导, 已内建)、
   .env 加载。实现路径(RIG-2): fork 项目内模板 `cache/cli-registry/wrapper.sh.tmpl`,
   在 exec 前加 `set -a; [ -f "<PROJECT_ROOT>/.env" ] && source "<PROJECT_ROOT>/.env"; set +a`
   (与 llm-radar-run.sh 的 set -a 模式一致); 不用 cli-registry 原模板的 .env 逻辑
   (原模板无 .env, 非交互环境 `lr run` 会报 DEEPSEEK_API_KEY 未配置)。
4. 验证: `llm-radar help` / `lr help` 输出一致且非 --version 误判。

## 6. 边界与不做

- ❌ 不做完整 repair 封装(决策 D3, 仅 run --force)。
- ❌ 不修改 llm-radar-mcp-server.py 的 CLI(那是独立入口, 不在本次范围)。
- ❌ 不做下游 daily-checkin 接入(决策 D4, 后续单独推进)。
- ❌ 不改 snapshot 数据 schema(仅 CLI 层)。
- ⚠️ 实施时注意: 数据文件为 cron 并行写入, 测试必须隔离。已知污染源(08-15 事故):
  现有 temp_snapshot fixture 只隔离 snapshot_path/data_dir, project_root 不变,
  test_timestamp.py 直接读写真实 project_root/timestamp.json(5 处)。
  方案(RIG-4): status 测试新建 fixture 将 `collector.project_root` patch 到 tmp_path,
  并在 tmp 下预置 timestamp.json / data/metrics.json / data/snapshot.json 三文件,
  status 读取全部走 patch 后路径; 既有 test_timestamp 的 project_root 写入问题
  作为已知边界保留(不扩本方案范围), 但 status 测试绝不触碰真实项目根。

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
