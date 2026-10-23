# llm-radar 采集报告 → 飞书通知（模板定稿与落地）

> 需求：把「每天采集了什么」以飞书消息呈现，而不是只留日志。
> 定稿口径（2026-10-23 用户样张，逐字实现）：日期只出现在产物时间行（MM-DD）、分隔用 `・`、
> 中英文/数字之间补空格、`**…**` 为字面星号（飞书纯文本不渲染 markdown，用户已知并接受）、
> 异常消息为「根因优先」（根因 → 数据陈旧 → 连败 → 修复指令）。
>
> 相关：`twitter-login-persistence-v1.0-20261023.md`（X 侧登录态）、channel-notify-protocol（通知规范）。

---

## 1. 形态选择（为什么不是「每轮都发」）

| 形态 | 频率 | 判定 |
|:---|:---|:---|
| 每轮采集都发 | 8–9 条/天（主采集 :40 + X :20） | ❌ 噪音，违 channel-notify-protocol §5「监控/分析型不滥发」 |
| **每日日报** | 1 条/天（21:00） | ✅ 固定一条，0 新增也发（证明管线活着） |
| **异常告警** | 仅异常且指纹变化时 | ✅ watchdog：正常空 stdout 静默，恢复补一条 |

## 2. 消息模板（定稿）

### 2.1 日报 `📊 LLM Radar 日报`

```
📊 LLM Radar 日报
---
**今日热点（按日期倒序）**
1. {标题}（{来源}・{MM-DD}）        ← 最多 6 条, 按日期倒序, 按标题去重
...
---
- 实体：新增 {new_this_period}・更新 {updated_this_period}（模型 a / 公司 b / 人物 c / 工具 d 动态）
- 窗口：热点 X・公司 Y・模型 Z・人物 P・工具 Q
- X 热点：{账号数} 账号・{推文数} 条（{HH:MM} 采）
- 信源：本机 {ok}/{total} 成功

🕒 产物时间 {MM-DD HH:MM}
---
来源：cron job llm-radar-daily-digest({job_id})
```

口径细节：
- 「动态」计数 = 各维主事件日期字段 == 今天：llms/providers → `last_event_date`；people → `recent_activity_date`；tools → `last_update_date`
- 「窗口」= snapshot.stats 的 total_*
- 信源：`ok = round(run_history[-1].source_rate × SCRAPERS 数)`；三个分支：
  全成功 → `本机 6/6 成功`；有降级源 → `本机 4/6（2 源已降级）`；有失败但不足降级 → `本机 5/6（部分失败）`
  （**不能用 collector.log 的「抓取完成 X/Y」**：手动 `run` 只打 stdout 不落日志，会读到上一轮 cron 的旧值 — 2026-10-23 实测踩过）
- 「已降级」口径 = `source_health[k].last_result == 'fail'` 且该源 `consecutive_fails ≥ 3`；`last_result == 'reset'`
  （人工 `lr reset-health` 后的状态）不计入 —— 2026-10-23 收尾时 techcrunch/help 即为 `reset`。
- 产物缺失时降级为 `1. ❌ 产物不可用（原因）`，不发空正文

### 2.2 异常 `🔴 LLM Radar 异常`

```
🔴 LLM Radar 异常
---
**根因分析**
- {根因 1..3: driver 版本不匹配 / 源降级清单 / 兜底提示}
- 数据陈旧：快照产物 {MM-DD HH:MM}（{age}h 前，阈值 6.5h）     ← 仅在陈旧时输出
- 本机连续失败 {n} 次，首败 {MM-DD HH:MM}                       ← 仅 n≥3 时输出
- 修复指令：lr reset-health && lr run --force
---
来源：cron job llm-radar-collect-watch({job_id})
```

口径注记（评审 2026-10-23 实测）：`首败` 当前取的是 `run_history` 窗口内**最早一次** `success=False` 的记录
（`first_fail = fails[0]`），不是「本轮连败起点」。隔离演练里 `run_history[0]` 放一条 3 天前的旧失败，
告警就打出 `首败 10-20 09:40` 而真实连败起点是当天 —— 长窗口内出现过历史失败时会误导排障。
修法：从 `run_history` 末尾反向找第一条 `success=True`，其后的第一条失败即本轮首败。

### 2.3 恢复 `🟢 LLM Radar 已恢复`（异常消失时补一条，然后清状态）

```
🟢 LLM Radar 已恢复
---
- 数据：快照产物 {MM-DD HH:MM}（{age}h 前）
- 信源：本机 {ok}/{total} 成功
- 异常持续：{since} → 现在
---
来源：cron job llm-radar-collect-watch({job_id})
```

