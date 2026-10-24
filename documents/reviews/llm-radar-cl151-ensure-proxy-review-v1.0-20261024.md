# llm-radar CL151 ensure-proxy 实现 — review 报告 v1.0

- **日期**：2026-10-24
- **审查者**：Security Reviewer (review profile)
- **级别**：L2（`.review-level.yaml` level: L2，owner Jaden Li）
- **范围**：已 push 历史 `0044fb5`（feat：flclash_proxy / twitter-collector-cron.sh / twitter-collector.py + 3 个测试文件）、
  `1c2e21b`（docs：ops 实施记录 + 给 daily-checker 的回执 + README 索引一行）；
  对照件（仓外只读）：`daily-checker/documents/handoffs/CL151-twitter-collector-ensure-proxy-20261024.md`
- **方法**：源码逐行核对 + `git show` 差异审计 + **变异测试**（3 组钉子 + 3 组重连分支）+ 只读探针
  （importlib 加载模块、mock 分支，无网络、不启动 FlClash）+ 全量/针对性测试复跑 + 系统层只读核对
  （`codesign` / `spctl` / `Info.plist` / `crontab -l`）
- **结论**：**CONDITIONAL PASS — 86/100**（跳过语义与 `-g` 对齐成立；主要缺口 = 就绪判据在「已在运行」分支不探端口，
  与 CL151 §2/§3 偏差且此前未声明；重连分支补测前零覆盖）

---

## 1. 结论摘要

1. **「跳过 ≠ 失败」实现正确**（R1/SC4 一致）：cron step 1 失败 → `⏸️ 跳过本轮` + `exit 0`，位于任何数据写盘/Chrome 拉起之前；
   python 入口 ensure 失败 → `return 0`，早于 `write_document` / `commit_and_push`；X 管线本身**没有连败计数器**
   （`grep consecutive` 在 `scripts/` 只命中该行注释）⇒「不计连败」天然成立；通知面仅剩登录墙（R3 口径）。
2. **残留 `exit 1` / 异常文案已清零**：`grep -rn "无法访问 X" scripts/` = 空（审计开始时命中
   `scripts/twitter-collector-cron.sh:177` 与 cron 测试断言 —— 措辞问题，已修，OBS-1）。
3. **重连点实现可用，但守卫几乎恒真**：`cmd_collect` attach 失败 → `_ensure_proxy_ready()` → 重试一次；实测
   attach 2 次尝试 / 非 attach 1 次且不 ensure（无 (a) 误触发）、driver 未成则 `finally` 释放锁（无 (c) 泄漏）。
   但入口 `main()` 已 ensure 过，`ensure_ready` 在「已在运行」时立即 `ok=True` ⇒ 重连守卫等于「无条件重试一次」（OBS-2）。
4. **判据同源差异可接受（pgrep vs `macosx service check --json`），但存在第二处未声明的差异**：`ensure_ready` 在
   `is_running()` 为真时**短路返回 ok、不探 7890**，而 CL151 §3 的口径是 `port_open(7890) and found`。后果：
   「FlClash 在运行但 7890 关闭」不会被判未就绪 ⇒ 本轮走采集失败 `exit 1`（= 记失败），与 R1 意图相反（SEC-1 / LR-SEC-023）。
   已在 ops 文档 §1/§4-3 与回执「三处差异」声明，修复方案挂 O-6/CL152（需两侧口径确认）。
5. **测试判别力**：既有的 `-g` 与「跳过 vs 失败」钉子**真有判别力**（3 个变异全部变红）；但**新增的 attach 重连分支
   在补测前零覆盖** —— 把整段重连逻辑删掉，119 例全绿（TST-1，已补 5 例，补后 3 个变异全部变红）。
6. **风险项闭环**：`open -g` 仍会出 Dock 图标（`Info.plist` 无 `LSUIElement`）；本机 FlClash 为 adhoc 签名 +
   带 `com.apple.quarantine` 且 `spctl` 判定 rejected ⇒ 升级/重装后首次拉起若需 GUI 确认，cron 无交互 ⇒
   每轮静默跳过。O-1/O-2 未覆盖，已补 O-4（SEC-2 / LR-SEC-024）。
