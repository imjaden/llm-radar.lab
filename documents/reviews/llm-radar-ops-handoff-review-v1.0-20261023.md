# llm-radar 2026-10-23 ops 交接 — review 报告 v1.0

- **日期**：2026-10-23
- **审查者**：Security Reviewer (review profile)
- **级别**：L2（`.review-level.yaml` level: L2，owner Jaden Li）
- **范围**：已 push 历史 `b89b123` / `ae8b6e3` / `bc7fcae`（3 个 docs@ops）+ 当日 auto-push 数据 commit；
  两份新增文档 `documents/ops/twitter-login-persistence-v1.0-20261023.md`、`documents/ops/collect-report-notify-v1.0-20261023.md`
  + `documents/README.md` 索引两行；系统层落地件（LaunchAgent / chromedriver / ops 脚本 / 2 个 cron）只读核对
- **方法**：仓库事实复算（git / 日志 / 产物）+ 系统层只读探针（launchctl / lsof / sqlite 仅查 name·expires / 日志计数）
  + **隔离副本演练**（`cache/scratch/simrepo`，副本内替换 REPO 常量，生产零写入）
- **结论**：**CONDITIONAL PASS — 80/100**（事实与文档基本一致，🟡 项集中在「告警脚本健壮性」与「常驻调试端口风险」）

---

## 1. 结论摘要

1. **事实一致性成立**。本次把关键数字逐条复算：214 次「本轮无可用数据」、2313 条「未找到 tweet 元素」、
   11 次 `Failed to decrypt`、X 侧 300/300 与 98/102、主采集 6/6、`git 0 0`、LaunchAgent `state=running pid=8334 runs=2`、
   cookie `auth_token/ct0/twid` 过期 2027 —— 全部与文档一致（§3）。
2. **根因表述方向正确但需降一档措辞**。keychain 对照（cron 4 次拒绝 / GUI 0 次）+ 11:20 自然实验是强证据，
   但「keychain 拒绝 → cookie 解不开」是机制推断而非直接取证；`Failed to decrypt token for service AccountId-…`
   是 **账号 token** 日志，不是 cookie 解密报错。已在文档补「证据强度边界 + 一次性补证方法」（§4）。
3. **阈值口径存在实质问题**：`FRESH_HOURS=6.5` 对 X 侧（5h 节流）合理，对**主采集（6h 节流）只剩 0.25h 余量**，
   正常态年龄峰值实测 ≈7.0h（`:40` 跳过 → 下一槽才采）。建议分管线取 6.5 / 7.5h（§5）。
4. **发现一处 fail-open 缺陷（脚本侧，优先级最高）**：`age` 解析遇 `...Z` 后缀在 Python 3.9 抛错被吞 ⇒
   `age=None` ⇒ 陈旧告警**静默失效**。隔离副本已复现：30h 前的 `...Z` 快照，`--alert` 输出 0 字节（§5.3）。
5. **安全面新增一条必须交接的风险**：修复把「采集窗口内的调试 Chrome」变成 **24/7 常驻 + 有效 X 登录态 + CDP 9222**，
   本机任意进程可 attach 读 cookie / 代发操作。端口只监听回环（已核），但暴露时长从分钟级变成全天（§6 SEC-1）。
6. **治理合规全部通过**：commit subject 均为 `type@scope: subject`，命名与 `documents/README.md` 既有口径一致，
   `AGENTS.md` / `CLAUDE.md` 当日零改动，历史线性无 force 痕迹（§7）。
7. **需修正项已落地**：两份文档的 4 处事实/口径偏差 + O-5~O-8 已同批修正（§9 已落地清单）。
   脚本侧 5 项（OPS-1~OPS-5）在 ops profile（不在本仓），本报告给 patch 建议，**不代为改动**。

---

## 2. 评分表

