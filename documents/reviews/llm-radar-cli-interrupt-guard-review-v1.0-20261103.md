# llm-radar CL007 CLI 中断收敛（Ctrl-C 守卫）— review 报告 v1.0

- **日期**：2026-11-03
- **审查者**：Security Reviewer（review profile，L2）
- **受审提交**：`14dc48f fix@cli: Ctrl-C 守卫覆盖 import 期并统一 exit 130 (CL007)`，10 文件 / +304 −35
- **自查基线**：`db61a76`（`git rev-list --left-right --count origin/main...HEAD` = `0 1`，本地 ahead 1，未 push）
- **规范真源**：`~/CodeSpace/hermes-manager/skills-governance/cli-args-reference.md` v1.28（§11 中断收敛 4 条 + §11.2 三行模板 + §7 信封；只读，未改）
- **方法**：仓库事实复算（pytest / `hm check` / git）+ **真信号探针**（`set -m` 后台作业 + `kill -INT`，避免非交互 shell 的 SIG_IGN 陷阱）
  + **变异测试**（M1–M6 + M3 精确计数 + M6b/M6c 鉴别力对照）+ **import 竞态注入探针**（`sys.settrace` 在指定模块 import 期抛 KeyboardInterrupt）
  + 基线 worktree 对照（`/tmp/lr-base` = `db61a76`）
- **结论**：**PASS — 91/100**，`authorized_for_push = YES`
  （无 🔴；5 项 🟡 均为「wrapper 侧 / 钉子鉴别力 / 验收命令可复现性 / 门禁残余」类，核心四条硬条实现全部拿到独立证据）

---

## 1. 结论摘要

1. **四条硬条全部达标，且不是靠作者自述达标**。§11.1-1「唯一捕获点」/ -2「护栏覆盖模块级 import」/ -3「`--json` 信封 + stderr」/ -4「退出码 130」逐条有本报告独立取证（§4、§5），其中 import 期护栏用 **4 个真实 import 点注入**验证（`json/__init__.py` / `socket.py` / `shutil.py` / `flclash_proxy.py` 全部收敛 `SystemExit=130` 且零 traceback）。
2. **"重依赖惰性化"是真做了，不是搬到别处**。AST 扫描 collector 模块级 54 条执行语句，**全部为轻量**（env 解析 / Path 拼接 / 字面量 / `platform.system()`）；`openai`(0.34s)/`requests`/`prettytable` 三个重依赖仅在调用处出现，且请求点都在 `try/except Exception` 内（KeyboardInterrupt 是 BaseException，不会顺带被吞）。
3. **上一版"只包 main()"的病根已消除**：报障原文 `line 40, in <module> from openai import OpenAI … KeyboardInterrupt` 的那条路径在本次改动后不可能再触发（模块级已无该 import）。这条是本次评审最硬的回归证明。
4. **变异 6 组全部真红、全部可还原**（`sha256` 逐字节复核对齐，§6）。但**静态回退钉子的鉴别力不足**：M6b（连 import 行一起换掉、只留注释）静态钉子仍绿，M6c（连注释一起删）才红 ⇒ 钉子挡住了"整段退回"，挡不住"留注释保绿"（LR-CLI-004）。
5. **wrapper 侧实测出一处真实缺陷**：`--json` 模式下 env 段中断的两个人读提示**写 stderr 全部丢失**（`err=0B`，连 trap 首行的 `echo >&2` 探针也是 0B，而 fd1 正常）⇒ 用户只看到一行信封。已实测出修法（`exec 3>&2` + `>&3`，err 恢复 81B），见 LR-CLI-002。
6. **交接单里的"真实路径"验收命令按原样跑会误导人**：非交互 shell 的后台作业继承 `SIGINT=SIG_IGN`，同一命令 7/7 抽样 `rc=0`、零提示；加 `set -m` 后 7/7 `rc=130` + 两行提示 + 零 traceback。这条命令同时写在 handbook §六，必须修正，否则后续复核会把「守卫正常」误判成「守卫失效」（LR-CLI-005）。
7. **仓门禁仍未绿**：`hm check cli . --strict` = `中断收敛: 7/8`（缺 `scripts/mcp-protocol-demo.py`）⇒ 整仓 CLI 检查仍 ❌。本批把 1/8 提到 7/8，属改善但不闭合（LR-CLI-001，下一批 2 行可收）。
8. **一处仓级口径事实（不单方面改判）**：受审笔 subject 含 CJK，与 CL008「subject 全英文」冲突 —— `hm check commit` 默认 ✅、`--strict` ❌（31 条新笔同病，含本仓 6 笔历史 review 笔）。本审按「默认门禁绿 + 仓级历史一致」维持 PASS，**是否执行 CL008 交用户裁定**（LR-CLI-009 / T-4）
9. **安全面零新增攻击面**：`cli_interrupt` 不注册信号处理器、无 import 期副作用、无网络/文件写；新增行零凭据、零 `debug` 日志；`AGENTS.md` / `CLAUDE.md` / `.cli-registry.yaml` / crontab / `_verify()` 全部未动（§7）。