7. **治理合规通过**：subject 符合 `type@scope: subject`；历史线性无 force 痕迹（reflog 全为普通 commit）；
   `AGENTS.md` 自 2026-10-20 起零改动；评审结束 `origin/main...HEAD` = `0 0`。

---

## 2. 评分表

| 维度 | 权重 | 得分 | 依据 |
|:---|:---:|:---:|:---|
| 语义正确性（跳过 ≠ 失败 / R1 / SC4） | 25 | 23 | 两条入口都在写盘前返回 0、无通知、X 管线无连败计数（§3.1）；扣分：cron 未就绪文案仍以 `❌ … 无法访问 X` 呈现（已修） |
| 就绪判据与同源声明 | 20 | 15 | 端口判据只覆盖「本轮拉起」分支；`already_running` 短路不探 7890 ⇒ 与 CL151 §2/§3 偏差（§3.3 / SEC-1） |
| 重连点实现 | 15 | 12 | 只重试一次、异常路径释放锁、非 attach 不误触发（探针实证）；守卫近乎恒真、锁持有期间可能等 ensure ≤180s（OBS-2） |
| 测试判别力 | 20 | 19 | 变异矩阵 6/6 命中（补测后）；补测前重连分支零覆盖（TST-1，已补 5 例） |
| 文档一致性 | 10 | 9 | ops 文档/回执与代码对齐；扣分：handbook、`skills/x-twitter-collector/SKILL.md`、cron 头注释与日志仍写 `open -a` + `exit 1`（DOC-1，已修） |
| 安全（供应链 / 可见性 / 凭据） | 10 | 8 | 无凭据外泄、命令为固定 argv 无注入；但自动拉起 quarantine + adhoc 签名 app 绕开 Gatekeeper 摩擦（SEC-2，已登记 O-4） |
| **合计** | **100** | **86** | **CONDITIONAL PASS** |

---

## 3. 请求 §2 逐项回答

### 3.1（请求 1）语义正确性：`跳过 ≠ 失败`

| 断言 | 证据 | 判定 |
|:---|:---|:---:|
| cron 跳过时 exit 0 | `scripts/twitter-collector-cron.sh:242-247`；`tests/test_twitter_cron.py::test_flclash_start_not_ready_skips_round`（复跑通过） | ✅ |
| 跳过发生在任何写盘之前 | step 1 在 step 2（Chrome）/collector 之前；跳过前仅 `mkdir -p cache/pids`（`:54`） | ✅ |
| python 入口跳过不写盘 | `twitter-collector.py:1016-1019` 早于 `cmd_collect`（写盘在 `:937-941`） | ✅ |
| 不发任何通知 | `_notify_flclash_required` 已删（`grep` 无调用点）；`notify_required()` 仅 CLI 子命令保留（O-3）；跳过路径不发 `_notify_login_required` | ✅ |
| 不计连败 | X 管线无 `consecutive_fails` 存储（`grep -rn consecutive scripts/` 仅注释）；消费方 = `data/twitter.json` 新鲜度 | ✅ |
| 无残留 exit 1 路径 | `grep -rn "无法访问 X" scripts/` → 空（修前 `twitter-collector-cron.sh:177`）；`_is_flclash_running` 在 twitter 侧已不参与决策 | ✅（修后） |

补充事实：`evaluate_results` 全失败 → `exit 1`（`scripts/twitter-collector.py:423-438`）——
这**不是**代理判据路径，而是真·采集失败，符合约定；但见 SEC-1（代理不可用可能落进这条）。

### 3.2（请求 2）重连点实现

只读探针（`cache/scratch/cl151_probe.py`，mock 分支，无网络/无 GUI）：

```
probe1 ensure_ready(running=True, port7890=False) -> {'ok': True, 'started': False, 'reason': 'already_running'}
probe2 attach:      rc=1  start_driver_attempts=2  ensure_calls=1
probe3 non-attach:  rc=1  start_driver_attempts=1  ensure_calls=0
```

