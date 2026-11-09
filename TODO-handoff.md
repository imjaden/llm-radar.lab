# TODO-HANDOFF — llm-radar CL007 后续待执行清单
<!-- generated: 2026-11-09 · source: cache/draft/TODO-20261109.md · sha256:8bbf9ab5 -->
> 派生: 待执行 **3** 条 · 最近闭环 **CL12** · 差异知会 无（未找到含「差异知会」的设计文档）
> （本行由 `hm loop entry-page` 自动统计，人工段勿复述这些数字；`hm check handoff` 校验人工段声明与实数一致）
## 一、已登记待执行（来源: live draft cache/draft/TODO-20261109.md）

| 编号 | 标题 | 状态（派生摘要·全文见 draft） | kind | priority | 方案文档 |
|:--|:--|:--|:--|:--|:--|
| LLM-RADAR-CL008 | X 登录巡检落 cron（llm-radar-twitter-login-local） | 待办 | queued | normal | - |
| LLM-RADAR-CL009 | 飞书告警接入（外部依赖失效 → 统一通知） | 挂起 | queued | low | - |
| LLM-RADAR-CL010 | documents/README.md 索引漂移（hm check readme 4/5） | 待办 | queued | low | - |
<!-- generated end -->

> 交接时间：2026-11-03 19:00 CST · 交接人：ops 会话 · 目标仓：`~/CodeSpace/llm-radar.lab`（main）
> 状态锚（交接时）：`HEAD = 9f17634` / `origin/main = dfbdc85` / ahead 1；
> 本文件入库笔 = `docs@ops: CL007 待执行清单入库…`（紧跟其后，未推）⇒ 现 `HEAD` 比交接时前移 1 笔、`ahead = 2`。
> 以 §4 第一条命令的实测值为准（不要相信本文写死的 sha）。
> 闭环编号：**LLM-RADAR-CL007**（台账 `cache/draft/TODO-20261103.md`，状态 READY，未 verify）
> 新会话请先跑 §4 的「状态锚复核」三条命令，再按 §2 认领。

## 0. 一句话背景

任务书（上游只读）：`/Users/jadenli/CodeSpace/hermes-manager/documents/handoff/20261103-to-llm-radar-cli-interrupt-guard-prompt.md`
规范真源（只读）：`/Users/jadenli/CodeSpace/hermes-manager/skills-governance/cli-args-reference.md` §11（v1.28）+ §7 + §9。
需求 = 「Ctrl-C 不吐裸栈，中断与失败可区分（exit 130 + `--json` checkpoint 信封）」。
**实码已完成并 push**：`14dc48f`（主落地）→ `9b777b6`（复核轮 5 项）→ 评审 `6c7fea3` PASS 91/100、`dfbdc85` delta PASS 92/100。
本文件只列**未闭项**，不要重做已闭项。

## 1. 已完成（勿重做，仅供定位）

| 项 | 落点 | 证据 |
|:--|:--|:--|
| 单源收口模块 | `scripts/cli_interrupt.py`（`emit()` → 两行提示 + exit 130 + 信封；`_rerun_line` 用 `shlex.join`） | `tests/test_cli_interrupt.py` 14 例 |
| 8 个入口 `__main__` 守卫 | collector + `scripts/{twitter-collector,llm-radar-health,llm-radar-mcp-server,flclash_proxy,chromedriver_bootstrap,mcp_submit_update,mcp-protocol-demo}.py` | `hm check cli . --strict` ⇒ 中断收敛 **8/8**（行级） |
| import 期护栏 | collector：`openai`/`requests`/`prettytable` 惰性化 + import 块 `try/except`（库加载 `raise`） | 0.30s 注入无裸栈 |
| wrapper 期兜底 | `cache/system-command/llm-radar-wrapper.sh`（**gitignored**）：`exec 3>&2` + `trap … INT → 130` | `--json` 中断：stdout 58B 信封 + stderr 80B 两行 |
| 文档 | handbook §六（含 `set -m` 与边界 5 条）、方案 `documents/solutions/llm-radar-cl007-cli-interrupt-guard-design-v1.0-20261103.md`（canonical，568 行）+ 摘要版 `documents/ops/cl007-cli-interrupt-guard-v1.0-20261103.md` | 均已入仓 |
| 用户裁定 | **LR-CLI-009 维持现状**：本笔 subject 含中文，与 CL008「subject 全英文」冲突 ⇒ 豁免期内不动，**禁 amend**（会改已审 hash） | `hm check commit` 默认 ✅ |

## 2. 待执行（本仓，按优先级；括号内 = 评审编号）

