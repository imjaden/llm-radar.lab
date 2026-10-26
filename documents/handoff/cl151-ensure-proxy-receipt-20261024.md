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
- **就绪判据的两个分支**（2026-10-24 21:40 起，两分支都探端口 —— 修订了评审初版的偏差记录）：
  「FlClash 未运行」分支 = `open -g -a FlClash` 后等 7890 可连（就绪预算 180s，对齐上游 `verify.wait`）；
  **「FlClash 已在运行」分支同样先探 7890**：通则复用、零动作；不通则给 `RUNNING_PORT_GRACE=10s` 短预算再探，
  仍不通 ⇒ `not_ready(reason=port_closed)`，入口按「未就绪」**跳过本轮（exit 0）**，不再走采集失败。
  （此前版本「在运行即判就绪」已由 commit `799ca8e` 修复；真机证据：FlClash 在跑 + `ensure --port 7899`
  ⇒ `{"ok": false, "reason": "port_closed"}` 且不二次拉起。）
- **SC3 端口命名（本仓决定，2026-10-24）**：**维持现状**——保留 `TWITTER_FLCLASH_PORT` / `TWITTER_CDP_PORT`，
  不引入 `DK_PROXY_PORT` / `DK_TWITTER_CDP_PORT` 别名。两侧默认值一致（7890 / 9222），且本仓未改端口，
  故 SC3「改 CDP 端口 ⇒ 两侧同时改」当前**不触发**；若日后真要改端口，需两侧同批改名，届时再议。
- 开启命令已对齐 `open -g -a FlClash`（此前本仓漏 `-g`，本批修正）。

## SC1–SC5 状态（采集侧，2026-10-24）

| SC | 判据 | 采集侧状态 |
|:---|:---|:---|
| SC1 | 停止 + 启动采集 ⇒ 自动拉起、等 7890、采集成功、无 FlClash 通知 | ✅ 实测（20:59–21:05）：`open -g -a FlClash` → 7890 LISTEN → 10 账号 67 条 → 写盘+push → 释放，exit 0，通知 0 次 |
| SC2 | 停止 + 不需要采集 ⇒ 什么都不发生 | ✅ 实测：节流期内只打印「跳过: twitter.json 生成于 1.4h 前」，未启动、无告警（面板侧 info 由本仓侧验证） |
| SC3 | 改 CDP 端口 ⇒ 两侧同改 env | ⏸️ **不适用（本仓决定维持现状）**：端口未改，默认 7890/9222 两侧一致；见上「SC3 端口命名」 |
| SC4 | 启动失败 ⇒ 跳过并记日志、面板仍 info | ✅ 实测：死端口构造 ⇒ `⏸️ 跳过本轮` + exit 0 + 未进采集，twitter.json 未变 |
| SC4b | 9222 已在监听但代理未就绪 ⇒ 仍必须启动 FlClash | ✅ 实测：9222 复用不动、代理停止 ⇒ 仍 `open -g -a FlClash` |
| SC5 | 超时上限由 daily-checker heal 重启 + 四槽通知，采集侧不得重复通知 | ✅ 采集侧**零通知**：`flclash_proxy.py` 的 `notify` 子命令 / `NOTIFY_CMD` / `notify_required()` 已于 2026-10-26 删除，回归钉子 `test_no_notify_surface_left` 断言源码里不再有 `display notification`。不参与 heal、不重启进程 |

## 本仓行为变化（需 daily-checker 侧知悉）

- 「代理未就绪」现在是**跳过**：exit 0、不写数据、不计连败、不发任何通知；
  面板侧看到的应是「X 数据未更新」而不是新告警。若需要「连续 N 轮跳过」才升级提醒，请单独提需求（本仓可加进日报）。
- **补（2026-10-24 21:40，评审后）**：① 「进程在但 7890 不可达」现在也判**未就绪**（短预算 10s 后 `port_closed`），
  不再把「FlClash 开着但代理暂停」当成可采集；② `TWITTER_FLCLASH_ENSURE=0` 时采集器**只探测不拉起**
  （注入 `TWITTER_PROXY_NO_ENSURE=1`），不会再出现「关掉管理却被拉起且常驻」。两项均真机验证。