## 3. 触发阈值与去重

- 阈值：数据年龄 > **6.5h**（必须大于主采集 6h 节流）∪ 全局 `consecutive_fails ≥ 3` ∪ 已降级源 **≥ 2**
- 去重：指纹 = `{原因集合, 降级源清单, 是否连败}` 落 `cache/records/collect-report-state.json`；
  同指纹不重发；恢复时发一条并清 `active`
- 调度：日报 `0 21 * * *`；告警 `55 8-23 * * *`（夜间 0–7 点静默，夜间异常由次日日报体现）

### 3.1 阈值余量（评审实测校准 2026-10-23）

- **6.5h 对主采集只剩 0.25h 余量**。主采集节流 = 6h（`llm-radar-collector.py:1898`：`hours_since < 6` 即跳过），
  cron `40 * * * *` 每小时尝试 ⇒ 正常年龄峰值 ≈ 7.0h（`collector.log` 实证：`01:40 距上次成功采集仅 6.0h，跳过`
  → `02:40` 才真采；`08:40 6.0h 跳过` → `09:40` 真采）。告警在 `:55` 采样，紧邻跳过点的一次采样 ≈ 6.25h。
  ⇒ 任何 15 分钟级抖动（休眠唤醒错过 :40、单轮耗时变长、快照写入失败）都会把**正常态**判成 `stale`。
- 建议分管线取值：**主采集 7.5h**（= 6h 节流 + 1 轮 + 槽位抖动，与 X 侧 `6.5 = 5 + 1.5` 同一推导），
  **X 侧维持 6.5h**。当前两个脚本各自写死 `6.5`、注释各说各的（`llm-radar-collect-report.py:25` /
  `llm-radar-twitter-login-verify.py:31`），改一处不影响另一处，属漂移点。
- 若坚持 6.5h，则应在文档里明确语义 = **「缺 1 轮即报」**（今日 09:55 那次本可 15 分钟内发现），
  别写成「正常上限」；两种口径对应两种不同的运维期望，写混会导致后续误判为误报。
- **已知 fail-open（重要）**：`snapshot_facts()` 用 `datetime.fromisoformat(gen)` 解析 `generated_at`，
  Python 3.9 遇到 `...Z` 后缀会抛 `ValueError`，异常被吞掉 ⇒ `age=None` ⇒ `stale` 判据**静默失效**（告警不出、
  日志不留）。隔离演练已复现：把 `generated_at` 改成 30h 前的 `...Z`，`--alert` 输出 **0 字节**。
  当前采集器写的是本地 naive 时间（`2026-10-23T19:15:04.744471`）所以尚未触发；但格式一旦改成 UTC `Z`
  （或换成另一台机器产出），主新鲜度检查直接失效。修法：`datetime.fromisoformat(gen.replace('Z', '+00:00'))`
  + 全程 tz-aware 比较，并且 `age is None` 时按「陈旧」处理（fail-closed）。

### 3.2 对 2026-10-23 真实事故的反推（校准用）

当日 09:40–18:40 主采集 `chromedriver 154 vs Chrome 156` ⇒ 每轮 `抓取完成，0/6 个源成功`、`consecutive_fails`
一路累到 11，快照 `generated_at` 冻结在 03:02→11:03→19:03。若告警 job 当时已在：
`09:55` 命中 `stale`（03:02 起算 6.9h），`11:55` 命中 `fails`（≥3）—— 即当前阈值**能**覆盖这类事故，
延迟 15min–2h；同一事故因指纹变化会发两条（见 §6 O-5）。

## 4. 落地件

| 文件 | 作用 |
|:---|:---|
| `~/.hermes/profiles/ops/scripts/llm-radar-collect-report.py` | 主体：`--digest` / `--alert`，stdout 即消息正文 |
| `~/.hermes/profiles/ops/scripts/llm-radar-report-digest.py` | cron wrapper → `--digest` |
| `~/.hermes/profiles/ops/scripts/llm-radar-report-watch.py` | cron wrapper → `--alert` |
| cron `llm-radar-daily-digest` (4fb95acd0f81) | `0 21 * * *`，no_agent，deliver=feishu |
| cron `llm-radar-collect-watch` (e4bae95a6a40) | `55 8-23 * * *`，no_agent，deliver=feishu |
| `cache/records/collect-report-state.json` | 告警指纹/持续起点（gitignored） |

脚本特性：只读产物与 metrics/日志尾部，不写 repo；任意异常都 `exit 0` 并打印 `❌ 报告脚本异常 …`（避免 watchdog 自己静默挂掉）。

## 5. 复跑与验收

