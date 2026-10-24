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
- **delta 复审结论**（2026-10-24 23:00，范围 `9662e3f`/`799ca8e`/`a9a83a0`）：**PASS — 93/100**；
  SEC-1 / LR-SEC-023 与 DOC-2 已闭合，新增 RIG-1 / DOC-3 / TST-2 本批修复并验证（§11）

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
| SEC-1 / LR-SEC-023 | 🟡 | 「在运行但 7890 关闭」不判未就绪 ⇒ 走采集失败（与 CL151 §3 偏差，未声明） | ✅ **已闭合**（`799ca8e` 端口判据下推 + 短预算 `port_closed`；§11.1/§11.4/§11.6 复核） |
| SEC-2 / LR-SEC-024 | 🟡 | cron 自动拉起 quarantine/adhoc 签名 app，Gatekeeper 摩擦被绕过且失败静默 | ⬜ 待用户接受（O-4 已登记） |
| TST-1 | 🟡 | attach 重连分支零覆盖（删除逻辑 119 例全绿） | ✅ 已修（+5 例；变异 3/3 变红） |
| DOC-1 | 🟡 | cron 头注释/日志、handbook §2.3、SKILL.md 仍写 `open -a` + 「未就绪 exit 1」 | ✅ 已修 |
| DOC-2 | 🟡 | `TWITTER_FLCLASH_ENSURE=0` 语义漂移：python 入口仍拉起且不释放（FlClash 可常驻） | ✅ **已闭合**（Q-2：`799ca8e` 注入 `TWITTER_PROXY_NO_ENSURE=1`；本批补接线钉子 + 文档纠偏） |
| OBS-1 | 🟢 | 跳过路径仍印 `❌ … 无法访问 X`（易被日志侧误判失败） | ✅ 已修为 `⏸️ … 本轮跳过` |
| OBS-2 | 🟢 | 重连守卫近乎恒真（入口已 ensure）⇒ 等价无条件重试一次；锁持有期间可等 ensure ≤180s | ✅ 已记录（不改） |
| OBS-3 | 🟢 | 同一轮 ensure 调 2~3 次（cron → python main → 重连）；已在运行分支零成本 | ✅ 已记录（不改） |
| OBS-4 | 🟢 | `twitter-collector._is_flclash_running` 现仅被「两入口委托一致」测试使用 | ✅ 保留（有测试价值） |
| RIG-1 | 🟡 | 端口两侧不同源（Q-1 使端口成硬门禁后新增的永久跳过路径） | ✅ 已修（本批：wrapper `export` + 采集器 `_flclash_port()`；N3/N4 变异验证） |
| DOC-3 | 🟡 | ops §1/§4-3/O-5/O-6、handbook §2.3、SKILL、cron 头注释仍描述修复前行为 | ✅ 已修（本批） |
| TST-2 | 🟡 | `RUNNING_PORT_GRACE` 默认值 + `ENSURE=0` 接线 两处零覆盖 | ✅ 已补 2 钉（N1/N2 变异验证） |
| RIG-2 | 🟢 | `_flclash_owned` 用 `was_running` 而非 `started`（文述不符）+ µs 级竞态 | ⬜ 记录不改（建议另开一笔） |
| OBS-5 | 🟢 | 10s 预算实测 10.21s（末次探针在 deadline 后） | ✅ 已记录 |

findings_total = 14；findings_open = 1（SEC-2 待用户接受）；🟢 记录项 2（RIG-2 / OBS-5）。

> **§delta 复审后的状态（2026-10-24 23:00）**：SEC-1 / LR-SEC-023 ✅、DOC-2 ✅ 已闭合；
> 新增 RIG-1 / DOC-3 / TST-2 均已在本批修复并验证；判定升级为 **PASS 93/100**（§11.9）。

---

## 7. 待确认清单