| 维度 | 权重 | 得分 | 依据 |
|:---|:---:|:---:|:---|
| 事实一致性（数字/时间/命令可复算） | 30 | 27 | 12 项关键数字全部对上（§3）；扣分点为 17:35 假 FAIL 的年龄口径混用（3.9h vs 记录里的 4.1h）与「定时留档」实况（无周期 job） |
| 根因表述强度 | 20 | 16 | 对照证据强、自然实验设计干净；但机制推断写成结论、`AccountId` 日志被当作 cookie 解密证据、「窗口 hidden」这条独立空采路径未提 |
| 阈值与告警设计 | 20 | 13 | 6.5h 套两条不同节流管线（余量 0.25h）；`age` 解析 fail-open；`首败` 取错语义；driver 不匹配不触发告警；告警/恢复路径生产未触发过 |
| 治理合规（commit/命名/索引/受保护文件） | 15 | 15 | 全通过（§7） |
| 安全（攻击面/凭据/日志） | 15 | 9 | 常驻 CDP 面未在文档体现（已补）；`/tmp` 可预测路径 644 无轮转（低危）；已核日志无凭据串 |
| **合计** | **100** | **80** | **CONDITIONAL PASS** |

---

## 3. 事实核查（逐条复算）

| # | 文档断言 | 复算方式 | 实测 | 判定 |
|:--|:---|:---|:---|:---:|
| F-1 | 累计 214 次「本轮无可用数据」 | `grep -c` `cache/logs/twitter-collector/twitter.log` | 214 | ✅ |
| F-2 | 2313 条「未找到 tweet 元素」 | 同上 | 2313 | ✅ |
| F-3 | `Failed to decrypt` 共 11 次（每轮 `:20:0x` 一条） | `grep -c` `/tmp/twitter-chrome.log` | 11 | ✅ |
| F-4 | `twitter.json` 曾冻结于 `2026-10-21T10:02:28Z` | `git show eff931a~1:data/twitter.json` | `2026-10-21T10:02:28Z` / 300 条 | ✅ |
| F-5 | 11:20 那轮成功写盘 98 条 | `git show eff931a` + twitter.log | 98 条，`eff931a 11:25` `(98 changes)` | ✅ |
| F-6 | 端到端 10 账号 × 30 条 = 300 | `git show 0fd08eb:data/twitter.json` | 10 账号 `[30×10]` = 300，`05:28:36Z`（13:28） | ✅ |
| F-7 | 19:20 槽位再采得 102 条 | `git show 1b2eef8` + 19:35 校验日志 | 102 条，`1b2eef8 19:25` `(102 changes)` | ✅ |
| F-8 | 主采集 6/6 源 | `SCRAPERS` 正则 + `metrics.run_history[-1].source_rate` | 6 个键（qbitai…huggingface），rate 1.0 ⇒ 6/6 | ✅ |
| F-9 | `git rev-list origin/main...HEAD = 0 0` | 直接执行（评审时 + push 后） | `0 0` / `0 0` | ✅ |
| F-10 | LaunchAgent `state=running pid=8334 runs=2 last exit 0` | `launchctl print gui/501/...` | 完全一致（评审时仍为 pid 8334、runs 2） | ✅ |
| F-11 | cookie `auth_token/ct0/twid` 齐全、过期 2027 | 复制 `Default/Cookies` 只查 name/host/expires（不打印值） | `auth_token` 2027-10-23、`ct0` 2027-11-27、`twid` 2027-10-23，共 49 条 cookie | ✅ |
| F-12 | 两处 driver 均补 156 | `ls ~/.wdm/...`、`ls ~/.cache/selenium/...`、Chrome `--version` | 两处都有 `156.0.8078.47`；Chrome 156.0.8078.47 | ✅ |
| F-13 | 两个 cron：`4fb95acd0f81` `0 21 * * *` / `e4bae95a6a40` `55 8-23 * * *`，deliver=feishu | 读 ops `cron/jobs.json` | id/schedule/deliver/no_agent 全部一致 | ✅ |
| F-14 | 17:35 假 FAIL 已修正为 6.5h | `cache/records/twitter-login-persistence.log` | `17:35:45 age=4.1h → NG / FAIL`；`17:46:27 age=4.3h → OK / PASS`；`19:35:45 age=0.2h tweets=102 → PASS` | 🟡 见 DOC-4 |
| F-15 | 「定时留档」 | 读 `jobs.json` | 仅两个 **once** job（`be460122844c` error/disabled、`9a5c61eca6db` ok/disabled），**无常驻周期 job** | 🟡 见 DOC-4 |
| F-16 | plist 参数（RunAtLoad/KeepAlive/ThrottleInterval 30/Aqua/窗口坐标/URL） | `plutil -p` 实读 | 逐项一致；文档附录 A 的 plist 与磁盘 `plutil -p` **语义完全一致**（block 1093B == 文件 1093B） | ✅ |