```bash
S=~/.hermes/profiles/ops/scripts/llm-radar-collect-report.py
python3 "$S" --digest          # 打印日报正文（不发送）
python3 "$S" --alert           # 健康态应输出 0 字节
~/.hermes/profiles/ops/scripts/llm-radar-report-digest.py   # wrapper 路径验证
hermes cron list --profile ops | grep llm-radar            # 两个 job 的 next_run/last_status
```

验收断言：日报含 6 条热点 + 4 条 `- ` 元信息 + 产物时间 + 来源行（带真实 job_id）；
告警在健康态零输出；`cache/records/collect-report-state.json` 仅在异常/恢复时出现。

**评审实测（2026-10-23，生产只读 + 隔离副本演练）**：

| 路径 | 方式 | 结果 |
|:---|:---|:---|
| 日报（健康态） | 生产直接跑 `--digest` | 6 条热点 + 4 条元信息 + `🕒 产物时间 10-23 19:15` + `来源…(4fb95acd0f81)` ✅ |
| 日报（降级态） | 隔离副本 `source_rate=0.667` + 2 源 fail | `信源：本机 4/6（2 源已降级）` ✅ |
| 告警（健康态） | 生产直接跑 `--alert` | stdout **0 字节**、rc=0 ✅ |
| 告警（stale+fails+degraded） | 隔离副本（副本内替换 REPO 常量） | 模板逐行成立：`源降级…` / `数据陈旧…（11.0h 前，阈值 6.5h）` / `连续失败 4 次，首败 …` / `修复指令…` / `来源…(e4bae95a6a40)` ✅ |
| 去重 | 同上，第二次跑 | 同指纹 **0 字节**，`state.json` 落 `{"active": true, "fp": …, "since": …}` ✅ |
| 恢复 | 隔离副本恢复健康后跑 | `🟢 已恢复` 模板成立，`state.json` → `{"active": false, "cleared_at": …}` ✅ |

注意：**生产 `cache/records/collect-report-state.json` 至今不存在**（健康态不落盘，符合设计），
即生产上的异常/恢复两条路径仍**未被真实触发过**；上表告警/去重/恢复三行是隔离副本证据。
上线后第一次真实告警请人工核对一次正文与 `state.json`。

## 6. 观察项

- **O-1 噪音复核**：上线后 3 天统计消息条数（应≈3 条日报 + 0 告警）。若告警因单源抖动误报，把 `DEGRADED_ALERT` 从 2 调到 3。
- **O-2 夜间盲区**：0–7 点不发告警；若夜间断采且次日早间无人看，08:55 的首条告警会是最早信号。
- **O-3 热点去重**：同标题不同 id 会重复出现在窗口内（2026-10-23 实测排序后出现两条同名），脚本按标题去重，因此日报条数可能少于窗口内实际条数。
- **O-4 信源口径**：`SCRAPERS` 键数变化（新增/删除源）会自动反映到 `x/y`，无需改脚本；但 `source_health` 里 techcrunch/help 属历史残留键，不计入分母。
- **O-5 同一事故可能连发两条（评审实测推演）**：指纹含「原因集合」，一次长事故里 `stale` 先成立、快照更新后
  转成 `fails`，两次指纹不同 ⇒ 各发一条。2026-10-23 场景反推就是 09:55（stale）+ 11:55（fails）。
  可接受（信息不全→更全），但要知道「恢复」只在**全部原因消失**时才发，别把中间的 stale→fails 当成两条独立事故。
- **O-6 driver 不匹配目前不是触发条件**：`driver_mismatch` 只在告警正文里作根因行输出，判定仍靠
  `stale`/`fails`/`degraded`。2026-10-23 的 `0/6`（driver 154 vs Chrome 156）等 `consecutive_fails` 累到 3 才响，
  白等 2 轮。建议把「日志出现 chromedriver 主版本不匹配」直接并入 `alert_reasons`（即时告警 + 现成根因行）。
- **O-7 夜间静默 × 主采集 6h 节流 = 最长约 10h 盲区**：`55 8-23` 不覆盖 0–7 点，若 23:00 后断采，最早信号是
  次日 08:55（≈9.9h）；其间 21:00 的日报若已生成，正文只带「产物时间」而无陈旧标记，读者容易当成当轮数据。
  若要缩短，需另加一条早间 07:xx 的探活（属调度变更，`AGENTS.md` Ask First）。
- **O-8 `age` 解析 fail-open**：见 §3.1 末条（`...Z` 格式 ⇒ `age=None` ⇒ 不告警）。修法是 tz-aware 解析
  + `age is None → stale`，属**优先级最高**的脚本侧待修项（当前只是尚未踩到）。
