# llm-radar chromedriver 守卫 未闭合项闭环 — review 报告 delta2 v1.0

- 审查类型：Delta 复审（只审 4 条未闭合项，不扩域）
- 基线：`documents/reviews/llm-radar-chromedriver-guard-review-v1.0-20261026.md`（CONDITIONAL PASS 74）
- 本批范围：`63e9368`（code: LR-CDG-007 / LR-CDG-008 / Q-4 / 新钉子）+ `bb60333`（docs §4.2）
- 评审者：Security Reviewer（review profile, L2）
- 日期：2026-10-26
- 起点仓状态：`git rev-list --left-right --count origin/main...HEAD` = `0 0`（复核后仍 `0 0`，见 §8）

---

## 1. 结论摘要

**PASS — 86/100**（4 条全部闭合，无 🔴；新增 4 项 🟡 均属「标注/覆盖面」类，建议下一批，不阻塞）

| # | 项 | 请求判定 | 本次判定 | 关键证据 |
|:--|:---|:---|:---|:---|
| 1 | LR-CDG-007 `ensure(deadline)` + 两入口 `--deadline 60` | 待核 | ✅ **闭合**（含 1 处标签缺陷 → RIG-3） | 真 subprocess 探针：预算 0/1/2s 分别 0.00 / 1.00 / 2.01s 收口；变异 M2 红 |
| 2 | LR-CDG-008 X 侧注入主版本复核 | 待核 | ✅ **闭合**（覆盖面有缺口 → RIG-4） | 探针：154 注入被拒 + stderr 告警；变异 M3 **2 failed** |
| 3 | Q-4 `--watch` / 薄壳 rc 恒 0 | 待核 | ✅ **闭合** | 全分支 `return 0` + 异常兜底；harness 侧前提**已核实**（`cron/scheduler_script.py:526` → `cron/scheduler.py:1559` 另有引擎级 alert） |
| 4 | 回退分支钉子 `tests/test_report_driver_facts.py`（5 例） | 待核 | ✅ **闭合**（钉子本身不入仓 → TST-3） | 5 passed；变异 M1 `1 failed`（`test_fallback_takes_latest_recent_hit`） |
| — | Q-1 稳定路径未注册：告警 + 指令 vs 自愈 | 需口径 | **接受现状（不自愈）**，见 §6.1 | — |
| — | Q-2 60s 预算是否合适 | 需口径 | **接受 60s**，但预算非端到端（OBS-6），见 §6.2 | — |

实测计数器（全部本轮真跑，未引用 commit message 自述）：

- `tests/test_report_driver_facts.py` + `tests/test_chromedriver_bootstrap.py` = **30 passed**（5 + 25，与请求期望一致）
- `tests/test_twitter_collector.py` = **108 passed**
- 全量（`-m "not selenium"`，忽略 `test_cli.py` / `test_selenium.py`）= **381 passed, 2 deselected, 2 warnings in 98.16s**；跑后 `git checkout -- data/snapshot.json overview.json timestamp.json` 已还原
- 变异 4 组全部真跑、全部变红（§3）
- 真机：`--check` rc=0 / `verdict=compatible` / `stable_compatible=true` / Chrome 156.0.8078.47（1.19s）；`--print-path` → 稳定路径

---

## 2. 逐条实现核验

### 2.1 LR-CDG-007 预算（`scripts/chromedriver_bootstrap.py:169-238`）

实现与请求一致：

- `ensure(timeout=90, download_timeout=300, deadline=None)`；`budget(base) = base if left is None else min(base, left)`（`:180-182`），`exhausted()`（`:184-185`）在每步子进程前判定；`download` → `upgrade` → 复核三处都用 `budget(...)` 收口。
- 预算耗尽返回 `action='deadline'` 且**不发起** download/upgrade（`_follow` 内三处 early return，`:211-212` / `:221-222` / `:230-231`）。
- 两入口均改为 `--ensure --deadline 60`：`llm-radar-run.sh:71`、`scripts/twitter-collector-cron.sh:309`。
- `--watch` 仍 `ensure()` 无预算（:05 守卫保留完整 990s 预算）——**这是对的**：:05 距 :20 有 15 分钟，且三入口并发由 `flock` 兜住（SEC-1 已闭合），不需要给守卫削预算。