补充事实（评审新增，写回文档）：

- `127.0.0.1:9222` 仅回环监听（`lsof -nP -iTCP:9222 -sTCP:LISTEN`），外网不可达。
- `cache/pids/` 为空、pid 8334 未被采集器杀 —— 与文档「复用不释放」一致。
- `/tmp/twitter-chrome.log` 2177303B、`644 jadenli:wheel`，`grep -cE "auth_token|ct0=|Cookie:"` = **0**（无凭据串泄漏）。
- `data/overview.json` 当前**不存在**（请求里提到的脏文件清单含它；实际产物集为 snapshot/timestamp/metrics/twitter）。

---

## 4. 根因证据链评估（请求 §3.2）

**已成立（强对照）**：

1. 同一 profile、同一时段，cron 拉起时 `security_exception|ACCESS_DENIED` 计数 4、GUI 拉起 0（判据 3）；
2. `Failed to decrypt …` 11 条全部落在 cron 拉起的实例日志里（判据 4，本次复算 11 ✅）；
3. 11:20 自然实验：同命令同 profile，仅「Who launched Chrome」不同，结果从持续空采翻转为 98 条写盘；
4. 修复后 13:26–13:29 端到端 300 条 + launchd 启动窗口 keychain 异常 0。

**不足以称「直接因果」的部分**：

- 「keychain 不可达 ⇒ v10 cookie 解不开」是机制推断。Chrome 的 v10 密钥确来自 login keychain 的 `Chrome Safe Storage`，
  这一步没有做「cron 会话内显式读取该条目」的对照实验。
- `Failed to decrypt token for service AccountId-109824743945630652821` 是 Chrome **账号 token**（Google 账号同步）的解密失败，
  与 cookie 解密同源（同一 keychain 访问被拒）但**不是同一对象**；把它当「cookie 解密报错」会被挑刺。
- 判据 3/4 的时间窗是 10:20–10:30 的事后取证，当前已不可复跑（`log show` 窗口早已滚过）。

**建议的补证（一次即可闭环，成本 ~2 分钟）**：在 cron 会话内执行
`security find-generic-password -s "Chrome Safe Storage" -w`（可用 `launchctl submit` / `at` 拉起），
与 GUI 终端同一命令对照：一次成功 / 一次 `Permission denied` 即把结论从「强对照」升级为「直接因果」。
已在文档 §3 写入（含「不要把它当成 cookie 解密日志」的措辞提醒）。

**评审另发现一条被漏掉的独立空采路径**：`twitter.log` 中有一轮失败原因是
`页面处于 hidden (窗口被最小化/隐藏) ⇒ 首屏不渲染, 采集必然为空` —— 与 keychain 无关。
plist 通过 `--window-position=-1900,-297` 把窗口放到副屏，副屏拔掉/排列变化后可能整窗移出可视区或被判 hidden。
现有校验只数 `page target`，不读 `document.visibilityState` / 当前 URL ⇒ 这类回归不会提前暴露（SEC-3）。

---

## 5. 阈值口径评估（请求 §3.3）

### 5.1 两条管线的节流事实