---

## 2. 评分表

| 维度 | 权重 | 得分 | 依据 |
|:---|:---:|:---:|:---|
| §11 四条硬条实现正确性 | 30 | 28 | 四条全部独立取证（§4/§5）；扣分点：wrapper 侧 json 分支 stderr 全丢（LR-CLI-002）属 -3 后半条的实现缺口 |
| 覆盖面（import 期/6 脚本/真实路径） | 20 | 18 | 4 个 import 点注入 + 6 脚本入口矩阵 + 真信号 7/7；扣分点：`mcp-protocol-demo.py` 未覆盖致仓门禁 7/8（LR-CLI-001） |
| 钉子质量（能否防退） | 20 | 15 | 12 例、M1–M6 全红；扣分点：静态钉子注释即满足（LR-CLI-004）、wrapper 侧零 tracked 钉（GOV-1 未闭） |
| 文档与验收可复现 | 15 | 11 | handbook §六契约描述准确、边界 5 条如实；扣分点：验收命令漏 `set -m`（LR-CLI-005）、"11 例"计数错（LR-CLI-006） |
| 安全（攻击面/凭据/日志/权限面） | 15 | 15 | 零新增攻击面；无凭据；无 debug 日志；受保护文件未动；未引入监督子进程（stdin 语义无回归） |
| **合计** | **100** | **91** | **PASS** |

---

## 3. 逐条实现判定（交接单 §1 的 6 条）

