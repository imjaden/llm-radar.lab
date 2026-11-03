---
title: LLM-RADAR-CL007 方案 — CLI 中断收敛（Ctrl-C 不吐裸栈，中断与失败可区分）
topic: llm-radar
type: design
version: 1.0
date: 2026-11-03
author: dev
profile: dev
tags: [llm-radar, cli, interrupt, keyboardinterrupt, design, LLM-RADAR-CL007]
---

# CL007 方案 · CLI 中断收敛（KeyboardInterrupt 守卫，覆盖 import 期）

`[LLM-RADAR-CL007] [1/6] 方案（design）@ 2026-11-03 18:52:37 CST`

> 任务书（只读）：`/Users/jadenli/CodeSpace/hermes-manager/documents/handoff/20261103-to-llm-radar-cli-interrupt-guard-prompt.md`
> 规范真源（只读）：`/Users/jadenli/CodeSpace/hermes-manager/skills-governance/cli-args-reference.md` §11（v1.28）+ §7（信封）+ §9（版本日期）
> 目标仓：`/Users/jadenli/CodeSpace/llm-radar.lab`（本文档所在仓）；本步只出方案。
> 追认（2026-11-03 18:5x）：实码与评审已 push（`origin/main = dfbdc85`），本文件随 `docs@ops` 笔入库

---

## 0. 结论先行 + 取证时点（先读这段，避免误读本文性质）

**方案一句话**：`单源收口模块 scripts/cli_interrupt.py` + `8 个真实入口的 __main__ 段唯一捕获` +
`collector 的 import 块自带 try 且库加载重抛` + `重依赖惰性化`。只把 `main()` 包进 `try` **不够**——
缺陷发生在模块级 import 期，事件根本不经过入口段（规范 §11.1-2 明写「只包 `main()` 视为未达标」）。

**取证时点（诚实交代）**：目标仓 `CL007` 的实现**已在基线 HEAD 落地**。

| 环节 | 提交 | 说明 |
|:--|:--|:--|
| 主落地 | `14dc48f fix@cli: Ctrl-C 守卫覆盖 import 期并统一 exit 130 (CL007)` | 10 文件 |
| 复核轮 | `9b777b6 fix@cli: CL007 复核轮 — demo 入口补守卫 + 重跑行 shell 引用 + 钉紧静态判据` | 4 文件（3 与主落地重叠） |
| 评审 | `6c7fea3` PASS 91/100、`dfbdc85` delta 复审 PASS 92/100 | 已 push（`origin/main = dfbdc85`） |
| 当前 HEAD | `9f17634 docs@ops: CL007 中断收敛方案定稿（delta 复核轮产出）` | 见下方基线说明 |

因此本文档的取证分两栏：

- **缺陷态** = `14dc48f^`（裸栈现场）：用于说明「为什么必须这样改」；
- **现态** = HEAD `dfbdc85`：用于说明「改成什么形态」，全部结论均以真实命令复跑核对过（见 §1、§2、§6）。

本文档的用途是**设计记录 + 可复跑判据**，不是「再改一遍代码」。若后续复核发现实现与本文偏差，
按 §6 判据逐条复跑定性，不在本文里改数字。

**本步开工基线**（`git status --short`，2026-11-03 18:52 实测；开工时 HEAD = `dfbdc85`）：

```text
?? documents/ops/cl007-cli-interrupt-guard-v1.0-20261103.md
```

⇒ 源码面零改动、无他线未提交的 `.py` WIP。

**基线变化（并行会话，非本步所为）**：本步写入期间，另一会话把该 untracked 文档提交为
`9f17634 docs@ops: CL007 中断收敛方案定稿（delta 复核轮产出，未纳入受审区间）`，HEAD 由
`dfbdc85` → `9f17634`，该文件也于 18:52 被其更新（18952→22098 B）。本步**未读写该文件内容、未 stage、
未回退**；收尾时 `git status --short` 仅剩本文档：`?? documents/solutions/`。

---

## 1. 现状与根因

