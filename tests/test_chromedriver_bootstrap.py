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
    assert rc1 == 0 and '未能跟随' in m1, 'Q-4: 失败也只给正文, 退出码恒 0（避免引擎级重复告警）'
    m2, rc2 = cb.watch()
    assert (m2, rc2) == ('', 0), '同一故障指纹不重复发'

    good = {'verdict': 'compatible', 'chrome': '157.0.1.1', 'drivers': [], 'good': ['157.0.1.1']}
    monkeypatch.setattr(cb, 'ensure', lambda **k: (True, 'noop', good, ''))
    m3, rc3 = cb.watch()
    assert rc3 == 0 and '已恢复' in m3


# ---------- deadline / 异常兜底（LR-CDG-007 / Q-4） ----------
def test_ensure_deadline_short_circuits(cb, sandbox, monkeypatch):
    """采集前置守卫的硬预算: 预算耗尽即返回 deadline, 不发起 download/upgrade（采集不陪等）。"""
    monkeypatch.setattr(cb, 'check', lambda timeout=90: _check_payload(sandbox['stable'], '154.0.8037.92',
                                                                      icloud=False))
    monkeypatch.setattr(cb, '_run', lambda argv, timeout=120: sandbox['calls'].append(list(argv)) or (0, ''))
    ok, action, after, detail = cb.ensure(deadline=0)
    assert (ok, action) == (False, 'deadline'), detail
    assert sandbox['calls'] == [], f'预算耗尽仍动了 manager: {sandbox["calls"]}'


def test_ensure_deadline_bounds_subprocess_timeout(cb, sandbox, monkeypatch):
    """剩余预算必须抬成子进程 timeout 上限（否则 300s 的 download 照样能压过 60s 预算）。"""
    seq = iter([
        _check_payload(sandbox['stable'], '154.0.8037.92'),       # 稳定路径旧
        _check_payload(sandbox['stable'], '156.0.8078.47'),       # upgrade 后 ok
    ])
    monkeypatch.setattr(cb, 'check', lambda timeout=90: next(seq))
    seen = []

    def fake_run(argv, timeout=120):
        seen.append((list(argv), timeout))
        return 0, '✅ 升级完成'

    monkeypatch.setattr(cb, '_run', fake_run)
    ok, action, _, _ = cb.ensure(deadline=60)
    assert (ok, action) == (True, 'upgraded')
    assert seen and all(t <= 60.001 for _, t in seen), f'子进程 timeout 超出预算: {seen}'


def test_watch_never_returns_nonzero_on_exception(cb, sandbox, monkeypatch):
    """写盘/manager 异常不得静默, 也不得用 rc≠0 触发引擎级重复告警（Q-4）。"""
    def boom(*a, **k):
        raise OSError('disk full')

    monkeypatch.setattr(cb, '_watch', boom)
    msg, rc = cb.watch()
    assert rc == 0, 'rc 必须恒 0'
    assert '守卫执行异常' in msg and 'disk full' in msg


def test_cli_ensure_accepts_deadline(cb, sandbox, monkeypatch, capsys):
    monkeypatch.setattr(cb, 'check', lambda timeout=90: _check_payload(sandbox['stable'], '154.0.8037.92',
                                                                      icloud=False))
    monkeypatch.setattr(cb, '_run', lambda argv, timeout=120: sandbox['calls'].append(list(argv)) or (0, ''))
    rc = cb.main(['--ensure', '--deadline', '0'])
    out = capsys.readouterr().out
    assert rc == 1 and '"action": "deadline"' in out, out


def test_ensure_deadline_at_first_check_is_not_no_manager(cb, sandbox, monkeypatch, tmp_path):
    """RIG-3: 预算在首步 check 就用光时必须报 deadline, 不能报「manager 不可用」。

    不 stub `_run`（真起一个 manager 桩 + 真 timeout）—— 旧钉子都 stub 了 `_run`, 与生产不等价。
    """
    slow = tmp_path / 'slow-mgr'
    slow.write_text('#!/bin/sh\nsleep 5\n', encoding='utf-8')
    slow.chmod(0o755)
    monkeypatch.setattr(cb, 'MANAGER', slow)
    ok, action, after, detail = cb.ensure(deadline=0)
    assert (ok, action) == (False, 'deadline'), f'{action} / {detail}'
    assert 'no_manager' not in action
    assert '预算耗尽' in detail, detail


