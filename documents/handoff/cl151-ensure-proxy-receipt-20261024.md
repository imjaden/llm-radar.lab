# 回执：Twitter 采集侧 ensure-proxy（CL151）

- 日期：2026-10-24
- 回执方：llm-radar.lab（ops 会话）
- 收件依据：`daily-checker/documents/handoffs/CL151-twitter-collector-ensure-proxy-20261024.md`
- 详细实施与证据：`documents/ops/cl151-ensure-proxy-v1.0-20261024.md`

## 四条回执（对应 §5）

1. **采集任务入口是否已接入 ensure_proxy**：是。
   `scripts/twitter-collector-cron.sh`（cron 唯一入口）step 1 → `scripts/flclash_proxy.py ensure`；
   `scripts/twitter-collector.py` 入口 `_ensure_proxy_ready()`（手工/直跑路径），并在 attach 失败的重连点再 ensure + 重试一次。
2. **代理端口**：仍是 `7890`（就绪判据 = `127.0.0.1:7890` 可建连；来源上游 `verify.ports`）。本仓可用
   `TWITTER_FLCLASH_PORT` 覆盖（默认 7890），**未**引入 `DK_PROXY_PORT`；若需两侧同名，请示下。
3. **CDP 端口**：仍是 `9222`（`TWITTER_CDP_PORT` 可覆盖）。对应 daily-checker 侧 `DK_TWITTER_CDP_PORT`。
4. **SC1/SC2 是否已实测**：已实测（2026-10-24 20:59–21:05）——
   - SC1：FlClash 停止 + 采集启动 ⇒ 自动 `open -g -a FlClash` → 7890 LISTEN → 采集 10 账号 67 条 → 写盘+push → 采集后释放；exit 0；**FlClash 通知 0 次**。
   - SC2：FlClash 停止 + 节流期内不采集 ⇒ 只打印「跳过: twitter.json 生成于 1.4h 前」，FlClash 未被启动、无告警。
   - 另测：SC4（死端口构造未就绪）⇒ `⏸️ 跳过本轮` + exit 0 + 不进采集；SC4b（9222 已活但代理停）⇒ 仍拉起 FlClash。

## 三处差异声明

- **进程判据**：本仓用 `pgrep -x FlClash` ∪ `pgrep -f /Applications/FlClash.app`，未采用 `macosx service check --json`
  （`macosx` 在 cron PATH 不可见，需绝对路径 + 子进程开销；2026-10-09 已收敛为本仓唯一真源）。端口判据两侧一致（7890）。
- **就绪预算**：本仓 180s（对齐上游 `verify.wait`），非建议值 90s。
- **就绪判据的两个分支**（评审补记，2026-10-24）：「FlClash 未运行」分支 = 拉起后等 7890 可连（与 CL151 §3 一致）；
  **「FlClash 已在运行」分支只判进程、不探 7890**（对齐上游 policy「已在运行 → 直接复用」）。因此
  「在运行但 7890 关闭」本仓不会判未就绪 ⇒ 本轮走采集失败（exit 1），而非跳过。已知偏差，修复方案待两侧确认（建议 CL152）。
- 开启命令已对齐 `open -g -a FlClash`（此前本仓漏 `-g`，本批修正）。

## 本仓行为变化（需 daily-checker 侧知悉）

- 「代理未就绪」现在是**跳过**：exit 0、不写数据、不计连败、不发任何通知；
  面板侧看到的应是「X 数据未更新」而不是新告警。若需要「连续 N 轮跳过」才升级提醒，请单独提需求（本仓可加进日报）。
