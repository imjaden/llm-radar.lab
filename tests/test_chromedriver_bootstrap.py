#!/usr/bin/env python3
"""chromedriver 版本守卫单测（scripts/chromedriver_bootstrap.py）。

设计约束（与实现一一对应）:
  · manager 的 `verdict=compatible` 只要**任一**注册路径兼容即成立 ⇒ 采集侧只吃「稳定路径」,
    所以「稳定路径存在但不兼容」必须判 not ready（否则 Chrome 升级后采集悄悄用旧驱动）。
  · `upgrade` 必须带 `--all --json`（不加 --json 会 input() 等待 ⇒ cron 挂住）。
  · 状态不变 ⇒ 空输出（no_agent 静默）；指纹重复的失败不重复发。
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
MOD_PATH = ROOT / 'scripts' / 'chromedriver_bootstrap.py'


@pytest.fixture(scope='module')
def cb():
    spec = importlib.util.spec_from_file_location('chromedriver_bootstrap', MOD_PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture
def sandbox(cb, tmp_path, monkeypatch):
    """隔离 STABLE / STATE / MANAGER 三个路径, 并记录 manager 调用。"""
    stable = tmp_path / 'stable' / 'chromedriver'
    stable.parent.mkdir(parents=True)
    stable.write_text('bin', encoding='utf-8')
    monkeypatch.setattr(cb, 'STABLE', stable)
    monkeypatch.setattr(cb, 'STATE', tmp_path / 'state.json')
    mgr = tmp_path / 'chromedriver-manager'
    mgr.write_text('#!/bin/sh\n', encoding='utf-8')
    monkeypatch.setattr(cb, 'MANAGER', mgr)
    calls = []
    return {'stable': stable, 'mgr': mgr, 'calls': calls, 'tmp': tmp_path}


def _check_payload(stable, stable_ver, chrome='156.0.8078.47', good_ver='156.0.8078.47',
                   icloud=True):
    return {
        'command': 'check',
        'chrome_version': chrome,
        'paths': [
            {'path': '/x/other/chromedriver', 'exists': True, 'version': good_ver, 'compatible': True},
            {'path': str(stable), 'exists': True, 'version': stable_ver,
             'compatible': stable_ver == good_ver},
        ],
        'icloud': {'has_compatible': icloud},
        'verdict': 'compatible' if (stable_ver == good_ver or good_ver) else 'incompatible',
    }


# ---------- 判定 ----------
def test_ready_requires_stable_compatible(cb, sandbox):
    s = cb.state_summary(_check_payload(sandbox['stable'], '156.0.8078.47'))
    assert s['stable_compatible'] is True and cb._ready(s) is True

    s = cb.state_summary(_check_payload(sandbox['stable'], '154.0.8037.92'))
    assert s['stable_compatible'] is False
    assert s['verdict'] == 'compatible', 'manager 全局 verdict 仍可能是 compatible'
    assert cb._ready(s) is False, '稳定路径旧了就必须判未就绪（这是核心断言）'


def test_ready_when_no_stable_path(cb, sandbox, monkeypatch):
    sandbox['stable'].unlink()
    payload = _check_payload(sandbox['stable'], '156.0.8078.47')
    payload['paths'] = [p for p in payload['paths'] if p['path'] != str(sandbox['stable'])]
    s = cb.state_summary(payload)
    assert s['stable_exists'] is False
    assert cb._ready(s) is True, '没有稳定路径时任一兼容路径即可'


def test_usable_path_prefers_stable(cb, sandbox, monkeypatch):
    monkeypatch.setattr(cb, 'check', lambda timeout=90: _check_payload(sandbox['stable'], '156.0.8078.47'))
    assert cb.usable_path() == str(sandbox['stable'])


def test_usable_path_none_when_all_stale(cb, sandbox, monkeypatch):
    monkeypatch.setattr(cb, 'check', lambda timeout=90: {
        'chrome_version': '156.0.8078.47', 'verdict': 'incompatible',
        'paths': [{'path': str(sandbox['stable']), 'exists': True,
                   'version': '154.0.8037.92', 'compatible': False}],
        'icloud': {'has_compatible': False}})
    assert cb.usable_path() is None


# ---------- ensure ----------
def test_ensure_noop_when_ready(cb, sandbox, monkeypatch):
    monkeypatch.setattr(cb, 'check', lambda timeout=90: _check_payload(sandbox['stable'], '156.0.8078.47'))
    monkeypatch.setattr(cb, '_run', lambda argv, timeout=120: sandbox['calls'].append(argv) or (0, ''))
    ok, action, s, detail = cb.ensure()
    assert (ok, action) == (True, 'noop')
    assert sandbox['calls'] == [], '就绪时不得动 manager'


def test_ensure_upgrades_and_uses_non_interactive_flags(cb, sandbox, monkeypatch):
    seq = iter([
        _check_payload(sandbox['stable'], '154.0.8037.92'),      # 首次: 稳定路径旧
        _check_payload(sandbox['stable'], '156.0.8078.47'),      # upgrade 后: 已跟随
    ])
    monkeypatch.setattr(cb, 'check', lambda timeout=90: next(seq))

    def fake_run(argv, timeout=120):
        sandbox['calls'].append(list(argv))
        return 0, '✅ 升级完成'

    monkeypatch.setattr(cb, '_run', fake_run)
    ok, action, after, detail = cb.ensure()
    assert (ok, action) == (True, 'upgraded')
    assert after['stable_compatible'] is True
    upgrade = [c for c in sandbox['calls'] if 'upgrade' in c]
    assert upgrade and '--all' in upgrade[0] and '--json' in upgrade[0], \
        'upgrade 必须 --all --json（否则 input() 会挂住 cron）'


def test_ensure_downloads_when_icloud_lacks_match(cb, sandbox, monkeypatch):
    seq = iter([
        _check_payload(sandbox['stable'], '154.0.8037.92', icloud=False),
        _check_payload(sandbox['stable'], '156.0.8078.47'),
    ])
    monkeypatch.setattr(cb, 'check', lambda timeout=90: next(seq))
    monkeypatch.setattr(cb, '_run',
                        lambda argv, timeout=120: sandbox['calls'].append(list(argv)) or (0, ''))
    ok, action, _, _ = cb.ensure()
    assert (ok, action) == (True, 'upgraded')
    assert any('download' in c for c in sandbox['calls']), 'iCloud 无匹配版时必须先 download'


def test_ensure_no_manager(cb, sandbox, monkeypatch):
    monkeypatch.setattr(cb, 'check', lambda timeout=90: None)
    ok, action, _, detail = cb.ensure()
    assert (ok, action) == (False, 'no_manager')
    assert 'manager' in detail


# ---------- watch（cron 静默契约） ----------
def test_watch_silent_when_unchanged(cb, sandbox, monkeypatch):
    monkeypatch.setattr(cb, 'ensure',
                        lambda **k: (True, 'noop', {'verdict': 'compatible', 'chrome': '156.0.8078.47',
                                                    'good': ['156.0.8078.47']}, ''))
    msg, rc = cb.watch()
    assert (msg, rc) == ('', 0)
    msg2, rc2 = cb.watch()
    assert (msg2, rc2) == ('', 0), '状态未变不得重复发'


def test_watch_reports_upgrade_once(cb, sandbox, monkeypatch):
    after = {'verdict': 'compatible', 'chrome': '156.0.8078.47',
             'good': ['156.0.8078.47'], 'stable': str(sandbox['stable'])}
    monkeypatch.setattr(cb, 'ensure', lambda **k: (True, 'upgraded', after, 'upgrade rc=0'))
    msg, rc = cb.watch()
    assert rc == 0 and '已自动跟随' in msg and '156.0.8078.47' in msg
    assert 'llm-radar-chromedriver-guard' in msg


def test_watch_failure_deduped_then_recovery(cb, sandbox, monkeypatch):
    bad = {'verdict': 'incompatible', 'chrome': '157.0.1.1', 'drivers': ['156.0.8078.47'],
           'good': [], 'stable': None}
    monkeypatch.setattr(cb, 'ensure', lambda **k: (False, 'still_incompatible', bad, 'upgrade rc=2'))
    m1, rc1 = cb.watch()
    assert rc1 == 1 and '未能跟随' in m1
    m2, rc2 = cb.watch()
    assert (m2, rc2) == ('', 1), '同一故障指纹不重复发（但退出码保持非零）'

    good = {'verdict': 'compatible', 'chrome': '157.0.1.1', 'drivers': [], 'good': ['157.0.1.1']}
    monkeypatch.setattr(cb, 'ensure', lambda **k: (True, 'noop', good, ''))
    m3, rc3 = cb.watch()
    assert rc3 == 0 and '已恢复' in m3


# ---------- CLI ----------
def test_cli_print_path_and_check(cb, sandbox, monkeypatch, capsys):
    monkeypatch.setattr(cb, 'check', lambda timeout=90: _check_payload(sandbox['stable'], '156.0.8078.47'))
    assert cb.main(['--print-path']) == 0
    assert str(sandbox['stable']) in capsys.readouterr().out

    assert cb.main(['--check']) == 0
    assert '"verdict": "compatible"' in capsys.readouterr().out


def test_cli_print_path_rc1_when_incompatible(cb, sandbox, monkeypatch, capsys):
    monkeypatch.setattr(cb, 'check', lambda timeout=90: {
        'chrome_version': '157.0.1.1', 'verdict': 'incompatible',
        'paths': [{'path': str(sandbox['stable']), 'exists': True,
                   'version': '156.0.8078.47', 'compatible': False}],
        'icloud': {'has_compatible': False}})
    assert cb.main(['--print-path']) == 1
    assert capsys.readouterr().out.strip() == ''