def test_resolve_single_call_when_ready(cb, sandbox, monkeypatch, capsys):
    """OBS-6: 采集入口只需一次 `--resolve` —— 就绪时零 manager 动作, 直接给出稳定路径。"""
    payload = _check_payload(sandbox['stable'], '156.0.8078.47')
    monkeypatch.setattr(cb, 'check', lambda timeout=90: payload)
    monkeypatch.setattr(cb, '_run', lambda argv, timeout=120: sandbox['calls'].append(list(argv)) or (0, ''))
    rc = cb.main(['--resolve', '--deadline', '60'])
    assert rc == 0
    assert capsys.readouterr().out.strip() == str(sandbox['stable'])
    assert sandbox['calls'] == [], f'就绪时不该再动 manager: {sandbox["calls"]}'


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


# ---------- review 2026-10-26 补钉（每例对应一条实测缺口） ----------
def _healthy(stable):
    return {'verdict': 'compatible', 'chrome': '156.0.8078.47', 'good': ['156.0.8078.47'],
            'drivers': [], 'stable': str(stable), 'stable_compatible': True, 'paths': ['/p/other']}


def _stale_stable(stable):
    """核心形态: 稳定路径被覆盖成旧版, 但**另一个**注册路径仍兼容 ⇒ manager verdict 仍是 compatible。"""
    return {'verdict': 'compatible', 'chrome': '156.0.8078.47', 'good': ['156.0.8078.47'],
            'drivers': ['154.0.8037.92'], 'stable': None, 'stable_compatible': False,
            'paths': ['/p/other']}


def test_watch_reports_upgrade_when_verdict_unchanged(cb, sandbox, monkeypatch):
    """REGRESSION（🔴）: verdict/chrome/good 全不变时, 升级成功消息曾被指纹去重吞掉。

    实测: 健康一轮 → 稳定路径注入 154 → 自动跟随成功 ⇒ 旧实现返回 ('', 0) 静默。
    """
    monkeypatch.setattr(cb, 'ensure', lambda **k: (True, 'noop', _healthy(sandbox['stable']), ''))
    assert cb.watch() == ('', 0)                      # 健康基线（写指纹）

    monkeypatch.setattr(cb, 'ensure', lambda **k: (True, 'upgraded', _healthy(sandbox['stable']), 'upgrade rc=0'))
    msg, rc = cb.watch()
    assert rc == 0 and '已自动跟随' in msg, 'verdict/good 不变时升级消息不得被去重'


def test_watch_reports_failure_when_verdict_unchanged(cb, sandbox, monkeypatch):
    """REGRESSION（🔴）: 同形态的**失败**也必须发（否则飞书收不到任何告警, 只有 rc=1）。"""
    monkeypatch.setattr(cb, 'ensure', lambda **k: (True, 'noop', _healthy(sandbox['stable']), ''))
    cb.watch()
    monkeypatch.setattr(cb, 'ensure', lambda **k: (False, 'download_failed', _stale_stable(sandbox['stable']),
                                                   'download rc=1 网络不可达'))
    msg, rc = cb.watch()
    assert rc == 0 and '未能跟随' in msg, 'verdict/good 不变时失败消息不得被去重'


def test_watch_reports_each_upgrade_event(cb, sandbox, monkeypatch):
    """「真升级」是事件不是状态: 连着两轮都升级也必须各发一条（指纹去重只适用于故障）。"""
    monkeypatch.setattr(cb, 'ensure', lambda **k: (True, 'upgraded', _healthy(sandbox['stable']), 'upgrade rc=0'))
    msg1, rc1 = cb.watch()
    msg2, rc2 = cb.watch()
    assert rc1 == 0 and rc2 == 0
    assert '已自动跟随' in msg1 and '已自动跟随' in msg2, '第二次真升级被指纹吞掉'


def test_state_keeps_fault_since_across_repeats(cb, sandbox, monkeypatch):
    """恢复消息要能说「从什么时候开始坏」: since 必须跨多次失败保留（save_state 全量覆盖易丢）。"""
    monkeypatch.setattr(cb, 'ensure', lambda **k: (False, 'still_incompatible', _stale_stable(sandbox['stable']), ''))
    cb.watch()
    first = cb.load_state()['since']
    assert first
    cb.watch()
    assert cb.load_state()['since'] == first, 'since 被覆盖 ⇒ 恢复消息失去故障起点'

    monkeypatch.setattr(cb, 'ensure', lambda **k: (True, 'noop', _healthy(sandbox['stable']), ''))
    msg, rc = cb.watch()
    assert rc == 0 and first in msg, '恢复消息应引用故障起点'


