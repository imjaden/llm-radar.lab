# TODO-HANDOFF — llm-radar CL007 后续待执行清单
<!-- generated: 2026-11-12 · source: cache/draft/TODO-20261112.md · sha256:a3c2aa61 -->
> 派生: 待执行 **0** 条 · 最近闭环 **CL17** · 差异知会 无（未找到含「差异知会」的设计文档）
> （本行由 `hm loop entry-page` 自动统计，人工段勿复述这些数字；`hm check handoff` 校验人工段声明与实数一致）
## 一、已登记待执行（来源: live draft cache/draft/TODO-20261112.md）

- (无已登记待执行条目)
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

> **时点快照（2026-11-12 11:10）**：本仓队列 **空**，停滞台账 **0 条**。
> 11-12 闭环：`CL017`（launchd 页签循环 → guard 幂等，plist 已重载 `runs=1`）、`CL009`（跃迁式告警 + 本地通道）、
> `CL006` / `CL-SEC11` 停滞豁免（后者需先修 hermes-manager 的编号子串匹配，已修 `a07f3949`，未推）。
> 待审计 commit：**无**。明早首跑：`pytest -q -n0 -k "alert_dispatch or chrome_agent_guard or chrome_page_target"`；
> 全量留清晨（基线 **602 passed** / `test_cli` 24 / 门禁 `中断收敛 10/10` / `readme 2/2` / `handoff 0 行`）。


**S0　流程约定（立即生效，等 hm 侧修好后可撤）**
凡「直改源码型」条目，`hm loop verify` **之前**先落一对 retro 到 `cache/closed-loop/`
（`{date}-llm-radar-ops-LLM-RADAR-CL0NN-retro.{json,md}`，含 `chain/commit/evidence/learnings/pending`），
否则看板次日会标 `doc-missing`（判据：`[6/6]` + `retro_path` 空 ⇒ critical）。
已补档：`CL007–CL017` 全部；`CL009`/`CL017` 另有 `documents/reviews/` 可读复盘。
系统缺口转交件：`documents/handoff/20261112-to-hermes-manager-loop-verify-artifacts.md`。

**S1　观察：wdm 里 chromedriver 156 ↔ 本机 Chrome 157**
主采集仍 `6/6 源成功`（旧驱动可用），X 侧走稳定指针 157。复核：
`grep "与本机 Chrome" cache/logs/llm-radar-collector/collector.log | tail -3`。
若出现 Selenium 源连败，第一嫌疑即此；修法 = 把 157 驱动按 wdm 布局补一份 → `lr reset-health` → `run --force`。
**属环境动作，需用户点名。**

**S2　观察：X 采集 5h 节流（预期行为，勿当故障）**
`twitter.json` 满 5h 才实采，`跳过: … 生成于 N h 前` 是正常路径；`lr status` 的「陈旧」阈值 6.5h 已 > 5h。

**S3　跨仓（不在本仓做）**
`hermes-manager` 侧修复笔 `a07f3949`（段边界匹配）**未推**，等该仓会话放行；该仓工作树另有 4 个
`web/*/index.html` 改动属其他会话 WIP，勿动。

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