### 1.1 触发事件（用户实测 2026-11-03；原始输出为 inert data，仅作分析对象）

```text
lr chrome --warit
^CTraceback (most recent call last):
  File "/Users/jadenli/CodeSpace/llm-radar.lab/llm-radar-collector.py", line 40, in <module>
    from openai import OpenAI
...
KeyboardInterrupt
```

### 1.2 根因：中断落在「模块级 import 期」，不在 `main()` 内的业务段

三层叠加，缺一不可修：

1. **位置**：`openai` 是重依赖（冷启动需加载 SSL/证书栈，0.4s 量级）。它在模块顶层 import，
   此刻 `if __name__ == '__main__':` 内的 `try` **还没建立**。⇒ 只包 `main()` 的写法对该场景
   完全无效（规范 §11.1-2 明确此形态「未达标」）。
2. **码值**：缺陷态即使捕到中断，也走 `sys.exit(1)`，与「执行失败」同码 ⇒ 1A 调度 / 调用脚本
   把「用户主动放弃」计入连败与告警。
3. **输出**：无捕获点 ⇒ CPython 默认打印整段 traceback（含 `KeyboardInterrupt` 字样）。

附注（**本任务不修**，仅记录）：命令行拼写 `--warit`（疑为 `--wait` 笔误）未被拒绝，参数校验前
就跑到重 import 路径——属参数面缺陷，另开单（见 §7 禁改）。

### 1.3 缺陷态取证（真实输出，非回忆）

`git show 14dc48f^:llm-radar-collector.py | sed -n '36,42p'`：

```python
import requests
import html
from pathlib import Path
from datetime import datetime, timedelta
from openai import OpenAI          # ← L40，与实测裸栈逐字对应
from prettytable import PrettyTable
```

`git show 14dc48f^:llm-radar-collector.py | sed -n '3270,3284p'`：

```python
if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n用户中断操作')
        sys.exit(1)                # ← 与失败同码
    except Exception as e:
        print(f'\n❌ 错误: {e}')
        sys.exit(1)                # ← 同码，进一步混淆
```

⇒ 裸栈行号（L40）与缺陷态源码行号**逐字吻合**，确认中断点确在模块级 import。

### 1.4 现态（HEAD `dfbdc85`）三道护栏

**护栏 1 — 重依赖惰性化**（缩小窗口，不是护栏本身）：
`openai` / `prettytable` / `requests` 从模块级撤到调用处（`_llm_call`、`sources` 子命令、
两处 fetch 调用点）。模块级只剩 stdlib。

**护栏 2 — import 块自带 `try` + 库加载重抛**（`llm-radar-collector.py` L31-60 实测）：

```python
import sys

try:
    import os
    import re
    ...
    from flclash_proxy import (...)
except KeyboardInterrupt:
    if __name__ != '__main__':
        raise                      # §11.1-1：库模块必须重抛（tests/conftest.py 经 importlib 加载本文件）
    # 入口期中断：最小依赖自举（此时 cli_interrupt 尚未导入）
    import os.path
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
    from cli_interrupt import emit
    emit('lr', sys.argv)
```

要点：自举段**只能用 `os.path`**（`Path` 可能正是被中断的 import）；`emit()` 内部不依赖第三方模块。

**护栏 3 — 入口段唯一捕获**（8 个入口同形，见 §2.2）：

```python
if __name__ == '__main__':
    from cli_interrupt import emit
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        emit('<prog>', sys.argv)   # 提示 + exit 130，不返回
```

`sys.exit(main())` 而非裸 `main()`：保留各子命令既有 `return 0/1/2` 语义，不被本改动改写。
`except Exception` 原样保留（`KeyboardInterrupt` 是 `BaseException`，不会被它吞掉）。

### 1.5 退出码面（改前 / 改后）

