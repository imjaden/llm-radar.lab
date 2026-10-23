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

# 2) keychain（启动窗口内应为 0）
log show --last 10m --predicate 'process == "Google Chrome"' | grep -cE "security_exception|ACCESS_DENIED|Failed to decrypt"

# 3) 登录态
curl -s 127.0.0.1:9222/json/list | grep -E '"type": *"page"' -A2

# 4) 端到端
bash scripts/twitter-collector-cron.sh --force
python3 -c "import json;d=json.load(open('data/twitter.json'));print(d['generated_at'],len(d['targets']),sum(len(t['tweets']) for t in d['targets']))"
```

## 7. 观察项

- **O-1 节流与本修复的关系**：X 侧 5h 节流不变（`:20` 每小时尝试、`twitter.json` < 5h 跳过），所以「每小时都能看到采集」
  仍不成立，正常间隔 5–7h；判断回归不要用「今天只跑了一次」当证据。
- **O-2 崩溃兜底**：LaunchAgent KeepAlive 负责重拉；若 Chrome 连续崩溃退出（last exit code 非 0 且 runs 猛增），
  `ThrottleInterval 30` 会限速，需人工看 `/tmp/twitter-chrome.log`。
- **O-3 登录态真实过期**：cookie 到 2027 年才过期；若未来真登出，仍按老办法在有头窗口登一次（`lr chrome` 或
  `open -na "Google Chrome" --args --remote-debugging-port=9222 --user-data-dir=$HOME/chrome-twitter-cdp https://x.com/login`），
  新实例会立即读到，不需要改代码。
- **O-4 chromedriver 版本随 Chrome 走**：Chrome 自动升级后需补同 major 的 driver
  （2026-10-23 已补 `156.0.8078.47` → `~/.cache/selenium/chromedriver/mac-arm64/`）。

## 8. 变更清单

| 变更 | 位置 | 是否入库 |
|:---|:---|:---|
| LaunchAgent 定义 | `~/Library/LaunchAgents/com.jaden.llm-radar-twitter-chrome.plist` | 否（用户目录） |
| 安装/重载脚本 | `cache/install-twitter-chrome-agent.sh` | 否（cache/ gitignored） |
| chromedriver 156 | `~/.cache/selenium/chromedriver/mac-arm64/156.0.8078.47/chromedriver` | 否 |
| 本记录 | `documents/ops/twitter-login-persistence-v1.0-20261023.md` | 是 |
| 采集器 / wrapper / 前端 | 无改动 | — |
