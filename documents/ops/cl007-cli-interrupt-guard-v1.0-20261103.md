---
title: LLM-RADAR-CL007 方案 — CLI 中断收敛（Ctrl-C 不吐裸栈，中断与失败可区分）
topic: llm-radar
type: design
version: 1.0
date: 2026-11-03
author: dev
profile: dev
---

# CL007 方案 · CLI 中断收敛（KeyboardInterrupt 守卫）

> 任务书（只读）：`hermes-manager/documents/handoff/20261103-to-llm-radar-cli-interrupt-guard-prompt.md` §1-§4
> 规范真源（只读）：`hermes-manager/skills-governance/cli-args-reference.md` §11（v1.28）+ §7（信封）
> 改动范围：仅 `~/CodeSpace/llm-radar.lab`；本文件为步骤 1/6（只出方案，不改任何 `.py`、不 commit、不 push）

## 0. 结论先行 + 取证时点（必须读）

**结论**：方案 = 「单源收口模块 `scripts/cli_interrupt.py` + 各入口 `__main__` 段唯一捕获 + 重依赖惰性化」。
只把 `main()` 包进 `try` 不够（缺陷发生在模块级 import 期，不经过入口段），因此**同时**做两件事：把
`openai` / `prettytable` / `requests` 从模块级撤到调用处，并在 collector 的 import 块外套一层自带护栏的
`try`（被 importlib 当库加载时**重抛**）。

**取证时点（诚实交代，勿误读）**：本仓 `CL007` 的实现已在基线 HEAD 落地
（`14dc48f fix@cli: Ctrl-C 守卫覆盖 import 期并统一 exit 130 (CL007)` + 复核轮 `9b777b6`，评审 `6c7fea3`
PASS 91/100；复核轮 `dfbdc85` PASS 92/100，均已 push `origin/main`）。因此本文档的取证分两栏：

- **缺陷态** = `14dc48f^`（2026-11-03 13:49 之前），即任务书 §2 实测那段裸栈的现场；
- **现态** = HEAD `9b777b6`，即本方案对应的实现形态（已用真实命令核实，见 §1、§4）。

本文档的作用：把「为什么这样改」固化成设计记录，并给出可复跑的判据；**不是**再改一遍代码。
若后续要做的是复核或返工，以 §4 判据为准。

## 1. 现状取证

### 1.1 入口结构（`llm-radar-collector.py`）

| 项 | 缺陷态 `14dc48f^` | 现态 HEAD `9b777b6` |
|:--|:--|:--|
| 体量 | 3284 行 | 3300 行（+16 行护栏/注释） |
| 分发方式 | **无 argparse**，`main()`（L3177）里 `if command == '...'` 手工分发；`argv[1]` 即子命令 | 未变（本任务未碰命令面） |
| import 块 | L27-40 平铺，**模块级** `requests` / `from openai import OpenAI`（**L40**）/ `from prettytable import PrettyTable` | L31 起整块进 `try:`，重依赖已撤；L53 `except KeyboardInterrupt:` 入口自举收口 |
| 入口段 | L3276 `if __name__ == '__main__':` → `try: main()` | L3289；`from cli_interrupt import emit`（L3292）+ `except KeyboardInterrupt: emit('lr', sys.argv)` |
| 单文件双身份 | 既是入口也是库（`tests/conftest.py` 经 importlib 加载） | 未变；import 期护栏用 `if __name__ != '__main__': raise` 区分（库加载必须重抛，§11.1-1） |

**缺陷复现锚点**：任务书贴的裸栈是 `line 40, in <module>  from openai import OpenAI` —— 与缺陷态
`git show 14dc48f^:llm-radar-collector.py | sed -n '40p'` **逐字对应**。⇒ 中断点确在模块级 import，不在 `main()`。

### 1.2 import 期重依赖清单（缺陷根因）

| 依赖 | 缺陷态位置 | 耗时量级 | 处置（现态） |
|:--|:--|:--|:--|
| `openai` | 模块级 L40 | 0.4s 级（冷启动含 SSL/证书栈） | 惰性化到 `_llm_call` 内（L381） |
| `prettytable` | 模块级 L41 | 中 | 惰性化到 `sources` 子命令（L2652） |
| `requests` | 模块级 L36 | 中 | 惰性化到 2 处调用点（L1519 / L2832） |
| `flclash_proxy`（本仓辅助） | 模块级（需 `sys.path` 注入后 import） | 小 | 保留在 `try:` 内（自身无重依赖） |
| 其余 stdlib（os/re/json/sys/time/shutil/subprocess/platform/socket/html/pathlib/datetime） | 模块级 | 极小 | 保留在 `try:` 内，不惰性化（避免噪音） |