| # | 条目 | 判定 | 证据 |
|:--|:--|:--:|:--|
| 1 | 单一捕获点 + 单源文案 | **满足**（含 1 处记录性偏差） | 7 入口 `__main__` 段均 `from cli_interrupt import emit` + `except KeyboardInterrupt: emit(...)`；文案/退出码只有 `scripts/cli_interrupt.py` 一份（M5 变异红证明文案位真被钉）。⚠️ 记录：collector 因「既是入口又是库（3284 行）」形成**第二个捕获点 = 模块级 import 护栏**，这是 §11.1-2 要求与 §11.1-1「唯一」的张力，实现选择「库路径 `raise` 重抛」并通过 427 全量（`tests/conftest.py` 走 importlib 加载）证明未吞；探针亦证 import 期中断收敛 130 |
| 2 | 护栏覆盖模块级 import | **满足** | ① `openai`/`requests`/`prettytable` 移到调用处（`_call_deepseek` / 抓取 1 处 / `_cdp_call` / `list_sources`），无回漂；② AST 扫 collector 模块级 54 条语句全轻量；③ 注入探针 4 个 import 点全 `SystemExit=130`、零 traceback；④ 6 脚本入口模块级只有 stdlib，0.02–0.14s 抽样 6/6 `rc=130` 有提示无裸栈 |
| 3 | `--json` 信封（§7/§11.1-3） | **满足**（wrapper 侧有隐患） | A4 探针 3/3：stdout 恰好 58B 单行 `{"status": "error", "data": null, "error": "interrupted"}`，两行提示在 stderr；成功态七字段巡检信封未动（`lr status --json` 实测 7 字段 / `rc=0` / stderr 0 字节，`tests/test_cli.py:160` 钉仍在）。⚠️ LR-CLI-002：wrapper（bash）侧 json 分支的 stderr 提示实测全丢 |
| 4 | 退出码 130 | **满足** | Python `SystemExit(130)`；真信号 7/7（1.0–4.0s 步长）；wrapper env 段 7/7（0.02–0.40s）；6 脚本矩阵 + 裸 `python3 scripts/*.py` 路径均 130 |
| 5 | wrapper 期兜底（加做项） | **有隐患** | trap 确实生效（埋点 log 3/3 `TRAP-FIRED`，rc=130，人类模式两行提示在 stdout 可见）；但 json 模式 stderr 全丢（LR-CLI-002）；且落在 gitignored 生成物（GOV-1 未闭，见 Q2） |
| 6 | 新增 12 例钉子 | **满足**（鉴别力有缺口） | `12 passed in 0.78s`；M1–M6 全红（§6）；缺口 = 静态钉子只查字符串存在（LR-CLI-004） |

**关于 `llm-radar-mcp-server.py` 的形态**（值得单独记录，不判红）：其余 6 入口把 try 放在 `__main__` 段，mcp-server 把 try 放在 `__main__` 段内的 dispatch 处，且 `run_http_server` 另有一处 `serve_forever()` 的 `except KeyboardInterrupt`（打印「⏹️ 服务器已停止」后 `rc=0`）。这与 §11.1-1 的字面（"只在 `__main__` 的 try 中捕获一次"）存在偏离，但语义上仍是进程边界捕获、且 serve_forever 的 Ctrl-C 是**优雅停止**而非「未完成」，实现与 handbook §六第 5 条口径一致。判定：**记录，不判红**；风险提示 = 同一进程内存在两处捕获点，后续若在 `run_http_server` 里新增 `except KeyboardInterrupt: pass` 会静默吞中断，建议下一批加注释钉子。

---

## 4. 数据验证（命令原样 + 实测结果）

```bash
cd /Users/jadenli/CodeSpace/llm-radar.lab
PY=/opt/homebrew/Caskroom/miniconda/base/envs/py3.12/bin/python
$PY -m pytest tests/test_cli_interrupt.py -q -n0
# -> 12 passed in 0.78s

$PY -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q -n0
# -> 427 passed, 2 deselected, 2 warnings in 95.32s

$PY -m pytest tests/test_cli.py tests/test_gitflow.py -q -n0
# -> 62 passed in 3.02s

python3 cache/scratch/cl007_guard_matrix.py
# -> 合计 6/6 PASS（6 个脚本入口 rc=130，文案齐全）

python3 cache/scratch/cl007_a4_probe.py
# -> [1]/[2]/[3] rc=130 envelope_ok=True hints_in_stderr=2 stdout_lines=1 traceback=False
#    stdout: '{"status": "error", "data": null, "error": "interrupted"}'
```

**真实路径（人类模式）** —— 交接单给的命令**按原样在脚本里跑不出 130**，原因见 LR-CLI-005：

```bash
# 交接单原样（非交互 shell）: 7/7 抽样 rc=0、零提示（SIGINT 被 SIG_IGN 继承）
lr fetch qbitai & PID=$!; sleep 3; kill -INT $PID; wait $PID; echo "rc=$?"   # -> rc=0

# 加 set -m 后（作业控制开启，SIGINT 正常投递）: 7/7 全部收敛
set -m
for d in 1.0 1.5 2.0 2.5 3.0 3.5 4.0; do lr fetch qbitai & PID=$!; sleep $d; kill -INT $PID; wait $PID; echo "d=$d rc=$?"; done
# -> 7/7 rc=130，hint_lines=1，traceback=0，末尾 '   💡 重跑: lr fetch qbitai'
#    样例: '⛔ 已中断 (Ctrl-C) — lr fetch 未完成'（第 2 行按 §11.2 省略）
```