| # | 问题 | 建议 |
|:--|:---|:---|
| Q-1 | 是否把端口判据下推到 `already_running` 分支（CL151 §3 原口径）？涉及：`ensure_ready` 语义、cron 归属判定改 `ensure --json`、主采集海外源共用真源 | ✅ **已决策并落地**（`799ca8e`）：判据下推 + `RUNNING_PORT_GRACE=10s`；cron 采用「始终 ensure + `was_running` 定归属」（未用 `--json` 读 `started`，见 RIG-2） |
| Q-2 | `TWITTER_FLCLASH_ENSURE=0` 是否保留？若保留，python 侧 `=0` 应退化为「只探测不拉起」（否则 FlClash 被拉起却无人释放） | ✅ **已决策并落地**（`799ca8e` + 本批接线钉子）；生产 cron 未设该变量（默认 1） |
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

> **状态变更（2026-10-24 23:00，delta 复审）**：Q-1/Q-2 已由 `799ca8e` 落地并经本报告 §11 复核 ——
> **SEC-1 / LR-SEC-023 ✅ 已闭合、DOC-2 ✅ 已闭合**；本批复审另发现并修复 3 项（RIG-1 / DOC-3 / TST-2）。
> 现行判定：**PASS 93/100**（见 §11）。

---

## 11. §delta — Q-1/Q-2 闭环复审（2026-10-24 22:20–23:00）

- **复审范围**（`origin/main...HEAD` = `0 0`，全程无 force push）：
  `9662e3f`（docstring 同步 `open -g`）、`799ca8e`（Q-1 端口判据 + Q-2 只探测，含 4 处测试）、
  `a9a83a0`（ops 文档 §2b + 回执补实测）。
- **方法**：逐行核对 5 处改动 → 变异矩阵 **14 组**（delta 自带 10 组 + 本批新增 4 组）→ mock 端口探针（不启 GUI/不建连）→
  全量复跑 → 文档一致性 + 治理核对。
- **结论**：**PASS 93/100**。Q-1/Q-2 的**行为**修得对，但 delta 自身引入 1 个新的永久跳过路径（RIG-1）与 1 套
  自相矛盾的文档（DOC-3），且新增测试有 2 处零覆盖（TST-2）；三项均在本批复审**直接修复并验证**。

### 11.1 请求 §1 逐项核对

| # | 断言 | 代码位置 | 复核结果 |
|:--|:---|:---|:---:|
| 1 | `RUNNING_PORT_GRACE=10`；在运行 → 先探端口；不通 → 短预算轮询 → `port_closed` 且不发 `open` | `scripts/flclash_proxy.py:52,100-116` | ✅（探针 A/B：10.21s 返回 `port_closed`，外部命令调用 `[]`） |
| 2 | cron 取消「在运行即 return 0」；`was_running` 决定 `OWNED_FLCLASH`；两种跳过文案；`ENSURE=0` 注入 `NO_ENSURE` | `scripts/twitter-collector-cron.sh:166-192,258-264` | ✅（变异 M3/M5/M6 全红） |
| 3 | `TWITTER_PROXY_NO_ENSURE=1` ⇒ 只探测（进程 ∧ 端口）不拉起 + 打日志 | `scripts/twitter-collector.py:81-107` | ✅（变异 M9/M10 全红） |
| 4 | 主采集 `if blocked:` + `was_running` ⇒ `_flclash_owned = not was_running` | `llm-radar-collector.py:1112-1131` | ✅（变异 M7/M8 全红） |
| 5 | 4 处新增/改写测试 | `tests/test_flclash_proxy.py:155-168`、`test_twitter_cron.py:438-476`、`test_twitter_collector.py:995-1010`、`test_source_health_skip_semantics.py:187-201` | ✅ 存在且有效（判别力见 §11.4） |

### 11.2 请求 §2.1：跳过风暴 —— 口径建议（不改代码）

**实测成本**：X 侧 `:20` 每小时唤醒，但 **step 0 节流先于 step 1 代理**（`twitter-collector-cron.sh:240-250`，
`TWITTER_THROTTLE_HOURS` 默认 **5h**）⇒ 「代理暂停、数据新鲜」时**根本到不了 ensure**，等 0s。
只有「节流已过（数据 ≥5h）」的轮次才付 `RUNNING_PORT_GRACE`：实测 **10.21s/轮**，即 **≤10.2s/h ≈ 4min/天**；
主采集 `:40` 同为 10.21s/轮、且每轮只调一次（`fetch_all` 内单点）。两者都是后台 cron，无用户可感。

**建议口径（三层，全部不违背 R1）**：

