# chromedriver 自动跟随（Chrome 升级不再打穿采集）· v1.0
- 日期：2026-10-26
- 范围：`llm-radar.lab`（采集侧）+ `~/.hermes/profiles/ops`（告警脚本 / cron）
- 前置：`chromedriver-manager`（script-miner，CLI `~/.local/bin/chromedriver-manager`）为唯一真源

## 1. 两个问题（都已在 2026-10-26 修复）

### 1.1 假告警：Feishu 报「chromedriver 154 与本机 Chrome 155 不匹配」
真实状态是 **Chrome 156.0.8078.47 + driver 156**（`chromedriver-manager check --json` ⇒
`verdict: compatible`）。告警里的 154/155 来自 **2026-10-21 17:40 的历史日志行**。根因三条叠加：

1. `llm-radar-collect-report.py::health_facts()` 用 `tail_lines(1200)` **正序**扫、命中即 `break`
   ⇒ 报的是窗口内**最老**一条，不是当前状态；
2. 窗口 1200 行 ≈ 5 天（`collector.log` 25k 行 / 1.4MB，无轮转）⇒ 问题修好后仍持续复报；
3. 判据来源错：用日志正则猜版本，而不是问权威工具。

修法：`driver_facts()` 改以 `chromedriver-manager check --json` 为准（`compatible` ⇒ 不报，
否则报 `driver X ≠ Chrome Y（chromedriver-manager 判定）`）；回退分支改为**倒序取最新**且只认
**最近 24h** 的命中，文案由「起持续告警」改为「最近一次 MM-DD HH:MM」；告警指纹加入
`v`（`ok:chrome:driver`）字段，状态变化即重报。

### 1.2 Chrome 自动升级打穿采集（10-23 实测：6 源全降级 12 连败）
`~/.wdm` / `~/.cache/selenium` 里的驱动按**版本目录**存放，Chrome 一升级就找不到匹配版本，
采集器 `_resolve_chromedriver` 只能退回旧驱动（日志 `主版本 154 与本机 Chrome 156 不匹配`）。

## 2. 方案（三层，互相兜底）

```
① 稳定指针  ~/Library/Application Support/llm-radar/chromedriver/chromedriver
            （不带版本 → 已用 `chromedriver-manager add --path` 注册; manager 的 upgrade 会写它）
② 采集注入  llm-radar-run.sh / scripts/twitter-collector-cron.sh 调
            scripts/chromedriver_bootstrap.py --print-path → export CHROMEDRIVER / TWITTER_CHROMEDRIVER
            （两采集器的候选序第一位; 只有「已验证兼容」才注入, 拿不到就回退原有扫描逻辑）
            **前置守卫**: print-path 为空（所有注册路径都不兼容/manager 不在）时才跑 --ensure 再问一次
            ⇒ 不等每小时 :05 的 cron, 当场跟随; 取不到就静默回退, 绝不阻断采集
③ cron 守卫  llm-radar-chromedriver-guard（每 :05）→ --watch
            不就绪 ⇒ iCloud 有匹配版则只 upgrade, 否则先 download(重试 1 次) 再 upgrade, 最后复核
            状态不变 ⇒ 空输出（静默）; 升级/失败/恢复 ⇒ 单条飞书
```

设计与实现要点：
- **非交互**：一律 `upgrade --all --json`（不加 `--json` 时 manager 会 `input()` 等选择，cron 会挂住）。
- **采集侧只认稳定路径**：manager 的 `verdict=compatible` 只要任一注册路径兼容即成立，
  所以守卫用 `stable_compatible` 判定「采集是否真的可用」（稳定路径旧了 ⇒ 必须 upgrade）。
- **不自己下载驱动**：下载/校验/iCloud 归档全部交给 manager，本仓不引入第二套真源。
- **失败仍可采集**：注入失败只是回退到原扫描逻辑，不会阻断采集；海外源不就绪按「跳过」处理。

## 3. 实测证据（2026-10-26，真机）

| 场景 | 操作 | 结果 |
|:---|:---|:---|
| 注册稳定路径 | `chromedriver-manager add --path ~/Library/Application Support/llm-radar/chromedriver/chromedriver` | 注册成功；`check --json` 两条路径均 `compatible` |
| 版本旧了能否自愈 | 把 154 驱动覆盖到稳定路径 → `chromedriver_bootstrap.py --ensure` | `action: upgraded`（`upgrade rc=0`），稳定路径回到 `156.0.8078.47`，**离线**（iCloud 已有匹配版，未触发 download） |
| 采集侧注入 | `./llm-radar-run.sh --help` | `[run] chromedriver: …/Application Support/llm-radar/chromedriver/chromedriver` |
| cron 最小环境 | `env -i PATH=/usr/bin:/bin … --print-path` | 正常输出路径（manager 用绝对路径，不依赖 `~/.local/bin` 在 PATH） |
| 两采集器解析 | 分别调 `_resolve_chromedriver` | 主采集 → 稳定路径；X 采集 → `(稳定路径, 'env:TWITTER_CHROMEDRIVER')`，**无版本不匹配告警** |
| 告警侧修复 | `llm-radar-report-watch.py` | 告警正文中 chromedriver 假根因消失（只剩真实原因） |
| 前置守卫·有回退路径 | 稳定路径覆盖为 154 后 `env -u CHROMEDRIVER ./llm-radar-run.sh --help` | `[run] chromedriver: …/script-miner/cache/chromedriver/chromedriver`（回退到兼容路径，**不**触发 ensure） |
| 前置守卫·全不可用 | 同上但 `CHROMEDRIVER_MANAGER=/nonexistent/mgr` | 打印 `[run] chromedriver 未就绪 ⇒ 尝试自动跟随（ensure）`，采集照常继续（不阻断） |

