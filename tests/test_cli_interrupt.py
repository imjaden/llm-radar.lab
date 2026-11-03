#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CL007 — Ctrl-C 中断收口钉子（规范: skills-governance/cli-args-reference.md §11 + §7）。

四条判据（每条都能独立变红）:
1. 人类模式中断 ⇒ 首行 `⛔ 已中断 (Ctrl-C) — <指令> 未完成` + 第三行 `💡 重跑:`，退出码 **130**；
2. 同上且 **不吐 traceback**（§11.2 「禁打印 traceback / 堆栈」）；
3. `--json` 模式中断 ⇒ stdout 只有 checkpoint 信封（§7），人类提示整体走 stderr；
4. 静态：全部 CLI 入口的 `__main__` 段都接 `cli_interrupt`（防退回「只包 main()」形态）。

注入方式：真实入口文件 + `runpy.run_path(run_name='__main__')` + trace 钩子在入口函数首帧抛
KeyboardInterrupt —— 等价于「信号恰好落在该命令执行期」。真实 SIGINT 对 <0.2s 的短命令不可控，
会让用例随机红绿；这里只替换「信号何时到达」这一个变量，执行体与文案全走生产代码。
"""

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
COLLECTOR = ROOT / 'llm-radar-collector.py'
SCRIPTS = ROOT / 'scripts'

# 入口清单 = CL007 白名单（tasks/ 与 demo/scratch 不在本批, 见回执）
ENTRIES = [
    'scripts/twitter-collector.py',
    'scripts/llm-radar-health.py',
    'scripts/flclash_proxy.py',
    'scripts/chromedriver_bootstrap.py',
    'scripts/mcp_submit_update.py',
    'scripts/llm-radar-mcp-server.py',
    'scripts/mcp-protocol-demo.py',
]

_HARNESS = r'''
import os, runpy, sys
TARGET, ENTRY, EXTRA = {target!r}, {entry!r}, {extra!r}
# 复刻 `python3 <script>` 的约定: sys.path[0] = 脚本所在目录（入口段靠它 import cli_interrupt）
sys.path.insert(0, os.path.dirname(os.path.abspath(TARGET)))
def hook(frame, event, arg):
    if event == 'call' and frame.f_code.co_name == ENTRY \
            and frame.f_code.co_filename.endswith(TARGET):
        raise KeyboardInterrupt
    return None
sys.settrace(hook)
sys.argv = [TARGET] + EXTRA
runpy.run_path(TARGET, run_name='__main__')
'''


def _run_interrupted(target, extra, entry='main', timeout=120):
    code = _HARNESS.format(target=target, entry=entry, extra=extra)
    # mcp_submit_update.py 的 key 检查在模块级（早于入口段）: 占位值只用于过闸, main 不会执行
    env = {**os.environ, 'LLM_RADAR_MCP_KEY': 'probe-only-not-a-credential'}
    return subprocess.run([sys.executable, '-c', code], capture_output=True,
                          text=True, timeout=timeout, cwd=ROOT, env=env)


def test_human_mode_interrupt_prints_hint_and_exit_130():
    r = _run_interrupted('llm-radar-collector.py', ['status'])
    assert r.returncode == 130, f'中断须 exit 130（§11.1-4），实际 {r.returncode}: {r.stdout[-400:]}'
    assert '⛔ 已中断 (Ctrl-C) — lr status 未完成' in r.stdout, r.stdout[-400:]
    assert '💡 重跑: lr status' in r.stdout, r.stdout[-400:]


def test_human_mode_interrupt_has_no_traceback():
    r = _run_interrupted('llm-radar-collector.py', ['status'])
    assert 'Traceback (most recent call last)' not in r.stdout + r.stderr
    assert 'KeyboardInterrupt' not in r.stdout + r.stderr


def test_json_mode_stdout_is_envelope_only():
    r = _run_interrupted('llm-radar-collector.py', ['status', '--json'])
    assert r.returncode == 130
    assert r.stdout.strip() == json.dumps(
        {'status': 'error', 'data': None, 'error': 'interrupted'}), f'stdout 必须只有信封: {r.stdout!r}'
    assert '⛔ 已中断 (Ctrl-C)' in r.stderr, '人类提示须走 stderr（§11.1-3）'
    assert '⛔ 已中断 (Ctrl-C)' not in r.stdout


@pytest.mark.parametrize('rel', ENTRIES)
def test_script_entry_routes_through_cli_interrupt(rel):
    extra = ['status'] if rel.endswith('llm-radar-mcp-server.py') else []
    entry = 'cmd_status' if rel.endswith('llm-radar-mcp-server.py') else 'main'
    r = _run_interrupted(rel, extra, entry=entry)
    assert r.returncode == 130, f'{rel}: rc={r.returncode} {r.stderr[-300:]}'
    assert '⛔ 已中断 (Ctrl-C)' in r.stdout, f'{rel}: 缺中断提示'
    assert 'Traceback' not in r.stdout + r.stderr, f'{rel}: 吐了裸栈'


ENTRY_TAIL = "if __name__ == '__main__':"


def _entry_slice(path):
    """入口段切片：只判 __main__ 之后的代码，避免模块 body 里的同名注释充当钉子。"""
    src = path.read_text(encoding='utf-8')
    return src[src.index(ENTRY_TAIL):]


def test_static_all_entries_declare_single_catch_point():
    """静态回退钉子（LR-CLI-004 收紧）：入口段切片内必须有**代码行**
    `except KeyboardInterrupt:` 且调用 `emit(` —— 只留注释不算达标（变异 M6b 须转红）。"""
    bad = []
    for f in [COLLECTOR] + [ROOT / rel for rel in ENTRIES]:
        tail = _entry_slice(f)
        has_except = re.search(r'^\s*except KeyboardInterrupt:\s*$', tail, re.M)
        has_emit = re.search(r'^\s*emit\(', tail, re.M)
        if not (has_except and has_emit):
            bad.append(f'{f.relative_to(ROOT)} (except={bool(has_except)}, emit={bool(has_emit)})')
    assert not bad, f'入口段缺代码级收口: {bad}'


def test_static_collector_import_guard_reraises_for_library_use():
    """import 期护栏：库加载（tests via importlib）必须重抛，不能吞（§11.1-1「清理后重抛」）。"""
    src = COLLECTOR.read_text(encoding='utf-8')
    assert 'except KeyboardInterrupt:' in src
    assert "if __name__ != '__main__':" in src, 'import 期护栏须区分入口/库加载'
    assert src.count("if __name__ != '__main__':") == 1
    after = src.split("if __name__ != '__main__':", 1)[1].lstrip('\n ')
    assert after.startswith('raise'), '库加载路径必须重抛 KeyboardInterrupt'


def test_rerun_line_shell_quotes_arguments(capsys):
    """LR-CLI-003：重跑行必须做 shell 引用，含元字符的实参复粘后仍是同一条命令。"""
    sys.path.insert(0, str(SCRIPTS))
    try:
        import cli_interrupt
    finally:
        sys.path.remove(str(SCRIPTS))

    argv = ['lr', 'commit', 'wip; rm -rf /tmp/x']
    with pytest.raises(SystemExit):
        cli_interrupt.emit('lr', argv)
    out, _ = capsys.readouterr()
    assert shlex.join(argv) in out, f'重跑行未做 shell 引用: {out!r}'
    assert 'lr commit wip; rm -rf /tmp/x' not in out, '朴拼形态出现 ⇒ 复粘会执行另一条命令'


def test_emit_contract_json_and_human(capsys):
    sys.path.insert(0, str(SCRIPTS))
    try:
        import cli_interrupt
    finally:
        sys.path.remove(str(SCRIPTS))

    with pytest.raises(SystemExit) as exc_json:
        cli_interrupt.emit('lr', ['lr', 'status', '--json'])
    out, err = capsys.readouterr()
    assert exc_json.value.code == 130
    assert json.loads(out) == {'status': 'error', 'data': None, 'error': 'interrupted'}
    assert '💡 重跑: lr status --json' in err