| 子问题 | 判定 | 说明 |
|:---|:---:|:---|
| (a) 非 attach 模式误触发 | ❌ 不存在 | `if not cdp_port or ...` 先把 `cdp_port=None` 短路 ⇒ 不 ensure、不重试（probe3 + `test_non_attach_never_ensures_or_retries`） |
| (b) 代理正常但 CDP 真断 ⇒ 多一次无意义重试/延迟 | ⚠️ 存在，代价小 | 因入口已 ensure，守卫恒真 ⇒ 实际等于「attach 失败一律重试一次」；失败重试需重新 `_resolve_chromedriver` + `webdriver.Chrome` 尝试（秒级，不拉 Chrome）。收益：覆盖 chromedriver 竞争/瞬时断连；代价：真·CDP 死亡（9222 关闭）时多一次必然失败 —— python 侧无重启 Chrome 能力，重试无法救活，属冗余尝试 |
| (c) 异常路径未关 driver / 未释放锁 | ❌ 不存在 | `driver` 在成功前保持 `None`；`finally` 关 driver + `lock.release()`；probe 后 `cache/scratch/probe-profile/` 无 `.collector.lock` 残留。注意：`lock` 在 `start_driver` 前获取 ⇒ 重连路径若真需要拉起 FlClash，锁会被持有到 ≤180s（OBS-2） |

### 3.3（请求 3）判据同源声明

- **pgrep 双判据 vs `macosx service check --json`：可接受**。理由（cron PATH 不可见、1.3s/次与降级 20s 子进程开销、
  2026-10-09 已收敛唯一真源防 `osascript … 'quit app "FlClash"'` 自命中）成立且有回归钉子
  （`test_counterexample_osascript_shaped_process_not_matched`）；端口判据两侧同为 7890。
- **但「端口同源」只对了一半**：`ensure_ready` 的 `already_running` 短路不探端口（`scripts/flclash_proxy.py:101-102`），
  cron 的 `ensure_flclash` 也在 `flclash_running` 真时直接 `return 0`（`twitter-collector-cron.sh:166-170`）。
  ⇒ 三层（cron / python 入口 / 重连点）的**有效判据都是「进程在跑」**，CL151 §3 的 `port_open and found` 只在「要拉起」时生效。
- 回执**此前未讲清**（只声明了「进程判据」与「预算」两处）。**已补**为「三处差异」第 3 条 + ops 文档 §4-3 / O-6。

### 3.4（请求 4）测试判别力（变异矩阵，全部实跑）

| 变异 | 施加位置 | 结果 |
|:---|:---|:---|
| M1 去掉 `-g`（`('open','-a',…)`） | `flclash_proxy.START_CMD` | **2 failed**（`test_ensure_ready_starts_and_waits_for_port`、`test_commands_and_thresholds_match_declaration_policy`）✅ |
| M2 cron 跳过 `exit 0` → `exit 1` | `twitter-collector-cron.sh` | **1 failed**（`test_flclash_start_not_ready_skips_round`）✅ |
| M3 python 跳过 `return 0` → `return 1` | `twitter-collector.py` main | **1 failed**（`TestProxyEnsureSkip`）✅ |
| M-prev 整段删掉 attach 重连（补测前） | `cmd_collect` | **119 passed** ⇒ **零覆盖**（TST-1 的铁证） |
| M4 重连分支删掉（补测后） | 同上 | **2 failed / 25 passed** ✅ |
| M5 非 attach 也重试（去掉 `not cdp_port`） | 同上 | **1 failed / 26 passed** ✅ |
| M6 重连前不 ensure（守卫恒真但无 ensure） | 同上 | **2 failed / 25 passed** ✅ |

补测内容（本批新增 5 例）：`TestAttachReconnect` 4 例（恰好一次重试 / 重试成功继续采集写盘 / ensure 不就绪不重试 /
非 attach 不 ensure 不重试）+ `_ensure_proxy_ready` 非 Darwin 恒 True 且不执行任何外部命令。
外加 cron 侧两条：日志须出现 `open -g -a FlClash`；跳过路径**不得**出现 `无法访问 X`。