⇒ 惰性化后模块级只剩 stdlib，import 期窗口从「秒级」降到「毫秒级」；但**惰性化不是护栏本身**，
只是把窗口缩小。真正的护栏是 1.3 的 `try` + `cli_interrupt.emit`。

### 1.3 现有退出码面（改前/改后）

| 场景 | 缺陷态 | 现态（本仓契约） |
|:--|:--|:--|
| 正常完成 / help / 无参 | `0` | `0` 不变 |
| 通用失败（未知命令、目录缺失、抓取失败） | `1` | `1` 不变 |
| 用法错误 | 部分脚本 `2`（`chromedriver_bootstrap.py:396`、`flclash_proxy.py:216`、`twitter-collector.py:935/1005`） | `2` 不变 |
| **用户 Ctrl-C** | **`1`（collector：`print('\n用户中断操作'); sys.exit(1)`）或裸栈 `130/1` 不确定或 bash `rc=-2`** | **`130`**（新增，唯一真源常量 `EXIT_INTERRUPTED`） |

缺陷态 collector 入口段原文（`git show 14dc48f^:llm-radar-collector.py` L3276-3284）：

```python
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n用户中断操作')
        sys.exit(1)          # ← 与「失败」同码 ⇒ 调用方无法区分
    except Exception as e:
        print(f'\n❌ 错误: {e}')
        sys.exit(1)          # ← 同码，进一步混淆
```

两处硬伤：① `exit 1` 与失败同码（1A 调度会把用户中断当执行失败计入连败）；② `try` **只包 `main()`**，
import 期中断根本到不了这里（§11.1-2 明确「只包 `main()` 视为未达标」）。

### 1.4 入口全集（`grep -rln "if __name__" --include='*.py' .`，13 条命中）

| # | 路径 | 性质 | 本批处置 |
|:--|:--|:--|:--|
| 1 | `llm-radar-collector.py` | 主入口（双身份） | ✅ 改（import 护栏 + 入口段） |
| 2 | `scripts/twitter-collector.py` | X 采集入口 | ✅ 改 |
| 3 | `scripts/llm-radar-health.py` | 健康检查 | ✅ 改 |
| 4 | `scripts/flclash_proxy.py` | 代理 helper（兼 CLI） | ✅ 改 |
| 5 | `scripts/chromedriver_bootstrap.py` | driver 引导 | ✅ 改 |
| 6 | `scripts/mcp_submit_update.py` | MCP 提交 | ✅ 改 |
| 7 | `scripts/llm-radar-mcp-server.py` | MCP server | ✅ 改（仅 dispatch 期；`serve_forever` 属优雅停止，见 R-5） |
| 8 | `scripts/mcp-protocol-demo.py` | demo | ✅ 改（`hm check cli` 按「含 `__main__` 段的 `*.py`」计入口 ⇒ 7/8 会判缺，LR-CLI-001） |
| 9 | `tasks/al-init.py` | agent-loop 任务 | ⛔ 不动（中断语义涉状态机，另批） |
| 10 | `tasks/al-scanner.py` | agent-loop 任务 | ⛔ 不动（同上） |
| 11 | `cache/scratch/chromedriver_discriminator_demo.py` | 临时取证脚本（**gitignored**） | ⛔ 不动（不入仓产物） |
| 12 | `tests/test_twitter_cron.py` | 测试夹具：命中在**三引号字符串内**（L160，非真实入口） | ⛔ 不动（grep 假阳性，须在回执里注明） |
| 13 | `tests/test_cli_interrupt.py` | 本批新增（自带 `__main__` 在 heredoc 字符串内） | ➕ 新增 |

⇒ **白名单 = 8 个真实入口**（1-8）。第 12 条说明「A1 枚举计数会多 1」，直接拿 grep 计数当分母会得到
错误的 `m/n`，须人工剔除字符串假阳性 —— 这是本方案对 §5-A1 的口径修正。

## 2. 方案

### 2.1 形态选择（A/B/C，取 B）