**wrapper env 段窗口（0.02–0.40s，共 7 点）**

```
d=0.02 rc=130 hints=1 traceback=0 first='⛔ 已中断 (Ctrl-C) — lr status 未完成'
d=0.10 rc=130 hints=1 traceback=0
d=0.40 rc=130 hints=1 traceback=0
```

**wrapper `--json` 模式（0.05–0.25s）—— 缺陷现场**

```
d=0.05 rc=130 out_bytes=58 err_bytes=0   out=[{"status": "error", "data": null, "error": "interrupted"}]
d=0.10 rc=130 out_bytes=58 err_bytes=0   err=[]          <-- 两行人类提示丢失
d=0.25 rc=130 out_bytes=58 err_bytes=0   err=[]
# 埋点对照: trap 首行 echo "STDERR-PROBE" >&2 同样 0B ⇒ 不是 emit 逻辑问题, 是该 trap 上下文 fd2 写不进
# 修法实测: 包装器顶部 exec 3>&2, 提示改 >&3  ⇒ err_bytes=81, err=[⛔ 已中断…|💡 重跑: lr status --json]
```

**import 期护栏探针（`sys.settrace` 在指定模块 import 期抛 KeyboardInterrupt，`run_name='__main__'`）**

```
target=json/__init__.py   fired=True SystemExit=130  + 两行提示, 零 traceback
target=socket.py          fired=True SystemExit=130
target=shutil.py          fired=True SystemExit=130
target=flclash_proxy.py   fired=True SystemExit=130
target=os.py              fired=False（os 在探针进程已被 site 预载，无 call 事件；实进程 os 为首个 import，见 §9 待确认 T-1）
```

**仓门禁（独立于作者自述）**

```bash
hm check cli . --strict
# -> ❌ 中断收敛: 7/8 入口含 KeyboardInterrupt 守卫（缺: mcp-protocol-demo.py）
```

**基线 worktree 对照（`/tmp/lr-base` = `db61a76`）**：全量 `415 passed, 2 deselected`（97.32s）⇒ 本批 `427 = 415 + 12`，**新增恰好 12 例、零回归**；`hm check cli --strict` 中断收敛 **2/8**（缺 `mcp_submit_update / chromedriver_bootstrap / flclash_proxy / twitter-collector / mcp-protocol-demo …`）⇒ 本批为净改善（2/8 → 7/8）、未闭合。

**测试脏产物已还原**：`git checkout -- timestamp.json overview.json data/snapshot.json`（跑完全量后 `git status --short` 为空）。

---

## 5. 变异测试（M1–M6 + 2 组补充）

还原口径：每轮变异后 `git checkout`-等价的逐字节回写 + `sha256` 复核 + `py_compile`。

基线 sha256：

```
llm-radar-collector.py   269f941d31eea5fa64ad3134ef7004090e230db04284a2ecc2af70b91f8fff16
scripts/cli_interrupt.py ebe4162b78bd118f8b8772c761bee55ef2481c697739575107b0675a66b004b1
scripts/flclash_proxy.py 31a56c09c3646ea6572ced75a28d3ed104e016275c0e3c4aa87c21592ddc3f01
```