复跑（本机 py3.12）：
- `tests/test_flclash_proxy.py tests/test_twitter_cron.py tests/test_twitter_collector.py` → **142 passed**
- 全量（非 selenium，ignore test_cli/test_selenium）→ **321 passed, 2 deselected**
- 跑完 `git checkout -- data/snapshot.json overview.json timestamp.json` 已还原（评审式只读取证）

### 3.5（请求 5）`open -g` 由 cron 触发的副作用

| 项 | 实测 | 结论 |
|:---|:---|:---|
| 抢焦点 | `-g` 生效（真源 argv 对齐上游 policy `open -g -a FlClash`，policy 第 22 行逐字一致） | ✅ 不抢前台 |
| Dock 图标 | `Info.plist` 无 `LSUIElement` / `LSBackgroundOnly` ⇒ 常规 app，**图标仍会出现** | ⚠️ 用户可感知（未文档化，已补 O-4） |
| Gatekeeper 首次提示 | `codesign -dv` → `Signature=adhoc`；`xattr` 带 `com.apple.quarantine`；`spctl -a -vv` → **rejected**；本机已人工放行过（SC 实测可拉起） | ⚠️ 升级/重装后首次由 cron `open` ⇒ 对话框无人可点 ⇒ ensure 超时 ⇒ 每轮静默跳过（O-1 盲区）。已补 O-4 + 缓解建议 |
| 文档覆盖 | 原 O-1（可见性）/ O-2（释放与用户实例）均未覆盖上述两点 | ❌ → 已补 O-4 |

---

## 4. 安全审查

### 🔴 无

### 🟡 SEC-1（LR-SEC-023）就绪判据在「已在运行」分支不探端口 ⇒ 代理不可用被记为采集失败

- 位置：`scripts/flclash_proxy.py:101-102`（`already_running` 短路）+ `scripts/twitter-collector-cron.sh:166-170`（同款短路）。
- 触发链：FlClash 进程在、7890 关闭（暂停代理 / 改端口 / 上轮 `open` 后端口尚未 LISTEN 的超时窗口）⇒
  cron 判「已在运行」→ python 入口 ensure 返回 ok → 采集 10 账号全部网络失败 → `evaluate_results` → `exit 1`
  ⇒ 与 CL151 §2/§3 的「代理未就绪 ⇒ 跳过」相反，且**会延续**（下轮仍判在运行）。
- 影响：不涉凭据/越权，属**可用性与告警语义**；对 daily-checker 面板表现为「采集失败」而非「跳过」。
- 修复建议（待确认 Q-1，建议 CL152）：`already_running` 且 `is_port_listening(port)` 为假 ⇒ 短预算等待后判 `not_ready`；
  cron 侧改用 `ensure --json` 读 `started` 以保住「只释放自启实例」的归属判定。
  本批**未改**（跨项目口径变更 + 会影响 `llm-radar-collector.py` 共用真源），只做声明与文档纠偏。

### 🟡 SEC-2（LR-SEC-024）cron 自动拉起 quarantine + adhoc 签名 app

- 事实：`spctl` rejected、adhoc 签名、保留 quarantine 标记；`open -g` 无交互。
- 风险：Gatekeeper 的「首次人工确认」摩擦被自动化绕过（本机已放行，属**已接受风险**）；重装/升级后摩擦回归时，
  表现为静默跳过而非显式失败（O-1 盲区叠加）。
- 修复建议：不改启动策略（用户已定「按需开启」），改为**可见性**：日报/`collect-report` 增加代理状态行；
  升级 FlClash 后手工启动一次确认。已登记 O-4。

### 🟢 通过项

