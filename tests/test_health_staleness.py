#!/usr/bin/env python3
"""`scripts/llm-radar-health.py` 的判定点口径钉子（与 `lr status` 同源）。

跨仓需求 crossrepo-llm-radar-staleness / DAILY-CHECKER-CL191：
夜间合盖不采 ⇒ 纯绝对小时数必在早晨误报；两处出口（CLI status / 线上探针）必须同一口径，
否则 daily-checker 拿到 ok、我们自己的 freshness cron 仍报「数据过期」，等于没修。
"""
import importlib.util
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

from conftest import import_collector

ROOT = Path(__file__).resolve().parent.parent
HEALTH = ROOT / 'scripts' / 'llm-radar-health.py'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope='module')
def health():
    return _load(HEALTH, 'llm_radar_health_staleness')


def _at(hh, mm=0, days_ago=0):
    return datetime.combine(date.today() - timedelta(days=days_ago), time(hh, mm))


def _ts(dt, status='success'):
    return {'last_run_at': dt.isoformat(), 'last_run_status': status, 'last_news_date': dt.date().isoformat()}


class TestHealthJudgePoint:
    def test_morning_after_yesterday_is_silent(self, health):
        """昨日 19:33 采到、今天 07:42 探测 ⇒ 静默 (原误报)。"""
        code, msg = health.check(_ts(_at(19, 33, days_ago=1)), now=_at(7, 42))
        assert (code, msg) == (0, '')

    def test_silent_one_minute_before_judge_point(self, health):
        code, msg = health.check(_ts(_at(19, 33, days_ago=1)), now=_at(10, 9))
        assert (code, msg) == (0, '')

    def test_alerts_right_after_judge_point(self, health):
        code, msg = health.check(_ts(_at(19, 33, days_ago=1)), now=_at(10, 11))
        assert code == 1
        assert '数据过期' in msg and '判定点 10:10' in msg, msg

    def test_same_day_success_suppresses_until_grace(self, health):
        """今天 09:00 首采、09:15 探测 ⇒ 仍在宽限内 (判定点 09:30) ⇒ 静默。"""
        assert health.check(_ts(_at(9, 0)), now=_at(9, 15)) == (0, '')

    def test_threshold_applies_after_grace(self, health):
        """今天 09:00 采、22:00 探测 (13h > 12h) ⇒ 硬告警。"""
        code, msg = health.check(_ts(_at(9, 0)), now=_at(22, 0))
        assert code == 1 and '数据过期' in msg

    def test_critical_override_before_judge_point(self, health):
        """>48h 不受判定点保护: 凌晨 03:00 也要硬告警。"""
        code, msg = health.check(_ts(_at(19, 33, days_ago=3)), now=_at(3, 0))
        assert code == 1 and '兜底判定' in msg, msg

    def test_quality_failure_stays_soft(self, health):
        """质量失败但数据新鲜 ⇒ exit 0 + 软告警 (REA-2 语义未被改动)。"""
        code, msg = health.check(_ts(_at(9, 0), status='failed'), now=_at(9, 10))
        assert code == 0 and '质量告警' in msg

    def test_future_timestamp_is_clamped(self, health):
        code, msg = health.check(_ts(_at(13, 0)), now=_at(10, 0))
        assert (code, msg) == (0, ''), msg

    def test_grace_and_first_slot_env(self, health, monkeypatch):
        monkeypatch.setattr(health, 'STALENESS_GRACE_MIN', 0)
        assert health.staleness_judge_point(_at(8, 0), None, None) == _at(9, 40)
        monkeypatch.setattr(health, 'FIRST_SLOT_TODAY', 'not-a-time')
        monkeypatch.setattr(health, 'STALENESS_GRACE_MIN', 30)
        assert health.staleness_judge_point(_at(8, 0), None, None) == _at(10, 10)


def test_parity_with_collector(health):
    """两处出口同一口径: health 用 last_run_at 近似「今日成功时刻」时,
    与 collector.staleness_verdict(now, last_dt, first_ok) 的结论必须逐一相等。"""
    mod = import_collector()
    lasts = [_at(19, 33, days_ago=1), _at(3, 0), _at(9, 0), _at(9, 40), _at(11, 0),
             _at(19, 33, days_ago=3)]
    nows = [_at(7, 42), _at(9, 0), _at(9, 20), _at(10, 5), _at(10, 11), _at(16, 0),
            _at(22, 0), _at(3, 0)]
    mismatches = []
    for last in lasts:
        for now in nows:
            for status in ('success', 'failed'):
                is_stale, _, _ = health.staleness_verdict(now, last, status)
                first_ok = last if (status == 'success' and last.date() == now.date()) else None
                freshness, _, _ = mod.staleness_verdict(now, last, first_ok)
                if is_stale != (freshness in ('warning', 'critical')):
                    mismatches.append((last.isoformat(), now.isoformat(), status, is_stale, freshness))
    assert not mismatches, mismatches