| 管线 | 节流 | 来源 | cron 尝试 | 正常年龄峰值 |
|:---|:---|:---|:---|:---|
| X（twitter.json） | 5h | `scripts/twitter-collector-cron.sh:44` `TWITTER_THROTTLE_HOURS=5` | 每小时 `:20` | ≈7h 但只在采后翻转，采样点峰值 ≈6.2h |
| 主采集（snapshot） | 6h | `llm-radar-collector.py:1898` `if hours_since < 6` | 每小时 `:40` | **≈7.0h**（实证 `01:40 6.0h 跳过 → 02:40 采`） |

### 5.2 `FRESH_HOURS=6.5` 的问题

- 告警在 `:55` 采样。跳过判据是 `< 6h`，所以「6.0h 跳过」之后的一次采样 = 6.0 + 0.25 = **6.25h**，
  距 6.5h 只有 **0.25h**；任何 15 分钟级抖动（休眠错过 `:40`、单轮耗时变长、快照写入失败）都会把正常态判成 `stale`。
- 与文档自身推导不一致：X 侧用 `5h + 1.5h = 6.5h`，主采集照同一推导应为 `6h + 1.5h = 7.5h`，却复用 6.5h。
- 反过来看，6.5h 的「缺 1 轮即报」语义是有价值的（今日 09:55 本可 15 分钟内发现），所以两条都成立，
  **但必须在文档写明是哪一种语义**，否则后续运维会把真告警当误报。

**建议**：主采集 7.5h / X 侧 6.5h，分别持有常量；两个脚本目前都写死 6.5 且注释各说各的（漂移点）。

### 5.3 fail-open（本次最实质的缺陷）

`llm-radar-collect-report.py:88-92`：

```python
age = (datetime.now() - datetime.fromisoformat(gen)).total_seconds() / 3600
except Exception: pass   # ⇒ age 保持 None
```

Python 3.9（本机 `python3 -VV` = 3.9.6）对 `2026-10-22T14:22:44Z` 抛 `ValueError`，异常被吞 ⇒ `age=None` ⇒
`alert_reasons()` 里 `f['age'] is not None` 为假 ⇒ **`stale` 永不成立，且日志无痕**。
当前采集器写本地 naive 时间（`2026-10-23T19:15:04.744471`）所以尚未踩到；一旦格式改成 UTC `Z`
（跨机采集、格式统一）主新鲜度检查直接失效。

**实测证据（隔离副本）**：把 `generated_at` 改成 30h 前的 `...Z`，`--alert` 输出 **0 字节**；
同一脚本在 11h naive 时间下正常输出 `数据陈旧：…（11.0h 前，阈值 6.5h）`。

**修法**：`datetime.fromisoformat(gen.replace('Z', '+00:00'))` + tz-aware 比较 + `age is None` 时按陈旧处理（fail-closed）。

### 5.4 `DEGRADED_ALERT=2` / `FAIL_ALERT=3` 的误报漏报判断

- 误报：降级要求 **同源 `consecutive_fails ≥ 3`** 且 `last_result == 'fail'`，单源抖动不会触发；
  `reset` 态不计入（已核今日 techcrunch/help = `reset`）⇒ 2 的取法合理。
- 漏报：`consecutive_fails` 在「全部源被跳过」的轮次**仍会自增**（实测 12:40 连败 4 → 13:40 连败 5 → …→ 18:40 连败 11），
  所以 `FAIL_ALERT=3` 对「全源降级空转」有效；今日事故若告警在，11:40 就达 3，11:55 必响。
- 真正漏报在**触发面**而非阈值：driver 主版本不匹配只作根因行出现，不作触发条件（今日白等 2 轮，OPS-4）。
- 夜间 `0–7` 点静默 × 6h 节流 ⇒ 最长 ≈10h 无信号（O-7，已写入文档）。

---

## 6. 安全审查

### 🔴 无

### 🟡 SEC-1（LR-SEC-020）常驻调试端口 = 全天候会话接管面

