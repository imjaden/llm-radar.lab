# X 采集登录态持久化（cron 拉起 Chrome 读不到 keychain）记录

> 涵盖 2026-10-23 的排查、根因、修复与验收证据。现象 = cron 跑 X 采集长期「10 账号全未找到 tweet 元素 / 登录态失效」，
> 人工重登后过几小时又失效；`data/twitter.json` 自 2026-10-21 18:02 起冻结。
> 结论 = 与 Twitter、与 cookie 过期都无关；是 **cron 拉起的 Chrome 落在 macOS 后台安全会话，读不到 login keychain，
> 解不开 v10 加密的 cookie**。修复 = 调试 Chrome 改由 launchd 在 GUI(Aqua) 会话常驻，cron 只 attach。

---

## 1. 现象与初判陷阱

| 项 | 实测 |
|:---|:---|
| 采集器日志 | 累计 214 次「本轮无可用数据」、2313 条「未找到 tweet 元素」、偶发 `url=https://x.com/i/jf/onboarding/web?mode=login&redirect_after_login=…` ⇒ `❌ 登录态失效` exit 2 |
| 数据 | `data/twitter.json` generated_at 停在 `2026-10-21T10:02:28Z`（= 18:02 CST） |
| cookie DB | `~/chrome-twitter-cdp/Default/Cookies` 里 `auth_token`/`ct0`/`twid` **齐全**，创建 2026-10-23 10:23，过期 2027 |

陷阱：既有排查口径「cookie 总数 0（无 auth_token/ct0）⇒ 需人工重登」只覆盖了「已丢失」这一半；
本次 cookie 明明在盘上、且未过期，仍报登录态失效 ⇒ **必须再问一句「这个浏览器是谁拉起的」**。

## 2. 根因

macOS 上 Chrome 的 cookie / token 以 v10 形式落盘，密钥来自 login keychain 的 `Chrome Safe Storage`
（新版另经 access group `EQHXZ8M8AV.com.google.Chrome.unexportable-keys`，实测 secd 查询即此组）。
cron（vixie cron，launchd 系统域 → setuid）拉起的进程落在后台安全会话，拿不到 keychain：

```
[com.apple.securityd:atomicfile] create /Library/Keychains/System.keychain.sb-…: Permission denied
[com.apple.securityd:security_exception] MacOS error: -25337
[com.apple.securityd:security_exception] CSSM Exception: -2147414007 CSSMERR_DL_OS_ACCESS_DENIED
Failed to decrypt token for service AccountId-109824743945630652821
```

⇒ 解不开 cookie ⇒ x.com 视作未登录（部分页重定向 login 墙，其余页首屏无 tweet）⇒ 采集器判登录态失效、不写盘。
GUI 会话拉起的同一 profile 无以上任何报错 ⇒ 对外正常。所以「重登一次能好、下一轮又坏」是必然。

## 3. 判别证据（同一 profile，2026-10-23 10:20–10:30）

| # | 判据 | 命令 | 结果 |
|:--|:---|:---|:---|
| 1 | 盘上登录态 | 读 `Default/Cookies`（只查 name/expires，不打印值） | auth_token/ct0/twid 各 1，未过期 |
| 2 | GUI 实例 | `curl -s 127.0.0.1:9222/json/list` | `page \| Home / X \| https://x.com/home`（已登录） |
| 3 | keychain 拒绝 | `log show --start <ts> --end <ts+40s> --predicate 'process == "Google Chrome"' \| grep -cE "security_exception\|ACCESS_DENIED"` | cron 拉起 = **4**；GUI 拉起 = **0** |
| 4 | 解密失败 | 同上窗口 `grep -c "Failed to decrypt"`；或 `grep -c "Failed to decrypt" /tmp/twitter-chrome.log` | cron 拉起 = 有（每轮 `:20:0x` 一条，共 11 次）；GUI 拉起 = 0 |

