# Agent Loop 设计 v1.0 — llm-radar

> 跨 Profile 开发协作工作流：需求 → 开发 → 评审，全自动编排。
> 基于文件 + cron 接力，零外部依赖。

---

## 1. 总览

### 1.1 解决的问题

| 痛点 | 现状 | 目标 |
|---|---|---|
| profile 隔离 | dev/review/research 各开一个 TUI 窗口，手动传递信息 | 自动化编排，无需人工切窗口 |
| 评审遗漏 | 代码改完人工叫 reviewer | cron 自动检测状态，通知 reviewer |
| 失败追踪 | non-existent | 3 次失败自动升级人工 |
| 进度不可视 | 只有聊天记录 | 任务状态机 + Markdown 报告 |

### 1.2 核心文件

| 文件 | 位置 | 用途 |
|---|---|---|
| **`requirements.md`** | 项目根目录 | 需求文档（[requirements-spec](documents/requirements-spec.md) 格式） |
| **`tasks/active-task`** | 项目根目录 | symlink → 当前活跃的 task 目录 |
| **`tasks/<task-dir>/task-manifest.yaml`** | `tasks/` 下 | 任务状态机（YAML） |
| **`tasks/<task-dir>/demand.md`** | `tasks/` 下 | 需求副本，锁定范围 |
| **`tasks/<task-dir>/features.md`** | `tasks/` 下 | developer 交付清单 |
| **`tasks/<task-dir>/audit-log.md`** | `tasks/` 下 | reviewer 评审报告（含失败明细） |
| **`audit-log.md`** | 项目根目录 | 聚合评审日志 |

### 1.3 三个角色

| 角色 | Profile | Session | 职责 |
|---|---|---|---|
| **Requirement (requirement)** | research | news-radar | 编写/完善 **`requirements.md`** |
| **Developer (developer)** | dev | news-radar | 读 **`requirements.md`** → 实现 → 测试 → git commit → 写 **`features.md`** |
| **Reviewer (reviewer)** | review | news-radar-review | 读 **`demand.md`** + **`features.md`** → 评审 → 写 **`audit-log.md`** |

### 1.4 三个 cron job

| Job | Profile | 类型 | 职责 |
|---|---|---|---|
| **scanner** | ops | `no_agent=True` 纯脚本 | 状态判断 + 文件操作 + git push（通过后） |
| **developer-executor** | dev | agent mode + script context | 理解需求 → 写代码 → commit → 写 `features.md` |
| **reviewer-executor** | review | agent mode | 评审代码 → 写 `audit-log.md` |

---

## 2. task-manifest.yaml 状态机（核心设计）

### 2.1 Schema

```yaml
# tasks/<task-dir>/task-manifest.yaml
task_id: "al-20260711-001"         # 任务唯一 ID（日期-序号）
title: "第 1 轮需求"               # 对应 requirements.md 标题
author: "jaden"                    # 发起人
created_at: "2026-07-11T10:00:00+08:00"
closed_at: null                    # 完成后写入

state: created                     # 状态机：见 2.2
retry_count: 0                     # 评审不通过次数（仅 review step 增加）
max_retries: 3                     # 最大允许重试次数
escalated: false                   # 是否升级人工

source: "requirements.md"          # 本任务对应的需求文件
source_hash: "sha256:..."          # requirements.md 内容哈希（检测变更）

history:
  - step: created
    profile: research
    date: "2026-07-11T10:00:00+08:00"
    summary: "任务已创建，需求待编写"
  - step: demand
    profile: research
    date: null
    summary: null
  - step: assign
    profile: ops
    date: null
    summary: null
  - step: implement
    profile: dev
    date: null
    summary: null
  - step: review
    profile: review
    date: null
    summary: null
  - step: close
    profile: ops
    date: null
    summary: null
```

### 2.2 状态机

