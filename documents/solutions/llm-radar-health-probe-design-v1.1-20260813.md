---
title: llm-radar 线上数据新鲜度探针设计
topic: llm-radar
type: design
version: 1.1
date: 2026-08-13
author: hermes-1.2.0
tags: [llm-radar, cron, watchdog, monitoring, health]
profile: ops
provider: deepseek
model: deepseek-v4-flash
---

# llm-radar — 线上数据新鲜度探针(health watchdog)设计

> 版本: v1.1 | 日期: 2026-08-13
> 作者: ops (hermes-1.2.0)
> 数据来源: hermes cron 现有 job 配置、llm-radar 采集任务 cron、用户需求确认
> 变更: v1.0 → v1.1 记录确认项 A1 B1 C2(2026-08-13)

## 背景/动机

llm-radar 的数据由两端采集(服务器 Linux 7×24 + 本机 macOS),cron 触发 `llm-radar-run.sh run`,产出推送到 GitHub Pages(自定义域名 llm-radar.lab.jaden.tech)。

用户提出:通过解析 `https://llm-radar.lab.jaden.tech/timestamp.json` 即可判断 CI/采集链路是否跑通成功(至少最新数据时间控制在 7 小时内)。该检查能端到端验证完整链路:采集 → push → GitHub Pages 部署 → CDN 缓存,是"数据新鲜度探针"。

现状:该检查逻辑**不存在**。CLI 无 health 指令,hermes cron 的 health-daily/health-weekly 只检查 hermes-manager 自身,不覆盖 llm-radar 站点。

## 术语表

| 术语 | 定义 |
|------|------|
| cron job | hermes cron 调度的定时任务,两种模式(no_agent 脚本 / LLM agent) |
| no_agent 模式 | 到点只运行脚本,不调用 LLM,零 token 消耗,输出 = 脚本 stdout |
| watchdog(看门狗) | no_agent 脚本的经典写法:正常静默,异常输出告警 |
| health-daily | 现有 hermes cron job:每天 9:00 检查 hermes-manager 自身健康 |
| timestamp.json | 线上健康检查端点,含 last_run_at/last_run_status/last_news_date 等字段 |

## 第一部分:health cron 模式

hermes cron 的每个 job 由 `no_agent` 字段决定执行模式:

| 维度 | no_agent=true(脚本模式) | no_agent=false(LLM 模式) |
|------|--------------------------|---------------------------|
| 执行 | 到点运行 script 字段指定的脚本 | 启动 agent 会话按 prompt 推理 |
| 输出 | 脚本 stdout 原样 | LLM 生成的文本 |
| 成本 | 零 token,秒级 | 消耗 token,分钟级 |
| 适用 | 确定性检查(阈值、探针、看门狗) | 需要理解/总结/判断的任务 |

现有 4 个 hermes cron job 全部是 no_agent=true 模式:
- health-daily(`0 9 * * *`)→ ops-health-quick.py
- health-weekly(`0 9 * * 0`)→ ops-health-full.py
- macosx-monitor(`every 10m`)→ macosx-monitor.sh
- task-lifecycle-watch(`every 30m`)→ task-lifecycle-watch.py

## 第二部分:health-daily 模式

health-daily 是 watchdog 的一个具体实例:

- 配置:schedule `0 9 * * *`(每天 9:00),no_agent=true,deliver=local
- 脚本:ops-health-quick.py —— 薄 wrapper,内部调用 `hermes-manager.py health quick`(检查 hermes-manager 脚本健康:文件存在、可执行等)
- deliver=local:输出只存档(可通过 cron list 查看),不推送到聊天平台
- 现状:只检查 hermes-manager 自身,不覆盖 llm-radar 站点

## 第三部分:watchdog 逻辑

watchdog(看门狗)是 no_agent 脚本的经典设计模式,核心规则:

1. 脚本每次触发做检查
2. **正常时输出为空(空 stdout)→ 静默**——hermes 不发送任何消息,用户无感
3. **异常时输出告警文本 → hermes 把 stdout 当消息投递**
4. **非零退出码 → hermes 发送错误警报**(防止看门狗本身坏掉无人知晓)

典型实例 macosx-monitor.sh:
- 每 10 分钟触发,检查 CPU/内存/温度/电量是否超阈值
- 未超阈值 → 静默;超阈值 → 输出一行告警 + 冷却 30 分钟防刷屏
- 用户只在真出事时收到通知

## 方案 B:llm-radar 数据新鲜度探针

### B1. 探针脚本 `llm-radar-health.py`

独立脚本,不修改 llm-radar-collector.py(避免污染采集器):

```
#!/usr/bin/env python3
逻辑:
1. 请求 https://llm-radar.lab.jaden.tech/timestamp.json (timeout 15s)
2. 解析 last_run_at / last_run_status / last_news_date
3. 计算新鲜度: now - last_run_at
   - 新鲜度 ≤ 阈值(默认 7h) 且 status == success → 静默, exit 0
   - 新鲜度 > 阈值 或 status != success → 输出告警, exit 1
4. 网络失败/JSON 解析失败 → 输出错误告警, exit 1
```

放置位置:`~/.hermes/profiles/ops/scripts/llm-radar-health.py`(与现有 cron 脚本同目录)