| # | 变异 | 期望 | 实测 | 还原 sha 一致 |
|:--|:--|:--|:--|:--:|
| M1 | collector `__main__` 段 `except KeyboardInterrupt: emit(...)` 整段删 | 人类模式用例红 | 🔴 **1 failed**（`test_human_mode_interrupt_prints_hint_and_exit_130`） | ✅ |
| M2 | `emit()` json 分支 `stream = sys.stderr` → `sys.stdout` | json 信封用例红 | 🔴 **1 failed**（`test_json_mode_stdout_is_envelope_only`） | ✅ |
| M3 | `EXIT_INTERRUPTED = 130` → `1` | 全部 rc 断言红 | 🔴 **9 failed / 3 passed**（3 绿 = 无 traceback 例 + 2 条静态例，均不含 rc 断言，符合预期） | ✅ |
| M4 | import 护栏 `raise` → `pass` | 静态重抛例红 | 🔴 **1 failed**（`test_static_collector_import_guard_reraises_for_library_use`） | ✅ |
| M5 | `_cmd_label()` 恒返回 `prog` | 文案断言红 | 🔴 **1 failed**（人类模式文案例） | ✅ |
| M6 | flclash 入口 `emit(...)` → `print('用户中断操作'); sys.exit(1)`（保留 import 行） | 矩阵用例红 + 静态钉子？ | 矩阵 🔴 **1 failed**（`…[scripts/flclash_proxy.py]`）；**静态钉子仍绿** ⇒ LR-CLI-004 | ✅ |
| M6b | 同上，但**连 import 行一起换掉、保留上方注释** | 静态钉子应有鉴别力 | 🟢 **静态钉子仍绿**（11 passed）⇒ 注释里的 `cli_interrupt` 字样即可满足 | ✅ |
| M6c | 同 M6b，再删掉注释行 | 静态钉子红 | 🔴 **1 failed** | ✅ |

**M3 的 3 个绿**说明钉子是「按断言维度分层」的（rc 层 / 文案层 / 静态层），不是一个大用例，这一点设计正确。

---

## 6. 发现清单

### 🟡 下一批（P2，不阻塞本次 push）

| ID | 标题 | 证据 | 修复建议 |
|:--|:--|:--|:--|
| **LR-CLI-001** | 仓门禁 `hm check cli . --strict` 仍 ❌（中断收敛 7/8，缺 `scripts/mcp-protocol-demo.py`） | `hm check cli . --strict` → `❌ 中断收敛: 7/8`；交接单把 demo 归到"另批"，但 gate 不认这个豁免 | 二选一：① demo 入口补 5 行守卫（成本最低，与本批同形态）；② 在 `hm check cli` 侧登记豁免（跨仓，周期长）。建议 ① |
| **LR-CLI-002** | wrapper（bash）`--json` 模式中断的人类提示写 stderr **全部丢失** | 5 个 delay × 3 轮：`out_bytes=58 / err_bytes=0`；trap 首行 `echo "STDERR-PROBE" >&2` 亦 0B（非 emit 逻辑，是该 trap 上下文 fd2 不可写）；`exec 3>&2` + `>&3` 实测恢复 81B | 模板侧：包装器顶部 `exec 3>&2`，trap 内提示写 `>&3`；同时补一条 shell 级钉子（脚本化 `set -m` + `kill -INT`） |
| **LR-CLI-003** | `_rerun_line()` 不做 shell 引号 ⇒「同一条可复制命令」对含空格/元字符的实参**语义漂移** | `_rerun_line` = `' '.join([prog] + argv[1:])`；`lr commit "wip; rm -rf /tmp/x"` 会打印成 `lr commit wip; rm -rf /tmp/x`（复粘即执行不同命令） | 改 `shlex.join([prog] + sys.argv[1:])`；wrapper 侧 `${LLM_RADAR_ARGV[*]}` 同问题（用 `printf %q`）。属 §11.2「不得给需要补参数的半成品」的上位要求 |
| **LR-CLI-004** | 静态回退钉子鉴别力不足：只断言文件里出现 `cli_interrupt` 字符串 ⇒ 注释即满足 | M6b（删代码留注释）静态钉子**绿**；M6c（连注释删）才红 | 断言收紧为「`__main__` 段切片内同时出现 `except KeyboardInterrupt` 与 `emit(`」，并断言 7 入口逐个命中（现只判"文件含字符串"） |
| **LR-CLI-005** | 验收命令不可复现：非交互 shell 的后台作业继承 `SIGINT=SIG_IGN` ⇒ 交接单/handbook §六 那条 `lr fetch qbitai & … kill -INT` 实测 7/7 `rc=0`、零提示 | 无 `set -m`：7/7 `rc=0`（且抓取跑完）；加 `set -m`：7/7 `rc=130` + 提示 | handbook §六与验收块补 `set -m`（或 `setsid` + `kill -INT -PGID`），并写明"脚本/agent 环境必须开作业控制" |