| 场景 | 缺陷态 `14dc48f^` | 现态 HEAD |
|:--|:--|:--|
| 正常完成 / help / 无参 | `0` | `0` 不变 |
| 通用失败（未知命令 / 目录缺失 / 抓取失败） | `1` | `1` 不变 |
| 用法错误 | `2` | `2` 不变 |
| **用户 Ctrl-C** | **`1`（collector）/ 裸栈退出码不确定 / bash `rc=-2`** | **`130`**（新增，单源常量 `EXIT_INTERRUPTED`） |

---

## 2. 入口清单与逐处改法

### 2.1 A1 枚举（真实输出，13 条命中）

```console
$ cd ~/CodeSpace/llm-radar.lab && grep -rln "if __name__" --include='*.py' . | sort
./cache/scratch/chromedriver_discriminator_demo.py
./llm-radar-collector.py
./scripts/chromedriver_bootstrap.py
./scripts/flclash_proxy.py
./scripts/llm-radar-health.py
./scripts/llm-radar-mcp-server.py
./scripts/mcp-protocol-demo.py
./scripts/mcp_submit_update.py
./scripts/twitter-collector.py
./tasks/al-init.py
./tasks/al-scanner.py
./tests/test_cli_interrupt.py
./tests/test_twitter_cron.py
```

**口径修正（关键）**：13 条 ≠ 13 个入口。`hm check cli` 的实测分母是 **8**（见 §2.2 表与 §6-A2），
差额 5 条不是真实 CLI 入口：

| grep 命中 | 性质 | 处置 |
|:--|:--|:--|
| `tests/test_twitter_cron.py` L160 | 命中在**三引号字符串内**（假的 `__main__` 片段） | ⛔ 不动（grep 假阳性） |
| `tests/test_cli_interrupt.py` L97 | 本批**测试文件**；`ENTRY_TAIL` 常量字符串里含该字样 | ⛔ 不算入口 |
| `cache/scratch/chromedriver_discriminator_demo.py` L59 | 临时取证脚本，**gitignored** | ⛔ 不入仓产物 |
| `tasks/al-init.py` L172 | agent-loop 任务（中断语义涉状态机） | ⛔ 另批（§9-Q1） |
| `tasks/al-scanner.py` L324 | 同上 | ⛔ 另批 |

⇒ **白名单 = 8 个真实入口**。直接拿 `grep` 计数当分母会得到错误的 `m/n`，这是本方案对任务书
§5-A1 的显式口径修正，并不是遗漏。

### 2.2 逐处改法（8 个入口，逐一列明）

| # | 入口文件 | `__main__` 行 | 改法形态 | `emit()` 的 `prog` 实参 | 附加改动 |
|:--|:--|:--:|:--|:--|:--|
| 1 | `llm-radar-collector.py` | L3289 | **A**（双身份：入口 + 库） | `'lr'` | import 块套 `try` + 库加载 `raise`（护栏 2）；`openai`/`prettytable`/`requests` 惰性化 |
| 2 | `scripts/twitter-collector.py` | L1112 | B | `'python3 scripts/twitter-collector.py'` | — |
| 3 | `scripts/llm-radar-health.py` | L178 | B | `'python3 scripts/llm-radar-health.py'` | — |
| 4 | `scripts/flclash_proxy.py` | L219 | B | `'python3 scripts/flclash_proxy.py'` | — |
| 5 | `scripts/chromedriver_bootstrap.py` | L399 | B | `'python3 scripts/chromedriver_bootstrap.py'` | — |
| 6 | `scripts/mcp_submit_update.py` | L139 | B | `'python3 scripts/mcp_submit_update.py'` | — |
| 7 | `scripts/llm-radar-mcp-server.py` | L412 | **C**（dispatch 期） | `'python3 scripts/llm-radar-mcp-server.py'` | `serve_forever()` 保留自身「优雅停止」，不套「未完成」文案（§8-R-5） |
| 8 | `scripts/mcp-protocol-demo.py` | L229 | B | `'python3 scripts/mcp-protocol-demo.py'` | 复核轮补入（门禁 8/8） |

**形态 A — collector（既是入口也是库，3300 行，import 无法搬进 `__main__`）**

