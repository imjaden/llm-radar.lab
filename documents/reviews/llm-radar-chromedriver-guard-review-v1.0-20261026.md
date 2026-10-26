# llm-radar chromedriver 自动跟随 + CL151 收尾 — review 报告 v1.0

- **日期**：2026-10-26
- **reviewer**：Security Reviewer（review profile）
- **级别**：L2（实现审计 + 安全审查）
- **审计范围（实际）**：`b8b4b3c` → `4b54e10`（含本批修正两笔）
  - `b8b4b3c` feat 守卫脚本 + 采集注入 + 13 例测试
  - `9a50cee` fix FlClash notify 面删除 + env 安全解析（int 类）
  - `135a3eb` docs ops 文档
  - **`b9207f6`** fix 采集前置 `--ensure`（**评审开始后由并发 ops 会话追加并推送**，见 §7 G-1）
  - `fb653c6` / `4b54e10` 本批 review 修正（fix / docs）
- **结论**：**CONDITIONAL PASS — 74/100**。判定为 CONDITIONAL 的唯一原因是评审当时存在 1 个 🔴：
  守卫的「通知契约」在本方案的**核心场景**下完全静默（成功与失败都不发消息）。该 🔴 与 5 项 🟡
  已在本批 `fb653c6` 落地并推送，`4b54e10` 同步文档；**待复审**（预期 ~90）。
- **推送状态**：`git push origin main` 成功，`origin/main == HEAD == 4b54e10`，`rev-list --left-right --count origin/main...HEAD` = `0 0`，全程无 force。

---

## 1. 结论摘要

| 判定项 | 结论 |
|:---|:---|
| 请求 §1 根因（告警复述 9 天前状态） | ✅ 根因成立，且报告的 3 个数字**逐项复算命中**（§2.1） |
| 请求 §3-1 `_ready()` 三段式 | 🟡 三情形中「稳定路径存在但**未注册**」判错（`RIG-1`）：永远 not ready 且 remediation 无效 ⇒ 已修 |
| 请求 §3-2 ensure 分支 | 🟡 永久性失败也重试（`RIG-2`）；`still_incompatible` 消息不足以定位（`RIG-1`）⇒ 已修 |
| 请求 §3-3 watch 指纹/静默契约 | 🔴 **指纹盲区**（`SIG-1`）+ 与兄弟 watchdog 的 rc/`since` 契约不一致 ⇒ 已修 |
| 请求 §3-4 采集侧注入安全性 | 🟢 注入面本身安全（引号 export、无 eval、argv 固定）；🟡 但三入口并发覆盖同一稳定路径（`SEC-1`）⇒ 已加锁 |
| 请求 §3-5 CL151 收尾 | ✅ notify 面**彻底**删除（零调用点 + CLI 拒绝）；🟡 env 安全解析只收了 int，float 两处仍能 import 期打死采集（`ENV-1`）⇒ 已修 |
| 请求 §3-6 测试判别力 | 🟡 请求点名的 3 组变异里 **2 组命中、1 组无从命中**（回退分支零测试）；且指纹缺口无钉子 ⇒ 已补 8 钉 + 新文件 19 例 |
| 平台事实 | `check --json` = compatible / Chrome `156.0.8078.47` / `stable_compatible=true`；guard `--watch` 静默 exit 0（复跑复现） |

---

## 2. 数据与产物验证（全部实跑）

### 2.1 请求 §1 的三个数字（独立复算）

| 断言 | 命令/来源 | 实测 | 判定 |
|:---|:---|:---|:---|
| `collector.log` 25,269 行 | `wc -l` | `25269` | ✅ |
| 全日志仅 53 条不匹配，最后一条 `2026-10-23 11:40` | `grep -c` / `grep -n \| tail -1` | `53`；末条 = `24594:2026-10-23 11:40:21 … 154 与本机 Chrome 156` | ✅ |
| tail 1200 起点 = 第 24070 行（`2026-10-21 13:40`）、首条命中 = 第 24104 行（`2026-10-21 17:40` 的 `154 vs 155`） | `awk 'NR==24070'` / `sed -n 24104p` | `24070: 2026-10-21 13:40:01`；`24104: 2026-10-21 17:40:05 ⚠️ chromedriver 主版本 154 与本机 Chrome 155 …` | ✅ 完全一致 |

