#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""告警分流（CL009）判据钉子。

设计红线（每条都可独立变红）：
1. 凭据类 1 次即报（不能等连败 3 次）；可自愈类按门槛（model/quota=2、network/other=3）。
2. **跃迁式**：首次出现发、升级为 critical 发、恢复发；同级在 dedupe 窗口内不重发。
3. 数据陈旧 / 源降级 / X 链路异常都能独立成条 —— 这些是「静默故障」的三条主通道。
4. `--dry-run` 不写状态、不调 osascript；发送失败不影响返回 0（best-effort）。
5. 采集器接线在 metrics 落盘之后（`_dispatch_alerts(metrics)`），且失败不冒泡。
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))

import llm_radar_alert as A  # noqa: E402

NOW = datetime(2026, 11, 12, 10, 0, 0)


def ts(hours_ago=0):
    return (NOW - timedelta(hours=hours_ago)).isoformat()


def healthy_metrics():
    return {'consecutive_fails': 0, 'last_error': None,
            'source_health': {'qbitai': {'consecutive_fails': 0}}}


def healthy_ts():
    return {'last_run_at': ts(0), 'last_run_status': 'success'}


# ---------- classify ----------

def test_auth_missing_reports_on_first_failure():
    m = {'consecutive_fails': 1, 'last_error': {'kind': 'auth_missing', 'at': ts(0)}}
    alerts = A.classify(m, healthy_ts(), now=NOW, x_health={})
    assert [a['kind'] for a in alerts] == ['auth_missing']
    assert alerts[0]['level'] == 'critical'
    assert 'DEEPSEEK_API_KEY' in alerts[0]['fix']


def test_network_waits_for_third_failure():
    for consec, expect in ((2, 0), (3, 1)):
        m = {'consecutive_fails': consec, 'last_error': {'kind': 'network', 'at': ts(0)}}
        alerts = A.classify(m, healthy_ts(), now=NOW, x_health={})
        assert len([a for a in alerts if a['kind'] == 'network']) == expect


def test_model_warns_from_second_failure():
    m = {'consecutive_fails': 2, 'last_error': {'kind': 'model', 'at': ts(0)}}
    alerts = A.classify(m, healthy_ts(), now=NOW, x_health={})
    assert [(a['kind'], a['level']) for a in alerts] == [('model', 'warning')]


def test_stale_data_is_critical_and_threshold_aware():
    old = A.classify(healthy_metrics(), {'last_run_at': ts(7)}, now=NOW, x_health={})
    fresh = A.classify(healthy_metrics(), {'last_run_at': ts(1)}, now=NOW, x_health={})
    assert [a['kind'] for a in old] == ['stale'] and old[0]['level'] == 'critical'
    assert fresh == []


def test_degraded_sources_are_reported_once():
    m = healthy_metrics()
    m['source_health'] = {'qbitai': {'consecutive_fails': 3}, 'jiqizhixin': {'consecutive_fails': 1}}
    alerts = A.classify(m, healthy_ts(), now=NOW, x_health={})
    assert [a['kind'] for a in alerts] == ['source_degraded']
    assert 'qbitai' in alerts[0]['text'] and 'jiqizhixin' not in alerts[0]['text']


def test_x_health_sidecar_reports_but_ignores_stale_sidecar():
    bad = A.classify(healthy_metrics(), healthy_ts(), now=NOW,
                     x_health={'status': 'page0', 'detail': 'page targets=0', 'at': ts(1)})
    old = A.classify(healthy_metrics(), healthy_ts(), now=NOW,
                     x_health={'status': 'page0', 'detail': 'page targets=0', 'at': ts(30)})
    assert [a['kind'] for a in bad] == ['x_health'] and bad[0]['level'] == 'critical'
    assert old == []


def test_healthy_state_produces_nothing():
    assert A.classify(healthy_metrics(), healthy_ts(), now=NOW, x_health={'status': 'ok'}) == []


# ---------- decide ----------