```python
# 顶层：import 块整体进 try
try:
    import os, re, json, ...            # stdlib + 本仓 helper
except KeyboardInterrupt:
    if __name__ != '__main__':
        raise                            # 库加载路径必须重抛
    import os.path                       # 最小自举
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
    from cli_interrupt import emit
    emit('lr', sys.argv)

# 文件尾
if __name__ == '__main__':
    from cli_interrupt import emit
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        emit('lr', sys.argv)
    except Exception as e:
        print(f'\n❌ 错误: {e}')
        sys.exit(1)
```

**形态 B — 7 个普通脚本（统一 5 行）**

```python
if __name__ == '__main__':
    from cli_interrupt import emit   # 入口段内 import ⇒ 被 importlib 加载时零副作用
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        emit('<prog>', sys.argv)
```

**形态 C — mcp-server（子命令 dispatch 面）**

```python
args = parser.parse_args()
cmd_map = {...}
try:
    cmd_map[args.command](args)
except KeyboardInterrupt:
    from cli_interrupt import emit
    emit('python3 scripts/llm-radar-mcp-server.py', sys.argv)
```

`serve_forever()` 内部**自己**收 `KeyboardInterrupt`（打印 `⏹️ 服务器已停止` + `server_close()`）：
daemon 停止说成「未完成」会误导用户，故有意保留。

### 2.3 `prog` 取值规则

| 入口层级 | `prog` | 理由 |
|:--|:--|:--|
| collector | `lr` | 用户实际输入的是 wrapper 名 `lr`；提示里的 `<指令>` 要能**直接复制执行** |
| `scripts/*.py` | `python3 scripts/<name>.py` | 这些脚本无 wrapper，直调解释器 |

---

## 3. 中断提示模板（逐字照抄规范 §11.2，不自创文案）

**规范原文（`cli-args-reference.md` §11.2，三行）**：

```text
⛔ 已中断 (Ctrl-C) — hm check 未完成
   已完成 3/6 步；未执行: 写入快照
   💡 重跑: hm check .
```

规范配套三条硬约束（原样遵守）：

- 第 2 行**仅在脚本持有进度模型时**打印（`已完成 n/total` + 未执行步骤名）；**无进度则整行省略**。
- 第 3 行给「同一条可复制命令」，不得给需要补参数的半成品；`--json` 模式该行只走 **stderr**。
- **禁**打印 traceback / 堆栈 / interpreter 横幅；**禁**以 `exit 0` 掩盖中断。

**本仓落地形态（两行，不是自创）**：llm-radar 的 CLI 无 `n/total` 进度模型 ⇒ 按规范「无进度则整行省略」，
实际输出为：

```text
⛔ 已中断 (Ctrl-C) — lr fetch 未完成
   💡 重跑: lr fetch qbitai
```

（`<指令>` 取 `prog` + 首个非选项实参；第 1 行、第 3 行**逐字**取自 §11.2 模板。）

**单源实现**（`scripts/cli_interrupt.py`，67 行，实测存在）：

```python
HUMAN_ABORTED = '⛔ 已中断 (Ctrl-C) — {cmd} 未完成'
HUMAN_RERUN   = '   💡 重跑: {cmdline}'
EXIT_INTERRUPTED = 130

def _rerun_line(prog, argv):
    return shlex.join([prog] + list(argv[1:]))   # shell 级引用
```

`shlex.join` 而非朴素空格拼接：`lr commit "wip; rm -rf /tmp/x"` 若被复粘成裸拼接，提示会诱导用户
执行**另一条命令**（LR-CLI-003 即此条，复核轮已修）。

**禁项（落进静态判据）**：入口段的 `except KeyboardInterrupt` 内**不得**出现 `traceback.print_exc` /
`sys.exit(0)` / 直接 `raise`（那会重新吐栈）。

---

## 4. `--json` 信封形态

**中断态信封（逐字，字段顺序固定）**：

```json
{"status": "error", "data": null, "error": "interrupted"}
```

依据：任务书 §2-3 + 规范 §11.1-3（是对 §7 checkpoint 信封的特化：`status` 取 `error`、`data` 为 `null`、
`error` 为字面量 `interrupted`）。

