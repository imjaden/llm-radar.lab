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
- 信源：`ok = round(run_history[-1].source_rate × SCRAPERS 数)`；全成功写 `成功`，否则写 `（N 源已降级）`
  （**不能用 collector.log 的「抓取完成 X/Y」**：手动 `run` 只打 stdout 不落日志，会读到上一轮 cron 的旧值 — 2026-10-23 实测踩过）
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

## 6. 观察项

- **O-1 噪音复核**：上线后 3 天统计消息条数（应≈3 条日报 + 0 告警）。若告警因单源抖动误报，把 `DEGRADED_ALERT` 从 2 调到 3。
- **O-2 夜间盲区**：0–7 点不发告警；若夜间断采且次日早间无人看，08:55 的首条告警会是最早信号。
- **O-3 热点去重**：同标题不同 id 会重复出现在窗口内（2026-10-23 实测排序后出现两条同名），脚本按标题去重，因此日报条数可能少于窗口内实际条数。
- **O-4 信源口径**：`SCRAPERS` 键数变化（新增/删除源）会自动反映到 `x/y`，无需改脚本；但 `source_health` 里 techcrunch/help 属历史残留键，不计入分母。