自然实验（最强证据）：2026-10-23 11:20 那轮 cron **成功**（`写盘 data/twitter.json (98 条推文)`），
唯一差别是当时 9222 上恰好有一个 10:22 人工（`open -na …`，GUI 会话）拉起的实例，wrapper 走了
「外部常驻实例，复用、不释放」分支 ⇒ 同一条 cron 命令、同一个 profile，只换「谁拉起 Chrome」结果就反转。

**证据强度边界（评审注记 2026-10-23）**：判据 3/4 是「同一时段、同一 profile、不同拉起方」的对照观测，
不是解密实验；「keychain 拒绝 → cookie 解不开」这一步是机制推断（v10 密钥取自 login keychain 的
`Chrome Safe Storage`），未做直接取证。另外 `Failed to decrypt token for service AccountId-…` 是 Chrome
**账号 token** 的解密失败日志，与 cookie 解密失败同源但并非同一对象，引用时不要当成“cookie 解密报错”的直接证据。
补强方式（一次即可闭环）：在 cron 会话内（`launchctl submit`/`at` 拉起的命令）执行
`security find-generic-password -s "Chrome Safe Storage" -w`，与 GUI 终端同命令对照 —— 一次成功 / 一次 denied
即从「对照观测」升级为「直接因果」。当日未做此步，故本文档结论按「强对照证据 + 机制推断」表述。

## 4. 修复

**做法**：不再由 cron 拉起/关闭调试 Chrome，改为 launchd 在 `gui/<uid>` (Aqua) 会话常驻；cron 只 attach。

- `~/Library/LaunchAgents/com.jaden.llm-radar-twitter-chrome.plist`
  - `RunAtLoad` + `KeepAlive(true)` + `ThrottleInterval 30` + `LimitLoadToSessionType=Aqua` + `ProcessType=Interactive`
  - 参数：`--remote-debugging-port=9222 --user-data-dir=/Users/jadenli/chrome-twitter-cdp
    --window-position=-1900,-297 --window-size=880,1000 https://x.com/home`
  - 日志仍写 `/tmp/twitter-chrome.log`（与历史诊断路径连续）
- 安装/重载脚本：gitignored `cache/install-twitter-chrome-agent.sh`（关旧实例 → bootout 确认 → bootstrap 重试 →
  等 9222 → 无 page target 则 `PUT /json/new` 补 → 打印 state/pid/CDP/页面）。**必须在 Terminal.app 执行**：
  hermes 网关会话对 `launchctl bootstrap|submit` 有硬门禁。
- 采集器与 wrapper **零改动**：`scripts/twitter-collector-cron.sh` 已有「9222 已就绪且无 pidfile ⇒ 外部常驻实例，
  复用不杀」，故不再自己拉起、不再 `kill`。

### 4.1 两个必须记住的坑

1. **attach 需要至少一个 page target**。不带 URL 启动的 Chrome 可能 0 个 target ⇒ chromedriver 报
   `session not created: cannot connect to chrome at 127.0.0.1:9222 … unable to discover open page`，
   采集器直接 `❌ 无法连接调试 Chrome`（比「登录态失效」更易误判）。修法：plist 参数末尾带 URL；临时救场
   `curl -s -X PUT 'http://127.0.0.1:9222/json/new?https://x.com/home'`。
2. **改 plist 必须 bootout + bootstrap 重载**（launchd 缓存 job 定义）；`Bootstrap failed: 5: Input/output error`
   的真实含义是「job 未卸干净就 bootstrap」（竞态），不是 plist 坏了。

## 5. 验收（2026-10-23 13:26–13:29 实测）