**事实**：LaunchAgent `KeepAlive=true` + `RunAtLoad` 让带真实登录态的 Chrome 24/7 常驻，`--remote-debugging-port=9222`
只监听 `127.0.0.1`（已核 lsof），但**本机任意进程**都能 attach CDP：`Network.getAllCookies` 直接取 x.com cookie，
或 `Input`/`Runtime.evaluate` 代发操作 ⇒ 等同 X 账号接管。旧形态只在采集窗口存在该端口，本次修复把暴露时长放大到全天。
两份文档原有的 O-1~O-4 均未覆盖此风险。

**修复建议（按代价排序）**：
1. （最低成本，本次已落地）在文档 + 交接清单里显式登记「本机存在常驻调试端口 + 有效登录态」，让后续任何装机/排障知道这条面；
2. 放弃 24/7：改 `StartCalendarInterval` 在 `:15–:25` / `:35–:45` 两窗拉起，缩短暴露（需重算 wrapper 的 attach 假设）；
3. 专用 macOS 账号承载该 Chrome（跨账号 loopback 仍可达，需配合 pf 收窄）。

**已落地**：`twitter-login-persistence` 新增 O-5 + §8「安全影响」，并把 plist 全文入库（附录 A）。

### 🟡 SEC-2（LR-SEC-021）/tmp 可预测日志路径

`StandardOutPath/StandardErrorPath = /tmp/twitter-chrome.log`：世界可读目录、固定文件名、当前 2.1MB 无轮转。
已核**无凭据串**（`auth_token|ct0=|Cookie:` 命中 0），实际风险是：同机其他用户可读诊断日志；固定路径存在符号链接抢占面
（launchd 以本人身份打开）；长期增长无上限。
**建议**：改 `~/Library/Logs/llm-radar/twitter-chrome.log`（640）+ 启动时按大小截断。属低成本、可选。

### 🟡 SEC-3（LR-SEC-022）留档校验不覆盖「可见性 / 登录墙」

verify 脚本 4 项判据只查 page target 数量（`twitter-login-verify.py:85-97`），不读 `document.visibilityState`，
也不看当前 URL 是否被重定向到 `/login`。今日日志里**真实发生过** `visibility=hidden ⇒ 首屏不渲染 ⇒ 空采`；
`/login` 重定向则是登录态失效的直接信号（脚本第 12 行 docstring 也仍写着过时的 `< 2h`）。
⇒ 结果是「数据 10 账号且非零 + 年龄达标」能兜住，但定位靠人肉翻日志。
**建议**：加两条只读判据（`Runtime.evaluate` 取 `visibilityState`；`location.href` 不含 `/login`），并把 docstring 的 `2h` 改 `6.5h`。

### 🟢 通过项

- 仓库/文档/日志中**未发现 token、key、cookie 值**（文档只引用 name/expires；`AccountId-109824743945630652821` 为公开的账号数字 ID，
  非凭据；`EQHXZ8M8AV.…unexportable-keys` 为 Chrome 的 Team ID 前缀，非密钥）。
- 飞书投递只含计数与时间戳（无账号名、无 URL、无凭据），job_id 暴露可接受。
- ops 脚本只读产物 + 日志尾部；异常时 `exit 0` 并打印 `❌ 报告脚本异常 …`（watchdog 自身不静默挂掉），设计正确。
- 本日无源码/依赖改动 ⇒ 无新增 CVE 面；chromedriver 156 来自同 major 官方分发。

---

## 7. 治理合规