真 subprocess 探针（假 manager，`$BH scratch/cdg-delta2/probe_deadline.py`）：

| 场景 | deadline | 实测 action | 实测耗时 | 判定 |
|:---|:---:|:---|:---:|:---|
| A. manager 每步 5s（首步 `check` 即超预算） | 0 | `no_manager` ❗ | 0.00s | 边界收口 ✅ / **标签错**（RIG-3） |
| B. 同上 | 1 | `no_manager` ❗ | 1.00s | 边界收口 ✅ / **标签错**（RIG-3） |
| C. `check` 快、`download` 慢 | 2 | `deadline` | 2.01s | ✅ 正确（`detail='预算耗尽: 放弃 download 重试'`） |

### 2.2 LR-CDG-008 注入复核（`scripts/twitter-collector.py:609-676`）

- `_target_major(cdp_port)`（`:609`）从 CDP `/json/version` 读目标主版本；`_driver_major(path)`（`:622`）实跑 `<path> --version`（timeout 20s）取 `ChromeDriver (\d+)\.`。
- 注入路径三分支（`:647-658`）：读不出 ⇒ stderr 告警 + 跳过；与目标不符 ⇒ stderr 告警 + 落回扫描；一致 ⇒ 采用。**方向正确**，且告警走 stderr（不污染 stdout 采集输出）。
- 真机复核：`_driver_major(稳定路径)` = **156**，与 `--check` 的 Chrome 156 一致。
- 降级口径（🟢 记录）：`TWITTER_CDP_PORT` 读不到（Chrome 未起/非 attach）时 `major=None` ⇒ 注入路径只要 `--version` 可读即采用，**不做匹配比对**。cron 实走 `--attach`（`twitter-collector-cron.sh:318`）且 Chrome 由脚本先拉起，故生产路径上比对生效；仅异常序（Chrome 未起）退化为「只验可读」。

### 2.3 Q-4 rc 语义（`scripts/chromedriver_bootstrap.py:303-337`；ops 薄壳 `llm-radar-chromedriver-guard.py`）

- `watch()` 外包 try/except → 异常也返回 `(正文, 0)`（`:303-316`）；`_watch()` 三个成功/失败出口全部 `, 0`（`:332` / `:334` / `:336-337`）。
- ops 薄壳（非本仓，`~/.hermes/profiles/ops/scripts/`）三条路径全部 `sys.exit(0)`，真实 rc 打 stderr。
- **harness 前提核实（这是上一轮 Q-4 一直没闭的口子）**：`cron/scheduler_script.py:526` `if proc.returncode != 0:` → `(False, …)` → `cron/scheduler.py:1559` `if not ok:` 生成 `⚠ Cron watchdog '<job>' script failed` 的**独立 alert**。⇒ 「rc≠0 会另发引擎级通知、与正文去重叠加成重复」的前提**成立**，恒 0 是正确的收敛方向。
- 代价（🟢 记录，口径需知）：rc 恒 0 后 run ledger 永远 success，失败态只能从正文/`cache/records/chromedriver-guard.json` 的 `since` 读；与兄弟 watchdog `llm-radar-collect-watch`（→ `llm-radar-report-watch.py` → `llm-radar-collect-report.py --alert`）口径一致。

### 2.4 回退分支钉子（`tests/test_report_driver_facts.py`，5 例）

5 例全部命中请求点：compatible 静默 / 不兼容报三元组 / 24h 外不复报 / 窗口内取最新（9 天 + 5 分钟两条）/ 指纹含 `v`。
唯一结构性问题见 TST-3：被测文件在 ops profile，**不入本仓 git**，靠 `pytestmark = skipif(not REPORT.is_file())` 兜。本机 5 passed；换机/CI 则 5 skipped（`381` 会变成 `376 passed, 5 skipped`），变异证据无法从仓内复现。

---

