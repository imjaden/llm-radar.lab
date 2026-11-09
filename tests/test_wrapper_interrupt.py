#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CL007 P3（SEC-1）—— `lr` bash 包装层的中断钉子（shell 级）。

为什么必须单独钉 wrapper：`lr`/`llm-radar` 是 bash 包装层（`cache/system-command/*-wrapper.sh`，
**gitignored 生成物**），env 段（conda activate + `.env`）占掉启动的大半时间，SIGINT 常常落在
bash 而不是 Python。Python 侧的 `cli_interrupt` 钉子（`tests/test_cli_interrupt.py`）**完全覆盖不到**
这一段，所以 `install.py --force` 重生成 wrapper 把 `trap` / 高位 fd 副本冲掉时，所有 Python 用例仍然全绿。

判据（每条都能独立变红）:
1. `--json` 模式被中断 ⇒ rc=130，**stdout 恰好 58B**（只有 checkpoint 信封，无 env banner/进度行）；
2. 同一次中断 ⇒ stderr 非空且含 `⛔ 已中断` / `💡 重跑`（人类提示不许丢）；
3. 人类模式被中断 ⇒ rc=130，提示走 stdout（stderr=0B）—— 与 §11 人类模式契约一致。

前提缺失（CI 没有 `~/.local/bin/lr`）⇒ 整组 skip，不制造假红。
"""
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROBE = ROOT / 'scripts' / 'wrapper-interrupt-probe.sh'
WRAPPER = Path.home() / '.local' / 'bin' / 'lr'
ENVELOPE_BYTES = 58          # {"status": "error", "data": null, "error": "interrupted"}

pytestmark = pytest.mark.skipif(
    not PROBE.exists() or not WRAPPER.exists(),
    reason='无 wrapper 生成物（CI/新机）⇒ 跳过 shell 级钉子',
)


def _run(mode):
    r = subprocess.run(['bash', str(PROBE), mode, '1.2'],
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, f'探针自身失败: {r.returncode} {r.stderr[-300:]}'
    line = next((ln for ln in r.stdout.splitlines() if ln.startswith('RESULT')), '')
    assert line, f'探针无 RESULT 行: {r.stdout[-300:]}'
    return line, r


def test_json_mode_stdout_is_envelope_only():
    line, r = _run('--json')
    assert 'skip' not in line, f'探针被跳过: {line}'
    assert 'rc=130' in line, f'--json 中断必须 exit 130: {line}'
    assert f'stdout={ENVELOPE_BYTES}B' in line, (
        f'--json 的 stdout 只许放信封({ENVELOPE_BYTES}B)，实际: {line}\n'
        f'   —— 常见回退: env banner / 进度行又打到 stdout（2026-11-09 实测 124B 事故）'
    )
    assert '⛔ 已中断' in r.stdout, '信封之外不该有其它内容，提示应在 stderr'
    assert 'stderr=0B' not in line, f'--json 模式下人类提示不得丢: {line}'


def test_json_mode_hints_go_to_stderr():
    _, r = _run('--json')
    assert '⛔ 已中断 (Ctrl-C)' in r.stdout.split('--- stderr ---')[-1], 'stderr 缺中断提示'
    assert '💡 重跑' in r.stdout.split('--- stderr ---')[-1], 'stderr 缺重跑行'


def test_human_mode_hints_on_stdout():
    line, r = _run('--human')
    assert 'rc=130' in line, f'人类模式中断必须 exit 130: {line}'
    assert 'stderr=0B' in line, f'人类模式提示应走 stdout: {line}'
    assert '⛔ 已中断 (Ctrl-C)' in r.stdout and '💡 重跑' in r.stdout
    assert 'Traceback' not in r.stdout, '不得吐裸栈'
