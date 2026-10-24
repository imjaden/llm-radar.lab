# Twitter 采集侧 ensure-proxy 落地（daily-checker CL151）

> 依据：daily-checker `documents/handoffs/CL151-twitter-collector-ensure-proxy-20261024.md`（用户 2026-10-24 定稿：
> 「FlClash 默认可以关闭，若 Twitter 采集服务需要 FlClash 开启则进行开启动作」）。
> 本仓职责：需要代理的一侧（X 采集）在**采集开始前**确保代理就绪；不做反向通知、不把「未运行」当异常。
> 回执件：`documents/handoff/cl151-ensure-proxy-receipt-20261024.md`。

---

## 1. 四口径落地对照

| 口径 | CL151 要求 | 本仓实现 | 结论 |
|:---|:---|:---|:---|
| 需要信号 | 采集要发起（不是 CDP 9222） | 节流判断（wrapper step 0）先于代理（step 1）；只有真要采集才 ensure | ✅ |
| 代理就绪 | FlClash 在运行 **且** 7890 可连 | `is_port_listening(7890)` + `pgrep -x FlClash` ∪ `pgrep -f /Applications/FlClash.app` | ⚠️ 端口同源；进程判据用 pgrep 双判据（见 §4 偏差 1） |
| 开启命令 | `open -g -a FlClash`（禁 `service restart`） | `START_CMD=('open','-g','-a','FlClash')` | ✅（此前漏 `-g`，本批修正，见 §2-1） |
| CDP 9222 | 只代表浏览器在，不能当代理就绪 | 代理判定不读 9222；SC4b 实测「浏览器在 + 代理停」仍会拉起 | ✅ |

禁止项核对：① 不反向发 FlClash 通知 —— 采集入口**已删除** `_notify_flclash_required()` 调用（本地通知也不发）；② 不把「未运行」当异常 —— 就绪失败改为 `⏸️ 跳过本轮`、exit 0、不计连败；③ 不每轮无条件启动 —— 节流/无目标时根本不进入 ensure。

## 2. 代码改动

| # | 文件 | 改动 |
|:--|:---|:---|
| 1 | `scripts/flclash_proxy.py` | `START_CMD` 加 `-g`（对齐上游 policy `open -g -a FlClash` 与 CL151；此前本仓漂移为 `open -a`） |
| 2 | `scripts/twitter-collector-cron.sh` | ensure 失败由 `exit 1` → `⏸️ 跳过本轮` + `exit 0`（跳过 ≠ 失败） |
| 3 | `scripts/twitter-collector.py` | 新增 `_ensure_proxy_ready()`（委托真源 `ensure_ready`）；采集入口由「未运行→exit 1+通知」改为「ensure 失败→跳过 exit 0」；`cmd_collect` 的 attach 失败点补**重连前 ensure + 重试一次**（CL151 的 CDP 断连重连点）；删除 `_notify_flclash_required()` |

测试（`tests/`）：`test_flclash_proxy.py`（`-g` 与 policy 一致性断言，防再漂移）、`test_twitter_cron.py`（`test_flclash_start_not_ready_skips_round`：exit 0 + 跳过文案 + 不进采集 + 无残留 pid）、`test_twitter_collector.py`（新增 `TestProxyEnsureSkip` 三例：跳过不采集不通知 / 委托真源 / 真源异常返回 False）。
全量结果：`316 passed, 2 deselected`（非 selenium，`--ignore test_cli/test_selenium`）。

## 3. SC 实测（2026-10-24 20:59–21:05，真机）

| SC | 前置 | 命令 | 实测 |
|:---|:---|:---|:---|
| SC2 | FlClash 停 + twitter.json 1.4h（节流期内） | `bash scripts/twitter-collector-cron.sh` | `跳过: twitter.json 生成于 1.4h 前`；exit 0；FlClash 仍停（未启动、未告警） |
| SC4 | FlClash 停 + 就绪判据指向死端口 7899 且预算 2s | `TWITTER_FLCLASH_PORT=7899 TWITTER_FLCLASH_READY_TIMEOUT=2 bash scripts/twitter-collector-cron.sh --force` | `❌ 2s 内 7899 未 LISTEN` → `⏸️ 跳过本轮: FlClash 代理未就绪`；exit 0；未进采集；twitter.json 未变 |
| SC4b + SC1 | FlClash 停、**9222 已活**（浏览器常驻） | `bash scripts/twitter-collector-cron.sh --force` | `[flclash] 启动: open -g -a FlClash` → `✅ 已就绪 (7890 LISTEN)` → 10 账号采集 → `✅ 写盘 (67 条)` + commit `518e548` + push 成功 → `✅ FlClash 已释放`；exit 0；日志中 FlClash 通知次数 = 0；9222 实例未被杀 |

说明：SC4 首次尝试用「预算 1s」模拟失败不成立 —— FlClash 冷启动 1s 内即 LISTEN（`✅ 已就绪`），于是正常进入采集；改用**死端口**才能稳定构造「起得来但不可达」。

## 4. 与 CL151 的两处差异（已在回执中声明）

1. **进程判据**：CL151 建议 `macosx service check --json` → `decisions[FlClash].found`；本仓保留 `pgrep -x` ∪ 应用路径双判据。理由：`macosx` 只存在于 `~/.local/bin`，**cron PATH 不可见**（实测 `env -i PATH=… sh -lc 'command -v macosx'` 为空），改用需硬编码绝对路径并承担每次 1.3s（降级时 20s）子进程开销；且 2026-10-09 已把 pgrep 双判据收敛为本仓唯一真源（防 `osascript … 'quit app "FlClash"'` 自命中）。端口判据两侧同源（7890）。
2. **预算**：CL151 例给 90s；本仓沿用 `READY_TIMEOUT=180s`（对齐上游 `verify.wait`，冷启动实测 1–30s，180s 留足余量）。

## 5. 观察项

- **O-1** 跳过语义的可见性：代理长期起不来时表现为「X 数据不更新」，靠 `collect-report` 日报的 `X 热点` 行与采集日志定位；如需显式提醒，可在日报里加「本机代理状态」行（未做）。
- **O-2** 采集后释放与用户日常使用：本批保留「仅释放本脚本拉起的实例」；用户自行开的 FlClash 不会被关。
- **O-3** `flclash_proxy.py::notify_required()` 现在无人调用（保留函数，`notify` 子命令仍在）；R3「只保留 FlClash 侧超时重启一条通知」据此成立。