- 无命令注入面：`START_CMD`/`STOP_CMD` 为固定 argv 元组，`_run` 走 list 形式，无 shell 拼接；cron 侧只传受控 env 数值。
- 无凭据/敏感信息进日志：跳过与就绪日志仅含端口、pid、超时值；未打印代理配置或 profile 路径内容。
- 失败安全方向正确：`ensure_ready` 异常 → `False`（跳过）而非放行采集；重连守卫在 helper 异常时不重试。
- 历史自愈纪律：reflog 无 `force`/`amend` 痕迹；`origin/main...HEAD` 评审期间保持 `0 0`。

---

## 5. 文档一致性核查

| # | 文档断言（`1c2e21b`） | 复算 | 判定 |
|:--|:---|:---|:---:|
| D-1 | SC2：节流期内不启动 FlClash | 代码顺序 step 0 → step 1；`test_throttle_skips_when_fresh` 通过 | ✅ |
| D-2 | SC4b：9222 活但代理停仍拉起 | cron step 1 在 `is_ready`（CDP）判定之前，无 9222 短路 | ✅ |
| D-3 | 「代理就绪 = `is_port_listening(7890)` + pgrep 双判据」 | 仅「拉起」分支成立；`already_running` 分支不探端口 | ❌ → 已修（§1 / §4-3） |
| D-4 | 两处差异（进程判据 / 预算） | 实为三处（缺「判据分支」）；且 `ENSURE=0` 语义漂移未提 | ❌ → 已补（回执「三处差异」+ O-5） |
| D-5 | 测试「`TestProxyEnsureSkip` 三例」+ 全量 316 | 现为四例 + `TestAttachReconnect` 四例；全量 321 | ⚠️ 数字滞后 → 已更新 |
| D-6 | cron/handbook/SKILL 描述 `open -a FlClash`、未就绪 exit 1 | 三处仍在描述旧行为 | ❌ → 已修（DOC-1） |

---

## 6. 发现项与状态

| # | Severity | 标题 | 状态 |
|:--|:---:|:---|:---|
| SEC-1 / LR-SEC-023 | 🟡 | 「在运行但 7890 关闭」不判未就绪 ⇒ 走采集失败（与 CL151 §3 偏差，未声明） | ⬜ 待确认 Q-1（建议 CL152）；文档已纠偏 |
| SEC-2 / LR-SEC-024 | 🟡 | cron 自动拉起 quarantine/adhoc 签名 app，Gatekeeper 摩擦被绕过且失败静默 | ⬜ 待用户接受（O-4 已登记） |
| TST-1 | 🟡 | attach 重连分支零覆盖（删除逻辑 119 例全绿） | ✅ 已修（+5 例；变异 3/3 变红） |
| DOC-1 | 🟡 | cron 头注释/日志、handbook §2.3、SKILL.md 仍写 `open -a` + 「未就绪 exit 1」 | ✅ 已修 |
| DOC-2 | 🟡 | `TWITTER_FLCLASH_ENSURE=0` 语义漂移：python 入口仍拉起且不释放（FlClash 可常驻） | ✅ 已声明（O-5）+ 待确认 Q-2 |
| OBS-1 | 🟢 | 跳过路径仍印 `❌ … 无法访问 X`（易被日志侧误判失败） | ✅ 已修为 `⏸️ … 本轮跳过` |
| OBS-2 | 🟢 | 重连守卫近乎恒真（入口已 ensure）⇒ 等价无条件重试一次；锁持有期间可等 ensure ≤180s | ✅ 已记录（不改） |
| OBS-3 | 🟢 | 同一轮 ensure 调 2~3 次（cron → python main → 重连）；已在运行分支零成本 | ✅ 已记录（不改） |
| OBS-4 | 🟢 | `twitter-collector._is_flclash_running` 现仅被「两入口委托一致」测试使用 | ✅ 保留（有测试价值） |

findings_total = 9；findings_open = 2（SEC-1 待 CL152 / SEC-2 待接受）。

---

## 7. 待确认清单