## 3. 变异矩阵（4 组，全部真跑，全部真红）

| 组 | 变异（仅改动指定处） | 命令 | 结果 | 命中用例 |
|:---|:---|:---|:---|:---|
| M1 | `llm-radar-collect-report.py:177` 回退分支 `reversed(tail_lines(1200))` → 正序（`:208` 那处保留） | `pytest tests/test_report_driver_facts.py -q` | **1 failed, 4 passed** | `test_fallback_takes_latest_recent_hit` |
| M2 | `ensure.budget()` → 直接 `return base` | `pytest tests/test_chromedriver_bootstrap.py -q` | **1 failed, 24 passed** | `test_ensure_deadline_bounds_subprocess_timeout`（观测 `upgrade timeout=300 > 60`） |
| M3 | `twitter-collector.py:649` 注入分支直接 `return env_path, …`（复核移除） | `pytest tests/test_twitter_collector.py -q -k env_override` | **2 failed, 1 passed** | `test_env_override_rejected_on_major_mismatch` + `test_env_override_unreadable_version_falls_back` |
| M4 | `_watch()` 末行失败分支 → `(0 if ok else 1)` | `pytest tests/test_chromedriver_bootstrap.py -q -k watch` | **2 failed, 5 passed** | `test_watch_failure_deduped_then_recovery` + `test_watch_reports_failure_when_verdict_unchanged` |

还原与复验：M1 后 ops 脚本 sha256 复原为 `011f9c0a…68e0`（5 passed）；M2/M4 `git checkout -- scripts/chromedriver_bootstrap.py`（25 passed）；M3 `git checkout -- scripts/twitter-collector.py`（108 passed）；`git status` 空。

判别力备注（🟢，不影响判定）：M1 的失败形式是 `TypeError: argument of type 'NoneType' is not iterable`（正序先撞 9 天前命中 ⇒ `msg=None`），不是断言信息本身。红得对，但报错可读性差；建议下一批在该用例先断 `msg is not None` 再断内容。

---

## 4. 安全审查

本批无新增信任边界、无凭据面、无 shell 拼接（`_run` / `_driver_major` 均走 argv 列表，无 `shell=True`）。

### 🔴

无。

### 🟡（新增，建议下一批，均不阻塞）

