"""Test `lr status` checkpoint protocol: 四态评估 + 边界 + fixture 隔离 (RIG-4/O-4).

status 读取统一走 self.project_root 派生路径; fixture 将 project_root patch 到 tmp_path
并预置 timestamp.json / data/metrics.json / data/snapshot.json 三文件,
绝不触碰真实项目根。
"""
import json
import re
import subprocess
from datetime import datetime, timedelta

import pytest

from conftest import import_collector

EMOJI_RE = re.compile(r'[🟢🟡🔴ℹ️✅❌]')


@pytest.fixture
def status_env(tmp_path):
    """隔离 status 环境: project_root → tmp_path + 预置三数据文件 + 返回 (collector, mod)."""
    mod = import_collector()
    c = mod.LLMRadarCollector()
    c.api_key = 'test-key'
    c._skip_push = True
    for m in ('_print_ok', '_print_err', '_print_info', '_print_warn'):
        setattr(c, m, lambda msg: None)

    # RIG-4: project_root → tmp_path; O-4 防御性同步 patch data_dir/snapshot_path
    c.project_root = tmp_path
    c.data_dir = tmp_path / 'data'
    c.snapshot_path = tmp_path / 'data' / 'snapshot.json'

    data_dir = tmp_path / 'data'
    data_dir.mkdir()

    # 默认健康态: 1h 前成功运行
    _write_timestamp(tmp_path, hours_ago=1, status='success')
    _write_metrics(data_dir, consec_fails=0)
    _write_snapshot(data_dir)

    return c, mod


def _write_timestamp(tmp_path, hours_ago=1, status='success', last_run_at=None):
    ts = {
        'last_run_at': last_run_at or (datetime.now() - timedelta(hours=hours_ago)).isoformat(),
        'last_run_status': status,
        'entity_count': 10,
    }
    (tmp_path / 'timestamp.json').write_text(json.dumps(ts), encoding='utf-8')


def _write_metrics(data_dir, consec_fails=0):
    (data_dir / 'metrics.json').write_text(
        json.dumps({'consecutive_fails': consec_fails}), encoding='utf-8')


def _write_snapshot(data_dir):
    snapshot = {
        'providers': [{'id': f'p{i}'} for i in range(5)],
        'people': [{'id': f'pe{i}'} for i in range(3)],
        'tools': [],
        'llms': [],
        'hotspots': [],
        'stats': {},
    }
    (data_dir / 'snapshot.json').write_text(json.dumps(snapshot), encoding='utf-8')


def _run_status(c, mod, json_mode=False):
    c._git_run = lambda *a, **kw: subprocess.CompletedProcess(['git'], 128, '', 'not a repo')
    return c.status(json_mode=json_mode)


class TestStatusOk:
    def test_seven_fields_json(self, status_env):
        c, mod = status_env
        result = _run_status(c, mod, json_mode=True)
        assert set(result) == {'id', 'label', 'status', 'icon', 'message', 'checks', 'actions'}
        assert result['id'] == 'llm-radar'
        assert result['status'] in ('ok', 'warning', 'critical', 'info')

    def test_ok_state(self, status_env):
        c, mod = status_env
        result = _run_status(c, mod)
        assert result['status'] == 'ok'
        assert result['icon'] == '🟢'
        assert result['message'].startswith('数据新鲜')
        assert not EMOJI_RE.search(result['message'])

    def test_ok_checks(self, status_env):
        c, mod = status_env
        result = _run_status(c, mod)
        labels = [ch['label'] for ch in result['checks']]
        assert labels == ['数据日期', '实体数', '质量门禁', 'Git 同步', '热点数']
        # 实体数: 5 providers + 3 people = 8
        entity_check = result['checks'][1]
        assert entity_check['value'] == '8 (5/3/0/0/0)'
        assert entity_check['status'] == 'info'
        # 质量门禁 success
        assert result['checks'][2]['value'] == 'success'
        assert result['checks'][2]['status'] == 'ok'
        # Git: 非 git 仓库 → n/a info (不升级状态)
        assert result['checks'][3]['value'] == 'n/a'
        assert result['checks'][3]['status'] == 'info'
        # 热点数: 空 snapshot hotspots → 0 条 warning (LLM-RADAR-CL005)
        assert result['checks'][4]['label'] == '热点数'
        assert result['checks'][4]['value'] == '0 条'
        assert result['checks'][4]['status'] == 'warning'
        # 热点数 warning 不影响主 status (仍 ok)
        assert result['status'] == 'ok'

    def test_actions_present(self, status_env):
        c, mod = status_env
        result = _run_status(c, mod)
        assert len(result['actions']) >= 1
        assert result['actions'][0]['cmd'] == 'lr run --force'