| 项 | 要求 | 实测 | 判定 |
|:---|:---|:---|:---:|
| commit subject | `type@scope: subject` | `docs@ops: 留档 X 采集登录态持久化修复 (…)` / `docs@ops: 修正留档校验阈值 (…)` / `docs@ops: 采集报告飞书模板定稿 (…)`；数据 commit `auto-push@llm-radar: update …`（`AGENTS.md` §11 既定形态） | ✅ |
| 命名口径 | `documents/ops/<topic>-v1.0-YYYYMMDD.md` | 两份新增均符合（与 `linux-deployment-v1.0-20260701.md` 等同构） | ✅ |
| 索引 | `documents/README.md` 收录 | 两行均在「保留原位」段，描述与正文一致（`b89b123` +1 行、`bc7fcae` +1 行） | ✅ |
| 受保护文件 | `AGENTS.md` / `CLAUDE.md` 不改 | `git log --since=2026-10-22 -- AGENTS.md CLAUDE.md` = 空 | ✅ |
| 历史形态 | 禁 force | reflog 仅 `commit` / `merge origin/main: Fast-forward`；`origin/main...HEAD = 0 0` | ✅ |
| 数据产物 | 手工编辑禁止 | 4 个 twitter commit、4 个 data commit 均由采集器产生（`✅ push 成功` 在日志内） | ✅ |
| 文档漂移 | 未回填 details 手册 | 本次未改 `documents/handbooks/*`（建议见 §10 备忘，非阻塞） | ✅ |

---

## 8. 遗漏项评估（O-1~O-4 × 2 份）

| 文档 | O 项 | 评价 | 缺口 |
|:---|:---|:---|:---|
| login-persistence | O-1 节流与修复的关系 | 正确且重要（避免用「今天只跑一次」当回归证据） | — |
| | O-2 崩溃兜底 | 覆盖 KeepAlive/ThrottleInterval | 缺「runs 猛增」的自动告警，只有「人工看日志」 |
| | O-3 真实过期 | 覆盖，操作可行 | — |
| | O-4 driver 跟版 | **只写了 `~/.cache/selenium`**，漏 `~/.wdm`（主采集侧） | 今日 9.4h 事故正是 `.wdm` 侧 154 vs 156 ⇒ 已补（DOC-5） |
| | 未覆盖 | — | **常驻 CDP 攻击面**（SEC-1）、**窗口 hidden 空采**（SEC-3）、**定义未入库**（可复现性） ⇒ 已补 O-5/O-6/O-7 |
| collect-report | O-1 噪音复核 | 合理（3 天观察 DEGRADED=2→3） | 缺「首发告警正文人工核对」这一步 ⇒ 已补 §5 末段 |
| | O-2 夜间盲区 | 覆盖方向对 | 缺与 6h 节流叠加的量化（≈10h）⇒ 已补 O-7 |
| | O-3 热点去重 | 准确（实测两条同名） | — |
| | O-4 信源口径 | 准确（`SCRAPERS` 6 键 vs `source_health` 8 键，残留 techcrunch/help） | — |
| | 未覆盖 | — | **`首败` 语义**（OPS-2）、**指纹变化连发两条**（O-5）、**driver 不匹配不作触发**（OPS-4）、**`age` fail-open**（OPS-1） ⇒ 已补 O-5~O-8 |

**「Chrome 升级 → driver 跟随」是否应纳入巡检：应该，而且这是今日真实事故的成因。**
证据：`collector.log` 09:40 起每轮 `chromedriver 主版本 154 与本机 Chrome 156 不匹配` → `❌ Selenium 初始化失败` →
`抓取完成，0/6 个源成功`，连续 11 轮（09:40–18:40），快照 `generated_at` 冻结 03:02→11:03→19:03。
建议把「日志出现主版本不匹配」直接并入 `alert_reasons`（现成的根因行即告警正文，零新增依赖）。

---

## 9. 发现项与状态