测试：`tests/test_chromedriver_bootstrap.py`（13 例：ready 判定 / usable_path / ensure noop·upgrade·download /
watch 静默·去重·恢复 / CLI 退出码）+ 既有套件 ⇒ 全量 **343 passed, 2 deselected**。

## 4. 运行时契约

- 状态文件：`cache/records/chromedriver-guard.json`（`ts / ok / action / sig / since / summary / detail`）。
- 退出码：**`--watch` 恒 0**（Q-4：harness 对 rc≠0 另发引擎级通知，会与正文去重叠加成重复告警）；
  其余子命令供本地/采集侧消费：`--print-path` / `--check` / `--ensure` 就绪 0、不就绪 1（`--check` 的 rc
  是「采集是否真的可用」，不是 manager 的全局 verdict）。
- 通知纪律：`sig` = `ready + verdict + chrome + good + action`（**不含 ready 会漏掉本设计的核心场景**：
  manager 的 `verdict=compatible` 只要任一注册路径兼容，稳定路径被覆盖成旧版时 `verdict/chrome/good`
  全不变 ⇒ 消息被去重吞掉）；同一 `sig` 不重复发；**真升级是事件，每次都发**（不去重）；
  失败持续期间只发第一条；恢复正常发一条 `✅ 已恢复`（带故障起点 `since`）。
- 跨入口互斥：守卫 `:05` / 主采集 `:40` / X 采集 `:20` 都会调 `ensure()`，manager 的 upgrade 是
  `shutil.copy2` 覆盖同一稳定路径（非原子）⇒ `ensure()` 用 `cache/records/.chromedriver-guard.lock`
  的 `flock` 串行化；拿不到锁的入口立即返回 `busy`（不排队，采集绝不阻塞）。
- 手工排查：
  ```bash
  python3 scripts/chromedriver_bootstrap.py --check          # 当前判定（含 stable_compatible）; rc=0 才算「采集可用」
  python3 scripts/chromedriver_bootstrap.py --print-path     # 采集器会用的路径
  python3 scripts/chromedriver_bootstrap.py --ensure         # 立即跟随（幂等）
  chromedriver-manager check --json                          # 权威真源
  ```

## 4.1 review 修正（2026-10-26 安全评审，v1.1）

| 项 | 问题（实测） | 修法 |
|:---|:---|:---|
| 🔴 SIG-1 | `watch()` 指纹只含 `verdict/chrome/good` ⇒ 稳定路径被注入旧驱动（本设计的核心场景）时三项全不变，**升级成功与失败消息都被去重吞掉**（`watch()` 实测返回 `('', 1)`，飞书零告警） | 指纹加 `ready` + `action`；`upgraded` 作为事件永不参与去重；`since` 落盘供恢复消息引用 |
| 🟡 RIG-1 | `upgrade` 的 `rc=3` 是 manager 的 `noop` 专用码，旧实现当 `upgrade_failed`；且稳定路径**未注册**给 manager 时 upgrade 永远 `noop`，修复指令（`download && upgrade`）无效 ⇒ 每小时误报且不带可执行指令 | `rc=3` 归入非失败分支；`rc=3` 且稳定路径在盘 ⇒ `stable_unmanaged`，消息直接给 `chromedriver-manager add --path` |
| 🟡 RIG-2 | `download` 对**永久性**失败（无可用下载地址 / 读不到 Chrome 版本）也重试 1 次 ⇒ 白等最多 300s 并多打一次 API | 命中永久性特征即不再重试（网络抖动仍重试 1 次） |
| 🟡 SEC-1 | 三个入口并发 `ensure()` ⇒ 两路 `shutil.copy2` 覆盖同一稳定路径（非原子），采集器可能 exec 到半个二进制（正是本方案要消灭的失败态） | `flock` 串行化（非阻塞，`busy` 直接跳过） |
| 🟡 CLI-1 | `--check` 调两次 manager（约 2×0.86s，且打印快照与 rc 不是同一次快照），rc 用**全局 verdict** ⇒ 稳定路径旧了仍返回 0（同 §2 的 pitfall） | 单次调用；rc = `_ready()`（「采集是否真的可用」） |
| 🟡 ENV-1 | CL151「env 安全解析」只收口了 **int**：`llm-radar-collector.py` 仍有两处模块级 `float(os.environ[...])`，`LLM_RADAR_FLCLASH_READY_TIMEOUT=''` ⇒ import 期 `ValueError` ⇒ 整轮采集失败（实测） | 新增 `_env_float()`（脏值/≤0 回退默认），`FLCLASH_READY_TIMEOUT` / `DEGRADED_RETRY_HOURS` 改走它；`tests/test_env_parsing.py` 19 例锁住 |
| 🟢 DOC-1 | `flclash_proxy.py` docstring 与 `skills/x-twitter-collector/SKILL.md` 仍写 `notify` 子命令（CL151 R3 已删） | 同步删除 |