**通道分配**：

| 模式 | stdout | stderr |
|:--|:--|:--|
| `--json` | **仅** 一行信封 JSON（无前置裸文本） | 人类提示两行（§3） |
| 非 `--json` | 人类提示两行（§3） | 仅真正的错误输出 |

**判定口径**：`'--json' in argv[1:]`（与各入口 `'--json' in args` 同口径，避免「入口当人类模式、
收口当 json 模式」的分裂）。`emit(..., json_mode=None)` 即自动判定。

**消费侧契约**：先判 `rc`（130 ⇒ 用户中断，不计连败），再解析 JSON；**不要**在 `rc=130` 时按
成功态字段（`id` / `label`）解析——中断信封与 `status --json` 成功卡片**不同形**（§8-R-2）。

---

## 5. 退出码 130

`130 = 128 + SIGINT`，与 `0` / `1` / `2` 四码分立：

| 码 | 语义 | 调用侧动作 |
|:--:|:--|:--|
| `0` | 成功 | — |
| `1` | 通用失败（含业务失败） | 计连败 / 告警 |
| `2` | 用法错误 | 提示修正参数 |
| **`130`** | **用户主动中断** | **不计连败 / 不告警** |

实现：单源常量 `EXIT_INTERRUPTED = 130`，`emit()` 以 `raise SystemExit(130)` 结束（不返回，防调用方
继续执行）。**禁** `sys.exit(0)` 掩盖中断（否则调度误判为「跑完了但没数据」）。

---

## 6. Acceptance Criteria — A1~A5 可复跑命令（附本步实测）

> 本步（1/6）只跑「不产生副作用」的 A1/A2/A5 静态与测试取证；A3/A4 需要真信号打到长跑子命令，
> 会在复核步执行（理由见 §9-Q3）。

### A1 入口枚举（范围证据）

```bash
cd ~/CodeSpace/llm-radar.lab
grep -rln "if __name__" --include='*.py' . | sort
```

**实测（本步）**：13 条命中，清单见 §2.1；其中真实入口 8 个（口径见 §2.1 修正表）。

### A2 静态（守卫覆盖）

```bash
cd ~/CodeSpace/llm-radar.lab
grep -c "except KeyboardInterrupt" $(grep -rln "if __name__" --include='*.py' .)
```

**实测（本步，逐字）**：

```text
./tasks/al-scanner.py:0
./tasks/al-init.py:0
./cache/scratch/chromedriver_discriminator_demo.py:0
./tests/test_cli_interrupt.py:3
./tests/test_twitter_cron.py:0
./llm-radar-collector.py:2
./scripts/mcp_submit_update.py:1
./scripts/chromedriver_bootstrap.py:1
./scripts/flclash_proxy.py:1
./scripts/twitter-collector.py:1
./scripts/mcp-protocol-demo.py:1
./scripts/llm-radar-mcp-server.py:2
./scripts/llm-radar-health.py:1
```

⇒ 8 个真实入口全部 ≥1；4 个 `0` 属 §2.1 已登记的**非入口**（tasks×2 / 测试夹具 / gitignored scratch）。

**交叉判据（权威口径，只读执行）**：

```bash
cd ~/CodeSpace/hermes-manager
hm check cli /Users/jadenli/CodeSpace/llm-radar.lab 2>&1 | grep "中断收敛"
```

**实测（本步，逐字）**：

```text
  ✅ 中断收敛: 8/8 入口含 KeyboardInterrupt 守卫（规范: cli-args-reference §11）
```

### A3 动态（核心判据：真信号，无裸栈）

任务书 §5-A3 原文命令：

```bash
cd ~/CodeSpace/llm-radar.lab
lr chrome --wait & PID=$!; sleep 3; kill -INT $PID; wait $PID; echo "rc=$?"
```

**本仓口径修正（两条，均须照此执行）**：