### 🟢 记录（不修）

| ID | 标题 | 说明 |
|:--|:--|:--|
| **LR-CLI-006** | handbook 写「单元/行为钉（11 例）」，实测 **12 例** | `12 passed`；顺手改数字即可 |
| **LR-CLI-007** | `emit()` 写 stdout/stderr 无 `OSError` 兜底 | `lr status \| head -1` 这类已关管道 + Ctrl-C ⇒ `BrokenPipeError` 覆盖中断文案；代码级判定，未专门构造信号竞争 |
| **LR-CLI-008** | bash 侧手抄第二份文案（§11.2「禁手抄第二份」） | JSON 信封字面量与两行提示在 wrapper 内重复；人类模式首行多一个前导 `\n`（python 侧没有）⇒ 模板侧应改为调用 `python3 -c` 里的 `emit`，或至少逐字节对齐 |
| **LR-CLI-009** | 受审笔 subject 含 CJK，与 CL008「subject 全英文」冲突（`hm check commit` 默认 ✅ / `--strict` ❌） | `hm check commit --strict` 把 `14dc48f` 计入「含中文字符 subject: 31 条（❌ 硬错误…新笔 31 条按治理裁定须英文, 违规记审计 CONDITIONAL）」；同清单含本仓 6 笔历史 review 笔 ⇒ 仓级口径从未执行 | 见 §9 T-4；本审不单方面改判（默认门禁绿 + 31 笔仓级历史），**是否执行 CL008 由用户裁定**；若执行，需 `git commit --amend` 改 subject（本审不做，改名会改已审 hash） |

---

## 7. 安全审查（Security Reviewer 视角）

| 项 | 结论 | 证据 |
|:--|:--|:--|
| 新增攻击面 | 🟢 零 | `cli_interrupt` 只做 `json.dumps` 静态字典 + `print` + `SystemExit`；不注册信号处理器、不读环境变量、不写文件、不联网 |
| 凭据/密钥 | 🟢 无 | 新增行扫描 `sk-…` / `api_key=<字面量>` / `secret` / `passwd` 零命中；`tests/test_cli_interrupt.py` 的 `LLM_RADAR_MCP_KEY='probe-only-not-a-credential'` 是过闸占位值，非真实凭据 |
| 日志规范 | 🟢 合规 | 无新增 `debug` 级日志（Console 规范）；错误仍走既有 `❌ 错误` 单行收口 |
| 命令注入 / 复粘执行面 | 🟡 见 LR-CLI-003 | 中断提示把 argv 原样拼进"可复制命令"，含 `;`/`|`/引号的实参会改变语义；风险通道是**用户复粘**，不是自动执行 |
| 终端转义注入 | 🟢 低 | argv 由用户自己输入并回显，未见外部摄入文本进入提示（抓取文本不经过 emit） |
| 进程/信号语义 | 🟢 无回归 | 未引入"监督子进程 + kill 转发"，MCP server stdio 的 stdin 语义与退出码保真度不变（这是 Q3 拒绝该方案的关键依据） |
| 受保护文件 | 🟢 未动 | `AGENTS.md` / `CLAUDE.md` / `.cli-registry.yaml` / crontab / `_verify()` 全未触及（`git show --stat` 核对） |
| 数据产物 | 🟢 | 未改 `data/snapshot.json` 等生产产物；评审跑测试产生的脏产物已 `git checkout` 还原 |

