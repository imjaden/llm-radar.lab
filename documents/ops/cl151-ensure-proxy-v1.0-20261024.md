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
| 代理就绪 | FlClash 在运行 **且** 7890 可连（CL151 §2） | 未运行 → `open -g -a FlClash` 后轮询 `is_port_listening(7890)`；**已在运行 → 只判进程，不探端口**（真源 `ensure_ready` 的 `already_running` 短路） | ⚠️ 端口判据只覆盖「本轮拉起」分支：「在运行但 7890 关闭」不门禁（→ §4 差异 3 / O-6 待决策）；进程判据用 pgrep 双判据（→ §4 差异 1） |
| 开启命令 | `open -g -a FlClash`（禁 `service restart`） | `START_CMD=('open','-g','-a','FlClash')` | ✅（此前漏 `-g`，本批修正，见 §2-1） |
| CDP 9222 | 只代表浏览器在，不能当代理就绪 | 代理判定不读 9222；SC4b 实测「浏览器在 + 代理停」仍会拉起 | ✅ |

禁止项核对：① 不反向发 FlClash 通知 —— 采集入口**已删除** `_notify_flclash_required()` 调用（本地通知也不发）；② 不把「未运行」当异常 —— 就绪失败改为 `⏸️ 跳过本轮`、exit 0、不计连败；③ 不每轮无条件启动 —— 节流/无目标时根本不进入 ensure。

## 2. 代码改动

| # | 文件 | 改动 |
|:--|:---|:---|
| 1 | `scripts/flclash_proxy.py` | `START_CMD` 加 `-g`（对齐上游 policy `open -g -a FlClash` 与 CL151；此前本仓漂移为 `open -a`） |
| 2 | `scripts/twitter-collector-cron.sh` | ensure 失败由 `exit 1` → `⏸️ 跳过本轮` + `exit 0`（跳过 ≠ 失败） |
| 3 | `scripts/twitter-collector.py` | 新增 `_ensure_proxy_ready()`（委托真源 `ensure_ready`）；采集入口由「未运行→exit 1+通知」改为「ensure 失败→跳过 exit 0」；`cmd_collect` 的 attach 失败点补**重连前 ensure + 重试一次**（CL151 的 CDP 断连重连点）；删除 `_notify_flclash_required()` |

测试（`tests/`）：`test_flclash_proxy.py`（`-g` 与 policy 一致性断言，防再漂移）、`test_twitter_cron.py`（`test_flclash_start_not_ready_skips_round`：exit 0 + 跳过文案 + 不进采集 + 无残留 pid；另断言日志里出现 `open -g -a FlClash` 且**不得**出现 `无法访问 X`）、`test_twitter_collector.py`（`TestProxyEnsureSkip` 四例：跳过不采集不通知 / 委托真源 / 真源异常返回 False / 非 Darwin 恒 True 且不执行外部命令；`TestAttachReconnect` 四例：attach 失败恰好重试一次 / 重试成功后继续采集写盘 / ensure 不就绪时不重试 / 非 attach 模式不 ensure 不重试）。
全量结果：`321 passed, 2 deselected`（非 selenium，`--ignore test_cli/test_selenium`；三件针对性复跑 `142 passed`）。

## 2b. 评审反馈闭环（2026-10-24 21:40，CONDITIONAL PASS 86/100 → Q-1/Q-2 已修）

评审提出两个真问题，均按推荐修复并真机验证：