| ID | 级别 | 标题 | 状态 |
|:---|:---:|:---|:---|
| SEC-1 / LR-SEC-020 | 🟡 | 常驻 CDP 9222 = 全天候会话接管面（文档未登记） | ✅ 已在文档 O-5 + §8 登记（风险本身按 (c) 接受，方案 (a)/(b) 待用户决策） |
| SEC-2 / LR-SEC-021 | 🟡 | `/tmp/twitter-chrome.log` 可预测路径、644、无轮转（已核无凭据） | ✅ 文档附录 A 已注明；改 `~/Library/Logs` 属可选改进 |
| SEC-3 / LR-SEC-022 | 🟡 | 留档校验不查 `visibilityState` / `/login` ⇒ hidden 空采不可发现 | ✅ 文档 O-6 已给两条只读判据；脚本待 ops 修 |
| DOC-4 | 🟡 | 17:35 假 FAIL 的年龄口径混用（记录是 4.1h、正文写 3.9h）；「定时留档」实为两个已 disabled 的一次性 job | ✅ 已改为实测日志值并写明调度实况 |
| DOC-5 | 🟡 | O-4 只写 `~/.cache/selenium`，漏主采集的 `~/.wdm` | ✅ 已改写为两处缓存 + 今日 11 轮实证 |
| DOC-6 | 🟡 | `collect-report` §2.1 信源三分支口径不全（缺「（部分失败）」）/ 未写 `reset` 态不计入 | ✅ 已补齐 |
| OPS-1 | 🟡 | `age` 解析 fail-open（`...Z` ⇒ `age=None` ⇒ 陈旧告警静默失效） | ⬜ 待 ops（patch 见 §10） |
| OPS-2 | 🟡 | `首败` 取 `run_history` 窗口内最早失败，非本轮连败起点（演练打出 `首败 10-20`） | ⬜ 待 ops |
| OPS-3 | 🟡 | `FRESH_HOURS=6.5` 同时用于 5h / 6h 两条管线，主采集余量仅 0.25h | ⬜ 待 ops（建议 7.5h 分管线） |
| OPS-4 | 🟡 | driver 主版本不匹配不作触发条件（今日白等 2 轮） | ⬜ 待 ops |
| OPS-5 | 🟢 | `twitter-login-verify.py` docstring 仍写 `< 2h`（改常量未同步注释） | ⬜ 待 ops（纯注释） |
| OBS-5 | 🟢 | 生产 `collect-report-state.json` 从未生成 ⇒ 告警/恢复路径生产未触发（本次用隔离副本演练闭环） | ✅ 文档 §5 已注明 |

---

## 10. 修改意见

### 10.1 已落地（本报告同批 push）

`documents/ops/twitter-login-persistence-v1.0-20261023.md`：

1. §3 增「证据强度边界」：限定「对照观测 + 机制推断」，指出 `AccountId` 日志是账号 token 而非 cookie，给出一次性补证命令；
2. §6 第 2 项：`log show --last 10m` 改为**绑定实例启动窗口**（`launchctl kickstart -k` + `--last 30s` + 采集槽位告警），
   原命令在空闲时段必然 0、不能作验收证据；
3. §6.1：改为记录真实日志值（`17:35:45 age=4.1h FAIL` / `17:46:27 4.3h PASS` / `19:35:45 0.2h 102 条`），
   补「留档调度实况（两个 once job 已 disabled，无常驻 job）」与「6.5h 只对 X 侧成立、docstring 2h 漂移」；
4. §7：O-4 扩为两处 driver 缓存 + 今日 11 轮实证；新增 O-5（CDP 攻击面）/ O-6（hidden 空采 + 校验判据）/ O-7（定义未入库）；
5. §8 + 附录 A：登记录入安全影响，并把 plist 全文入库（`plutil -lint` OK，与磁盘 `plutil -p` 语义一致），附还原步骤。

`documents/ops/collect-report-notify-v1.0-20261023.md`：

6. §2.1 信源三分支 + `reset` 不计入降级；
7. §2.2 增「首败」口径注记与修法（§2.3 标题保持不变）；
8. §3.1/§3.2 新增：阈值余量实测（6.25h vs 6.5h，建议主 7.5h）、`age` fail-open 复现与修法、今日事故反推（09:55 stale / 11:55 fails）；
9. §5 增「评审实测表」（生产只读 + 隔离副本：日报/降级/告警/去重/恢复六行）；
10. §6 新增 O-5（指纹变化连发）/ O-6（driver 不作触发）/ O-7（夜间 10h 盲区）/ O-8（fail-open 优先级最高）。