```
                  ┌──────────────────────┐
                  │      created         │  需求编写中（人工编辑 requirements.md）
                  └──────────┬───────────┘
                             │ 人工确认
                             ▼
                  ┌──────────────────────┐
                  │      demand          │  需求已锁定，可开始执行
                  └──────────┬───────────┘
                             │ scanner
                             ▼
                  ┌──────────────────────┐
                  │      assigned        │  已分配至 dev
                  └──────────┬───────────┘
                             │ dev-executor
                             ▼
                  ┌──────────────────────┐
                  │    in_progress       │  开发中
                  └──────────┬───────────┘
                             │ 实现完成，写 features.md
                             ▼
                  ┌──────────────────────┐
                  │      review          │  等待评审
                  └──────────┬───────────┘
                       ┌─────┴─────┐
                       ▼           ▼
               ┌───────────┐ ┌───────────┐
               │  passed   │ │  failed   │  retry_count +1
               └─────┬─────┘ └─────┬─────┘
                     │       ┌─────┴─────┐
                     │       │  < 3 次   │  → state = assigned
                     │       │  >= 3 次  │  → escalated
                     ▼       └───────────┘
               ┌───────────┐
               │  closed   │  → scanner git push
               └───────────┘
```

### 2.3 状态流转约束

| 当前状态 | 允许的下一状态 | 谁来触发 |
|---|---|---|
| `created` | `demand` | 人工 |
| `demand` | `assigned` | scanner |
| `assigned` | `in_progress` | dev-executor |
| `in_progress` | `review` | dev-executor |
| `review` | `passed` / `failed` | reviewer-executor |
| `failed` | `assigned` / `escalated` | scanner |
| `passed` | `closed` | scanner |
| `escalated` | `assigned` / `demand` | **人工** |

---

## 3. 工作流流程

### 阶段 0：需求编写（人工 / research profile）

```
入口: 人工创建或修改 requirements.md（requirements-spec 格式）
产出: requirements.md + task-manifest.state == created
触发: 人工运行 tasks/al-init.py
```

```bash
cd ~/CodeSpace/llm-radar.jaden.tech
python3 tasks/al-init.py "第 1 轮需求：新增 RSS 数据源"
```

**需求编写完成后**：state → demand，表示可开始执行。

### 阶段 1：scanner（ops, no_agent, 每 5 分钟）

Scanner 脚本 `tasks/al-scanner.py` 逻辑：

```
每 5 分钟:
  1. git pull
  2. 读取 tasks/active-task/task-manifest.yaml
  3. 根据 state 决定动作:

     demand → 复制 requirements.md 快照到 demand.md → state=assigned
     failed → retry<3 则 state=assigned; retry>=3 则 escalated=true
     passed → git push → state=closed → 追记根 audit-log.md
     escalated → 打印警告

  4. 更新 tasks/agents-teamwork.yaml
```

### 阶段 2：开发实现（dev-executor, dev, agent mode, 每 10 分钟）

```
1. 读取 demand.md + task-manifest.yaml
2. state = in_progress
3. 逐条实现 → 测试 → git commit
4. 写 features.md
5. state = review
```

### 阶段 3：评审（reviewer-executor, review, agent mode, 每 10 分钟）

```
1. 读取 demand.md + features.md
2. 逐项评审（功能完整性、敏感信息、数据质量、测试覆盖）
3. 写 audit-log.md
4. 通过 → state=passed; 不通过 → state=failed, retry_count+1
```

### 阶段 4：收尾 / 循环（scanner 驱动）

**通过（state == passed）**：

```
scanner → git push → state=closed → 追记根 audit-log.md
```

**不通过（state == failed）**：

```
retry_count < max_retries: state = assigned
retry_count >= max_retries: escalated = true
```

**方案 C（已确认）**：不修改 demand.md 或 requirements.md，失败详情记入 audit-log.md，developer 回归后阅读修复。

### 阶段 5：人工介入

人工查看：
```
tasks/<al-task-id>/demand.md     → 原始需求
tasks/<al-task-id>/features.md   → 实现情况
tasks/<al-task-id>/audit-log.md  → 评审报告 + 3 次失败明细
```

---

## 4. tasks/agents-teamwork.yaml（项目级追踪）

```yaml
project: "llm-radar.jaden.tech"
task_count: 1
open_task_count: 1
escalated_tasks: []
tasks:
  al-20260711-001:
    title: "第 1 轮需求：新增 RSS 数据源"
    state: created
    created_at: "2026-07-11T10:00:00+08:00"
    cycles: 0
    escalated: false
```

scanner 每次执行后同步更新此文件。

---

## 5. 目录结构