| 方案 | 形态 | 判定 |
|:--|:--|:--|
| A | 每个入口手抄三行提示 + `sys.exit(130)`（7 份副本） | ❌ 文案/退出码必然漂移；§11.2「照抄执行」不等于抄 7 份 |
| **B** | **单源模块 `scripts/cli_interrupt.py`：`emit(prog, argv)` 打印 + `raise SystemExit(130)`；各入口只调一次** | ✅ **采纳**（§11.3 已明确「就地捕获 **或** 引用单源收口模块」为等价达标形态） |
| C | 注册 `signal.signal(SIGINT, handler)` 全局接管 | ❌ 会改变子进程/交互式语义，且对 import 期同样不覆盖首个字节码前窗口；与 §11.4 冲突 |

选 B 的附加理由：`emit()` 只做「打印 + 退出」，**不注册信号处理器、无 import 期副作用**，所以库模块可以安全
地引用它而不破坏 §11.1-1（库模块禁捕获/禁吞）。

### 2.2 收口模块契约（`scripts/cli_interrupt.py`，67 行）

| 元素 | 值 | 依据 |
|:--|:--|:--|
| `HUMAN_ABORTED` | `⛔ 已中断 (Ctrl-C) — {cmd} 未完成` | §11.2 第 1 行 |
| 第 2 行（进度） | **整行省略** —— 本仓 CLI 无 `n/total` 进度模型 | §11.2「无进度则整行省略」 |
| `HUMAN_RERUN` | `   💡 重跑: {cmdline}` | §11.2 第 3 行 |
| `cmdline` 生成 | `shlex.join([prog] + argv[1:])` | 同一条可复制命令；朴素空格拼接遇 `wip; rm -rf` 会诱导执行**另一条**命令（LR-CLI-003） |
| `ERROR_ENVELOPE` | `{"status": "error", "data": null, "error": "interrupted"}` | §11.1-3 逐字（字段顺序固定，测试按整串比） |
| `EXIT_INTERRUPTED` | `130` | §11.1-4 |
| 输出通道 | `--json` ⇒ 信封走 stdout，人类提示走 **stderr**；非 json ⇒ 提示走 **stdout** | §11.1-3 / §11.2 |
| `prog` | collector 传 `lr`（与 wrapper 侧逐字节同源）；脚本传 `python3 scripts/<name>.py` | 提示里的 `<指令>` 要能被用户直接复制 |

### 2.3 入口捕获覆盖模块级 import（双护栏）

**护栏 1 —— 重依赖惰性化**（缩小窗口，见 1.2）：模块级只留 stdlib。

**护栏 2 —— import 块自带 `try` + 库加载重抛**（collector 专用，因其 3300 行、import 无法搬进 `__main__`）：

```python
try:
    import os, re, json, ...            # stdlib
except KeyboardInterrupt:
    if __name__ != '__main__':
        raise                            # §11.1-1：库模块必须重抛
    import os.path                       # 最小依赖自举（此时 cli_interrupt 尚未导入）
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
    from cli_interrupt import emit
    emit('lr', sys.argv)
```

要点：自举段**不能**用 `Path`（它可能正是被中断的 import），只能用 `os.path`；`emit()` 内部不用任何第三方模块。

**护栏 3 —— 入口段唯一捕获**（8 个入口同形）：

```python
if __name__ == '__main__':
    from cli_interrupt import emit        # 入口段内 import ⇒ 被 importlib 加载时零副作用
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        emit('<prog>', sys.argv)          # 三行提示 + exit 130（不返回）
```

`sys.exit(main())` 而非 `main()`：保留各子命令原有 `return 0/1/2` 的退出码语义，不被本改动改写。
`except Exception` 保留原样（`KeyboardInterrupt` 是 `BaseException`，不会被它吞掉）。

### 2.4 `--json` 信封

- stdout **只有一个 JSON 对象**（无前置裸文本、无「用户中断操作」之类），供 `lr status --json` 的消费方直接 `json.loads`；
- 判定方式 `'--json' in argv[1:]`，与各入口 `'--json' in args` 同口径（不会出现「入口认为 json、收口认为非 json」的分裂）；
- 人类提示（两行）在 json 模式**整体**走 stderr，stdout 保持纯净（stderr 允许有多行）。

### 2.5 退出码 130