| 项 | 问题 | 修复 | 真机证据 |
|:---|:---|:---|:---|
| Q-1（SEC-1 / LR-SEC-023） | `ensure_ready()` 在「已在运行」分支直接返回 ok、**不探 7890**；CL151 §3 要求 `port_open and found`。后果：代理暂停/端口未起时判「就绪」⇒ 整轮抓取失败（表现成「未找到 tweet 元素」，易误判登录态/风控） | 新增 `RUNNING_PORT_GRACE=10s`：已在运行但端口不通 ⇒ 短预算等待后返回 `not_ready(reason=port_closed)`；wrapper 取消「在运行就直接返回」的短路，改为**始终 ensure + was_running 决定归属**（不重复拉起、不误释放）；主采集同步改为「无论是否在运行都 ensure」，并用 `started` 语义决定 `_flclash_owned`（此前若在运行则不会走到这段，改后必须靠 was_running 防误杀） | `python3 scripts/flclash_proxy.py ensure --port 7899`（FlClash 在跑、端口关）⇒ `{"ok": false, "reason": "port_closed", "pids": [67192, 67199]}`，10s 内不可达告警，**未二次拉起**（实例数仍 1） |
| Q-2（DOC-2） | `TWITTER_FLCLASH_ENSURE=0` 时 python 入口仍会 ensure 拉起，而释放只在 wrapper 的 owned 分支 ⇒ 可能「拉起后常驻」 | wrapper 在 ENSURE=0 时注入 `TWITTER_PROXY_NO_ENSURE=1`；`_ensure_proxy_ready()` 在该模式下**只探测（进程 ∧ 端口）不拉起** | `TWITTER_FLCLASH_ENSURE=0 … --force` ⇒ 日志 `ℹ️ TWITTER_PROXY_NO_ENSURE=1, 只探测不拉起: 未就绪` → `⏸️ 跳过本轮`，exit 0，代理**未被拉起** |

新增回归：`test_ensure_ready_running_but_port_closed_is_not_ready`（真源）、`test_flclash_running_but_port_closed_skips_round`（cron 编排）、`test_no_ensure_mode_only_probes`（采集器）、`test_already_running_flclash_is_never_owned`（改为「仍验端口但不接管」）。全量 **324 passed, 2 deselected**。

## 3. SC 实测（2026-10-24 20:59–21:05，真机）

| SC | 前置 | 命令 | 实测 |
|:---|:---|:---|:---|
| SC2 | FlClash 停 + twitter.json 1.4h（节流期内） | `bash scripts/twitter-collector-cron.sh` | `跳过: twitter.json 生成于 1.4h 前`；exit 0；FlClash 仍停（未启动、未告警） |
| SC4 | FlClash 停 + 就绪判据指向死端口 7899 且预算 2s | `TWITTER_FLCLASH_PORT=7899 TWITTER_FLCLASH_READY_TIMEOUT=2 bash scripts/twitter-collector-cron.sh --force` | `❌ 2s 内 7899 未 LISTEN` → `⏸️ 跳过本轮: FlClash 代理未就绪`；exit 0；未进采集；twitter.json 未变 |
| SC4b + SC1 | FlClash 停、**9222 已活**（浏览器常驻） | `bash scripts/twitter-collector-cron.sh --force` | `[flclash] 启动: open -g -a FlClash` → `✅ 已就绪 (7890 LISTEN)` → 10 账号采集 → `✅ 写盘 (67 条)` + commit `518e548` + push 成功 → `✅ FlClash 已释放`；exit 0；日志中 FlClash 通知次数 = 0；9222 实例未被杀 |

说明：SC4 首次尝试用「预算 1s」模拟失败不成立 —— FlClash 冷启动 1s 内即 LISTEN（`✅ 已就绪`），于是正常进入采集；改用**死端口**才能稳定构造「起得来但不可达」。
文案修订（2026-10-24 评审）：上表沿用实测原文（`❌ … 未 LISTEN, 无法访问 X`）；评审后该行改为 `⏸️ … 未 LISTEN, 本轮跳过 (不计失败; CL151)`，语义与退出码不变（exit 0），仅去掉易被日志侧误判为异常的 `❌ … 无法访问 X` 措辞。

## 4. 与 CL151 的三处差异（已在回执中声明）

1. **进程判据**：CL151 建议 `macosx service check --json` → `decisions[FlClash].found`；本仓保留 `pgrep -x` ∪ 应用路径双判据。理由：`macosx` 只存在于 `~/.local/bin`，**cron PATH 不可见**（实测 `env -i PATH=… sh -lc 'command -v macosx'` 为空），改用需硬编码绝对路径并承担每次 1.3s（降级时 20s）子进程开销；且 2026-10-09 已把 pgrep 双判据收敛为本仓唯一真源（防 `osascript … 'quit app "FlClash"'` 自命中）。端口判据两侧同源（7890）。
2. **预算**：CL151 例给 90s；本仓沿用 `READY_TIMEOUT=180s`（对齐上游 `verify.wait`，冷启动实测 1–30s，180s 留足余量）。
3. **就绪判据的两分支**（2026-10-24 评审补记）：CL151 §3 口径是 `port_open(7890) and found`，**两个分支都探端口**；本仓 `ensure_ready` 在 `is_running()` 为真时**短路返回 `ok=True`、不再探 7890**（对齐上游 policy「已在运行 → 直接复用」语义，也是 `llm-radar-collector.py` 海外源共用同一真源的原因）。后果：`FlClash 在运行但 7890 关闭`（暂停代理 / 改端口 / 拉起后端口尚未 LISTEN 的窗口）**不会被判未就绪** ⇒ 本轮继续采集 ⇒ 全部 target 网络失败 ⇒ `evaluate_results` 走「本轮无可用数据」`exit 1`（= 记失败），与 R1「不当异常」的意图相反。修复需要同时改真源分支与包装层归属判定（`ensure --json` 读 `started` 才能保住「只释放自启实例」），属跨项目口径变更 ⇒ 挂 O-6 待决策（建议 CL152 处理）。