class TestStatusStates:
    def test_warning_stale(self, status_env):
        """7h < age <= 48h → warning"""
        c, mod = status_env
        _write_timestamp(c.project_root, hours_ago=mod.STALE_HOURS + 2)
        result = _run_status(c, mod)
        assert result['status'] == 'warning'
        assert result['icon'] == '🟡'
        assert '数据偏旧' in result['message']

    def test_critical_old(self, status_env):
        """age > 48h → critical"""
        c, mod = status_env
        _write_timestamp(c.project_root, hours_ago=mod.CRITICAL_HOURS + 2)
        result = _run_status(c, mod)
        assert result['status'] == 'critical'
        assert result['icon'] == '🔴'
        assert '数据过期' in result['message']

    def test_critical_snapshot_missing_no_exception(self, status_env):
        """验收 #3: 无 snapshot → critical 不抛异常"""
        c, mod = status_env
        (c.project_root / 'data' / 'snapshot.json').unlink()
        result = _run_status(c, mod)
        assert result['status'] == 'critical'
        assert result['icon'] == '🔴'
        assert '快照缺失' in result['message']

    def test_critical_timestamp_missing(self, status_env):
        c, mod = status_env
        (c.project_root / 'timestamp.json').unlink()
        result = _run_status(c, mod)
        assert result['status'] == 'critical'
        assert '数据缺失' in result['message']

    def test_critical_consecutive_fails(self, status_env):
        """全局 consecutive_fails >= 3 → critical (run 级)"""
        c, mod = status_env
        _write_metrics(c.project_root / 'data', consec_fails=5)
        result = _run_status(c, mod)
        assert result['status'] == 'critical'
        assert '连续失败 5 次' in result['message']

    def test_consecutive_fails_below_threshold_ok(self, status_env):
        """consecutive_fails = 2 (< 3) 不升级"""
        c, mod = status_env
        _write_metrics(c.project_root / 'data', consec_fails=2)
        result = _run_status(c, mod)
        assert result['status'] == 'ok'

    def test_warning_quality_failed(self, status_env):
        c, mod = status_env
        _write_timestamp(c.project_root, hours_ago=1, status='failed',
                         last_run_at=(datetime.now() - timedelta(hours=1)).isoformat())
        # 覆盖写入带 last_run_detail
        ts_path = c.project_root / 'timestamp.json'
        ts = json.loads(ts_path.read_text(encoding='utf-8'))
        ts['last_run_detail'] = '事件中位数新鲜度 200h > 168h'
        ts_path.write_text(json.dumps(ts), encoding='utf-8')
        result = _run_status(c, mod)
        assert result['status'] == 'warning'
        assert result['icon'] == '🟡'
        assert '质量门禁失败' in result['message']

    def test_warning_git_divergence(self, status_env, tmp_path):
        """非 0/0 分叉 → warning (本地 ref, 不 fetch)"""
        c, mod = status_env
        # 构造真实 git 仓库: 2 commits, origin/main 停在 HEAD~1 → ahead=1
        subprocess.run(['git', 'init', '-q', '-b', 'main'], cwd=tmp_path, check=True)
        subprocess.run(['git', 'config', 'user.name', 'test'], cwd=tmp_path, check=True)
        subprocess.run(['git', 'config', 'user.email', 'test@test'], cwd=tmp_path, check=True)
        (tmp_path / 'f.txt').write_text('x')
        subprocess.run(['git', 'add', '-A'], cwd=tmp_path, check=True)
        subprocess.run(['git', 'commit', '-qm', 'c1'], cwd=tmp_path, check=True)
        (tmp_path / 'f2.txt').write_text('y')
        subprocess.run(['git', 'add', '-A'], cwd=tmp_path, check=True)
        subprocess.run(['git', 'commit', '-qm', 'c2'], cwd=tmp_path, check=True)
        subprocess.run(['git', 'update-ref', 'refs/remotes/origin/main', 'HEAD~1'], cwd=tmp_path, check=True)

        result = c.status()
        assert result['status'] == 'warning'
        git_check = [ch for ch in result['checks'] if ch['label'] == 'Git 同步'][0]
        assert git_check['value'] == '1 ahead / 0 behind'
        assert git_check['status'] == 'warning'

    def test_git_no_fetch(self, status_env):
        """status 不触发 git fetch (全只读约束)"""
        c, mod = status_env
        calls = []

        def fake_git(*args, **kw):
            calls.append(args)
            return subprocess.CompletedProcess(['git'], 128, '', 'not a repo')

        c._git_run = fake_git
        c.status()
        assert not any(a[0] == 'fetch' for a in calls)
        assert not any(a[0] == 'pull' for a in calls)