```
llm-radar.jaden.tech/
├── requirements.md
├── tasks/
│   ├── active-task -> al-20260711-001/
│   ├── agents-teamwork.yaml
│   ├── al-scanner.py, al-init.py, al-dev.sh, al-review.sh
│   ├── .agent-loop.lock
│   ├── al-20260711-001/
│   │   ├── task-manifest.yaml
│   │   ├── demand.md
│   │   ├── features.md
│   │   └── audit-log.md
│   └── al-20260711-002/
├── audit-log.md
├── documents/
│   ├── README.md
│   ├── [loop]/          requirements-spec.md, agent-loop-design.md
│   ├── [pipeline]/      data-flow.md, agent-loop-plan.md
│   ├── [mcp]/           mcp-protocol-design.md
│   ├── [integ]/         hermes-integration.md
│   ├── [ops]/           linux-deployment.md, supabase-migration.md
│   └── archive/
└── ...
```

### 命名前缀约定

`tasks/` 下 agent-loop 相关文件统一使用 `al-` 前缀：

| 缩写 | 全称 | 原因 |
|---|---|---|
| `al` | **A**gent **L**oop | `ls tasks/al*` 一键列出所有 loop 文件，不与其他工具混淆 |
| `al-rename.sh` | agent-loop rename script | 一次性迁移脚本 |

---

## 6. cron job 编排（方案 B：多个独立 cron job 轮询）

| Job | Profile | 类型 | 频率 | 脚本 |
|---|---|---|---|---|
| **scanner** | ops | `no_agent=True` 纯脚本 (Python) | 每 5 分钟 | `tasks/al-scanner.py` |
| **dev-executor** | dev | agent mode | 每 10 分钟 | `tasks/al-dev.sh` |
| **reviewer-executor** | review | agent mode | 每 10 分钟 | `tasks/al-review.sh` |
| **escalation-reminder** | ops | `no_agent=True` 纯脚本 | 每 6 小时 | 内置于 `tasks/al-scanner.py` |

各 job 启动时通过 flock 获取文件锁 `tasks/.agent-loop.lock`，拿不到锁则跳过本轮。

**`al-scanner.py` 使用 Python 实现**（非 Shell），以支持 flock、yaml 解析、sha256 哈希等操作。

### 详细 Prompt

见 §6.3（al-dev.sh）+ §6.4（al-review.sh）的 prompt 定义。

---

## 7. 失败处理

### 7.1 超时

| 节点 | 超时时间 | 处理 |
|---|---|---|
| scanner | 4 分钟（间隔 5 分钟） | 跳过本轮，下轮继续 |
| dev-executor | 9 分钟（间隔 10 分钟） | 下轮发现 state 仍是 in_progress → 跳过（不重复执行） |
| reviewer-executor | 9 分钟 | 同上 |

### 7.2 Job 运行时长异常监测

三个 cron job 共享同一个文件锁。若某 job 异常中断（crash、hang），锁未被释放，后续 job 持续跳过。

**问题**：锁持有超过 15 分钟应视为异常。

**监测逻辑**（scanner 每次轮询时执行）：

```python
STALE_THRESHOLD = 900  # 15 分钟

def lock_is_stale(lock_path):
    if not os.path.exists(lock_path):
        return False
    age = time.time() - os.path.getmtime(lock_path)
    return age > STALE_THRESHOLD
```

**锁回收与状态修复**：

```
scanner 检测到过期锁 (>15min):
  ├── 强制释放锁（删除 .agent-loop.lock）
  ├── 记录警告到 cron output
  │
  ├── 若当前 state == in_progress:
  │     → state = assigned（回退，允许 dev 重新执行）
  │     → 打印 "⚠️ dev-executor 可能异常中断，已回退 state 为 assigned"
  │
  ├── 若当前 state == review 且 audit-log.md 为空:
  │     → state = review（保留，等待下次 reviewer job）
  │     → 打印 "⚠️ reviewer-executor 可能异常中断，保留 state"
  │
  └── 其他 state: 正常流转
```

**各 job 自身超时退出**：

```python
import signal
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(840)  # 14 分钟（cron 间隔 10min，留缓冲）
```

### 7.3 去重

scanner 使用 `source_hash` 检测 requirements.md 变更：内容未变不创建重复任务。

### 7.4 并发

- 文件锁 + state 自检 + source_hash 三重防护
- 同一时间最多一个 job 在跑

### 7.5 Escalated 任务超过 24h 未处理 → 通知提醒

scanner 每次轮询检测到 `state == escalated` 时，检查 `task-manifest.yaml` 的 `escalated_at` 字段（scanner 在 escalated 时自动写入）。若超过 24 小时未处理，scanner 输出额外警告：