`128 + SIGINT = 130`，与 0 / 1 / 2 四码分立。调用侧判据变为：`130 ⇒ 用户主动放弃`（不计连败、不告警），
`1/2 ⇒ 真失败`（计入连败/告警）。这正是任务目标「中断与失败可区分」。

### 2.6 wrapper 层（同一契约，gitignored 生成物）

`lr` / `llm-radar` = `~/.local/bin/lr -> cache/system-command/llm-radar-wrapper.sh`（bash）。该壳在
`load_environment`（conda activate + `.env`）期间 Python 尚未 `exec`，SIGINT 只落在 bash ⇒ 无 handler 时
零输出 + `rc=-2`。方案：`trap ... INT` → 同文案 + `exit 130`；`exec` 后用 fd 3 保存 stderr 副本
（trap 上下文里 fd2 不可写，实测提示 0 字节，LR-CLI-002）。`exec` 之后 trap 随 exec 消失，由 Python 侧接管。

⚠ 该文件是 **生成物且 gitignored**，`install.py --force` 重生成即丢（GOV-1）—— 模板侧回填是上游 OB-1，
不在本仓本批。

## 3. 改动面文件清单

实现落地批次 = `14dc48f`（10 文件）+ `9b777b6`（4 文件，其中 3 个与前者重叠）：

| # | 文件 | 性质 | 改动 |
|:--|:--|:--|:--|
| 1 | `scripts/cli_interrupt.py` | **新增**（67 行） | 单源收口：文案/信封/退出码/`shlex.join` 重跑行 |
| 2 | `llm-radar-collector.py` | 改 | import 块套 `try` + 库加载重抛（L31-60）；重依赖惰性化（openai/prettytable/requests 撤模块级）；入口段 `emit('lr', sys.argv)` |
| 3 | `scripts/twitter-collector.py` | 改（+8/-1 行级） | 入口段接 `emit` |
| 4 | `scripts/llm-radar-health.py` | 改 | 同上 |
| 5 | `scripts/flclash_proxy.py` | 改 | 同上 |
| 6 | `scripts/chromedriver_bootstrap.py` | 改 | 同上 |
| 7 | `scripts/mcp_submit_update.py` | 改 | 同上 |
| 8 | `scripts/llm-radar-mcp-server.py` | 改 | dispatch 期接 `emit`（`serve_forever` 保留自身优雅停止） |
| 9 | `scripts/mcp-protocol-demo.py` | 改（复核轮） | 同上（门禁 8/8） |
| 10 | `tests/test_cli_interrupt.py` | **新增**（157 行 / 14 例） | 行为钉 + 静态钉子 |
| 11 | `documents/handbooks/llm-radar-cli-governance-handbook-v1.0-20260908.md` | 改 | 新增「六、Ctrl-C 中断行为」章节（契约/覆盖范围/5 条边界/验证命令） |
| — | `cache/system-command/llm-radar-wrapper.sh` | 改（**gitignored**） | `trap INT → exit 130` + fd3 兜 stderr |

**不动**：`tasks/al-{init,scanner}.py`、`cache/scratch/*`、`tests/test_twitter_cron.py`（见 1.4）、
所有采集/合并业务逻辑、`data/*.json` 生产产物、cron 配置。

## 4. 测试判据

### 4.1 注入方式（为什么不用真信号）

真实 SIGINT 对 `<0.2s` 的短命令不可控（打早 = 未启动，打晚 = 已结束），用例会随机红绿。方案：
真实入口文件 + `runpy.run_path(run_name='__main__')` + `sys.settrace` 钩子在**入口函数首帧**抛
`KeyboardInterrupt` —— 只替换「信号何时到达」这一个变量，执行体、文案、退出码全走生产代码。
harness 先 `sys.path.insert(0, dirname(entry))` 复刻 `python3 <script>` 的 `sys.path[0]` 约定。

### 4.2 判据矩阵（`tests/test_cli_interrupt.py`，14 例，2026-11-03 实测 `14 passed in 0.37s`）