---

## 8. 口径裁定（Q1–Q4）

**Q1 「`status --json` 两态两形，接受先判 rc 还是要求中断态带 `id`？」**
→ **接受「先判 rc（或 `status == 'error'`）再取字段」，不要求中断态补 `id`/`label`。**
理由：① §7 只定义了一个错误信封，补 `id` 等于造第三种形状，跨仓会立刻分叉；② 两态其实已有第二个判别位（巡检信封 `status ∈ ok|warning|critical|info`，中断信封恒 `error`），硬判据不缺；③ 现有钉子 `test_json_mode_stdout_is_envelope_only` 用**精确等值**锁定了信封形状，等于把"不许多字段"钉死，这是对的，别动。
附加要求（下一批，文档级）：在 handbook §六 之外，把"消费方契约 = rc 优先 + `status` 兜底"写进 `documents/`（现 §六 已有一句 ⚠ 足够，建议升为独立小节，避免下一批有人来"补 id"）。

**Q2 「wrapper trap 落在 gitignored 生成物，接受本批不落模板 + 回执声明？」**
→ **接受不阻塞本次 push，但回执声明必须升级为两条硬约束。** 理由：GOV-1 是既有债（`.env` 段同样是手工 patch），本批把 trap 加进生成物属"止血"而非"治本"，把它当阻断条件等于用一个已知未闭的债卡死一次净改善。
附加约束：① 跨仓模板回填**必须带 LR-CLI-002 的 fd3 修正**，否则会把"json 模式零人读提示"这个缺陷复制到所有项目；② 仓内要留**tracked** 的模板片段（patch 片段或 handbook 代码块），让"机器重装即失"可被 review 复算 —— 现在库内零钉，重装后无人能发现退化。

**Q3 「解释器启动段 20–40ms 接不到，接受为边界还是改监督子进程？」**
→ **接受为边界，明确拒绝"监督子进程 + kill 转发"。** 理由：代价不对称 —— 换来的是约 1.7% 时序窗口内"静默 `rc=-2` 或 `line 0` 裸栈"，付出的是 MCP stdio 的 stdin 透传语义、退出码保真、`kill`/`wait` 语义、PID 文件一致性（§2-16 判据）全部要重算，风险远大于收益。
附加要求（跨仓，文档级）：这条边界目前只写在**本仓 handbook**，而规范 §11.4 只列了"子进程"/"SIGTERM"两条 ⇒ 应把"解释器启动段不可覆盖（≈20–40ms，抽样 98.3%）"补进 `cli-args-reference.md` §11.4，否则每个仓都会重新发现一次并各自造词。

**Q4 「6 个 scripts 入口用 `python3 scripts/xxx.py`，collector 用 `lr`，是否统一？」**
→ **不统一，规矩应改为「prog = 该入口的真实可调用形态」。** 依据：§11.2 第 3 行的合同是"同一条**可复制**命令"。6 个脚本没有 wrapper（`lr` 只 `exec` collector），统一成 `lr` 会让重跑行**不可执行**；反过来让 collector 用 `python3 llm-radar-collector.py` 又和用户实际敲的 `lr` 不一致，且丢掉 wrapper 的环境段（conda/`.env`）⇒ 复跑大概率失败。
附加要求（跨仓，文档级）：把该口径写进 §11.2 附注「有 wrapper 用 wrapper 名；无 wrapper 用"解释器 + 仓内相对路径"」，并顺带规定 LR-CLI-003（必须 `shlex.join`）。

---

## 9. 待确认（T）