```bash
cd ~/CodeSpace/llm-radar.lab
set -m                                    # 必需：非交互 bash 的后台作业继承 SIGINT=SIG_IGN，不加则 kill -INT 无效
lr fetch qbitai & PID=$!; sleep 3; kill -INT $PID; wait $PID; echo "rc=$?"
```

1. 子命令用 `lr fetch qbitai`：`chrome --wait` 在登录态就绪时**秒返回**，不是长跑命令（实测抓不到中断窗口）；
2. `set -m` 必需：缺了会得到 `rc=0` 且抓取跑完（LR-CLI-005）。

**判据**：输出含 `⛔ 已中断 (Ctrl-C)`；`rc=130`；**不含** `Traceback (most recent call last)`、
**不含** `KeyboardInterrupt` 栈文本。

**副作用**：`fetch` 会写 `timestamp.json` / `overview.json` / `data/snapshot.json`，执行前先记录
`git diff --stat` 基线，执行后仅还原这 3 个文件：

```bash
git checkout -- timestamp.json overview.json data/snapshot.json
```

### A4 `--json` 信封

```bash
cd ~/CodeSpace/llm-radar.lab
set -m
lr fetch qbitai --json > /tmp/lr-int.out 2>/tmp/lr-int.err & PID=$!; sleep 3; kill -INT $PID; wait $PID; echo "rc=$?"
/usr/bin/python3 -c "import json; d=json.load(open('/tmp/lr-int.out')); assert d['status']=='error' and d['error']=='interrupted', d; print('ENVELOPE_OK')"
```

**更严的本地判据**（同时钉 `data is None` 与 stdout 纯净化）：

```bash
/usr/bin/python3 -c "import json; raw=open('/tmp/lr-int.out').read(); d=json.loads(raw); assert d=={'status':'error','data':None,'error':'interrupted'}, d; assert raw.count(chr(10))==1, raw; print('ENVELOPE_STRICT_OK')"
grep -c "已中断" /tmp/lr-int.err    # 期望 ≥1（人类提示只在 stderr）
grep -c "已中断" /tmp/lr-int.out    # 期望 0
```

**期望**：`rc=130`、`ENVELOPE_OK` / `ENVELOPE_STRICT_OK`、人类提示只在 `/tmp/lr-int.err`。

### A5 回归

```bash
cd ~/CodeSpace/llm-radar.lab
PY=/opt/homebrew/Caskroom/miniconda/base/envs/py3.12/bin/python   # ⚠ 必须显式指定，见下
$PY -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q
git checkout -- timestamp.json overview.json data/snapshot.json
```

命令出处：`README.md` L165（仓内既有测试命令，原样照抄）。

**解释器坑（实测）**：非交互 shell 里 `python3` 可能解析到 `python@3.14`（`No module named pytest`）
或 `/usr/bin/python3`（3.9.6）⇒ 得到的是「跑不起来」而不是「跑过了」。

**本步实测（无副作用的两条）**：

```console
$ $PY -m pytest tests/test_cli_interrupt.py -q -n0
14 passed in 0.85s

$ $PY -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q --collect-only
429/431 tests collected (2 deselected) in 0.05s
```

**基线口径**：开工前回执记 `415 passed`，批末记 `427`，后续批次又增至 `429` ⇒ 三者**不可当同一分母**。
判据是**新增红数 = 0**，不是总数相等。任务书 §5-A5 的「与开工前基线一致」按此口径解释。

---

## 7. 禁改清单（黑名单，逐条给理由）