### 2.2 告警侧修法（ops `llm-radar-collect-report.py::driver_facts()`）

合成日志探针（`LOG`/`CHROMEDRIVER_MANAGER` 注入，未触碰生产数据）：

| 场景 | 期望 | 实测 |
|:---|:---|:---|
| 9 天前 + 2h 前各一条命中 | 取**最近**一条 | `('chromedriver 155 与本机 Chrome 156 不匹配（最近一次 10-26 06:10）', 'log:155:156')` ✅ |
| 只有 9 天前命中 | 不报（超 24h） | `(None, 'log:stale(10-17 17:40)')` ✅ |

> 修法本身正确：**倒序 + 24h 窗口**。但该文件在 `~/.hermes/profiles/ops/scripts/`（**不入本仓 git**），
> 且 `tests/` 对它**零引用** ⇒ 变异「改回正序扫」不会变红（§4 表 M3）。

### 2.3 平台与采集侧

| 项 | 命令 | 实测 |
|:---|:---|:---|
| 守卫判定 | `chromedriver_bootstrap.py --check` | `verdict=compatible` / `chrome=156.0.8078.47` / `stable_compatible=true` / rc=0 |
| 采集会用的驱动 | `--print-path` | `~/Library/Application Support/llm-radar/chromedriver/chromedriver` |
| 幂等 | `--ensure` | `{"ok": true, "action": "noop"}` |
| cron 入口静默 | `~/.hermes/profiles/ops/scripts/llm-radar-chromedriver-guard.py` | stdout 空 / rc=0 |
| 状态文件 | `cache/records/chromedriver-guard.json` | 修正后新增 `since` 字段（`None` 表示健康） |
| 单次 `--print-path` 成本 | `/usr/bin/time -p`×3 | **0.86s / 0.86s / 0.88s**（文档写「~0.4s」，属低报，见 🟢 DOC-2） |

### 2.4 测试与变异（全部实跑）

```
tests/test_chromedriver_bootstrap.py   13 → 21 passed
tests/test_env_parsing.py              19 passed（新增）
全量（非 selenium）                     343 → 370 passed, 2 deselected
跑后已 git checkout -- data/snapshot.json overview.json timestamp.json（工作区干净）
```

变异矩阵（`scripts/chromedriver_bootstrap.py`，逐个改→跑→还原，还原后与基线字节一致）：

| # | 变异 | 结果 |
|:---|:---|:---|
| M1 | `_ready()` 退回 `verdict == 'compatible'`（请求点名） | ✅ 红（7 failed；含 `test_ready_requires_stable_compatible`） |
| M2 | `upgrade --all --json` → 裸 `upgrade`（请求点名） | ✅ 红（`test_ensure_upgrades_and_uses_non_interactive_flags`） |
| M3 | 告警回退分支改回**正序扫**（请求点名） | ❌ **无从变红**：`tests/` 对 `driver_facts` 零引用（该文件不在本仓） |
| M4 | 指纹退回 `verdict\|chrome\|good` | ✅ 红（`test_watch_reports_failure_when_verdict_unchanged`） |
| M5 | `--check` rc 用全局 verdict | ✅ 红（`test_cli_check_exit_code_follows_readiness`） |
| M6 | `rc=3` 当失败 | ✅ 红（`test_ensure_flags_unmanaged_stable_path`） |
| M7 | 去掉跨入口 flock | ✅ 红（`test_ensure_single_writer_when_lock_held`） |
| M8 | 去掉 `upgraded` 事件分支 | ✅ 红（`test_watch_reports_each_upgrade_event`） |

> M4/M8 是新增钉子（原 13 例对 🔴 盲区**全绿**——这正是缺口能过审的原因）。

---

## 3. 请求 §3 逐项回答

### 3.1 `_ready()` 三情形（请求问题 1）

