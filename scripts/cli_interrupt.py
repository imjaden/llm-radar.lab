#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ctrl-C 中断收口唯一真源 —— 对齐 skills-governance/cli-args-reference.md §11 (v1.28, 2026-11-03)。

各入口模块的 `__main__` 段是**该进程的唯一捕获点**（§11.1-1），文案/退出码/信封全部来自本模块，
避免 7 份手抄文案漂移（§11.2「照抄执行，不要自己发明文案」）:

    if <入口段>:
        from cli_interrupt import emit        # 入口段内 import ⇒ 被 importlib 加载时零副作用
        try:
            sys.exit(main())
        except KeyboardInterrupt:
            emit('lr', sys.argv)              # 三行提示 + exit 130（不返回）

契约（§11 §7）:
- 人类提示：第 1 行 `⛔ 已中断 (Ctrl-C) — <指令> 未完成`；第 2 行进度模型本仓无 ⇒ 整行省略；
  第 3 行 `💡 重跑: <同一条可复制命令>`。禁打印 traceback / 堆栈。
- 退出码 130（= 128 + SIGINT），与 0 成功 / 1 通用失败 / 2 用法错误区分。
- `--json` 模式：stdout 只允许 checkpoint 信封（§7），人类提示一律走 stderr。
- 本模块只做打印与退出：不注册信号处理器、无 import 期副作用；库模块禁捕获/禁吞（§11.1-1），
  只能在入口段调用本模块。
"""

import json
import sys
from typing import NoReturn

HUMAN_ABORTED = '⛔ 已中断 (Ctrl-C) — {cmd} 未完成'
HUMAN_RERUN = '   💡 重跑: {cmdline}'
ERROR_ENVELOPE = {'status': 'error', 'data': None, 'error': 'interrupted'}
EXIT_INTERRUPTED = 130


def _cmd_label(prog, argv):
    """`<prog> <子命令>`：取首个非选项实参（与各入口 `command = argv[1]` 同口径）。"""
    for arg in argv[1:]:
        if not arg.startswith('-'):
            return f'{prog} {arg}'
    return prog


def _rerun_line(prog, argv):
    """同一条可复制命令：原样拼回实参，不补参、不猜（§11.2 第 3 行）。"""
    return ' '.join([prog] + list(argv[1:]))


def emit(prog, argv, json_mode=None) -> NoReturn:
    """打印中断提示并强制 exit 130（本函数不返回）。

    json_mode=None ⇒ 按 argv 里是否含 `--json` 自动判定（与各入口 `'--json' in args` 同口径）。
    """
    if json_mode is None:
        json_mode = '--json' in list(argv[1:])
    if json_mode:
        sys.stdout.write(json.dumps(ERROR_ENVELOPE, ensure_ascii=False) + '\n')
        sys.stdout.flush()
        stream = sys.stderr
    else:
        stream = sys.stdout
    print(HUMAN_ABORTED.format(cmd=_cmd_label(prog, argv)), file=stream)
    print(HUMAN_RERUN.format(cmdline=_rerun_line(prog, argv)), file=stream)
    raise SystemExit(EXIT_INTERRUPTED)
