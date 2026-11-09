---
author: hermes-v0.20.6(2026.8.27)
profile: dev
type: summary
date: 2026-09-08
---

# llm-radar cli-governance handbook v1.0（CLI/工程治理）

> documents-consolidation phase-2 草稿（只写文件，未 commit）。素材全文（gitignored）：
> `cache/doc-consolidation/llm-radar-cli-governance-extract.md`。
> 代码行号核实基准：2026-09-08 工作区 `llm-radar-collector.py`（2779 行）——collector 为 sys.argv 手工分发（无 argparse），doc 行号属 jaden.tech 时代已漂移，正文一律标现行号。

## 一、定位

本手册覆盖 llm-radar 的 CLI 命令面与工程治理：cli-registry 全局注册（CL-SEC11）、skills 供给站 + prompt 子命令（LLM-RADAR-CL004）、cli-runtime-files 运行时产物布局（v1.0, HM-DESIGN-SEC-265）、wrapper env 修复（CL005）。

素材：13 份 = cli-governance 8 + skills-prompt 3 + runtime-files-migration-audit 1 + cl005-wrapper-env-fix-audit 1。

## 二、功能概述

- **命令面现状（code 核实 2026-10-21；`main()` L3053 起）**：`help`（打印 `print_grouped_help` L2862）/ `prompt [<skill>]`（L3076 派发，实现 `_cmd_prompt` L2936）/ **`chrome [--wait|--status] [--port N] [--profile DIR] [--secondary]`（L3081 派发，实现 `_cmd_chrome` L2791；2026-10-21 新增：手工拉起/检查 chrome-twitter-cdp，供人工登录）** / `status [--json]`（L3085 派发）/ `fetch <source>`（L3090）/ `merge` / `run [source] [--force]`（L3105）/ `selenium-check` / `sources` / `reset-health` / `crontab --status|--add|--remove|--list|--update`（L3123）/ `commit [msg]`（L3137）/ `auto-push`（L3149）；未知命令 exit 1。**无 `cron`/`verify` 子命令**（定时入口是 `crontab`）。HELP 全 args 扫描拦截 = fetch/run/commit/crontab/**chrome**（2026-10-21 加入 chrome）。两个实现约束：`chrome` 不实例化 collector（不依赖 API key）；`chrome --status/--wait` 直连 CDP WebSocket 读浏览器级 `Storage.getCookies`，**不经 chromedriver**（既规避 Selenium Manager stall，也避免「按页面域取 cookie ⇒ 停在 newtab 时误判未登录」）。
- **全局注册**：`.cli-registry.yaml` 入 git（含 env.conda_sh/brew_prefix）；`~/.local/bin/{llm-radar,lr}` symlink → `cache/system-command/llm-radar-wrapper.sh`（wrapper exec 前 `set -a; [ -f .env ] && source .env; set +a`，不 echo key）。
- **grouped help**：hm-style 4 组【采集执行/数据管理/Git 集成/定时任务】+ 功能概述；空入参 exit=0；`<cmd> help` exit=0 无副作用。
- **`lr status --json` checkpoint 协议**：七字段 `{id,label,status,icon,message,checks[4: 数据日期/实体数/质量门禁/Git 同步],actions[3: run/push/repair]}`；数据源全只读（timestamp.json 项目根、metrics.json 全局 consecutive_fails、git rev-list 分叉检测不主动 fetch、snapshot.json）。四态：ok(<7h 且质量 success) / warning(7-48h 或 git 分叉或质量 failed) / critical(>48h 或 snapshot 缺失或全局 consecutive_fails≥3) / info(附属项)。无 --json 文本单行输出（无 emoji）。
- **prompt/skills 供给**：`SKILLS_DIR = PROJECT_ROOT/skills`（L64）；`lr prompt` 无参列技能 / `<name>` 全文 / `<name> --brief`（扫 `^#{2,3}` 行）/ `--json` 信封 `{status,error,data}`；不存在 → stderr ❌ + 可用列表 + exit 1。实测 skills/ 2 份：github-workflow + x-twitter-collector。
- **runtime-files 布局（2026-09-08 迁移后）**：`data/` 只放真实数据；运行时产物全部 `cache/`（gitignored）——`cache/logs/{llm-radar-collector,twitter-collector,llm-radar-mcp-server}/`、`cache/llm-radar-collector/fetch-cache.json`、`cache/pids/llm-radar-mcp-server.pid`。
- **阈值常量**：`STALE_HOURS = int(os.environ.get('LLM_RADAR_STALE_HOURS','12'))`（L67-70，2026-09-03 由 7 放宽，跨夜空窗需余量）、`CRITICAL_HOURS = int(os.environ.get('LLM_RADAR_CRITICAL_HOURS','48'))`（L71）。注意 health 脚本 `scripts/llm-radar-health.py` L38 同读该 env（详见 ops handbook）。

## 三、机制与指令说明

- **main() 分发顺序（code）**：help（不实例化 collector）→ prompt（在 LLMRadarCollector() 实例化之前，无 API key 噪音）→ status（走 `_silent_collector()`）→ 其余命令实例化后分发 → else exit 1。
- **status 评估细节**：`not snapshot` 覆盖缺失与空 dict；`_git_divergence()` 非 git 仓库/rev-list 失败 → (None,None,'info') 不升级；quality 缺失 → 'info'；边界 `> STALE_HOURS` 才 warning、`> CRITICAL_HOURS` 才 critical（恰 7h ok）。
- **run --force 语义**：绕过 `_think` 6h 节流（main() L2260-2262，force 已内建）。
- **注册链路（§5.2，含 RIG-2/3/10 修正）**：①建 `.cli-registry.yaml` ②生成 wrapper——**install.py 无 `--template` 标志**（TEMPLATE 硬编码 install.py:20），故 fork 模板到 `cache/cli-registry/wrapper.sh.tmpl` 移除 script-miner calls.log 统计段后**手工从 fork 模板生成**（sed 填充 {{name}}/{{target_script}}/{{python}}/{{conda_env}} + chmod 755 + ln -sf）③验证 `llm-radar help` / `lr help` 一致。
- **runtime-files 迁移要点**：数据写盘 mkdir 保留（snapshot 仍写 data/，`self.data_dir.mkdir` L1604）；fetch-cache/crontab 日志/mcp pid 全部走 `cache/` 并在写前 mkdir；`.gitignore` `cache/` 覆盖新路径；diff 仅路径段 + docstring 零逻辑改动。

## 四、用法示例

```bash
# 全局命令（注册后）
lr help                 # grouped help，空入参 exit=0
lr status --json        # checkpoint 七字段（daily-checker 消费接口）
lr run --force          # 一键修复：绕过 6h 节流强制采集收敛
lr prompt               # 技能列表（ai-interchange 供给通道）
lr prompt x-twitter-collector --brief
lr crontab --status     # 定时任务状态
lr auto-push            # 数据推送

# 直接 python 形态（无注册环境/排障用）
python3 llm-radar-collector.py help
python3 llm-radar-collector.py run --force help   # HELP 全 args 扫描拦截：exit 0 仅打印用法

# 测试
python3 -m pytest tests/test_cli.py -q        # 21 passed（CL004 后含 prompt 8 用例）
python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_selenium.py -q   # 全量（近期 263-266 passed）

# 跑完还原测试污染（test_timestamp/test_isolation 写真实根文件）
git checkout -- timestamp.json overview.json data/snapshot.json
```

## 五、关键决策（原文编号）

### 族 A cli-governance（CL-SEC11, 2026-08-23）

- 问题：`python3 llm-radar-collector.py <cmd>` 无全局注册 / help 平铺 / 空入参 exit=1 / 无 --json。
- 决策表 **D1-D7**（v1.1 终版，2026-08-23 探讨确认「1A 协议闭环，决策 6+1 项全部锁定」）：**D1** 全局注册名 `llm-radar` 主名 + `lr` 别名（alias_list）/ **D2** status 阈值新鲜 <7h=ok/7-48h=warning/>48h=critical / **D3** 修复动作=方案 B：仅 `lr run --force`，不做完整 repair 封装 / **D4** 实施顺序：先上游（dev），下游 checkpoint 接入后续 / **D5** STALE_HOURS 常量可配对齐全 health probe / **D6** `run --force` 必须绕过 cron 6h 节流 / **D7** `.cli-registry.yaml` 入 git。
- 评审修正（review 70/B CONDITIONAL → rereview 95/A → 实施后 recheck 100/A 链）：**REA-11**（§6 mcp-server 文件名错）、**RIG-1**（48h 阈值锁定独立 `CRITICAL_HOURS=48`，弃 STALE*7=49 近似）、**RIG-2**（wrapper .env 加载：set -a source .env）、**RIG-3**（fork 模板移除 script-miner calls.log 段）、**RIG-4**（status fixture 隔离：patch project_root → tmp_path + 预置 3 文件）、**RIG-5**（连续失败级别锁定：全局 consecutive_fails run 级，非 source_health 任一源）、**RIG-6/7/9**（🟢 timestamp 路径标注 / 不主动 fetch 语义 / 文本输出定义）、**RIG-10**（install.py 无 --template → 修法 ② 手工 fork 模板，零跨项目改动）。
- 安全评审 **SEC-1~6** 全 🟢（status 只读 / positional 拦截防误执行 / cmd 静态字符串 / user-level symlink / .env 不打印 / exit=1→0 无下游依赖）；**GOV-1~6** ✅。
- 实施与尾项：feat 26219ba（rebase 后 f371d49）；ops 独立实测 8 条验收 7 实测 + 1 单测证据，120 passed；impl audit 95/A 遗留 **LR-SEC-011**（`run --force help`/`fetch --force help` 绕过 args[0] 拦截 → fix 90b5aa5 改全 args `any(a.upper()=='HELP')` + 2 测试）；收敛复核 90/A 遗留 **LR-SEC-015**（mcp_submit_update.py:13 + mcp-protocol-demo.py:44 补 `scripts` 段）/ **LR-SEC-016**（README.md:139 + integ L230/L239/L266/L304 补 scripts/）/ **LR-SEC-017**（SHA rebase 前→后映射注记，append-only）。最终 recheck-v1.0 + recheck-v1.1：**100/100 (A) → PASS，findings_open: 0**。

### 族 B skills-prompt（LLM-RADAR-CL004, 2026-08-27）

- 问题：缺面向 AI 的使用说明供给通道（ai-interchange 通道①）+ `llm-radar prompt` 报「❌ 未知命令」。编号修正：CL001/002/003 已被当日闭环占用。
- 决策（选项号原文）：**D1 1A** 沉淀 `skills/x-twitter-collector/SKILL.md`（category devops，description 首 57 字符自含触发）/ **D2 1B** 内容=项目专属运维速查，通用 X 技术深坑指向 Hermes skill x-twitter-scraping 不整篇复制 / **D3 1C** prompt 全量对齐 hs（无参列表/全文/--brief/--json 信封/不存在报错 exit 1）/ **D4 2D** urllib3 噪音不动 / **D5 1E** 测试=test_cli.py 扩展 subprocess 黑盒 + skills 精确集合断言 / **D6 1F** 流程=设计→CL004 READY→dev→用户核实→review 审计→push（仅 review）。
- 行为矩阵 8 行（含 `<不存在> --json` `{status:error,data:null,error:…}` exit 1；skills/ 缺失或空 exit 1）。约束：纯文档+CLI，不调 LLM/不采集；prompt 不实例化 collector。
- 评审 90/A（**RIG-001** help 两行式缩进对齐修正——修正块「11 空格」系评审笔误实为 10、**RIG-002** 补第 8 用例 `test_cli_prompt_json_not_found`）→ impl audit 95/A（f0276ea；5 验收全 ✅；**AUD-001** 🟡 no_key_log 断言串大小写盲点，CI secrets 下守卫有效；IMPL-OBS-1~5 🟢）。终审 **PASS — 95/100 (A)**，test_cli 21 passed + 全量 243 passed。

### 族 C runtime-files（cli-runtime-files v1.0, HM-DESIGN-SEC-265 落地第 2 项 P4 W2, 2026-09-08）

- 迁移 3 commit：f9928eb feat@collector / 7e7e41d docs@sync / 7006ee2 docs@sync；运行时布局见 §二。
- 验收：cache 5 路径存在性 ✅；data/ 下 .log/.pid/fetch-cache 0 残留 ✅；grep 0 处旧路径引用 ✅；git check-ignore 3 文件 ✅；263 passed + 2 skipped。
- 终审：**Verdict: ✅ PASS — 100/100 (A)**。OBS-1（.gitignore 过期条目 L2/L5/L6/L10 未清理）/ OBS-2（远端 59.110.66.1 需重部署：linux-deployment 文档仍 tail data/collector.log）。

### 族 D wrapper env（LLM-RADAR-CL005 wrapper env, 2026-09-02）

- 根因链：旧 lr-wrapper.sh `CONDA_SH=""` → 回退路径缺 `/opt/homebrew` 前缀 → conda 未激活 → python3 回落 3.9.6/LibreSSL → urllib3 v2 NotOpenSSLWarning（collector L35 顶层 import requests，任何子命令均触发）。
- 修复 07baf8f：`.cli-registry.yaml` 仅 +2 行 env（conda_sh `/opt/homebrew/Caskroom/miniconda/base/etc/profile.d/conda.sh` + brew_prefix `/opt/homebrew`）；install.py L124-125 填充占位符。实测：干净 env `lr status` exit 0、py3.12 (3.12.13)、NotOpenSSLWarning 归零。
- 发现：**SEC-1** 🔴 cache/cli-registry/wrapper.sh.tmpl 与 .env 字节相同含 live DEEPSEEK_API_KEY（gitignored 未泄漏，审计中已删除）；**GOV-1** 🟡 wrapper .env 段为手工 patch，install.py --force 再生成即丢失（后续 P2：二选一 项目级模板覆盖 / AGENTS 记录补丁步骤）；**HYG-1** 🟡 orphan cache/system-command/lr-wrapper.sh 旧坏 wrapper（P3 可删）。
- 终审：**PASS — 95/100 (A)**；「核心修复正确最小，根因经 4 项实测闭环」。

## 六、Ctrl-C 中断行为（CL007, 2026-11-03）

**契约**（真源 `skills-governance/cli-args-reference.md` §11 + §7，本仓实现单一真源 `scripts/cli_interrupt.py`）：

- 提示两行（第 2 行「已完成 n/total」本仓无进度模型 ⇒ 整行省略）：
  `⛔ 已中断 (Ctrl-C) — <指令> 未完成` / `   💡 重跑: <同一条可复制命令>`；**禁打印 traceback**。
- 退出码 **130**（`128+SIGINT`），与 0 成功 / 1 通用失败 / 2 用法错误区分。
- `--json` 模式：stdout 只有 `{"status": "error", "data": null, "error": "interrupted"}`，人类提示全走 stderr。
  ⚠ 该信封与 `status --json` 成功态的七字段巡检信封**不同形**：按 `id`/`label` 解析的消费方在 rc=130 时取不到字段，须先判 rc。
- 捕获点 = 各入口 `__main__` 段（唯一一处），文案/退出码只从 `cli_interrupt.emit()` 出，禁手抄第二份。

**覆盖范围**（8 个入口 = `hm check cli --strict` 口径 8/8）：`llm-radar-collector.py` +
`scripts/{twitter-collector,llm-radar-health,llm-radar-mcp-server,flclash_proxy,chromedriver_bootstrap,mcp_submit_update,mcp-protocol-demo}.py`。
`scripts/mcp-protocol-demo.py` 虽是 demo，但 `hm check cli` 按「含 `__main__` 段的 `*.py`」计入口 ⇒ 补守卫把门禁从 7/8 推到 8/8（LR-CLI-001）。
**口径说明（P1）**：`n/n` 是**按入口文件逐个**判定「`__main__` 段内是否存在真实 `try/except KeyboardInterrupt` + `emit(` 收口」，即**行级判据**，不是代码行覆盖、也不是分支覆盖 —— 同一个入口里写了多段收口仍只计 1；反之少了收口即整条红。口径随入口数量走：2026-11-04 新增 `scripts/llm-radar-preflight.py`（含 `__main__`）后，当前口径为 **9/9**；`tests/test_cli_interrupt.py` 的入口清单已改为 **git 发现集派生**，新增入口自动纳入，不再手抄。
`tasks/al-{init,scanner}.py` 仍未纳入（agent-loop 调度、中断语义涉状态机）——另批。

**wrapper 层收口（tracked 模板片段，SEC-1）**：`lr` / `llm-radar` 的 bash 包装层是 **gitignored 生成物**
（`install.py --force` 重生成即丢），因此下面这段以**源码形态**入库，重装后按此回填，评审也据此复算：

```bash
# ① 必须在任何 `2>file` 重定向之前：把「真 stdout / 真 stderr」复制到高位 fd。
#    一旦先出现 `2>file`，后续 trap 里的提示就会被写进那个文件 ⇒ json 模式「零提示」。
exec 8>&1 9>&2

cli_registry_interrupted() {
    local _json=0 _a
    for _a in "${CLI_REGISTRY_ARGV[@]}"; do [ "$_a" = "--json" ] && _json=1; done
    if [ "$_json" = "1" ]; then
        printf '⛔ 已中断 (Ctrl-C) — %s 未完成\n   💡 重跑: %s\n' "$1" "$1" >&9   # 真 stderr
        exit 130
    fi
    printf '⛔ 已中断 (Ctrl-C) — %s 未完成\n   💡 重跑: %s\n' "$1" "$1"
    exit 130
}
trap cli_registry_interrupted INT

# … env 段（conda activate + .env）…

# ② exec 目标前关掉高位 fd，避免被目标进程继承
exec 8>&- 9>&-
exec "$interpreter" "$TARGET_SCRIPT" "$@"
```

钉子：`tests/test_wrapper_interrupt.py`（shell 级，`set -m` + `kill -INT`；无 wrapper 的机器/CI 自动 skip）。

**覆盖边界（实测，别承诺全窗口）**：

1. `lr` / `llm-radar` 是 bash 包装层（`cache/system-command/llm-radar-wrapper.sh`）：env 段（conda activate + `.env`）占掉启动的大半，此期间 SIGINT 落在 **bash** 而非 Python。已加 `trap … INT → exit 130` 兜住（实测 0.05~0.38s 全部 PASS，改动前该段是「零输出 + rc=-2」）。wrapper 是 **gitignored 生成物**，`install.py --force` 重生成即丢（GOV-1）。
2. 重依赖已全部惰性化（`openai` / `prettytable` / `requests` 移入调用处），模块级只剩 stdlib；collector 另在 import 块外套了一层 `try`（被 importlib 当库加载时**重抛**，符合 §11.1-1「清理后重抛」），故 import 期中断也走同一文案。
3. **残余窗口（解释器启动段，无法由任何一侧覆盖）**：`execve` 之后、Python 首条字节码之前（site + 本文件 150KB 编译，约 20–40ms；位置随机器负载漂移）。此段 bash 的 trap 已随 `exec` 消失、Python 侧代码尚未开始执行 ⇒ 极端情况仍是 `rc=-2` 静默或 `line 0` 的裸栈。实测抽样 3 轮 × 20 点（0.05→1.00s，步长 0.05）= **59/60 = 98.3%**，唯一失败点在 0.40s 且无提示。要 100% 只能把 wrapper 改成「监督子进程 + kill 转发」，代价是 stdio 模式（MCP server）的 stdin 语义，本批不做。
4. 中断发生在**子进程**（Selenium headless Chrome、`git`）时父进程只收自己的 `KeyboardInterrupt`，子进程可能继续存活（§11.4 边界），本批未做回收。
5. `llm-radar-mcp-server.py` 的 `serve_forever()` 被 Ctrl-C 是**优雅停止**（打印「⏹️ 服务器已停止」并关闭），不套「未完成」文案；仅 dispatch 期中断走统一收口。

**验证命令**（改动后必跑）：

```bash
# 单元/行为钉（22 例：8 入口矩阵 + 信封 + 静态回退钉子 + 重跑行 shell 引用 + 发现集/AST 矩阵）
python3 -m pytest tests/test_cli_interrupt.py -q -n0
# shell 级 wrapper 钉子（3 例；无 ~/.local/bin/lr 的机器自动 skip）
bash tests/../scripts/wrapper-interrupt-probe.sh --json 1.2   # 手工看 RESULT 行
# 真实路径（人类模式）: 3s 后打断 qbitai 抓取 ⇒ 应见两行提示、rc=130、无 Traceback
# ⚠ 必须 `set -m` 开作业控制：非交互 shell 的后台作业继承 SIGINT=SIG_IGN，
#   不加时 `kill -INT` 无效（实测 7/7 rc=0 且抓取跑完，2026-11-03 review LR-CLI-005）
set -m; lr fetch qbitai & PID=$!; sleep 3; kill -INT $PID; wait $PID; echo "rc=$?"
```

**数字与来源（P2：每个数字后附产生它的命令；改动后重测再改本表）**：

| 数字 | 产生它的命令 |
|:--|:--|
| 入口 **9/9** | `hm check cli . --strict \| grep 中断收敛` |
| `test_cli_interrupt` **22 passed** | `pytest tests/test_cli_interrupt.py -q -n0` |
| `test_cli_interrupt`+`test_preflight` **52 passed** | `pytest tests/test_cli_interrupt.py tests/test_preflight.py -q -n0` |
| `test_cli` **24** / `test_gitflow` **41** / 合计 **65 passed** | `pytest tests/test_cli.py tests/test_gitflow.py -q -n0` |
| wrapper `--json` 中断：stdout **58B**、stderr **≥80B**（2026-11-09 实测 151B，含 env banner） | `bash scripts/wrapper-interrupt-probe.sh --json 1.2` |
| wrapper 人类模式中断：stdout **287B**、stderr **0B** | `bash scripts/wrapper-interrupt-probe.sh --human 1.2` |
| 抽样 **59/60 = 98.3%**（解释器启动段残余窗口） | 2026-11-03 手工抽样 3 轮 × 20 点（0.05→1.00s，步长 0.05），**非用例**，不可当门禁 |

> 历史订正：旧稿的「64 passed」「stderr 59B」均与命令输出不符，已按上表口径改写；
> 「62 passed」是 P0 批新增 5 例前的旧值，现为 **65**（24+41）。凡引用数字必须能在本机复跑出来。

## 七、已知坑

1. **collector 无 argparse**：命令面在 main() 手工分发（L2665-2768）；改命令须同步 grouped help 文案与 test_cli 黑盒断言。不存在 `cron`/`verify` 子命令。
2. **HELP 拦截必须全 args 扫描**：仅 args[0] 检查会被 `run --force help` 绕过（LR-SEC-011 教训）；现实现限定 fetch/run/commit/crontab 四个带参子命令。
3. **install.py 无 --template**：wrapper 生成走后 fork 模板手工路线（RIG-10 修法②）；`install.py --force` 重生成会丢 .env 段（GOV-1, P2 未闭）。
4. **密钥副本事故**（SEC-1）：wrapper.sh.tmpl 误 cp 成 .env 副本含 live key——模板目录须禁止放含密钥文件，AGENTS.md L52 失效表述待用户侧修。
5. **STALE_HOURS 语义漂移**：文档（2026-08-23 族 A）锁定默认 7；现行 code 默认 12（2026-09-03 放宽，注释记录依据）。引用/排障以 code 实值 + `LLM_RADAR_STALE_HOURS` env 为准；health.py 与 collector.py 双文件读同一 env。
6. **项目路径漂移**：族 A 文档标 llm-radar.jaden.tech（旧仓库名），现行 llm-radar.lab——代码内 `scripts/` 段引用（LR-SEC-015/016）曾整体漏补。
7. **测试污染**：status fixture 已隔离（RIG-4），但 test_timestamp/test_isolation 仍写真实根文件——全量 pytest 后 git checkout 还原 3 文件。
8. **conda env 名平台差异**：`.cli-registry.yaml` env.conda=py3.12 仅本 Mac；Linux 主机需 conda llm-radar env（O-5；yaml L9 注释已注）。

## 八、参考文档

归档说明：13 份素材均为过程文档，已随 docs@archive（2026-09-08）移入 archive 桶，档案 = `documents/archive/{solutions,reviews}-20260908/`。

### 族 A cli-governance（8 份）

| 源文件（原位 documents/…） | 处置 |
|---|---|
| solutions/llm-radar-cli-governance-design-v1.1-20260823.md | 已归档 → archive/solutions-20260908/ |
| reviews/llm-radar-cli-governance-review-v1.0-20260823.md | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-cli-governance-rereview-v1.1-20260823.md | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-cli-governance-recheck-v1.0-20260823.md | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-cli-governance-recheck-v1.1-20260823.md | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-cli-governance-ops-verify-v1.0-20260823.md | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-cli-governance-convergence-review-v1.0-20260823.md | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-cli-governance-implementation-review-v1.0-20260823.md | 已归档 → archive/reviews-20260908/ |

### 族 B skills-prompt（3 份）

| 源文件（原位 documents/…） | 处置 |
|---|---|
| solutions/llm-radar-skills-prompt-design-v1.0-20260827.md | 已归档 → archive/solutions-20260908/ |
| reviews/llm-radar-skills-prompt-review-v1.0-20260827.md | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-skills-prompt-impl-audit-v1.0-20260827.md | 已归档 → archive/reviews-20260908/ |

### 族 C runtime-files（1 份）+ 族 D wrapper-env（1 份）

| 源文件（原位 documents/…） | 处置 |
|---|---|
| reviews/llm-radar-runtime-files-migration-audit-20260908.md | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-cl005-wrapper-env-fix-audit-20260902.md | 已归档 → archive/reviews-20260908/ |

相关现行保留项（不归档）：`.cli-registry.yaml`（仓库根，入 git）、`skills/x-twitter-collector/SKILL.md` 与 `skills/github-workflow/SKILL.md`（现行供给站内容）、`.hermes-project.yaml`（handoff 指向 documents/handoff/handoff-llm-radar.lab-ops.md）、`cache/doc-consolidation/llm-radar-cli-governance-extract.md`（gitignored 提炼产物）。