| 情形 | 期望 | 实现判定（修正前） | 结论 |
|:---|:---|:---|:---|
| 未注册稳定路径（指针不存在） | 任一兼容路径即可 | `stable_compatible=False`(False 分支不命中) → `stable_exists=False` → `any good` ⇒ **True** | ✅ 正确 |
| 稳定路径存在但旧 | 必须 not ready | `stable_exists=True` ⇒ **False** | ✅ 正确（核心断言，测试有钉） |
| 稳定路径被删 | 走 fallback | `stable_exists=False`（`STABLE.is_file()`）+ `any good` ⇒ **True** | ✅ 正确 |
| **稳定路径存在但未注册给 manager** | 应可自愈 | `stable_compatible` 永远 False（不在 `paths`）而 `stable_exists=True` ⇒ **永久 not ready**；`ensure()` 的 `upgrade --all` 只覆盖受管路径 ⇒ manager 返回 `rc=3(noop)` ⇒ 报 `upgrade_failed`，指令「download && upgrade」**修不好** | 🟡 `RIG-1`（已修） |
| manager 未安装 | 不得误判可用 | `check()` → None → `state_summary(None)` → `paths=[]` ⇒ **False**；`ensure` → `no_manager` | ✅ 无误判（有 `test_ensure_no_manager`） |

实测探针（未触碰真机驱动，`STABLE`/`check` 均注入）：

```
未注册稳定路径:  _ready=False | print-path 返回=<回退路径>
manage rc=3 时:  ensure => False, 'upgrade_failed'（旧）/ 'stable_unmanaged'（新）
```

即：**采集其实可用（有回退路径），守卫却每小时报错且给错指令**——噪音型缺陷，不阻断采集，故定 🟡。

### 3.2 ensure 的分支（请求问题 2）

- **download 重试只在真网络失败触发？** 修正前 **否**：`rc != 0` 一律重试一次。manager 的 `download` 对
  「无可用下载地址 / 读不到 Chrome 版本」同样返回 `rc=1`（`handle_download` → `_exit_code`），
  于是永久性失败要多花一次 `download_timeout=300s` 并多打一次 API ⇒ `RIG-2`（已修：永久性特征不重试）。
- **`upgrade` 成功仍不 ready ⇒ 消息够 5 分钟定位？** 修正前 **不够**。两种真实形态都只能看到
  `失败环节：upgrade_failed` + 160 字 detail：
  1. `rc=3`（noop）被当失败，而 `3` 的语义是「manager 无事可做」，需要人知道 manager 的私有退出码表；
  2. `still_incompatible` 的修复指令是无法生效的 `download && upgrade`。
  修正后：`rc=3` + 稳定路径在盘 ⇒ `stable_unmanaged`，消息直接给 `chromedriver-manager add --path "<稳定路径>"`。

### 3.3 watch 的指纹/静默契约（请求问题 3）

**🔴 SIG-1（本批唯一阻断）**：`sig = verdict|chrome|good`。而本方案的**核心场景**恰是
「稳定路径被覆盖成旧驱动，其它注册路径仍兼容」——此时 manager 的 `verdict=compatible`、
`chrome`、`good` 三项**全不变**，于是：

```
1) 健康一轮（写指纹 sig=A）
2) 稳定路径 → 154，自动跟随成功：ensure=(True,'upgraded') ⇒ watch() 返回 ('', 0)   ← 静默成功
3) 同形态但 download 失败：        ensure=(False,'download_failed') ⇒ watch() 返回 ('', 1) ← 静默失败(飞书零告警)
4) 对照: Chrome 大版本变了才 sig 变化 ⇒ 消息正常发出
```

场景 3 是 watchdog 最坏的失败态：**只有退出码，没有正文**。已修：指纹加 `ready` + `action`，
`upgraded` 作为「事件」永不参与去重，`since` 落盘供恢复消息引用。

**与兄弟 watchdog 的约定一致性（`llm-radar-collect-watch` / `llm-radar-report-watch.py`）**：

| 维度 | 兄弟 watchdog | 本守卫（修正前） | 判定 |
|:---|:---|:---|:---|
| 退出码 | **恒 0**（异常也 0，靠正文告警） | 失败期 rc=1 | 🟡 口径分叉（no_agent cron 对 rc≠0 的处理未在仓库内定义，见 Q-4） |
| 状态字段 | `{active, fp, since, cleared_at}`，`since` 跨轮保留 | 仅 `{ts, ok, action, sig, summary, detail}`，`save_state(**kw)` 全量覆盖 ⇒ `since` 无处存 | 🟡 已修（新增 `since`） |
| 恢复消息 | 带 `since` | 无起点 | 🟡 已修 |
| 异常路径 | `except` → 打印告警 → 0 | **无 try/except**：`save_state` 写盘失败即 traceback + rc=1 + 无正文（静默死） | 🟡 未改（见 Q-6，建议对齐兄弟） |

