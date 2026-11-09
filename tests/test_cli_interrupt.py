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

import ast
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

# 入口清单 = **发现集派生**（CL007 P4）: 手写清单会漏掉新入口
# （2026-11-04 新增 scripts/llm-radar-preflight.py 时，清单没跟上 ⇒ 该入口零覆盖、静态钉也失明）。
# 规则: git 索引里的 *.py, 含 `__main__`, 排除 tests/ cache/ tasks/（非产品入口）。
_ENTRY_EXCLUDE = {
    'llm-radar-collector.py',        # 主采集器单独覆盖（COLLECTOR）
    'scripts/cli_interrupt.py',      # 收口真源模块, 不是入口
}


def _discover_entries():
    out = subprocess.run(['git', 'ls-files', '*.py'], cwd=ROOT,
                         capture_output=True, text=True).stdout.splitlines()
    found = []
    for rel in out:
        if rel.startswith(('tests/', 'cache/', 'tasks/')) or rel in _ENTRY_EXCLUDE:
            continue
        try:
            src = (ROOT / rel).read_text(encoding='utf-8')
        except OSError:
            continue
        if '__main__' in src:
            found.append(rel)
    return sorted(found)


ENTRIES = _discover_entries()

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


def _call_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _has_interrupt_guard(path):
    """AST 判定（CL007 P5）：模块级 `if __name__ == '__main__'` 段里存在

        except KeyboardInterrupt:  <body 内含 emit(...) 调用>

    为什么不用「切片 + 行锚正则」（旧实现）：
      · X1 吞中断（`except KeyboardInterrupt: pass` 后面再来一句永不执行的 `emit(`）会假绿；
      · X2 合法写法 `except KeyboardInterrupt:  # 注释`、X3 `cli_interrupt.emit(...)` 会被误杀。
    """
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except SyntaxError:
        return False

    def is_main_guard(node):
        if not isinstance(node, ast.If):
            return False
        test = node.test
        return (isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name) and test.left.id == '__name__'
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Constant)
                and test.comparators[0].value == '__main__')

    for node in tree.body:
        if not is_main_guard(node):
            continue
        for sub in ast.walk(ast.Module(body=node.body, type_ignores=[])):
            if not isinstance(sub, ast.ExceptHandler):
                continue
            tp = sub.type
            name = tp.id if isinstance(tp, ast.Name) else (tp.attr if isinstance(tp, ast.Attribute) else None)
            if name != 'KeyboardInterrupt':
                continue
            for stmt in ast.walk(ast.Module(body=sub.body, type_ignores=[])):
                if isinstance(stmt, ast.Call) and _call_name(stmt.func) == 'emit':
                    return True
    return False


def test_static_all_entries_declare_single_catch_point():
    """静态回退钉子（AST 版）：每个入口的 `__main__` 段都必须有真实收口（吞中断/死 emit 不算）。"""
    bad = [str(f.relative_to(ROOT)) for f in [COLLECTOR] + [ROOT / rel for rel in ENTRIES]
           if not _has_interrupt_guard(f)]
    assert not bad, f'入口段缺代码级收口: {bad}'


@pytest.mark.parametrize('body,expect', [
    # X1: 吞中断 + 后面的 emit 是死代码 ⇒ 必须判红
    ("if __name__ == '__main__':\n"
     "    try:\n        main()\n"
     "    except KeyboardInterrupt:\n        pass\n"
     "    emit('x', sys.argv)\n", False),
    # X2: 合法写法 + 行尾注释 ⇒ 必须判绿
    ("if __name__ == '__main__':\n"
     "    try:\n        main()\n"
     "    except KeyboardInterrupt:  # 注释\n"
     "        emit('x', sys.argv)\n", True),
    # X3: 模块限定调用 ⇒ 必须判绿
    ("if __name__ == '__main__':\n"
     "    try:\n        sys.exit(main())\n"
     "    except KeyboardInterrupt:\n"
     "        cli_interrupt.emit('x', sys.argv)\n", True),
    # M6b: 只留注释、没有可执行收口 ⇒ 判红
    ("if __name__ == '__main__':\n"
     "    try:\n        main()\n"
     "    except KeyboardInterrupt:\n        # emit('x', sys.argv)\n        pass\n", False),
])
def test_static_ast_matrix(tmp_path, body, expect):
    f = tmp_path / 'entry.py'
    f.write_text(body, encoding='utf-8')
    assert _has_interrupt_guard(f) is expect


def test_discovery_covers_new_entries():
    """P4 判据：发现集必须覆盖当前全部 `__main__` 文件（新增入口自动纳入，不再靠手写清单）。"""
    undiscovered = []
    out = subprocess.run(['git', 'ls-files', '*.py'], cwd=ROOT,
                         capture_output=True, text=True).stdout.splitlines()
    for rel in out:
        if rel.startswith(('tests/', 'cache/', 'tasks/')):
            continue
        try:
            src = (ROOT / rel).read_text(encoding='utf-8')
        except OSError:
            continue
        if '__main__' in src and rel not in ENTRIES and rel not in _ENTRY_EXCLUDE:
            undiscovered.append(rel)
    assert not undiscovered, f'发现集漏项: {undiscovered}'


def test_demo_cleans_child_process_in_finally():
    """CL007 P6: demo 的 MCP Server 子进程必须在 `finally` 里收掉。

    旧实现把 `proc.stdin.close()/wait()` 写在正常路径末尾 ⇒ Ctrl-C 或断言失败时子进程常驻
    （持有 stdio 管道），下一轮再跑就叠进程。这里用 AST 判: main() 内存在
    `try ... finally`，且 finally 体内有 `proc.terminate` / `proc.kill` 兜底。
    """
    tree = ast.parse((SCRIPTS / 'mcp-protocol-demo.py').read_text(encoding='utf-8'))
    main_fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'main')
    tries = [n for n in ast.walk(main_fn) if isinstance(n, ast.Try)]
    assert tries, 'main() 内应有一个 try/finally 包裹子进程生命周期'
    fin = [n for n in tries if n.finalbody]
    assert fin, '缺 finally ⇒ 中断路径会残留 MCP Server 子进程'
    names = set()
    for stmt in ast.walk(ast.Module(body=fin[0].finalbody, type_ignores=[])):
        if isinstance(stmt, ast.Attribute):
            names.add(stmt.attr)
    assert {'terminate', 'kill'} <= names, f'finally 内需 terminate/kill 兜底, 实际: {sorted(names)}'
    assert 'wait' in names, 'finally 内需 wait 回收'


def test_preflight_entry_is_covered():
    """回归钉子：2026-11-04 新增的 preflight 入口必须既被发现、也有守卫。"""
    assert 'scripts/llm-radar-preflight.py' in ENTRIES
    assert _has_interrupt_guard(ROOT / 'scripts/llm-radar-preflight.py')


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