| ID | 项 | 为什么现在下不了结论 | 建议取证方式 |
|:--|:--|:--|:--|
| **T-1** | collector `import os`（首个 import）期间被中断时，护栏能否自举 | 探针进程里 `os` 已被 `site` 预载，无法构造"os 尚未 import"的入口态；CPython 在 import 失败时会把半初始化模块从 `sys.modules` 移除，理论上重入安全 | 用 `python3 -S -c` 起最小解释器（无 site），在 `os` import 前注入 trace 打断，看是否 `SystemExit=130` |
| **T-2** | `emit()` 在 stdout 已关闭（`\| head -0`）时的行为 | 需要"关管道 + 精确信号时序"双竞争，本次未构造 | `lr status \| head -1` 配合 `set -m` + `kill -INT`，看是否出 `BrokenPipeError` 裸栈（对应 LR-CLI-007） |
| **T-3** | `serve_forever()` 的 `rc=0`（优雅停止）是否会被 `hm check`/调度侧误判为"中断后成功" | 需要看 ops 侧调度器对 `rc` 的消费口径（cron 不判 rc；agent-loop 才判） | 查 `cron/scheduler.py` 对 `lr start` 的 rc 使用点 |
| **T-4** | CL008「commit subject 全英文」是否对本仓强制 | 默认门禁 `hm check commit` = ✅；`--strict` 下 31 条新笔全红（含 6 笔历史 `audit@review:` 中文 subject），且 `auto-push` type 本身就在 type 清单外（208 条）⇒ strict 在本仓实际不可用 | 用户裁定：① 保持默认（中文 subject 继续）② 仓级切 strict（需先处理 auto-push 与 31 笔存量）③ 只管新笔（则本笔需 amend，会改已审 hash） |

---

## 10. 下一批清单（按优先级）

| 序 | 项 | 类型 | 验收 |
|:--|:--|:--|:--|
| 1 | **LR-CLI-002** wrapper json 分支 stderr 丢失 ⇒ `exec 3>&2` / `>&3` + shell 级钉子 | 代码（gitignored + 模板） | 脚本化 `set -m` + `kill -INT`：`err_bytes > 0` 且含两行提示；信封 58B 不变 |
| 2 | **LR-CLI-001** `scripts/mcp-protocol-demo.py` 补守卫 ⇒ `hm check cli . --strict` 中断收敛 8/8 | 代码 | `hm check cli . --strict` 该行 ✅ |
| 3 | **LR-CLI-005** 验收命令补 `set -m`（handbook §六 + 交接模板） | 文档 | 复制粘贴即得 130（本次已实测 7/7） |
| 4 | **LR-CLI-004** 静态钉子收紧到 `__main__` 段切片 + `emit(` 同时存在 | 测试 | M6b 应转红（现为绿） |
| 5 | **LR-CLI-003** `_rerun_line` 改 `shlex.join`；wrapper 侧 `printf %q` | 代码 | 含空格/`;` 的实参重跑行可原样执行 |
| 6 | **LR-CLI-006/008** 计数修正 + bash 文案改调用单源 | 文档/代码 | 文案逐字节同源 |
| 7 | 跨仓：§11.4 补"解释器启动段"边界；§11.2 补 prog 口径 + `shlex` 要求 | 治理文档 | `cli-args-reference.md` v1.29 |

---

## 11. 治理与交付回执

- 受审 commit：`14dc48f`（10 文件，+304/−35），**无 force / 无 rebase / 无 amend 痕迹**；`AGENTS.md`、`CLAUDE.md` 未动。
- 评审三件：本报告 + `review-log.md`（Style B 追加）+ `.review-level.yaml`（`review_history` 追加，`safe_load` 复验），自成 `review@audit:` 一笔。
- 变异还原：3 个被改文件 `sha256` 与基线逐字节一致（§5），`py_compile` 全部 `rc=0`。
- 测试脏产物：`timestamp.json` / `overview.json` / `data/snapshot.json` 已 `git checkout` 还原。
- 结论：**PASS**，`authorized_for_push = YES`（用户本轮已授权）。