| # | 用例 | 判据 |
|:--|:--|:--|
| 1 | `test_human_mode_interrupt_prints_hint_and_exit_130` | `rc==130`；stdout 含 `⛔ 已中断 (Ctrl-C) — lr status 未完成` 与 `💡 重跑: lr status` |
| 2 | `test_human_mode_interrupt_has_no_traceback` | stdout+stderr **不含** `Traceback (most recent call last)`、**不含** `KeyboardInterrupt` |
| 3 | `test_json_mode_stdout_is_envelope_only` | `rc==130`；`stdout.strip()` **逐字等于**信封 JSON；提示在 stderr、不在 stdout |
| 4 | `test_script_entry_routes_through_cli_interrupt[7 参数]` | 7 个脚本入口各一轮：`rc==130` + 有提示 + 无裸栈 |
| 5 | `test_static_all_entries_declare_single_catch_point` | 8 个入口的 `__main__` **切片**内必须有**代码行** `except KeyboardInterrupt:` 且调用 `emit(`（注释不算；变异 M6b 须转红） |
| 6 | `test_static_collector_import_guard_reraises_for_library_use` | collector 有 `if __name__ != '__main__':` 且紧随 `raise`，且**只出现 1 次**（防库加载被吞） |
| 7 | `test_rerun_line_shell_quotes_arguments` | `lr commit 'wip; rm -rf /tmp/x'` 的重跑行必须等于 `shlex.join(argv)`，且不出现朴素拼接形态 |
| 8 | `test_emit_contract_json_and_human` | `SystemExit.code == 130`；json 模式 stdout 可 `json.loads` 且等于信封；重跑行进 stderr |
| 9 | **import 期注入（真信号路径）** | ⚠ 见 R-1：本批用**静态钉子**（#6）守 import 护栏，未做「import 期打真信号」的动态用例；真机验收走 §4.4 的手工抽样 |

### 4.3 回归判据（现有测试不回归）

```bash
cd ~/CodeSpace/llm-radar.lab
PY=/opt/homebrew/Caskroom/miniconda/base/envs/py3.12/bin/python   # ⚠ 见下方解释器坑
# 单套件（2026-11-03 实测 14 passed in 0.37s）
$PY -m pytest tests/test_cli_interrupt.py -q -n0
# 全量（2026-11-03 实测 429 passed, 2 deselected, 2 warnings in 96.72s；新增红数 = 0）
$PY -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q
# 跑完立即还原被测试写脏的生产产物（只读快照，别 commit）
git checkout -- timestamp.json overview.json data/snapshot.json
```

**解释器坑（实测踩到）**：本机 `python3` 在非交互/后台 shell 里可能解析到 `/opt/homebrew/opt/python@3.14/bin/python3.14`
（`No module named pytest`）或 `/usr/bin/python3`（3.9.6）⇒ 全量必须**显式**用 conda `py3.12`，否则得到的是
「跑不起来」而不是「跑过了」。基线比较：开工前回执记 `415 passed`，批末回执记 `427`；本次复跑 `429`
（后续批次又加了用例），三者不可直接当同一分母用 —— 判据是**新增红数 = 0**，不是总数相等。

**污染警告**：全量会写 `timestamp.json` / `overview.json` / `data/snapshot.json`；本会话工作树已有他线 WIP
（这 3 个文件本来就不是干净态），因此还原前必须先记录 `git diff` 基线，**不得**无脑 checkout 覆盖他线数据。

**兼容性判据**：本改动只动进程边界，不得改变任何子命令的既有 stdout 结构与 `return 0/1/2` 语义 ⇒
`tests/test_cli.py`（黑盒命令面断言）与 `test_gitflow.py` 必须与基线同绿。

### 4.4 真机验收（任务书 §5 A3/A4）

```bash
cd ~/CodeSpace/llm-radar.lab
set -m; lr fetch qbitai & PID=$!; sleep 3; kill -INT $PID; wait $PID; echo "rc=$?"   # 期望 rc=130 + 两行提示
/usr/bin/python3 -c "import json; d=json.load(open('/tmp/lr-int.out')); assert d=={'status':'error','data':None,'error':'interrupted'}, d; print('ENVELOPE_OK')"
```

`set -m` **必须**有：非交互 shell 的后台作业继承 `SIGINT=SIG_IGN`，不加则 `kill -INT` 无效
（实测 7/7 `rc=0` 且抓取跑完，LR-CLI-005）。子命令用 `fetch qbitai` 而非任务书的 `chrome --wait`
（后者在登录态已就绪时秒返回，不是长跑命令）。

## 5. 风险与禁改项