def test_ensure_flags_unmanaged_stable_path(cb, sandbox, monkeypatch):
    """稳定路径在盘上但**未注册**给 manager ⇒ upgrade 返回 rc=3(noop)。

    旧实现把 rc=3 当 upgrade_failed, 且给不出能修好的指令; 正确动作是 stable_unmanaged + add --path。
    """
    payload = {'chrome_version': '156.0.8078.47', 'verdict': 'compatible',
               'paths': [{'path': '/other/chromedriver', 'exists': True,
                          'version': '156.0.8078.47', 'compatible': True}],
               'icloud': {'has_compatible': True}}
    monkeypatch.setattr(cb, 'check', lambda timeout=90: payload)
    calls = []
    monkeypatch.setattr(cb, '_run', lambda argv, timeout=120: calls.append(list(argv)) or
                        (3, '{"command":"upgrade","noop":true,"upgraded":false}'))
    ok, action, s, detail = cb.ensure()
    assert (ok, action) == (False, 'stable_unmanaged'), f'rc=3 是 noop 不是失败, 实际 {action}'
    msg = cb.message(action, ok, {}, s, detail)
    assert 'add --path' in msg and str(sandbox['stable']) in msg, '消息必须给出可执行的修复指令'


def test_ensure_download_permanent_failure_not_retried(cb, sandbox, monkeypatch):
    """无可用下载地址（永久）⇒ 不得再花一次 5 分钟重试; 网络抖动才重试。"""
    monkeypatch.setattr(cb, 'check', lambda timeout=90:
                        _check_payload(sandbox['stable'], '154.0.8037.92', icloud=False))
    calls = []

    def fake_run(argv, timeout=120):
        calls.append(list(argv))
        return 1, '错误: 未找到适配 Chrome 156.0.8078.47 的下载地址（API 不可达 / 该版本未发布）'

    monkeypatch.setattr(cb, '_run', fake_run)
    ok, action, _, _ = cb.ensure()
    assert (ok, action) == (False, 'download_failed')
    assert len([c for c in calls if 'download' in c]) == 1, '永久性失败不得重试'

    calls.clear()

    def flaky(argv, timeout=120):
        calls.append(list(argv))
        return (1, 'URLError: <urlopen error timed out>') if len(calls) == 1 else (0, 'ok')

    monkeypatch.setattr(cb, '_run', flaky)
    ok, action, _, _ = cb.ensure()   # check 仍是 icloud=False 那轮 → 需要 download
    assert len([c for c in calls if 'download' in c]) == 2, '网络抖动必须重试一次'


def test_ensure_single_writer_when_lock_held(cb, sandbox, monkeypatch):
    """三个入口（守卫 :05 / 主采集 :40 / X :20）并发 ensure 时, manager 的 copy2 覆盖非原子 ⇒ 必须串行。"""
    monkeypatch.setattr(cb, 'check', lambda timeout=90: _check_payload(sandbox['stable'], '154.0.8037.92'))
    holder, state = cb._acquire_lock()
    assert state == 'locked'
    calls = []
    monkeypatch.setattr(cb, '_run', lambda argv, timeout=120: calls.append(list(argv)) or (0, ''))
    try:
        ok, action, _, _ = cb.ensure()
        assert action == 'busy' and calls == [], '锁被占用时不得触碰 manager'
    finally:
        cb._release_lock(holder)
    ok, action, _, _ = cb.ensure()          # 锁释放后必须能正常干活
    assert action != 'busy' and any('upgrade' in c for c in calls), '锁释放后应恢复跟进'


def test_cli_check_exit_code_follows_readiness(cb, sandbox, monkeypatch, capsys):
    """`--check` 的 rc 曾是 manager 全局 verdict ⇒ 稳定路径旧了仍返回 0（同 pitfall #2）。"""
    monkeypatch.setattr(cb, 'check', lambda timeout=90: {
        'chrome_version': '156.0.8078.47', 'verdict': 'compatible',
        'paths': [{'path': '/other/chromedriver', 'exists': True,
                   'version': '156.0.8078.47', 'compatible': True},
                  {'path': str(sandbox['stable']), 'exists': True,
                   'version': '154.0.8037.92', 'compatible': False}],
        'icloud': {'has_compatible': True}})
    assert cb.main(['--check']) == 1, '稳定路径不兼容时 --check 必须非零'
    out = capsys.readouterr().out
    assert '"stable_compatible": false' in out