| 断言 | 结果 |
|:---|:---|
| `launchctl print gui/501/com.jaden.llm-radar-twitter-chrome` | `state = running`、`pid = 8334`、`runs = 2`、`last exit code = 0` |
| launchd 实例启动窗口 keychain 异常 | `security_exception|ACCESS_DENIED|Failed to decrypt` = **0** |
| KeepAlive 自愈 | `kill -TERM 7866` → 4s 内重拉为 8334、`runs` 1→2，**重启后 `/json/list` 仍是 `Home / X`**（plist URL 参数已生效、登录态不随重启丢失） |
| 端到端采集 | `bash scripts/twitter-collector-cron.sh --force` → 「9222 已就绪 (外部常驻实例), 复用, 不释放」+ 10 账号 × **30 条 = 300** + `✅ 写盘` + `✅ push 成功` + exit 0 |
| 收尾 | `cache/pids/` 空、pid 8334 未变（未被采集器杀）；`git rev-list --left-right --count origin/main...HEAD` = `0 0` |

## 6. 复跑清单

```bash
# 1) 认领与自愈
launchctl print gui/$(id -u)/com.jaden.llm-radar-twitter-chrome | grep -E "state|pid|runs|last exit code"

# 2) keychain（必须绑定「实例启动窗口」；空闲时段跑 --last 10m 必然 0，不能作为验收证据）
#    ⚠️ 会 kill 常驻 Chrome（KeepAlive 会重拉），只在 :20/:40 采集槽位之外执行
launchctl kickstart -k gui/$(id -u)/com.jaden.llm-radar-twitter-chrome && sleep 10
log show --last 30s --predicate 'process == "Google Chrome"' | grep -cE "security_exception|ACCESS_DENIED|Failed to decrypt"

# 3) 登录态
curl -s 127.0.0.1:9222/json/list | grep -E '"type": *"page"' -A2

# 4) 端到端
bash scripts/twitter-collector-cron.sh --force
python3 -c "import json;d=json.load(open('data/twitter.json'));print(d['generated_at'],len(d['targets']),sum(len(t['tweets']) for t in d['targets']))"
```

### 6.1 定时留档（校验脚本）

- 脚本：`~/.hermes/profiles/ops/scripts/llm-radar-twitter-login-verify.py`（`no_agent`，零 LLM）；
  记录：`cache/records/twitter-login-persistence.log`（gitignored，append-only）；`deliver=local` 只存档不发飞书。
- **调度实况（评审 2026-10-23 核对 ops `cron/jobs.json`）**：该脚本目前只有两个 **一次性** job —
  `llm-radar-twitter-login-verify-1720`（`be460122844c`，`last_status=error`，已 disabled）与
  `...-1920`（`9a5c61eca6db`，`last_status=ok`，已 disabled）。**没有常驻周期 job**，即「定时留档」实际只发生在
  人工安排的两个时点；要持续留档须另建 cron（调度属 `AGENTS.md` Ask First 面，本记录不动）。
- 四项校验：数据（10 账号且每账号 >0、`generated_at` 年龄）、`git origin/main...HEAD = 0 0`、
  调试 Chrome 主进程存活、CDP 有 page target。
- **年龄阈值 `FRESH_HOURS=6.5`，必须大于 5h 节流**。X 侧是「每小时 :20 尝试 + `twitter.json` < 5h 跳过」⇒
  正常年龄上限 ≈ 5h + 一轮耗时。2026-10-23 17:35:45 首次触发时阈值误写 2h，记录行是
  `data: generated_at=2026-10-23T05:28:36Z age=4.1h … → NG`、`verdict: FAIL`（17:20 槽位在 3.9h 被正常节流跳过：
  wrapper 日志 `[twitter-cron] 跳过: twitter.json 生成于 3.9h 前`，18:20 仍跳 4.87h，19:20 才真采 5.87h）；
  同轮其余三项全 OK。已改 6.5h，17:46:27 重测 PASS（4.3h / 300 条 / `0 0` / pid 8334 / page 1），
  19:35:45 再测 PASS（0.2h / 102 条 / 同一 pid）。