| 场景 | 是否告警 | 理由 |
|:---|:---|:---|
| FlClash 未运行（本轮也没拉起来） | **不上报** | 维持 R1 原口径（用户主动关代理是合法状态） |
| FlClash 在运行但端口不通，**且 X 数据仍新鲜（<2× 节流阈值）** | **不上报** | 与「未运行」同属环境未就绪；10.2s 成本可忽略，逐轮告警会变成整点刷屏 |
| 同上，但 **X 数据年龄 > 2× 节流阈值（默认 10h）** | **上报一次（降噪指纹）** | 这才是「在跑却不通」的真实后果：永久静默跳过。用数据年龄作判据可复用现成阈值，避免新增状态机 |

落地面在 ops 侧（仓外只读核对）：`~/.hermes/profiles/ops/scripts/llm-radar-collect-report.py` 的
`alert_reasons()` **只看主快照 age / consecutive_fails / degraded**（L214-222），**完全没有 X 侧判据**；
digest 里 X 只有一行「N 账号・M 条（hh:mm 采）」（L204）。⇒ 建议另开一笔：给 `alert_reasons` 加 `x_stale`
（`data/twitter.json.generated_at` 年龄 > 2×`TWITTER_THROTTLE_HOURS`）+ digest 该行补 age 与 ⚠️。
**不建议**把「port_closed」做成逐轮 reason（会与 R1「不当异常」冲突，且与现有指纹去重机制不匹配）。

### 11.3 请求 §2.2：主采集侧影响（`_flclash_owned = not was_running`）

| 子问题 | 判定 | 依据 |
|:---|:---:|:---|
| 采集期间端口断开 ⇒ 「未拉起却释放」？ | ❌ 不会 | `owned=True` 仅当 `was_running=False` ∧ `ensure.ok`；端口断了不影响 flag；`release()` 对已退出进程返回 `{'ok': True, 'reason': 'not_running'}`（`flclash_proxy.py:142-143`），**幂等** |
| 「反之」（拉起却不释放）？ | ⚠️ 仅 µs 级竞态 | 检查 `was_running=True` 后、`ensure` 自己的 `is_running()` 之前进程若退出 ⇒ ensure 会 `open`（`started=True`）但 `owned=False` ⇒ 不释放（孤儿实例）。反向：检查 `False` 后用户手动打开 ⇒ `owned=True` ⇒ 本轮结束误释放用户实例。两向都由「读 `started`」消除（见 RIG-2） |
| `release_flclash_if_owned()` 幂等 | ✅ 成立 | `_flclash_owned = False` 在调用 `_release_flclash()` **之前**置位（`llm-radar-collector.py:1167-1172`）⇒ 重入直接返回 False；`run()` L2235 与 CLI `fetch` L3099 双调用点安全 |

### 11.4 请求 §2.3：10s 预算 + 与 `verify.wait=180s` 的关系

mock 端口探针（`cache/scratch/cl151_grace_probe.py`，无 GUI、无真实连接）：

```
A 端口恒不通 : {'ok': False, 'reason': 'port_closed', 'port': 7890}  实测 10.21s   外部命令调用 []
B 第3次就绪  : {'ok': True,  'reason': 'already_running'}            实测  4.14s   （覆盖「刚 open 完端口未 LISTEN」窗口）
C 非默认端口 : {'ok': False, 'reason': 'port_closed', 'port': 7899}  实测 10.28s
```

- **够不够**：够用于设计目标（代理暂停），因为「刚 `open` 完」的窗口在**同一轮**由 180s 分支覆盖；跨轮次撞上该窗口只可能是
  上一轮在 180s 内被杀/超时（Gatekeeper 对话框），此时 10s 判未就绪 → 跳过，语义正确（下轮重试）。
- **会不会太久**：单轮 10.21s（`RUNNING_PORT_GRACE` + 最后一次探针，超预算 ≈0.2s），相对 180s 与 6h 节流可忽略。
- **取值约束已锁**：`>0` ∧ `≥3×POLL_INTERVAL` ∧ `<READY_TIMEOUT/4`（`test_running_port_grace_is_declared_and_bounded`）。
- **文档**：`verify.wait=180s` 与 10s 的**分工**此前只在代码注释里，已补进 ops 文档 §2b「预算关系」段（本批）。