class TestStatusBoundary:
    def test_boundary_just_below_stale_ok(self, status_env):
        """age 略低于 STALE_HOURS → ok (严格 > 才 warning)"""
        c, mod = status_env
        _write_timestamp(c.project_root, last_run_at=(
            datetime.now() - timedelta(hours=mod.STALE_HOURS - 0.1)).isoformat())
        result = _run_status(c, mod)
        assert result['status'] == 'ok'

    def test_boundary_just_below_critical_warning(self, status_env):
        """age 略低于 CRITICAL_HOURS → warning (严格 > 才 critical)"""
        c, mod = status_env
        _write_timestamp(c.project_root, last_run_at=(
            datetime.now() - timedelta(hours=mod.CRITICAL_HOURS - 0.1)).isoformat())
        result = _run_status(c, mod)
        assert result['status'] == 'warning'

    def test_unparseable_timestamp_critical(self, status_env):
        c, mod = status_env
        _write_timestamp(c.project_root, last_run_at='not-a-date')
        result = _run_status(c, mod)
        assert result['status'] == 'critical'


class TestStatusOutput:
    def test_text_single_line_no_emoji(self, status_env, capsys):
        c, mod = status_env
        _run_status(c, mod, json_mode=False)
        out = capsys.readouterr().out
        assert out.startswith('LLM Radar: ')
        assert not EMOJI_RE.search(out)
        assert '| 质量 success' in out

    def test_json_pure_stdout(self, status_env, capsys):
        c, mod = status_env
        _run_status(c, mod, json_mode=True)
        out = capsys.readouterr().out
        data = json.loads(out)  # stdout 必须纯 JSON
        assert data['status'] in ('ok', 'warning', 'critical', 'info')


class TestRunForceThrottle:
    def test_force_bypasses_6h_throttle(self, status_env):
        """验收 #4: run --force 绕过 6h 节流 (_think force=True)

        用 status_env 隔离 (tmp_path), 绝不写真实 data/metrics.json。
        """
        c, mod = status_env
        metrics_path = c.project_root / 'data' / 'metrics.json'
        metrics_path.write_text(json.dumps({
            'last_success_time': (datetime.now() - timedelta(hours=1)).isoformat(),
            'consecutive_fails': 0,
        }), encoding='utf-8')

        # 无 force → 节流拦截 (上次成功 < 6h)
        assert c._think(force=False) is False
        # force=True → 绕过
        assert c._think(force=True) is True