## 5. 观察项

- **O-1** 跳过语义的可见性：代理长期起不来时表现为「X 数据不更新」，靠 `collect-report` 日报的 `X 热点` 行与采集日志定位；如需显式提醒，可在日报里加「本机代理状态」行（未做）。
- **O-2** 采集后释放与用户日常使用：本批保留「仅释放本脚本拉起的实例」；用户自行开的 FlClash 不会被关。
- **O-3** `flclash_proxy.py::notify_required()` 现在无人调用（保留函数，`notify` 子命令仍在）；R3「只保留 FlClash 侧超时重启一条通知」据此成立。
- **O-4** `open -g` 的用户可感知副作用（2026-10-24 评审补记）：`-g` 只保证**不抢焦点/不激活**，FlClash 是常规 app（`Info.plist` 无 `LSUIElement` ⇒ Dock 图标仍会出现）。更关键的是本机 app 带 `com.apple.quarantine` 且为 adhoc 签名（`codesign -dv` → `Signature=adhoc`；`spctl -a -vv` → `rejected`）：**FlClash 升级/重装后首次拉起若需用户在 GUI 确认「仍要打开」，cron 侧无交互 ⇒ ensure 超时 ⇒ 每轮静默跳过**（正是 O-1 的不可见区）。缓解：升级后手工启动一次并确认；日报建议带代理状态行。
- **O-5** `TWITTER_FLCLASH_ENSURE=0` 的语义已漂移（评审补记）：该开关现在只停用**包装层编排**；`twitter-collector.py` 入口无条件 `_ensure_proxy_ready()` ⇒ 仍会拉起 FlClash，而包装层不接管（`OWNED_FLCLASH=0`）⇒ 本轮**不释放** ⇒ FlClash 常驻，与「默认关闭、按需开启、用后释放」不符。生产 cron 未设该变量（默认 1），属潜在路径；若确认要保留该开关，应让 python 侧在 `=0` 时退化为「只探测不拉起」。
- **O-6** 「在运行但 7890 不可连」不门禁（= §4 差异 3）：待决策是否把端口判据下推到 `already_running` 分支（`already_running` + 端口不通 ⇒ 短预算等待/直接判未就绪）+ 包装层改用 `ensure --json` 读 `started` 维持归属判定。

## 6. 评审修订（2026-10-24，review profile）

| # | 改动 | 理由 |
|:--|:---|:---|
| 1 | `scripts/twitter-collector-cron.sh`：头注释与启动回显 `open -a FlClash` → `open -g -a FlClash`；未就绪行 `❌ … 无法访问 X` → `⏸️ … 本轮跳过 (不计失败; CL151)` | 日志与真源命令一致；跳过语义下不再出现「无法访问 X」这类异常文案（防日志侧误判失败） |
| 2 | `tests/test_twitter_collector.py` 新增 `TestAttachReconnect` 4 例 + 非 Darwin 1 例；`tests/test_twitter_cron.py` 增 `-g` 日志断言与 `无法访问 X` 禁现断言 | 复跑证明：补测前把 attach 重连分支整段删掉，119 例全绿（零覆盖）；补测后 3 个变异（删重连/非 attach 也重试/重连前不 ensure）全部变红 |
| 3 | 本文 §1/§2/§4/§5 修订 + 回执 §两处差异 → 三处 | 就绪判据分支差异与 `ENSURE=0` 语义漂移此前未声明，属文档失真 |