### 11.5 请求 §2.4：测试判别力（变异实测 14 组）

delta 自带钉子（变异施加在 `799ca8e` 的代码上，只跑受影响文件）：

| 变异 | 位置 | 结果 |
|:---|:---|:---|
| M1 `RUNNING_PORT_GRACE` 10→0 | `flclash_proxy.py` | **19 passed ⇒ 零判别**（该用例显式传 `running_grace=0.05`，默认常量无人管）🟡 → TST-2 |
| M2 删 `port_closed` 分支（恢复旧短路） | 同上 | 1 failed ✅ |
| M3 cron「在运行即 `return 0`」 | `twitter-collector-cron.sh` | 2 failed ✅ |
| M4 删 `export TWITTER_PROXY_NO_ENSURE=1` | 同上 | **1 passed ⇒ 零判别**（只测了采集器侧分支，没测 wrapper→采集器接线）🟡 → TST-2 |
| M5 成功一律 `OWNED_FLCLASH=1` | 同上 | 1 failed ✅ |
| M6 「在运行但不可达」文案回落通用版 | 同上 | 1 failed ✅ |
| M7 `_flclash_owned = True` | `llm-radar-collector.py` | 1 failed ✅ |
| M8 `was_running = False` | 同上 | 1 failed ✅ |
| M9 删采集器 `NO_ENSURE` 分支 | `twitter-collector.py` | 1 failed ✅ |
| M10 `NO_ENSURE` 恒就绪（不探端口） | 同上 | 1 failed ✅ |

本批新增 4 钉的判别力（变异施加在**含修复**的副本上）：

| 变异 | 期望变红的钉子 | 结果 |
|:---|:---|:---|
| N1 `RUNNING_PORT_GRACE=0` | `test_running_port_grace_is_declared_and_bounded` | **1 failed** ✅ |
| N2 删 `export TWITTER_PROXY_NO_ENSURE=1` | `test_flclash_ensure_disabled_exports_probe_only_flag` | **1 failed** ✅ |
| N3 删 `export TWITTER_FLCLASH_PORT` | 上述 + `test_flclash_started_then_released` | **2 failed** ✅ |
| N4 采集器忽略 `TWITTER_FLCLASH_PORT` | `test_flclash_port_env_is_honored` / `test_no_ensure_mode_probes_same_port` | **2 failed** ✅ |

复跑：`tests/` 全量（非 selenium，ignore test_cli/test_selenium）⇒ **329 passed, 2 deselected**（324 + 本批 5 钉）；
跑后 `git checkout -- data/snapshot.json overview.json timestamp.json` 已还原（`git status` 无数据产物）。

### 11.6 安全复核（🟡 SEC-1 闭合依据）

| 判定项 | 结论 |
|:---|:---:|
| 「在运行但 7890 关闭」现在判未就绪 → 跳过（exit 0、不计连败、不通知） | ✅ 闭合（SEC-1 / LR-SEC-023） |
| 端口不通时**不重复拉起**（避免双实例/配置互踩） | ✅ 探针 A 外部命令 `[]`；M2 变异即变红 |
| `ENSURE=0` 不再「拉起后常驻」 | ✅ 闭合（DOC-2）；且接线已有钉子（N2） |
| 新增代码的注入面 | 🟢 无（仍是固定 argv；cron 只新增两个 `export`，值为已校验的整数/端口串） |
| 凭据/敏感面 | 🟢 未变（日志仅端口/pid/超时值） |

### 11.7 本批复审发现与处置