- **该常量只对 X 侧成立，不能照搬到主采集**：主采集节流是 6h（`llm-radar-collector.py:1898` `hours_since < 6`），
  6.5h 仅余 0.5h。`collector.log` 实测峰值：`01:40 距上次成功采集仅 6.0h，跳过` → `02:40` 才真采（≈7.0h）；
  告警在 `:55` 采样，最紧一次采样 ≈ 6.25h。结论：主采集侧应取 7.5h（6h + 1 轮 + 槽位抖动），见
  `collect-report-notify-v1.0-20261023.md` §3.1。同理，本脚本 docstring 第 12 行仍写 `< 2h`（改常量时未同步注释），
  属待修的文字漂移，不影响判据。
- 槽位推算口令：`generated_at + 5h` 之后的**首个 :20 才真采**（例：13:28 生成 → 18:20 仍跳过(4.87h) → 19:20 采(5.87h)）。

## 7. 观察项

- **O-1 节流与本修复的关系**：X 侧 5h 节流不变（`:20` 每小时尝试、`twitter.json` < 5h 跳过），所以「每小时都能看到采集」
  仍不成立，正常间隔 5–7h；判断回归不要用「今天只跑了一次」当证据，也不要给新鲜度校验设 ≤5h 的阈值
  （否则每一个被节流的整点都会被误判为失败）。
- **O-2 崩溃兜底**：LaunchAgent KeepAlive 负责重拉；若 Chrome 连续崩溃退出（last exit code 非 0 且 runs 猛增），
  `ThrottleInterval 30` 会限速，需人工看 `/tmp/twitter-chrome.log`。
- **O-3 登录态真实过期**：cookie 到 2027 年才过期；若未来真登出，仍按老办法在有头窗口登一次（`lr chrome` 或
  `open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir=$HOME/chrome-twitter-cdp https://x.com/login`），
  新实例会立即读到，不需要改代码。
- **O-4 chromedriver 版本随 Chrome 走（两处缓存，缺一即查）**：Chrome 自动升级后需补同 major 的 driver。
  本机有两个独立 driver 缓存，分别服务两条采集链，**只补一个会留下半瘫**：
  - X 侧 attach：`~/.cache/selenium/chromedriver/mac-arm64/`（2026-10-23 补 `156.0.8078.47`，11:26）；
  - 主采集（webdriver_manager）：`~/.wdm/drivers/chromedriver/mac-arm64/`（同日补 `156.0.8078.47`，19:12）。

  实证代价：2026-10-23 09:40–18:40，主采集每轮 `chromedriver 主版本 154 与本机 Chrome 156 不匹配` →
  `❌ Selenium 初始化失败` → `抓取完成，0/6 个源成功`，连续 11 轮，快照 `generated_at` 冻结 03:02→11:03→19:03。
  即「Chrome 升级 → driver 跟随」必须是巡检项（建议纳入 `llm-radar-collect-watch` 的触发条件，见该文档 §6 O-7）。
- **O-5 常驻 CDP 的本地攻击面（安全）**：修复把「只在采集窗口存在的调试 Chrome」变成 **24/7 常驻 + 带真实登录态**。
  已核 `lsof`：`127.0.0.1:9222 (LISTEN)` 仅回环，外网不可达；但**本机任意进程**（含任意脚本/包安装钩子）都能 attach
  CDP，用 `Network.getAllCookies` 取 x.com cookie、或直接代发操作 ⇒ X 账号接管面，暴露时长从「几分钟/小时」变成「全天」。
  现有 O-1~O-4 未覆盖此风险。可选缓解（需权衡采集窗口对齐成本）：
  (a) 专用 macOS 账号跑该 Chrome（跨账号 loopback 仍可达，但配合 pf/防火墙可收窄）；
  (b) 放弃 KeepAlive，改 `StartCalendarInterval` 在 `:15–:25` / `:35–:45` 两个窗口拉起（缩短暴露，但要改 cron attach 假设）；
  (c) 接受风险，但必须在交接文档与 `documents/README.md` 条目里显式写明「本机存在常驻调试端口 + 有效登录态」。
  本次评审只要求 (c) 落地（已在 §8 与附录 A 标注），(a)/(b) 属需用户决策项。