测试：`tests/test_chromedriver_bootstrap.py` **20 例**（原 13 + 复核 7：指纹两形态 / 事件不去重 /
`since` 保留 / `stable_unmanaged` / 永久失败不重试 / 锁 / `--check` rc）、
`tests/test_env_parsing.py` **19 例**；变异 7 组（`_ready`→verdict、裸 `upgrade`、指纹退回三项、
`--check` rc 用 verdict、`rc=3` 当失败、去锁、去 upgraded 事件分支）**全部变红**。

### 已知未闭合（下一批，不在本批范围）

1. **告警侧回退分支零测试钉子**：`llm-radar-collect-report.py::driver_facts()` 在 ops profile 下
   （不入本仓 git），`tests/` 无任何引用 ⇒ 回退分支改回「正序扫」不会变红（变异实测绿）。
2. **`ensure()` 最坏耗时 ~16.5 分钟**（check 90 + download 300×2 + upgrade 300）发生在采集**之前**，
   若与下一槽位重叠会推迟一轮采集；建议对采集前置守卫用 `--ensure` 的短超时变体。
3. **X 采集不看版本**：`_resolve_chromedriver()` 命中 `TWITTER_CHROMEDRIVER` 即返回（不做主版本校验），
   把版本正确性完全托付给 manager；主采集仍会 `--version` 复核。
4. **日志轮转未做**：`collector.log` 25k 行无切割（告警已改权威源，故不再复报）。

## 4.2 未闭合项闭环（2026-10-26 第二批，v1.2）

| 项 | 问题 | 修法 | 证据 |
|:---|:---|:---|:---|
| LR-CDG-007（Q-2） | 采集前置 `ensure` 无总预算，最坏 ~990s 挡在采集前（check 90 + download 300×2 + upgrade 300） | `ensure(deadline=…)` + `--ensure --deadline 60`：预算按步分配（每步子进程 timeout = `min(基数, 剩余)`），耗尽 ⇒ `action='deadline'`、不动 manager，交回每小时的 cron；两处采集入口均用 60s | `test_ensure_deadline_short_circuits`（预算 0 时 manager 调用为空）+ `test_ensure_deadline_bounds_subprocess_timeout`（所有子进程 timeout ≤ 60） |
| LR-CDG-008（Q-3） | X 采集命中 `TWITTER_CHROMEDRIVER` 即采用，零版本复核（主采集有 `--version` 复核） | 注入路径也实跑 `--version`：读不出主版本 ⇒ 不信任；与 CDP 目标主版本不符 ⇒ 告警并回退缓存扫描 | `test_env_override_rejected_on_major_mismatch`（154 vs 156 ⇒ 回退且 stderr 有 `主版本 154`）+ `test_env_override_unreadable_version_falls_back`；真机 `target_major=156 / driver_major=156 ⇒ env 采用` |
| Q-4（rc 语义） | no_agent cron 对 rc≠0 会另发**引擎级**错误通知 ⇒ 与正文去重叠加成每小时重复响 | `--watch` 退出码**恒 0**（失败信息一律走正文）；ops 侧薄壳 `llm-radar-chromedriver-guard.py` 同样恒 0，并把真实 rc 打到 stderr；异常也兜底成一条正文（不再 traceback 静默死） | `test_watch_never_returns_nonzero_on_exception`；兄弟 watchdog `llm-radar-collect-watch` 同为恒 0，口径一致 |
| 回退分支零钉子 | `driver_facts()` 在 ops profile（不入本仓 git）⇒ 变异无从变红 | 本仓新增 `tests/test_report_driver_facts.py`：注入一个 fake manager 输出与一段**含 9 天前命中**的日志窗口，断言「compatible 时不报」「回退只认 24h 内且取最新」「指纹含版本三元组」 | 见该测试文件（用 `importlib` 直接加载 ops 脚本，无需复制实现） |

## 5. 已知边界

1. **采集进行中 Chrome 升级**：本次覆盖的是「采集开始前」与「每小时兜底」；会话中途升级仍会失败一轮，
   下一轮自动恢复（不做「中途重试」以免污染半轮数据）。
2. **iCloud 无匹配版且网络不可用**：守卫会连发 1 条失败消息后静默（指纹去重），并在下一小时重试；
   机器长期离线时以「采集跳过/降级」表达，不额外告警。
3. **X 采集的 Selenium Manager 路径**：`TWITTER_CHROMEDRIVER` 已注入，但若手工直跑
   `python3 scripts/twitter-collector.py --attach`（绕过 wrapper）则走原扫描逻辑（可自行 export）。
4. **日志轮转未做**（P4 待办）：本次只把告警判据从日志改成 manager，`collector.log` 仍无切割。