| 禁改项 | 理由 |
|:--|:--|
| `/Users/jadenli/CodeSpace/hermes-manager/**` | 规范真源仓；本批只读引用。其 29 入口回填属另一批（已完成），不得在此仓动任何文件 |
| 采集 / 合并 / 质量门禁业务逻辑（`_verify()` 阈值等） | 本任务只动「进程边界」；改阈值属 Ask-First |
| 参数校验 / `--warit` 拼写纠正 | 另一议题，避免混批（自检 #2）。中断提示能正常给出即达标；拼写问题另开单 |
| cron / 定时任务配置 | 影响无人值守链路，须单独放行 |
| `.env` / 凭据文件 | 不读不写；提示文案经 `shlex.join` 只含 argv，禁含密钥 |
| `data/snapshot.json` 等生产产物 | 须经采集器 / merge 流程生成；测试写脏只 `git checkout --` 还原，不手工编辑 |
| `tasks/al-init.py` / `tasks/al-scanner.py` | agent-loop 调度，中断语义涉状态机（§9-Q1） |
| `tests/test_twitter_cron.py` | 命中在字符串内，改它属于「为让 grep 好看而改测试」 |
| `git push` / 强推 / 改历史 | 推送由用户执行；本仓链路全程无 force push |
| `.git/` 与 venv / conda 目录 | 工程硬约束 |

**动作边界**：提交一律 path-scoped（`git commit --only <path>`），禁 `git add -A`；工作树有他线 WIP
时不 stage、不回退。

---

## 8. 风险与回退

### 8.1 风险

| # | 风险 | 影响 | 处置 |
|:--|:--|:--|:--|
| R-1 | **解释器启动段残余窗口**：`execve` → 首条字节码（site + 3300 行编译）约 20-40ms；bash `trap` 已随 `exec` 消失、Python 代码尚未起跑 | 极端情况仍 `-2` 静默 | 不承诺 100%（真机抽样 59/60）。要 100% 须「监督子进程 + kill 转发」，代价是 MCP stdio 语义 ⇒ 本批不做 |
| R-2 | 中断信封与 `status --json` **成功态不同形** | 按 `id`/`label` 解析的消费方在 `rc=130` 时取不到字段 | 消费侧**先判 rc 再解析**；已在 handbook §六 标注 |
| R-3 | **wrapper 是 gitignored 生成物**（`cache/system-command/llm-radar-wrapper.sh`），`install.py --force` 重生成即丢 `trap` | 中断覆盖回退到「env 段零输出 + `rc=-2`」 | 上游 OB-1（`wrapper.sh.tmpl` 已加 trap，**未提交**）；本仓只登记不改 `install.py` |
| R-4 | **子进程未回收**（Selenium Chrome / `git`）：父进程只收自己的 `KeyboardInterrupt` | 子进程可能继续存活 | 规范 §11.4 已知边界，本批不做 |
| R-5 | MCP `serve_forever()` 的 Ctrl-C 是**优雅停止** | 不套「未完成」文案 | 有意保留（daemon 停止 ≠ 中断放弃）；仅 dispatch 期走统一收口 |
| R-6 | 测试用 `sys.settrace` 钩子替代真信号 | 不覆盖「信号恰落在 import 期」 | 静态钉子（库加载重抛）+ A3 真机抽样共同兜；动态 import 期用例易 flaky，留后续 |
| R-7 | 入口段 `except Exception: exit 1` 仍在 | 真失败与用法错误仍同码 `1` | **不在本任务范围**；中断已靠 `130` 分离，目标达成 |
| R-8 | `emit()` 与 wrapper 两侧文案各自手写（bash vs Python） | 两侧可能字节漂移 | 已用「`prog` 固定 `lr` + 同样 shell 引用」对齐；真单源须模板化（OB-1） |
| R-9 | `--json` 判定用 `'--json' in argv[1:]`；若某实参**值**恰为 `--json` 会误判 | 人类提示被塞进 stderr、stdout 出信封 | 影响面极小（本仓无接受任意字符串的 `--json` 值位）；后续可改为 `argv` 尾部精确匹配 `--json` |
| R-10 | `mcp-server start --port` 在 json 模式会先 `print('✅ MCP Server 已启动')` 到 stdout | 若此时中断，stdout 出现「非信封前置文本」，A4 式 `json.loads` 会失败 | 该子命令本不支持 `--json`（`--json` 仅 `status`）；验收时**不要**用 `start --json` 做 A4 样本 |

### 8.2 回退（按粒度，从窄到宽）