- **O-6 窗口可见性/遮挡是一条独立的空采路径**：`cache/logs/twitter-collector/twitter.log` 中有一轮失败原因是
  `页面处于 hidden (窗口被最小化/隐藏) ⇒ 首屏不渲染, 采集必然为空`（与 keychain 无关）。plist 用
  `--window-position=-1900,-297` 依赖副屏存在；副屏拔掉/排列变化后整窗可能移出可视区或被判定 hidden。
  现有校验只数 `page target`，不读页面可见性/当前 URL ⇒ 这类回归不会被提前发现。
  建议给 verify 脚本加两条只读判据：CDP `Runtime.evaluate` 取 `document.visibilityState === 'visible'`，且
  `location.href` 不含 `/login`（两行代码，不引入写操作）。
- **O-7 定义未入库（可复现性）**：plist（`~/Library/LaunchAgents/…`）与安装脚本（`cache/`，gitignored）都不在 repo，
  重建只能靠本文文字。已把 plist 全文附在 §附录 A；安装脚本建议同样贴入本记录或 `documents/ops/`（无凭据，可入库）。

## 8. 变更清单

| 变更 | 位置 | 是否入库 |
|:---|:---|:---|
| LaunchAgent 定义 | `~/Library/LaunchAgents/com.jaden.llm-radar-twitter-chrome.plist` | 否（用户目录；全文见附录 A） |
| 安装/重载脚本 | `cache/install-twitter-chrome-agent.sh` | 否（cache/ gitignored） |
| chromedriver 156 | `~/.cache/selenium/chromedriver/mac-arm64/156.0.8078.47/` + `~/.wdm/drivers/chromedriver/mac-arm64/156.0.8078.47/` | 否 |
| 本记录 | `documents/ops/twitter-login-persistence-v1.0-20261023.md` | 是 |
| 采集器 / wrapper / 前端 | 无改动 | — |

**安全影响（必须随记录交接）**：本次修复的代价是 `127.0.0.1:9222` 上的调试 Chrome **全天常驻且带有效 X 登录态**，
本机任意进程可 attach 并读写该会话（详见 O-5）。旧形态只在采集窗口内暴露。这是有意接受的运维取舍，
不是遗漏；若后续要收窄，按 O-5 的 (a)/(b) 方案另开变更。

---

## 附录 A：LaunchAgent 定义（全文，可直接还原）

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jaden.llm-radar-twitter-chrome</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Applications/Google Chrome.app/Contents/MacOS/Google Chrome</string>
        <string>--remote-debugging-port=9222</string>
        <string>--user-data-dir=/Users/jadenli/chrome-twitter-cdp</string>
        <string>--window-position=-1900,-297</string>
        <string>--window-size=880,1000</string>
        <string>https://x.com/home</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>ThrottleInterval</key>
    <integer>30</integer>
    <key>LimitLoadToSessionType</key>
    <string>Aqua</string>
    <key>ProcessType</key>
    <string>Interactive</string>
    <key>StandardOutPath</key>
    <string>/tmp/twitter-chrome.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/twitter-chrome.log</string>
</dict>
</plist>
```

还原步骤：`cp` 到 `~/Library/LaunchAgents/` → `launchctl bootout gui/$(id -u)/com.jaden.llm-radar-twitter-chrome`
（未加载则跳过）→ `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jaden.llm-radar-twitter-chrome.plist`
→ 按 §6 第 1/3 项验收。注意 `/tmp/twitter-chrome.log` 为可预测路径且当前为 `644`（无凭据内容，
已核 `auth_token|ct0|Cookie:` 命中 0），仅作诊断用，勿指望其保密。