### 3.4 采集侧注入的安全性（请求问题 4）

| 检查 | 结论 |
|:---|:---|
| 命令注入 | 🟢 `_drv="$(…)"` 与 `export CHROMEDRIVER="$_drv"` 均加引号，无 `eval`；manager 侧 argv 固定，无 `shell=True` |
| 成本 | 🟢 单次 `--print-path` 实测 **0.86s**，每轮采集 1 次（`set -e` 下 `\|\| true` 有意吞错）⇒ 可接受；🟢 文档「~0.4s」低报 1 倍（DOC-2） |
| 多路径信任 | 🟢 `usable_path()` 只返回 manager 标 `compatible` 且**文件真实存在**的路径；稳定路径优先 |
| **X 采集绕过版本校验** | 🟡 `scripts/twitter-collector.py::_resolve_chromedriver()` 命中 `TWITTER_CHROMEDRIVER` 即 `return`，不做主版本复核（主采集仍 `--version` 比对）。⇒ 版本正确性 100% 托付 manager；manager 判错时 X 采集会被一起带错（表现为 attach 失败一轮）。**已记录，未改**（见 Q-3） |
| **并发非原子覆盖** | 🟡 `SEC-1`：manager 的 `upgrade` 是 `shutil.copy2` **覆盖**同一稳定路径，而 `:05`(守卫) / `:20`(X 采集前置) / `:40`(主采集前置) 三个入口都会 `ensure()`。守卫最坏耗时 = check 90 + download 300×2 + upgrade 300 ≈ **990s** ⇒ `:05` 轮可跨到 `:21:30`，与 `:20` 重叠 ⇒ 采集器可能 `exec` 到半个二进制。**已修**：`flock` 串行化（非阻塞，`busy` 立即跳过） |
| 写入面扩张 | 🟡 采集路径现在会触发**下载 + 覆盖驱动文件**（且 stdout/stderr 全丢弃），超出「采集器只读采集」的既有边界；`ensure` 无总预算（最坏 16.5 分钟挡在采集之前）⇒ 见 Q-2 |
| 供应链 | 🟢 新增面只调既有 manager；下载走 HTTPS 但无摘要校验（manager 既有属性，非本批引入）；无新增依赖、无新增凭据 |

### 3.5 CL151 收尾（请求问题 5）

- **notify 面已彻底删除**：`grep -rn "notify_required\|NOTIFY_CMD"` → 仅测试断言与历史文档命中；
  `flclash_proxy.py` CLI 无 `notify` 子命令（`argparse` 只有 `is-running|pids|ensure|release`）；
  `tests/test_flclash_proxy.py::test_no_notify_surface_left` 三重断言（无属性 / CLI rc≠0 / 源码无 `display notification`）✅
- **同类未收口项**：`grep "int(os.environ"` = 0 命中 ✅；但 **`float(os.environ[...])` 仍有 2 处模块级**（`llm-radar-collector.py:54,69`）：
  ```
  LLM_RADAR_FLCLASH_READY_TIMEOUT='abc'  => ValueError: could not convert string to float: 'abc'
  LLM_RADAR_FLCLASH_READY_TIMEOUT=''     => ValueError: could not convert string to float: ''
  ```
  即 `.env` 里留一个空值就 **import 期打死整轮采集**——与 CL151 §3 要修的坑完全同类 ⇒ `ENV-1`（已修：`_env_float` + 19 例测试）。
- 文档面：`skills/x-twitter-collector/SKILL.md` 仍列 `notify_required()` / `notify` 子命令，`flclash_proxy.py`
  docstring 首行仍写「通知」⇒ `DOC-1`（已修）。

### 3.6 测试判别力（请求问题 6）

| 请求点名的变异 | 结果 |
|:---|:---|
| `_ready()` → `verdict=='compatible'` | ✅ 红（3 例失败） |
| `upgrade --all --json` → 裸 `upgrade` | ✅ 红（1 例） |
| 回退分支正序扫 | ❌ **不可能变红**：`driver_facts()` 在 ops profile（不入本仓），`tests/` 零引用（`grep -rln "driver_facts" tests/` 空） |