| ID | 严重度 | 问题 | 证据 | 修复建议 |
|:---|:---:|:---|:---|:---|
| LR-CDG-009 / RIG-3 | 🟡 | **预算在首步 `check` 耗尽时被报成 `no_manager`**，`detail` 写「manager 不可用」。文档 §4.2 与 commit message 都写「耗尽 ⇒ `action='deadline'`」；实际只有 download/upgrade 步耗尽才是 `deadline`。两条相关钉子在 `_run` 被 stub 成成功的前提下才为真 ⇒ 钉子与生产行为不等价 | 探针 A/B：`action='no_manager' detail='manager 不可用: …fake_slow_mgr.sh'`（manager 其实可用）；`check()` 默认 `timeout=90`（`:66`）被 `budget()` 压到 0 ⇒ `_run` 捕 `TimeoutExpired` 返 99 ⇒ `parse_check` → `None` ⇒ `:190` 直接 `no_manager` | `check()` 区分「不可用」与「超预算」：超预算先判 `exhausted()` 返 `deadline`；或在 `st is None` 分支加 `if exhausted(): return False,'deadline',{},'预算耗尽: check 未完成'`。同步补一条**不 stub `_run`** 的钉子（真实 `timeout=0`） |
| LR-CDG-010 / RIG-4 | 🟡 | **LR-CDG-008 的「回退缓存扫描」不是实际落点**：注入被拒后先命中 `shutil.which('chromedriver')`（`:659`）并**无条件返回**，该分支零版本复核。目标 156 时，PATH 上的 154 驱动会被照用 ⇒ 复核只挡住了 env 一条路径 | 探针：目标 major=156、注入 154、PATH 上放 154 ⇒ `_resolve_chromedriver` 返回 `(…/bin154/chromedriver, 'PATH')`。钉子 `test_env_override_rejected_on_major_mismatch` 把 `shutil.which` stub 成 `None`，因此看不到这一层 | 给 PATH 分支同样过 `_driver_major` + `major` 比对（不符则继续扫缓存并 stderr 告警），或把 PATH 排除在候选之外；钉子补一例 PATH 命中错版本 |
| LR-CDG-011 / OBS-6 | 🟡 | **60s 预算不是端到端**：两入口在 `--ensure --deadline 60` 前后各有一次 `--print-path`，而那调用内部是 `usable_path() → check()`，默认 `timeout=90` 且**不受 deadline 约束** ⇒ shell 侧最坏 90+60+90 ≈ **240s**，文档 §4.2「最坏等待从 ~990s 压到 60s」高报 | `llm-radar-run.sh:67/71/72`、`scripts/twitter-collector-cron.sh:306/309/310`；`check(timeout=90)` 见 `:66`，`usable_path()` 见 `:115-117` | `--ensure` 的 JSON 已带 `stable`/`paths`（`main()` 输出 `**after`）⇒ 采集入口直接用 `--ensure` 输出的 `stable`，删掉「ensure 后再 print-path」；首个 `--print-path` 加 `--timeout`（或 `--deadline`）短预算。顺带省掉 2×0.9s manager 调用 |
| LR-CDG-012 / TST-3 | 🟡 | 钉子文件**跨仓依赖未版本化文件**（`~/.hermes/profiles/ops/scripts/llm-radar-collect-report.py`）+ `skipif(not is_file())`：换机即静默跳过，`381 passed` 与 M1 变红都只在有该文件的本机成立；该文件被任何人本地改动都不会经 review | `tests/test_report_driver_facts.py:21` `REPORT = Path.home()/'.hermes'/…`；`:26` skipif | 把 `driver_facts()` 收进本仓（如 `scripts/llm-radar-collect-report.py`，ops 侧改薄壳 exec），钉子改为仓内导入；仓内无该文件时才 skip，并在 CI/全量跑时把 skip 计为失败（`--strict-markers` + `skip` 白名单） |

### 🟢 通过项 / 记录项

| ID | 项 | 说明 |
|:---|:---|:---|
| PASS-1 | 命令注入面 | 新增 `_driver_major` 只做 `subprocess.run([path,'--version'])`，无 `shell=True`；被执行的仍是「本来就要被 selenium 执行的驱动」，未扩大执行面 |
| PASS-2 | 敏感信息 | 新增输出只有路径与主版本号，无 token/key；stderr 告警不含环境变量值对（只含路径） |
| PASS-3 | 失败即静默风险 | `--watch` 恒 0 + 指纹去重后，持续失败只响一次；但 `since` 落盘 + 恢复消息可追踪，且与兄弟 watchdog 同口径 —— 接受 |
| PASS-4 | manager 被杀窗口 | `_run` 超时会 SIGKILL manager；manager `upgrade` 是 `shutil.copy2(source, target)` **直写稳定路径**（`chromedriver-manager.py:1123`，非 temp+rename）⇒ 理论上有「半二进制」窗口。copy2 亚秒级，60s 预算的 kill 落点几乎不会落在 copy 内；该类风险在 SEC-1 之前即存在，非本批引入。记录不改，建议 manager 侧改「temp + `os.replace`」（另仓） |

### 待确认

1. `documents/ops/…-20261026.md` §4.2 写「真机 `target_major=156 / driver_major=156 ⇒ env 采用`」——本轮无 CDP 监听（`:9222` 空），`_target_major(9222)` 返回 `None`，**该真机证据无法复现**；`_driver_major(稳定路径)=156` 已复核。建议 docs 补一句测法（先 `bash scripts/twitter-collector-cron.sh` 起 Chrome）。
2. `message()` 没有 `action='deadline'` 分支（落到末尾 `return ''`）。当前不可达（`watch()` 不传 deadline），但若将来给 `--watch` 加预算，deadline 会**静默且不进指纹**（`_fingerprint` 只吃 state，不含 deadline）。建议先加一条显式分支或在 `watch` 里禁 deadline。

---