### 10.2 待 ops（不在本仓，给出 patch）

```python
# OPS-1 llm-radar-collect-report.py:88-92 —— fail-closed 解析
gen_raw = gen.replace('Z', '+00:00')
dt = datetime.fromisoformat(gen_raw)
dt = dt if dt.tzinfo else dt.astimezone()
age = (datetime.now().astimezone() - dt).total_seconds() / 3600
# 并把 alert_reasons 改为: if f['age'] is None or f['age'] > FRESH_HOURS: reasons.append('stale')

# OPS-2 llm-radar-collect-report.py:168-169 —— 本轮连败起点
streak = []
for r in reversed(rh):
    if r.get('success'):
        break
    streak.append(r)
first_fail = (streak[-1].get('time') or '')[:16] if streak else ''

# OPS-3 两个脚本分别持常量：主采集 7.5（6h 节流 + 1 轮 + 抖动），X 侧保持 6.5

# OPS-4 llm-radar-collect-report.py:214-222 —— 根因升级为触发条件
if h['driver_mismatch']:
    reasons.append('driver')
# build_alert 中已能输出 driver 根因行，改动量 2 行

# OPS-5 llm-radar-twitter-login-verify.py:12 —— docstring "< 2h" → "FRESH_HOURS(6.5h)"
```

### 10.3 备忘（非阻塞，未改）

- `documents/handbooks/llm-radar-ops-handbook-v1.0-20260908.md` 未收录这两份新文档的指针；README 已覆盖，不强制。
- 请求 §1 提到的 `data/overview.json` 当前不存在（历史产物清理后遗留表述），避免在交接材料里当现行产物引用。

---

## 11. 待确认清单

| # | 问题 | 影响 | 建议默认 |
|:--|:---|:---|:---|
| Q-1 | 是否接受「常驻调试 Chrome + 有效登录态」作为长期状态？ | SEC-1 风险敞口 | 接受但登记（已做）；若要收窄走 O-5 (b) 窗口化 |
| Q-2 | 6.5h 的语义确认为「缺 1 轮即报」还是「正常上限」？ | 决定是否改 7.5h | 主采集 7.5h（正常上限口径），X 保持 6.5h |
| Q-3 | 留档校验是否要建常驻 cron？频率？ | 无周期 job ⇒ 留档断档 | 若要，建议 `35 */6 * * *`（避开 :20/:40 采集槽） |
| Q-4 | 是否加早间 `07:xx` 探活，缩短夜间 10h 盲区？ | O-7 | 暂不加，先观察 3 天告警噪音 |
| Q-5 | 「每轮都发 8–9 条/天」是否应改为「成功轮次 8–9 条/天」？ | 文档口径 | 改为「成功轮次」表述（避免被理解成 24+5 条） |

---

## 12. 结论

**CONDITIONAL PASS — 80/100（B）**

- 事实层面：文档所述与实测**一致**，可以放心作为交接依据（唯一需要小心的是根因措辞强度，已降档并给出补证方法）。
- 通行条件（已全部落地为文档修正）：DOC-4 / DOC-5 / DOC-6 / SEC-1 登记 / SEC-3 判据建议 / O-5~O-8。
- 未闭合项（不阻塞本次交接，需 ops 侧跟进）：OPS-1（fail-open，**优先级最高**）、OPS-2、OPS-3、OPS-4、OPS-5；
  以及 Q-1~Q-5 五个待确认。
- 推送：本报告与文档修正同批 push（禁 force）。推送后 `git rev-list --left-right --count origin/main...HEAD` = `0 0`。

**实现 prompt**：⬜ 未生成（本次为文档/运维交付，无实现面需求；OPS-1~4 的 patch 已在 §10.2 给出，可直接施工）
