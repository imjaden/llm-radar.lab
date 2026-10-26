#!/usr/bin/env python3
"""告警侧 `driver_facts()` 的钉子（review 指出的「ops profile 脚本无测试 ⇒ 回退分支变异变不红」）。

被测对象不在本仓 git（`~/.hermes/profiles/ops/scripts/llm-radar-collect-report.py`），
这里用 importlib 直接加载真实文件，不复制实现：
  · manager 可用 ⇒ 以 `check --json` 为准（compatible 不报；不兼容报版本三元组）
  · manager 不可用 ⇒ 回退日志必须**倒序取最新**且**只认 24h 内**（旧实现正序 break 会报 9 天前的行）
"""
import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

REPORT = Path.home() / '.hermes' / 'profiles' / 'ops' / 'scripts' / 'llm-radar-collect-report.py'

pytestmark = pytest.mark.skipif(not REPORT.is_file(), reason='ops 报告脚本不在本机')


@pytest.fixture(scope='module')
def rf():
    spec = importlib.util.spec_from_file_location('llm_radar_collect_report', REPORT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _fake_run(stdout: str):
    import types
    return lambda *a, **k: types.SimpleNamespace(stdout=stdout, stderr='', returncode=0)


def _manager_json(verdict='compatible', chrome='156.0.8078.47', bad=None, good='156.0.8078.47'):
    paths = [{'path': '/x/stable/chromedriver', 'exists': True, 'version': good,
              'compatible': True}]
    if bad:
        paths[0]['version'] = bad
        paths[0]['compatible'] = False
    return json.dumps({'command': 'check', 'chrome_version': chrome, 'paths': paths,
                       'icloud': {'has_compatible': True}, 'verdict': verdict}, ensure_ascii=False)


def test_compatible_means_silent(rf, monkeypatch, tmp_path):
    monkeypatch.setattr(rf, 'CHROMEDRIVER_MANAGER', tmp_path / 'mgr')
    (tmp_path / 'mgr').write_text('#!/bin/sh\n', encoding='utf-8')
    monkeypatch.setattr(rf.subprocess, 'run', _fake_run('✅ 当前 Chrome 版本：156.0.8078.47\n'
                                                       + _manager_json()))
    msg, sig = rf.driver_facts()
    assert msg is None, f'compatible 不得产出根因行: {msg}'
    assert sig.startswith('ok:156.0.8078.47:156.0.8078.47')


def test_incompatible_reports_manager_verdict(rf, monkeypatch, tmp_path):
    monkeypatch.setattr(rf, 'CHROMEDRIVER_MANAGER', tmp_path / 'mgr')
    (tmp_path / 'mgr').write_text('#!/bin/sh\n', encoding='utf-8')
    monkeypatch.setattr(rf.subprocess, 'run',
                        _fake_run(_manager_json(verdict='compatible', bad='154.0.8037.92')))
    msg, sig = rf.driver_facts()
    assert '154.0.8037.92' in msg and 'chromedriver-manager 判定' in msg
    assert sig.startswith('bad:')


def test_fallback_ignores_history_outside_24h(rf, monkeypatch, tmp_path):
    """核心回归: 窗口里躺着 9 天前的命中, 但当前已修好 ⇒ 必须不报（旧实现会报）。"""
    log = tmp_path / 'collector.log'
    old = (datetime.now() - timedelta(days=9)).strftime('%Y-%m-%d %H:%M:%S')
    log.write_text(f'{old} ⚠️  chromedriver 主版本 154 与本机 Chrome 155 不匹配, 仍尝试使用: /x\n',
                   encoding='utf-8')
    monkeypatch.setattr(rf, 'CHROMEDRIVER_MANAGER', tmp_path / 'nope')
    monkeypatch.setattr(rf, 'LOG', log)
    msg, sig = rf.driver_facts()
    assert msg is None, f'历史行不得当现状: {msg}'
    assert sig.startswith('log:stale')


def test_fallback_takes_latest_recent_hit(rf, monkeypatch, tmp_path):
    log = tmp_path / 'collector.log'
    old = (datetime.now() - timedelta(days=9)).strftime('%Y-%m-%d %H:%M:%S')
    new = (datetime.now() - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
    log.write_text(
        f'{old} ⚠️  chromedriver 主版本 154 与本机 Chrome 155 不匹配, 仍尝试使用: /x\n'
        f'{new} ⚠️  chromedriver 主版本 155 与本机 Chrome 156 不匹配, 仍尝试使用: /y\n',
        encoding='utf-8')
    monkeypatch.setattr(rf, 'CHROMEDRIVER_MANAGER', tmp_path / 'nope')
    monkeypatch.setattr(rf, 'LOG', log)
    msg, sig = rf.driver_facts()
    assert msg is not None, '必须报出最新一条（None 说明回退分支扫错了方向/时间窗）'
    assert '155' in msg and '156' in msg, f'必须取最新一条, 而不是窗口内最老: {msg}'
    assert '154' not in msg
    assert sig == 'log:155:156'


def test_fingerprint_carries_driver_sig(rf):
    fp = json.loads(rf.fingerprint(['stale'], {'degraded': [], 'consecutive_fails': 0,
                                               'driver_sig': 'bad:156.0.8078.47:154.0.8037.92'}))
    assert fp['v'] == 'bad:156.0.8078.47:154.0.8037.92', '版本状态必须进指纹, 否则状态变化不重报'


# ---------- SEC-2 / LR-SEC-024: 代理三态可见性 ----------
def _stub_flclash(monkeypatch, running, port_open):
    import types
    m = types.ModuleType('flclash_proxy')
    m.is_running = lambda: running
    m.is_port_listening = lambda *a, **k: port_open
    monkeypatch.setitem(sys.modules, 'flclash_proxy', m)


def test_proxy_state_three_states(rf, monkeypatch):
    _stub_flclash(monkeypatch, False, False)
    assert rf.proxy_state() == '未运行（按需启动）'

    _stub_flclash(monkeypatch, True, True)
    assert '7890 可用' in rf.proxy_state()

    _stub_flclash(monkeypatch, True, False)
    state = rf.proxy_state()
    assert state.startswith('在运行但 7890 不可达'), 'Gatekeeper 待确认的唯一信号, 必须能报出这一态'


def test_digest_contains_proxy_line(rf, monkeypatch):
    _stub_flclash(monkeypatch, True, True)
    lines = [ln for ln in rf.build_digest().splitlines() if ln.startswith('- 代理：')]
    assert len(lines) == 1 and '7890 可用' in lines[0]


def test_alert_surfaces_proxy_anomaly(rf, monkeypatch):
    _stub_flclash(monkeypatch, True, False)
    msg = rf.build_alert({'age': 9.0, 'gen': '2026-10-26T00:00:00Z'},
                         {'driver_mismatch': None, 'degraded': [], 'consecutive_fails': 0,
                          'first_fail': ''}, ['stale'])
    assert '代理异常' in msg and msg.index('代理异常') < msg.index('数据陈旧'), \
        '代理异常应排在根因首位'