> **早处理：2026-11-06 ops 会话一批（已 push、未过 review）** —— 明早优先补审，按「小批复核」口径打包一笔、
> 不重开全量评审。commit 清单（时间序）：`576851e` lr chrome 网络门 · `571e40b` preflight `x_reach` ·
> `05d628b`→`0667668` 网络门复探裁剪（后者为前者的修正+文案）· `93c301d` 网络门用例钉端口前提 ·
> `af85df6` ahead≠分叉（`_sync_remote`/`_converge_fork`/`_git_divergence`）· `c26fae5` status 用例固定判定时刻 ·
> `902e838` auto-push 独立通道（`_push_ahead_on_skip`）· `c82e4a9` GOV-1 收口（`_load_dotenv` 入 `main()`）。
> 证据：`gh run list` 对应 `c82e4a9` 起全 `success`（`af85df6` 首跑红，已由 `c26fae5` 修正）。

**P1　handbook 注明「8/8 = 行级判据」（N6，🟢，10m）**
落点：`documents/handbooks/llm-radar-cli-governance-handbook-v1.0-20260908.md` §六。
要求：写明「`hm check cli . --strict` 整体仍 ❌，由既有 `help 打印规范`（4 条）与 `tool 指令检查点`（2 条）⚠️ 项升红，
基线 `df00d9c` 同 ❌ ⇒ 8/8 只是**该行**判据，不等于整仓门禁绿」。判据：§六 出现该语义；既有 ⚠️ 项另批不修。

**P2　数字口径订正 + 交接单数字附来源（N4，🟡，10m）**
要求：handbook §六 与后续 `cache/review-prep/*` 交接单里，每个数字后附产生它的命令。已知两处订正：
`tests/test_cli.py + tests/test_gitflow.py` = **62 passed**（不是 64，基线同 62）；
wrapper `--json` 中断 stderr = **80B**（人类模式 73B，`fetch qbitai` 对 78B），不是 59B。

**P3　仓内 tracked 模板片段 + shell 级钉子（SEC-1，🟡，25m）**
问题：wrapper 的 fd3 修复只存在于 **gitignored 生成物**，`install.py --force` 重生成即静默退回「json 模式零提示」，
评审无法从源码复算。
要求：① 仓内落一段 **tracked** 的模板片段（patch 或 handbook 代码块，含 `exec 3>&2` 位置必须在**任何** `2>file` 之前）；
② 一条 **shell 级**钉子（脚本：`set -m` + `kill -INT` + 断言 stdout 58B / stderr 80B），放 `tests/` 或 `scripts/`；
③ 跨仓模板回填已出件，见 §3 OB-1。

**P4　`ENTRIES` 与自动发现集对齐（N1，🟡，15m）**
问题：`tests/test_cli_interrupt.py` 的 `ENTRIES` 是手写清单；删掉 demo 后 13 passed、静态钉绿、`hm check` 仍 8/8 ⇒ 两层同时失明。
要求：`ENTRIES` 由发现集派生（`git grep -l "__main__" -- '*.py'`，去 `tests/`、`cache/`、`tasks/`），或加一条
「集合相等」断言（改一处即红）。判据：删 demo 后**转红**。

**P5　静态钉改 AST 判定（N2，🟡，25m）**
问题：现为「`__main__` 切片 + 行锚正则共现」⇒ 吞中断 + 死 `emit(` 仍绿（X1）；合法写法 `except KeyboardInterrupt:  # 注释`（X2）
与 `cli_interrupt.emit(...)`（X3）被误杀。
要求：`ast.walk` 找 `Try`，handler 为 `Name('KeyboardInterrupt')` 且其 `body` 内含 `Call`（func 名为 `emit` 或属性 `.emit`）。
判据：X1 红、X2/X3 绿、M6b（只留注释）红。

**P6　demo 子进程收尾（N5，🟢，10m）**
问题：`scripts/mcp-protocol-demo.py` 用 `Popen` 起 MCP server 后在 `main()` 内无 `finally`；被脚本化
`kill -INT <pid>`（handbook 自己的形态）打断会留活子进程（终端 Ctrl-C 打整个 pgroup 则不会）。
要求：`main()` 内 `try/finally: proc.terminate()`（必要时等待回收）。判据：注入中断后 `pgrep -f llm-radar-mcp-server` 计数 0。

**P7（另批，不在 CL007 面）　`tasks/al-init.py` / `tasks/al-scanner.py` 未纳入守卫**
理由：agent-loop 调度、中断语义涉状态机，需单独验证。若要开工，先补 `ENTRIES` 派生逻辑（P4）再纳。

## 3. 跨仓 / 已裁定（**本仓不做**）

- **OB-1（hermes-manager，需用户手工转交）**：wrapper 模板补 `trap`+`exec 3>&2`、§11.3 判据放宽、§11.1-2 补第三种形态、
  §11.4 补「解释器启动段」边界、§11.2 补 prog 口径 + `shlex`。
  prompt 文档：`/Users/jadenli/CodeSpace/llm-radar.lab/cache/handoff/prompt-hermes-manager-cli-interrupt-template-20261103.md`（v1.1，已并入评审结论）
  回执全文：`/Users/jadenli/CodeSpace/llm-radar.lab/cache/handoff/CL007-interrupt-guard-receipt-20261103.md`