另有 4 个**原 13 例全绿但实现是错的**位置，已补钉（§2.4 M4-M8）。

---

## 4. 安全审查

### 🔴

**SIG-1（LR-CDG-001）通知契约在核心场景静默 ⇒ 告警丢失**
证据：§3.3 的四步实跑。影响：Chrome 驱动被覆盖/损坏而 manager 全局 verdict 仍 compatible 时，飞书
既收不到「已自动跟随」也收不到「失败」，只剩 cron 退出码 1（而 rc 语义在无 agent 任务里未定义，Q-4）。
**已修**（`fb653c6`）：指纹含 `ready`+`action`；`upgraded` 事件永不去重；补 3 个钉子。

### 🟡

| ID | 项 | 处置 |
|:---|:---|:---|
| LR-CDG-002（`RIG-1`） | 稳定路径未注册 ⇒ 永久 not ready + `rc=3` 误判 + 指令无效 | ✅ 已修（`stable_unmanaged` + `add --path`） |
| LR-CDG-003（`SEC-1`） | 三入口并发 `copy2` 非原子覆盖稳定路径 ⇒ 可 exec 半二进制 | ✅ 已修（`flock`，`busy` 即跳过） |
| LR-CDG-004（`ENV-1`） | 模块级 `float(os.environ)` 空/脏值 ⇒ import 期打死采集（CL151 同类未收口） | ✅ 已修（`_env_float`） |
| LR-CDG-005（`RIG-2`） | 永久性 download 失败仍重试（+300s/次 + 多打 API） | ✅ 已修（永久特征短路） |
| LR-CDG-006（`CLI-1`） | `--check` 双调 manager 且 rc 用全局 verdict（稳定路径旧了仍 0） | ✅ 已修（单调 + `rc=_ready()`） |
| LR-CDG-007（Q-2） | 采集前置 `ensure` 无总预算（最坏 990s 挡在采集前），且写驱动=采集路径新增写面 | ⬜ 待决策（需 `--deadline` 或短超时变体） |
| LR-CDG-008（Q-3） | X 采集注入路径零版本复核 | ⬜ 记录（建议 `--print-path` 同时给版本，采集器 major 比对） |

### 🟢 通过项

- 无新增凭据/密钥进入代码、日志、前端（本批 diff 无 secret 形态；文档未含 token）。
- 无外部可执行文本进 prompt（本批不涉及采集内容），无 `eval`/`os.system`/未加引号展开。
- 路径来源为本地 manager JSON；`MANAGER` 可被 `CHROMEDRIVER_MANAGER` 覆盖仅为本地运维便利，cron 环境不可远程注入。
- 告警/状态文件均在 `cache/`（gitignored），不含敏感信息；ledger 与报告未打印密钥。

---

## 5. 维度评分

| 维度 | 权重 | 得分 | 依据 |
|:---|:---:|:---:|:---|
| 告警侧根因修复 | 15 | 13 | 三数字复算全中（§2.1）、倒序+24h 探针正确；扣分：该文件不入仓 ⇒ 回退分支零钉子（M3 无从命中） |
| 自动跟随核心语义（`_ready`/`ensure`） | 20 | 16 | 三情形中 2 情形精确、manager 缺失不误判；扣分：未注册稳定路径情形判错（RIG-1）+ rc=3 混淆 |
| 通知/静默/恢复契约 | 20 | 12 | 静默与恢复存在且幂等；扣分：🔴 指纹盲区（核心场景全静默）、`since` 缺失、与兄弟 watchdog 的 rc 契约分叉 |
| 采集侧注入（安全 + 成本） | 15 | 12 | 注入面无注入风险、成本 0.86s 可接受；扣分：并发非原子覆盖（SEC-1）、X 侧零复核（Q-3） |
| CL151 收尾 | 15 | 11 | notify 面彻底清除且有判别力钉子；扣分：env 安全解析只收 int，float 同类仍在（ENV-1） |
| 测试判别力 | 10 | 6 | 请求点名 3 组变异 2 中 1 无从命中；🔴 盲区在原 13 例全绿；已补 8+19 例 |
| 文档/治理一致性 | 5 | 4 | ops 文档详尽且与代码基本一致；扣分：`--print-path` 成本低报、SKILL/docstring 残留 `notify`、评审中并发追加 commit 未告知（G-1） |
| **合计** | **100** | **74** | **CONDITIONAL PASS**（修正后预期 ~90，待复审） |