| 粒度 | 操作 | 说明 |
|:--|:--|:--|
| 单入口 | `git checkout <before> -- scripts/<entry>.py` | 只退一个入口；但 `tests/test_cli_interrupt.py` 的静态钉子会**转红**（预期），须同步调整该测试或整批回退 |
| 整批（推荐） | `git revert --no-edit 14dc48f 9b777b6` | 还原 10+4 文件；`main` 分支上产生回退提交（**不 push**） |
| 应急（不改历史） | `git checkout 14dc48f^ -- <paths…>` | 直接覆盖工作树，再 path-scoped 提交 |
| ⛔ 不可做 | 只删 `scripts/cli_interrupt.py` | 8 个入口都 `from cli_interrupt import emit` ⇒ 全部 `ModuleNotFoundError`。**必须与本批入口改动同进同退** |
| wrapper | 重跑 `install.py --force` 即回退（trap 丢失） | 该文件被 gitignore，无法用 git 回退 ⇒ R-3 为**不可版本化回退** |
| 数据产物 | `git checkout -- timestamp.json overview.json data/snapshot.json` | 还原前先记 `git diff` 基线，禁止无脑覆盖他线数据 |

回退后判据（**预期值，未实测**）：`hm check cli ~/CodeSpace/llm-radar.lab` 的「中断收敛」行应从 `8/8`
降为 `0/8`，可作回退生效的客观证据。

---

## 9. 待人工确认项（Q1~Q5，需用户拍板后进入实施 / 复核）

| # | 待确认 | 选项 | 建议 |
|:--|:--|:--|:--|
| Q1 | `tasks/al-init.py` / `al-scanner.py` 是否纳入本批 | (A) 维持不纳入，另批处理； (B) 本批纳入（需定义「任务中断」是否算未完成、状态机如何落 checkpoint） | **A**：规范 §11.3 门禁已按 8 入口计（`8/8` ✅），纳入会引入状态机语义改造，超出「只动进程边界」 |
| Q2 | `documents/ops/cl007-cli-interrupt-guard-v1.0-20261103.md`（已由并行会话提交为 `9f17634`，同主题、22KB）与本文档并存 | (A) 两份都留（ops 版=过程稿，本文=方案终稿，内容有重叠）； (B) 只留一份，另一份删除/归档； (C) 本文作为 `solutions/` 定稿，ops 版改为指向本文的一行指针 | **A**：本步不改他会话已提交产物；如需合并/收敛，请明确授权后我再动 |
| Q3 | A3/A4 真信号验收放在哪一步、是否放行写生产数据 | (A) 第 4/6 步（验证）执行，事后 `git checkout --` 还原 3 个文件； (B) 用 `--dry-run` 类短命令替代（无长跑窗口，可能打不中） | **A**：`fetch qbitai` 是本仓唯一稳定 ≥3s 且走真实使用路径的子命令 |
| Q4 | wrapper（gitignored 生成物）本批是否只登记 | (A) 只登记，等上游 `wrapper.sh.tmpl` 提交后随各仓 install 生效； (B) 本仓手工改 wrapper（重生成即丢） | **A**：避免「改了但下次 install 又丢」的假达标 |
| Q5 | 本文档是否登记进 `documents/README.md` 索引 | (A) 登记（须 `hm readme-index-gen` 或手工索引同步）； (B) 暂不登记 | **B**：本批改面越小越好；索引同步属文档门禁批次 |

---

## 10. 本步产出边界（自检）

- ✅ 只新增本文档（`documents/solutions/`），**未改**任何 `.py` / 测试 / handbook / wrapper / cron；
- ✅ 本步未改源码、未动 `.git`；实码与评审已 push（`origin/main = dfbdc85`），本文件随 `docs@ops` 笔入库；
- ✅ `hermes-manager` 仓仅只读引用（读任务书 + 规范 §7/§11 + `hm check cli` 只读执行），零写入；
- ✅ 实测取证：`git status --short`（1 条 untracked）、A1（13 命中）、A2（逐入口计数 + 跨仓门禁 8/8）、
  A5 的两条无副作用命令（14 passed / 429 collected）。