| # | 风险 | 影响 | 处置 |
|:--|:--|:--|:--|
| R-1 | **解释器启动段残余窗口**：`execve` → 首条字节码（site + 3300 行/150KB 编译）约 20-40ms，bash trap 已随 `exec` 消失、Python 代码尚未起跑 | 极端情况仍 `rc=-2` 静默 | 不承诺 100%；实测抽样 59/60（98.3%）。要 100% 只能改「监督子进程 + kill 转发」，代价是 MCP stdio 模式 stdin 语义 ⇒ 本批不做 |
| R-2 | **信封与 `status --json` 成功态不同形**：成功态是七字段巡检卡片（`id/label/status/...`，`status` 是健康色值），中断态是 `{status:error,...}` | 按 `id`/`label` 解析的消费方在 `rc=130` 时取不到字段 | 消费方**先判 rc 再解析**；已在 handbook §6 显式标注 |
| R-3 | **wrapper 是 gitignored 生成物**，`install.py --force` 重生成即丢 trap | 中断覆盖回退到「env 段零输出 + rc=-2」 | GOV-1 未闭；上游 OB-1（`wrapper.sh.tmpl` 已加 trap，未提交）。本批只登记不改 `install.py` |
| R-4 | **子进程未回收**：中断发生在 `subprocess.run`（git / Selenium Chrome）时父进程只收自己的 `KeyboardInterrupt` | 子进程可能继续存活 | §11.4 已知边界，本批不做；长驻子进程的 `terminate()+wait` 属邻域（§2-16） |
| R-5 | **MCP server `serve_forever()`**：Ctrl-C 是「优雅停止」（打印 `⏹️ 服务器已停止` + `server_close()`） | 不套「未完成」文案 | 有意保留：把 daemon 停止说成「未完成」会误导；仅 dispatch 期中断走统一收口 |
| R-6 | **测试用 trace 钩子替代真信号** | 不覆盖「信号恰好落在 import 期」 | 静态钉子 #6 + §4.4 真机抽样共同兜；动态 import 期用例留作后续（真信号不可控，易 flaky） |
| R-7 | `except Exception: print('❌ 错误'); exit 1` 仍在入口段 | 真失败与用法错误仍同码 1 | **不在本任务范围**（§4 禁改：不混批异常面改造）；中断已靠 130 分离，目标达成 |
| R-8 | `emit()` 在 json 模式下 human 提示走 stderr，但 **wrapper 侧**用 fd3 副本 | 两侧实现不同源（bash 手写文案） | 已靠「`prog` 固定 `lr` + 同样 `printf '%q'` 引用」对齐字节；模板化才算真单源（OB-1） |

**禁改项（黑名单，逐条有理由）**

| 禁改 | 理由 |
|:--|:--|
| `~/CodeSpace/hermes-manager/**` | 规范真源仓；本批只读引用（含其 29 入口回填，属另一批） |
| 参数校验 / `--warit` 拼写纠正 | 另一议题，避免与本任务混批；中断提示能正常给出即达标。**注意**：`--warit` 未被拒 ⇒ collector 走到需要 API key 的重路径，属参数面缺陷，另开单 |
| 采集/合并/质量门禁业务逻辑 | 本任务只动「进程边界」；改 `_verify()` 阈值属 Ask-First（AGENTS.md） |
| cron / 调度配置 | 影响无人值守链路，须单独放行（用户 crontab 由 ops 侧接入） |
| `.env` / 凭据文件 | 不读不写；提示文案经 `shlex.join` 只含 argv，禁含密钥 |
| `data/snapshot.json` 等生产产物 | 须经采集器 / merge 流程生成；测试写脏只 `git checkout --` 还原，不手工编辑 |
| `tasks/al-{init,scanner}.py` | agent-loop 调度、中断语义涉状态机 ⇒ 另批 |
| `git push` / 强推 / 改历史 | 推送由用户执行；本仓自愈链路全程无 force push |

## 6. 与本批任务的边界

- 本步产出**仅本文档**；起草时未改任何 `.py`、未 commit、未 push（追认：本文件随后作为 `docs@ops` 一笔提交；
  实现笔 `9b777b6` 与复核件 `dfbdc85` 已 push）（`git status` 里 3 个改动文件是采集器写的
  生产数据产物，与本步无关）。
- 若下一批复核发现实现与本文偏差，按 §4.2 判据逐条复跑定性，不在本文里改数字。
- 建议后续（不在本批）：① 把本文登记进 `documents/README.md` 知识底座索引；② 补 import 期动态注入用例；
  ③ 上游 OB-1（wrapper 模板提交 + 各仓重生成）。