| # | Severity | 发现 | 处置 |
|:--|:---:|:---|:---|
| RIG-1 | 🟡 | **端口两侧不再同源**：Q-1 让端口成为硬门禁后，wrapper 用 `TWITTER_FLCLASH_PORT`、采集器却恒探 `READY_PORT(7890)`。设 `TWITTER_FLCLASH_PORT=7899`（文档公开的环境变量）⇒ wrapper 通过、采集器 10s 后 `port_closed` ⇒ **每轮静默跳过、永不采集**（Q-1 前被「在运行即 ok」掩盖） | ✅ 已修：wrapper `export TWITTER_FLCLASH_PORT`；采集器 `_flclash_port()` 读同一变量（非法值回退默认并告警）+ 3 例回归 |
| DOC-3 | 🟡 | **文档自相矛盾**：`a9a83a0` 只在 ops 文档**追加** §2b，§1 四口径表、§4 差异 3、§5 O-5/O-6 仍写「已在运行不探端口 / 待决策 / 仍会拉起不释放」；`handbook §2.3`、`skills/x-twitter-collector/SKILL.md`、cron 头注释同款（上一轮 DOC-1/DOC-2 的同一类漂移复发） | ✅ 已修：§1/§4-3/O-5/O-6 就地改写并标注历史、handbook/SKILL/cron 头注释同步 |
| TST-2 | 🟡 | 2 处零覆盖：`RUNNING_PORT_GRACE` 默认值无人断言（改 0 全绿）；`ENSURE=0` 的 `export` 无接线测试（删掉全绿） | ✅ 已补：`test_running_port_grace_is_declared_and_bounded` + `test_flclash_ensure_disabled_exports_probe_only_flag`（N1/N2 变异验证） |
| RIG-2 | 🟢 | `_flclash_owned` 用 `was_running` 而非真源 `started`（ops §2b 文述与实现不符）+ 两个 µs 级竞态（误释放用户实例 / 拉起不释放） | ⬜ 记录不改（改动需变 `_ensure_flclash_ready` 返回契约，3 个调用点受影响）；建议后续 `owned = res['started']` |
| OBS-5 | 🟢 | 10s 预算实际 10.21s（末次探针在 deadline 之后跑），文案「10s 内不可达」略保守 | ✅ 已记录（§11.4）；不影响语义 |

### 11.8 治理核对

- `git rev-list --left-right --count origin/main...HEAD` 全程 `0 0`；`git reflog -30` 无 `force`/`amend`。
- `git log --since=2026-10-20 -- AGENTS.md CLAUDE.md` = **0 条**（未改 `AGENTS.md`）。
- `crontab -l` 未变（`:40` 主采集 / `:20` X），未设 `TWITTER_FLCLASH_ENSURE`（生产走默认 1）⇒ 本批修复对生产为纯行为增强。
- 真机侧**未启动 FlClash**（评审开始时 `pgrep -x FlClash` 空、7890 未监听）⇒ 请求 §3 的
  `ensure --port 7899` **未重跑**（该命令在「未运行」时会拉起用户 app）；改用 mock 端口探针（§11.4）+
  沿用 ops §2b 的真机证据（`{"ok": false, "reason": "port_closed", "pids": [67192, 67199]}`）。

### 11.9 delta 评分

| 维度 | 权重 | 得分 | 依据 |
|:---|:---:|:---:|:---|
| Q-1 语义正确性（进程在≠代理通） | 25 | 24 | 两分支都探端口、不重复拉起；扣 1：端口同源缺口（RIG-1，已修） |
| Q-2 语义正确性（`ENSURE=0` 只探测） | 15 | 14 | 只探测分支实现正确；扣 1：接线零覆盖（TST-2，已补） |
| 归属判定（不误杀外部实例） | 15 | 13 | `was_running` 主路径正确、`release` 幂等；扣 2：与文述不一致 + 竞态（RIG-2） |
| 测试判别力 | 20 | 17 | 自带钉子 8/10 命中；2 缺口已补（N1–N4 全红） |
| 文档一致性 | 15 | 11 | ops 文档自相矛盾 + handbook/SKILL/cron 头注释残留旧行为（DOC-3，已修） |
| 安全 | 10 | 9 | 无注入/凭据面；SEC-1 已闭合 |
| **合计** | **100** | **93** | **PASS** |

### 11.10 建议再开一笔（非阻塞）

1. **ops 侧 X 陈旧告警**（§11.2）：`llm-radar-collect-report.py` 的 `alert_reasons()` 加 `x_stale`
   （`twitter.json` 年龄 > 2×`TWITTER_THROTTLE_HOURS`），digest 的 X 行补 age/⚠️。
2. **归属判定改读 `started`**（RIG-2）：`_ensure_flclash_ready()` 返回完整 dict，`owned = bool(res['started'])`，
   顺带把「拉起但未就绪」的实例纳入释放（当前会留孤儿 FlClash）。