### B2. cron job 注册

```
name:      llm-radar-freshness
script:    llm-radar-health.py
no_agent:  true
schedule:  (见 B3 触发频率设计)
deliver:   local(告警投递暂忽略, 仅存档, 可后续改为平台)
```

### B3. 触发频率设计(与采集任务结合)

当前采集任务节奏:
- 服务器 cron:`0 7,14,21 * * *`(每天 3 次,7×24 常开,主采集源)
- 本机 cron:`0 * * * *`(每小时,但 6h 防抖 → 实际约每 6-7h 有效采集一次)
- 6h 防抖逻辑:距上次成功采集 <6h 则跳过(collector.py:1391-1393)

探针触发频率设计原则:探针必须**晚于**采集任务,且能覆盖采集间隔内的新鲜度波动。

| 方案 | schedule | 逻辑 | 结论 |
|------|----------|------|------|
| A | `0 * * * *`(每小时) | 与采集同频,及时发现 | 过度频繁,7h 阈值下无必要 |
| B | `0 3,9,15,21 * * *`(每 6h) | 对齐 6h 防抖,采集后 2h 内必查 | ✅ 采用 |
| C | `0 8,15,22 * * *`(服务器采集后 1h) | 服务器 7/14/21 采集后 1h 检查 | 依赖服务器单点,本机补充时覆盖不足 |

**采用方案 B**:`0 3,9,15,21 * * *` 每 6h 触发一次。

理由:
- 探针阈值 7h,6h 间隔 < 7h,任何超过阈值的情况必然被至少一次探针捕获
- 与采集 6h 防抖节奏对齐:采集约每 6-7h 一次,探针每 6h 一次,二者同频
- 服务器 7/14/21 采集后,探针 9/15/21 点检查时数据应已新鲜(采集 ~5min + 部署 <1h)
- 本机每小时 cron 补充采集时,探针也能覆盖(本机实际约每 6-7h 有效采集,探针 6h 间隔在窗口内)

### B4. 阈值参数

- 新鲜度阈值:7h(用户指定:"至少最新数据时间控制在 7 小时内")
- 判断:`last_run_status == 'success'` 且 `now - last_run_at <= 7h`
- 可配置化(脚本顶部常量 `STALE_HOURS = 7`),便于后续调整

## 非目标

- 不修改 llm-radar-collector.py 采集逻辑
- 不添加 CLI 指令(保持采集器纯净)
- 不配置告警投递平台(用户明确"告警投递暂忽略",deliver=local 仅存档)
- 不解决采集任务本身的修复(已由 git-flow-fix 方案处理)

## 实施范围

| 文件 | 改动 |
|------|------|
| ~/.hermes/profiles/ops/scripts/llm-radar-health.py | 新增探针脚本 |
| hermes cron | 注册 job `llm-radar-freshness`(no_agent=true, schedule `0 3,9,15,21 * * *`, deliver=local) |

## 验收标准

1. 脚本手动执行:线上数据新鲜时 exit 0 且 stdout 空;人工构造过期场景(阈值设 0h)时 exit 1 且有告警输出
2. cron job 注册成功,`cron list` 可见,首次运行 last_status=ok
3. 探针触发不干扰采集任务(git 无残留、无副作用)

## 风险评估

| 风险 | 等级 | 缓解 |
|------|------|------|
| GitHub Pages CDN 缓存延迟导致误报 | 低 | 阈值 7h 充裕,部署延迟通常 <1h |
| 脚本依赖网络(本机离线) | 低 | 网络失败输出错误告警(而非静默),可区分"探针自身问题"与"数据过期" |
| 本机睡眠错过探针触发 | 低 | macOS cron 睡眠不触发(同采集问题);服务器为常开主源,采集数据仍在,且用户已知此限制 |
| 7h 阈值与 6h 采集间隔竞态 | 低 | 探针 6h 间隔 < 阈值 7h,任何过期必然被捕获 |

## 待确认清单(已确认 2026-08-13, 用户回复: A1 B1 C2)

| 项 | 决策 | 确认结果 |
|----|------|---------|
| A 触发频率 | A1 每 6h(`0 3,9,15,21 * * *`) | ✅ 采用(与采集 6h 防抖对齐) |
| B 阈值 | B1 7h(用户指定) | ✅ 采用 |
| C 探针脚本放置 | C2 项目内 scripts/ 目录(随 repo 版本化) | ✅ 采用 |

### 确认后实施范围

1. 项目内新增 `scripts/llm-radar-health.py`(随 repo 版本化, 与采集器同仓)
2. hermes cron 注册 job `llm-radar-freshness`(no_agent=true, schedule `0 3,9,15,21 * * *`, deliver=local, script 指向项目内脚本绝对路径)
3. 阈值常量 `STALE_HOURS = 7` 写入脚本顶部
4. 验收:手动执行 exit 0 静默 / 构造过期场景 exit 1 告警;cron list 可见且 last_status=ok

## 元信息

| 项目 | 内容 |
|:-----|:------|
| 版本 | 1.1 |
| 最后更新 | 2026-08-13 |
| 作者 | hermes-1.2.0 |
| Session | ops/llm-radar-health-probe |
| Model | deepseek/deepseek-v4-flash |