def test_first_alert_sends_then_dedupes_within_window():
    alerts = [{'level': 'warning', 'kind': 'quota', 'text': 't', 'fix': 'f'}]
    msgs1, st1 = A.decide(alerts, {}, now=NOW)
    msgs2, st2 = A.decide(alerts, st1, now=NOW + timedelta(hours=1))
    msgs3, _ = A.decide(alerts, st2, now=NOW + timedelta(hours=25))
    assert len(msgs1) == 1 and msgs2 == [] and len(msgs3) == 1


def test_escalation_to_critical_bypasses_window():
    warn = [{'level': 'warning', 'kind': 'model', 'text': 't', 'fix': 'f'}]
    crit = [{'level': 'critical', 'kind': 'model', 'text': 't2', 'fix': 'f'}]
    _, st = A.decide(warn, {}, now=NOW)
    msgs, st2 = A.decide(crit, st, now=NOW + timedelta(minutes=5))
    assert len(msgs) == 1 and msgs[0]['level'] == 'critical'
    assert st2['model']['level'] == 'critical'


def test_recovery_emits_receipt_and_clears_state():
    alerts = [{'level': 'critical', 'kind': 'auth', 'text': 't', 'fix': 'f'}]
    _, st = A.decide(alerts, {}, now=NOW)
    msgs, st2 = A.decide([], st, now=NOW + timedelta(minutes=30))
    assert len(msgs) == 1 and msgs[0]['level'] == 'info' and '已恢复' in msgs[0]['text']
    assert st2 == {}


def test_unclassified_error_is_not_silent_after_three_runs():
    m = {'consecutive_fails': 3, 'last_error': {'kind': 'other', 'at': ts(0)}}
    alerts = A.classify(m, healthy_ts(), now=NOW, x_health={})
    assert [a['kind'] for a in alerts] == ['other']


# ---------- check()/CLI ----------

def test_check_dry_run_sends_nothing_and_writes_no_state(tmp_path):
    sp = tmp_path / 'alert-state.json'
    m = {'consecutive_fails': 1, 'last_error': {'kind': 'auth', 'at': ts(0)}}
    res = A.check(state_path=sp, dry_run=True, now=NOW, channel='local',
                  metrics=m, ts_data=healthy_ts(), x_health={})
    assert len(res['messages']) == 1 and res['sent'] == 0
    assert not sp.exists(), 'dry-run 不得落状态（否则真故障会被永久去重掉）'


def test_check_persists_state_and_second_run_is_quiet(tmp_path):
    sp = tmp_path / 'alert-state.json'
    m = {'consecutive_fails': 1, 'last_error': {'kind': 'auth', 'at': ts(0)}}
    kw = dict(state_path=sp, now=NOW, channel='none', metrics=m,
              ts_data=healthy_ts(), x_health={})
    first = A.check(**kw)
    second = A.check(**kw)
    assert len(first['messages']) == 1 and second['messages'] == []
    saved = json.loads(sp.read_text(encoding='utf-8'))
    assert 'auth' in saved['kinds']


def test_cli_classify_json_envelope(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv('LLM_RADAR_ALERT_STATE', str(tmp_path / 's.json'))
    assert A.main(['classify', '--json']) == 0
    out = capsys.readouterr().out.strip()
    env = json.loads(out)
    assert env['status'] == 'success' and 'alerts' in env['data']


def test_collector_wires_dispatch_after_metrics_write():
    src = (ROOT / 'llm-radar-collector.py').read_text(encoding='utf-8')
    i_metrics = src.index("metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2))")
    i_call = src.index('self._dispatch_alerts(metrics)')
    assert i_call > i_metrics, '告警必须在 metrics 落盘之后判（否则读到上一轮）'
    body = src[src.index('def _dispatch_alerts'):]
    assert 'except Exception' in body, '告警失败不得冒泡到采集退出码'
    assert 'self._log_stream()' in body, '--json 模式下人类行必须走 stderr'