- **LR-CLI-009**：已裁定「维持现状」（见 §1 末行），不要动。

## 4. 复跑基线（改动前后必须对照；数字变了先归因再改）

```bash
cd ~/CodeSpace/llm-radar.lab
git rev-parse --short HEAD; git ls-remote origin main | cut -c1-7; git rev-list --count origin/main..HEAD  # 状态锚
PY=/opt/homebrew/Caskroom/miniconda/base/envs/py3.12/bin/python
$PY -m pytest tests/test_cli_interrupt.py -q -n0                       # 14 passed
$PY -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q -n0   # 429 passed, 2 deselected
$PY -m pytest tests/test_cli.py tests/test_gitflow.py -q -n0           # 62 passed
hm check cli . --strict 2>&1 | grep 中断收敛                            # ✅ 8/8（行级；整仓仍 ❌ 属既有 ⚠️）
python3 cache/scratch/cl007_guard_matrix.py                            # 6/6 PASS（不含 demo）
python3 cache/scratch/cl007_a4_probe.py                                # 3× rc=130 + 信封
set -m; lr status --json & PID=$!; sleep 0.25; kill -INT $PID; wait $PID; echo "rc=$?"   # 130 + 58B/80B
git checkout -- timestamp.json overview.json data/snapshot.json        # 跑完必做：还原测试脏产物
```

> **2026-11-06 实测覆盖（本会话新增测试后）**：全量 `540 passed, 2 deselected`；
> `tests/test_cli.py` 24 passed；`tests/test_gitflow.py + tests/test_status.py` 78 passed；
> 新增 `tests/test_push_on_skip.py` 9 passed、`tests/test_collector_dotenv.py` 6 passed。
> 上面三条命令的历史数字（429 / 62 / 14）是 CL007 基线，未改口径，仅作对照。

## 5. 文件索引

| 用途 | 路径 |
|:--|:--|
| 待执行清单（本文件） | `TODO-handoff.md` |
| 设计记录 canonical | `documents/solutions/llm-radar-cl007-cli-interrupt-guard-design-v1.0-20261103.md` |
| 设计摘要 | `documents/ops/cl007-cli-interrupt-guard-v1.0-20261103.md` |
| 评审报告（含 §12 delta） | `documents/reviews/llm-radar-cli-interrupt-guard-review-v1.0-20261103.md` |
| 评审任务书（首轮 / delta） | `cache/review-prep/20261103-cl007-cli-interrupt.md` / `…-delta.md`（gitignored） |
| 回执 + 跨仓 prompt | `cache/handoff/CL007-interrupt-guard-receipt-20261103.md`、`cache/handoff/prompt-hermes-manager-cli-interrupt-template-20261103.md`（gitignored） |
| 探针脚本 | `cache/scratch/cl007_guard_matrix.py`、`cl007_a4_probe.py`（gitignored） |
| wrapper 备份（改前） | `cache/scratch/llm-radar-wrapper.sh.cl007-bak`（gitignored） |

## 6. 纪律（违反会被评审打回）

1. **push 必须用户口令**；禁 `--force` / `rebase` 改历史 / `amend` 已审笔（`14dc48f`、`9b777b6` 已审）。
2. `AGENTS.md` / `CLAUDE.md` 受保护：须交互式单行 patch + 人工审批，禁 `-z`/`yolo` 直写。
3. 提交一律 path-scoped：`git commit -m "type@scope: subject" --only -- <paths>`（`-m` 在 `--` 之前）；
   提交后 `git show --name-only --format= HEAD` 证明零夹带。
4. 全量 pytest 会写脏 `timestamp.json` / `overview.json` / `data/snapshot.json` ⇒ 跑完 `git checkout --` 还原。
5. 改 wrapper（gitignored）后**必须**重跑 §4 的 `set -m` 那条；wrapper 若被 `install.py --force` 重生成，trap 会静默丢失。
6. 下一批做完走「小批复核」：打包一小笔 + 短任务书给 review（`--query-file … --oneshot -Q --yolo --in <repo>`，
   首段写「只做返工重审、不扩张范围」），**不重开全量评审**；PASS 后不再往仓里掺未审改动。
7. 台账条目格式：`cache/draft/TODO-<date>.md` 里**行首不能带 `>`**（`hm loop list` 解析不到），
   写 `- [ ] 标题: 描述（分类: …; 状态: READY; 闭环: LLM-RADAR-CL007; kind: queued; …）`，登记后
   `hm loop list --pending | grep CL007` 复核。
8. 完成由用户说「已核实」后执行 `hm loop verify LLM-RADAR-CL007`，AI 不自标完成。