---

## 6. 本批已落地改动

`fb653c6` fix@llm-radar（5 文件，+334/−22）
`4b54e10` docs@ops（2 文件，+38/−4）

- `scripts/chromedriver_bootstrap.py`：指纹（`ready`+`action`）、`upgraded` 事件不去重、`since` 落盘、
  `rc=3`→非失败、`stable_unmanaged` 分支与消息、永久性 download 不重试、`_acquire_lock`/`_release_lock`、
  `--check` 单次调用且 rc=`_ready()`、`_ready` 改 `.get()`（兼容历史状态/精简摘要）。
- `llm-radar-collector.py`：新增 `_env_float`；`FLCLASH_READY_TIMEOUT` / `DEGRADED_RETRY_HOURS` 改走它
  （`_env_int` 顺延到定义之后，行为不变）。
- `scripts/flclash_proxy.py` docstring、`skills/x-twitter-collector/SKILL.md`：去掉 `notify` 残留。
- 测试：`tests/test_chromedriver_bootstrap.py` 13→21 例；新增 `tests/test_env_parsing.py` 19 例。
- 文档：`documents/ops/chromedriver-auto-follow-v1.0-20261026.md` 新增 §4.1（修正表 + 运行时契约 + 未闭合项）。

验证：全量 `370 passed, 2 deselected`；变异 8 组全红；真机 `--check` rc=0 / `--ensure` noop / guard 静默 rc=0；
`git rev-list --left-right --count origin/main...HEAD` = `0 0`。

---

## 7. 待确认清单

| # | 问题 | 现状/建议 |
|:---|:---|:---|
| Q-1 | 「稳定路径存在但未注册」应**自动自愈**（`ensure` 内 `add --path`）还是只告警？ | 现为告警 + 可执行指令（保守）。自愈更省人力但会让守卫改 manager 配置，建议先观察一轮 |
| Q-2 | 采集前置 `ensure` 的最坏 990s 预算是否接受？ | 建议给 `--ensure --deadline 60`（超时即放弃，交回每小时 cron），避免与下一槽位重叠（LR-CDG-007） |
| Q-3 | X 采集 `TWITTER_CHROMEDRIVER` 是否要补主版本复核？ | 现状 100% 信任 manager；建议 `--print-path --json` 带版本，`_resolve_chromedriver` 比对 CDP 报的 major |
| Q-4 | no_agent cron 对 **rc≠0** 是否自行产生通知？ | 兄弟 watchdog 恒 0，本守卫失败期 rc=1（去重后正文为空）。若 harness 对 rc≠0 另行告警 ⇒ 去重失效、每小时间隔重复；需 ops 侧确认（我未在仓库内找到定义） |
| Q-5 | 告警脚本（`llm-radar-collect-report.py` / `report-watch.py`）是否纳入版本管理？ | 现仅在 ops profile，无 git 轨迹 ⇒ 本批最关键的「告警根因修复」不可审计、无回归钉子 |
| Q-6 | `watch()` 是否需要与兄弟 watchdog 对齐「异常也发正文 + rc 0」？ | 建议加 `try/except`：`save_state` 写盘失败不应让告警彻底静默 |

---

## 8. 治理核对

- **G-1 并发追加**：评审开始时 `origin/main == 135a3eb`（与请求一致），随后 `b9207f6`（采集前置 `--ensure`）
  由并发 ops 会话提交并推送（`08:09:35`），把审计范围扩到 4 笔。本报告已把该笔纳入审计（§3.4 写入面、
  SEC-1 并发窗口即由它放大）。**建议**：评审期间若再推实现笔，先告知 reviewer 或冻结分支。
- 无 `--force`、无 amend、无 `AGENTS.md` 改动（`git log --since=2026-10-20 -- AGENTS.md` = 0）。
- crontab 未改（`:40` 主采集 / `:20` X 采集）；cron 守卫 `5 7-23 * * *` 未改。
- 提交口径：`fix@llm-radar:` / `docs@ops:`，与本仓历史一致。
- 工作区收尾：测试产生的 `data/snapshot.json` / `overview.json` / `timestamp.json` 已 `git checkout --` 还原。