```python
# al-scanner.py 内
ESCALATED_NOTICE_THRESHOLD = 86400  # 24 小时

if manifest.get("escalated_at"):
    elapsed = time.time() - parse_iso_time(manifest["escalated_at"])
    if elapsed > ESCALATED_NOTICE_THRESHOLD:
        print(f"🚨 [提醒] escalated 任务已超过 24 小时未处理！")
        print(f"   请查看: tasks/active-task/audit-log.md")
        print(f"   操作指南: 设 state=assigned + retry_count=0")
```

**提醒效果**：cron output 会显示这些输出，你在任意 profile 中通过 `cronjob action=list` 可见。

如需更主动的推送（发消息到你终端），可以在 scanner 中增加日志写入：

```python
# 追加到 .agent-loop.escalation.log
with open("tasks/.agent-loop.escalation.log", "a") as f:
    f.write(f"[{datetime.now()}] escalated 任务超过 24h: {task_id}\n")
```

此日志文件可通过外部监控或你手动 `cat` 查看。

---

## 8. 与已有设计的衔接

- **agent-loop-plan.md**：数据管道闭环（数据采集），与开发流程闭环互补
- **hermes-integration.md**：MCP 数据写入通道，与开发方法论正交

---

## 9. 启动操作步骤

### 场景 A：我有需求，立即开始

```
Step 1 ─ 编辑 requirements.md（requirements-spec 格式）
Step 2 ─ python3 tasks/al-init.py "<标题>" --demand
         （加 --demand 直接创建即就绪，state 自动为 demand；
          不加则 state=created，需手动改）
Step 3 ─ 等 cron 自动流转（state=demand → scanner → assigned → ...）
Step 4 ─ cat tasks/active-task/features.md  / audit-log.md
```

### 场景 B：AI 定时检查变更

scanner 已自动检测 requirements.md 变更。或创建第 4 个 cron job（agent mode）定期询问。

### 场景 C：人工介入 escalated

```
cat tasks/active-task/audit-log.md
→ 重置 state + retry_count 或创建新 task
```

### 状态速查表

| 想法 | 操作 |
|---|---|
| 提需求 | 编辑 `requirements.md` |
| 开始迭代 | `al-init` → `state=demand` |
| 查进度 | `cat tasks/agents-teamwork.yaml` |
| 查实现 | `cat tasks/active-task/features.md` |
| 查评审 | `cat tasks/active-task/audit-log.md` |
| 人工介入 | 改 `task-manifest.yaml` 的 state + retry_count |

---

## 10. 与人协作的接口

| 操作 | 方式 |
|---|---|
| 创建/更新需求 | 编辑 `requirements.md`（requirements-spec 格式） |
| 初始化 task | `python3 tasks/al-init.py "&lt;标题&gt;"`（加 `--demand` 直接进入就绪态） |
| 确认需求完成 | `task-manifest.state = demand`（仅当未使用 `--demand` 时需要） |
| 查看进度 | `cat tasks/agents-teamwork.yaml` |
| 查看详细任务 | `cat tasks/<al-task-id>/task-manifest.yaml` |
| 查看实现 | `cat tasks/<al-task-id>/features.md` |
| 查看评审 | `cat tasks/<al-task-id>/audit-log.md` |
| 人工介入 | 改 `task-manifest.state` + 重置计数器 |

---

## 11. Bootstrapping

### 11.1 迁移脚本

```bash
bash tasks/al-rename.sh
```

自动重命名：loop.md→requirements.md, AUDITLOG.md→audit-log.md, current→active-task, task-*→al-*, 等。

### 11.2 创建 init 脚本

文件 `tasks/al-init.py`（见 §11.3 代码）。

### 11.3 注册 cron job

在 ops profile 终端：

```bash
cronjob action=create name="llm-radar scanner" schedule="every 5 min" profile=ops script=tasks/al-scanner.py no_agent=true

cronjob action=create name="llm-radar developer" schedule="every 10 min" profile=dev script=tasks/al-dev.sh prompt="..."

cronjob action=create name="llm-radar reviewer" schedule="every 10 min" profile=review script=tasks/al-review.sh prompt="..."
```

### 11.4 验证

```bash
cronjob action=list
cronjob action=run job_id=<scanner id>
```

---

> 版本: 1.2 | 更新: 2026-07-11 | 分类: [loop]