## 5. 维度评分

| 维度 | 权重 | 得分 | 依据 |
|:---|:---:|:---:|:---|
| LR-CDG-007 预算（`deadline`/`min(base,left)`/两入口 60s） | 25 | 21 | 三处子进程全收口、真 subprocess 探针 0.00/1.00/2.01s、M2 红；扣分：首步耗尽标签错（RIG-3，−2）、预算非端到端（OBS-6，−2） |
| LR-CDG-008 注入复核 | 25 | 20 | 三分支 + stderr 告警 + 真机 156 一致、M3 双红；扣分：PATH 回退零复核（RIG-4，−5） |
| Q-4 rc 语义 | 25 | 25 | 全部出口 0 + 异常兜底成正文 + 薄壳同步；harness 前提首次拿到源码级证据（`scheduler_script.py:526` / `scheduler.py:1559`） |
| 回退分支钉子 | 15 | 11 | 5 例命中 5 个请求点、M1 红；扣分：跨仓未版本化 + skipif（TST-3，−4） |
| 文档/治理 | 10 | 9 | §4.2 四行表逐项可核、$0 0$ 干净、数据产物已还原；扣分：「60s」「回退缓存扫描」两处表述与实现不符（−1） |
| **合计** | **100** | **86** | **PASS**（无 🔴；4 项 🟡 进下一批） |

---

## 6. 口径判定（请求 §3）

### 6.1 Q-1：稳定路径未注册 ⇒ 告警 + `add --path` 指令（不自愈）

**接受，维持不自愈。** 理由（按证据）：

1. 自愈 = 采集/守卫路径**写 manager 的注册表**（系统级共享状态），会把本设计的写面从「驱动二进制」扩到「配置」；本轮 RIG-4 正说明「多写一处就多一处未覆盖路径」。
2. `stable_unmanaged` 的指令是可直接粘贴的单行：`chromedriver-manager add --path "<STABLE>" && chromedriver-manager upgrade --all --json`（`scripts/chromedriver_bootstrap.py:271`），MTTR 一条命令；而自动 `add` 若路径本身是坏的一半二进制，会把坏路径**登记成受管**，后续 upgrade 一路复制坏件 —— 自愈反而放大故障。
3. 该状态是「一次性配置债」而非反复漂移：本机当前 `--check` 显示 `stable_compatible=true`、`paths` 含稳定路径 ⇒ 已注册，属低频事件。

保留条件：若同一条告警在 30 天内复现 ≥2 次，再考虑提升为「daily-checker 人工确认后自愈」（需 ops 明确授权，非采集侧静默改配置）。

### 6.2 Q-2：60s 预算是否合适（主采集 :40 / X :20 / 守卫 :05 三入口）

**接受 60s，但需补两条边界。**

- 覆盖能力：`--check` 实测 1.19s（冷启动），iCloud 已有匹配版时 `upgrade` 是本地 `copy2`（亚秒~数秒）⇒ 60s 覆盖「正常跟随」绰绰有余。
- 需要 download（走网）时 60s 大概率不够 ⇒ 放弃并交回 :05 的全预算守卫，**这正是设计意图**（采集不陪等），且失败是 `|| true` 可容忍的。
- 边界一：预算非端到端，shell 侧最坏 ≈240s（OBS-6）—— 数字要按实现改写，不能写「60s」。
- 边界二：:05 守卫故意保留 990s 无预算（距 :20 有 15 分钟），三入口并发由 `flock` 兜住（`busy` 立即跳过），因此「三入口同用 60s」的说法在实现上不成立也不需要成立 —— 文档别这么写。

---

## 7. 下一批清单（建议，均 🟡/🟢，按优先级）