| # | 问题 | 建议 |
|:--|:---|:---|
| Q-1 | 是否把端口判据下推到 `already_running` 分支（CL151 §3 原口径）？涉及：`ensure_ready` 语义、cron 归属判定改 `ensure --json`、主采集海外源共用真源 | 建议 CL152 采纳；等待超时用短预算（如 ≤15s）+ 不改 `verify.wait` |
| Q-2 | `TWITTER_FLCLASH_ENSURE=0` 是否保留？若保留，python 侧 `=0` 应退化为「只探测不拉起」（否则 FlClash 被拉起却无人释放） | 建议保留 + 退化；生产 cron 未设该变量（默认 1），可低优先 |
| Q-3 | O-1 是否需要「代理状态」进日报（长期静默跳过的唯一可见性来源） | 建议加（与 SEC-2 同一缓解） |

---

## 8. 修改意见（本批判定：CONDITIONAL PASS ⇒ 已直接落地）

### 8.1 已落地（本报告同批 commit）

| # | 文件 | 改动 |
|:--|:---|:---|
| 1 | `scripts/twitter-collector-cron.sh` | 头注释 + 启动回显 `open -a FlClash` → `open -g -a FlClash`；未就绪行 `❌ … 无法访问 X` → `⏸️ … 未 LISTEN, 本轮跳过 (不计失败; CL151)`（退出码不变 0） |
| 2 | `tests/test_twitter_collector.py` | `TestProxyEnsureSkip` +1（非 Darwin 恒 True 且不执行外部命令）；新增 `TestAttachReconnect` 4 例 |
| 3 | `tests/test_twitter_cron.py` | 启动日志断言含 `open -g -a FlClash`；跳过路径断言 `无法访问 X` **不出现** |
| 4 | `documents/ops/cl151-ensure-proxy-v1.0-20261024.md` | §1 判据行纠偏、§2 测试清单与计数（321/142）、§3 文案修订说明、§4 差异 3、O-4~O-6、§6 评审修订表 |
| 5 | `documents/handoff/cl151-ensure-proxy-receipt-20261024.md` | 「两处差异」→「三处差异」（补判据分支偏差） |
| 6 | `documents/handbooks/llm-radar-collector-pipeline-handbook-v1.0-20260908.md` | §2.3 两段：`open -g -a`、跳过语义（exit 0）、`ENSURE=0` 真实影响 |
| 7 | `skills/x-twitter-collector/SKILL.md` | 真源命令 `open -g -a`；「未就绪 → exit 1」→ 跳过 exit 0；`ENSURE=0` 语义更正；补 attach 重连语义 |

### 8.2 未改（留给 Q-1/Q-2 决策）

- `flclash_proxy.ensure_ready` 的 `already_running` 短路（SEC-1）、cron 归属改 `ensure --json`、python 侧 `ENSURE=0` 退化。
- 理由：均为跨项目/跨层语义变更，且 AGENTS.md「Ask First」精神要求先定口径再改行为；本批只做**事实纠偏 + 测试加固**。

---

## 9. 数据与产物验证

- 评审期间**未改任何数据产物**；两次测试跑后 `git checkout -- data/snapshot.json overview.json timestamp.json` 已还原（`git status` 仅剩本批 3 个代码/测试文件 + 文档）。
- SC 真机证据未重跑（按要求）：沿用 `documents/ops/…` §3；评审侧仅做**只读**环境核对：`pgrep -x FlClash` 无进程、`127.0.0.1:7890` 未监听（未启动代理、未打扰用户状态）。
- `crontab -l`：X 采集 `20 * * * *` + 主采集 `40 * * * *` 未变；未设 `TWITTER_FLCLASH_ENSURE`（⇒ 生产走默认 `1`）。

---

## 10. 结论

**CONDITIONAL PASS（86/100）**：CL151 的四口径在「要拉起」路径上落地正确，跳过语义与 `-g` 对齐有真判别力；
扣分集中在三处——就绪判据的「已在运行」分支不探端口（与 CL151 §3 偏差、此前未声明）、attach 重连分支补测前零覆盖、
以及 `open -g` 拉起 adhoc/quarantine app 的可感知风险未文档化。以上均已按「能直接修的就修、需口径决策的挂待确认」处理：
6 项文档/测试修订已提交 push，2 项行为变更留 Q-1/Q-2。