1. **RIG-4（LR-CDG-010）**：PATH 回退分支补主版本复核 + 钉子补「PATH 命中错版本」一例。—— 这是 LR-CDG-008 真正剩下的口子。
2. **RIG-3（LR-CDG-009）**：`st is None` 且 `exhausted()` ⇒ `action='deadline'`；补一条不 stub `_run` 的真实 `timeout=0` 钉子。
3. **OBS-6（LR-CDG-011）**：采集入口改用 `--ensure` JSON 的 `stable`，删第二次 `--print-path`；首个 `--print-path` 加短预算；文档 §4.2 的最坏等待改为实测口径。
4. **TST-3（LR-CDG-012）**：`driver_facts()` 收进本仓（或仓内 vendor），钉子改仓内导入，去掉跨仓 `Path.home()` 依赖。
5. 🟢 顺手：`message()` 补 `deadline` 分支（或 `watch()` 断言 `deadline is None`）；M1 用例先断 `msg is not None`；docs §4.2 补「真机 major 复现法」；manager `copy2` 改 `os.replace`（另仓）。

### 实现 prompt（dev，下一批；仅 RIG-4/RIG-3/OBS-6/TST-3 四项）

```text
仓库: /Users/jadenli/CodeSpace/llm-radar.lab（分支 main，起点 origin/main...HEAD = 0 0）
背景: documents/reviews/llm-radar-chromedriver-guard-review-delta2-v1.0-20261026.md §4 / §7

任务（严格按序，逐项落地+钉子；改完跑 §13.1/§13.2 全量）:
1. RIG-4 (LR-CDG-010) scripts/twitter-collector.py::_resolve_chromedriver
   - PATH 分支 (shutil.which) 也过 _driver_major + major 比对: 不符 ⇒ stderr 告警并继续扫缓存; 读不出 ⇒ 告警并继续扫缓存
   - 新钉: PATH 上放 154 (目标 156) ⇒ 不得返回该 PATH 驱动 (回到缓存扫描结果)
2. RIG-3 (LR-CDG-009) scripts/chromedriver_bootstrap.py::ensure
   - st is None 分支: 若 deadline 已耗尽 ⇒ return False,'deadline',{},'预算耗尽: manager check 未在预算内完成'
   - 新钉: 不 stub _run, 用真实 subprocess 语义 (timeout=0 或假 manager sleep) 断言 action=='deadline'
3. OBS-6 (LR-CDG-011)
   - llm-radar-run.sh / scripts/twitter-collector-cron.sh: 把 --ensure --deadline 60 的 stdout JSON 解析出 stable/paths，
     删掉其后那次 --print-path；首个 --print-path 加短预算（新增 --timeout，默认 90 不变）
   - documents/ops/chromedriver-auto-follow-v1.0-20261026.md §4.2: 「最坏等待 990s→60s」改成实测口径
4. TST-3 (LR-CDG-012)
   - driver_facts() 收进本仓（scripts/llm-radar-collect-report.py 或 vendor 副本），ops 薄壳改 exec 仓内路径
   - tests/test_report_driver_facts.py 改仓内导入，删 Path.home() 跨仓依赖与 skipif
约束: 不改 _verify 阈值 / crontab / .cli-registry.yaml env.conda；提交 type@scope: subject；no force push
验收: python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q 全绿；
      4 组新变异各自变红；跑后 git checkout -- data/snapshot.json overview.json timestamp.json
```

---

## 8. 治理核对

- `git rev-list --left-right --count origin/main...HEAD` = **0 0**（评审前、评审后各一次）
- 本批提交：`63e9368` fix@llm-radar（7 文件 +275/−31）、`bb60333` docs@ops（1 文件 +12/−1）；无 force / 无 amend / 无 rebase 改写
- 工作树：评审期间仅测试产物脏（`data/snapshot.json` / `overview.json` / `timestamp.json`）已 `git checkout --` 还原；变异改动全部还原，`git status` 空
- 未触碰：`AGENTS.md`、`crontab`、`.cli-registry.yaml`、`_verify()` 阈值、数据产物（除测试临时脏后还原）
- 未动 ops profile 之外的文件；M1 变异的 ops 报告脚本已按 sha256 复原（`011f9c0a…68e0`）
- 交叉核对：ops cron job `llm-radar-chromedriver-guard`（id `f253b63156d7`，`5 7-23 * * *`，`no_agent=true`，script `llm-radar-chromedriver-guard.py`）与本文档口径一致
