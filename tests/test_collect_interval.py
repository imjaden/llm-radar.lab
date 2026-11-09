#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""采集最短间隔 + 容差判据钉子（2026-11-09 边界修复）。

事故形态（实测）：cron 在整点 **:40** 触发，而上一次成功常落在 **:4x**（如 14:42:06），
于是 20:40:08 那轮的真实间隔是 **5.97h** —— 旧判据 `hours_since < 6` 严格成立 ⇒ 稳定跳过，
文案四舍五入又显示成「仅 6.0h，跳过（最短间隔 6h）」，看起来像边界写错。
后果不是一次跳过，而是**节拍被系统性拖成 7h**（14:42 → 21:40 → 次日 04:40…），每天少采 3 轮。

修复：判据改**分钟粒度 + 容差**（默认 10min）——「差几分钟」按到点处理；容差可 env 覆盖（0 = 退回严格）。

判据（每条都能独立变红）：
1. 5.97h（358min）在默认容差下 ⇒ **采**（旧行为：跳过）；
2. 容差设 0 ⇒ 5.97h **跳过**（证明容差是唯一杠杆）；
3. 5.0h ⇒ 跳过，且文案给出**分钟**（不再四舍五入成「6.0h」）；
4. 恰好 6.0h ⇒ 采（边界含等于）；
5. force=True ⇒ 恒采，且不读 metrics；
6. metrics 缺失 / 时间戳损坏 ⇒ 采（首跑与容错语义不变）。
"""
import importlib.util
import json
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / 'llm-radar-collector.py'


def load_module(fresh=True):
    spec = importlib.util.spec_from_file_location('llm_radar_collector_interval', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make(tmp_path, *, hours_ago=None, broken=False, consecutive_fails=0):
    tc = load_module()
    tc.COLLECT_INTERVAL_TOLERANCE_MIN = 10.0
    c = tc.LLMRadarCollector()
    c.data_dir = Path(tmp_path)
    mpath = c.data_dir / 'metrics.json'
    if broken:
        mpath.write_text('{not json', encoding='utf-8')
    elif hours_ago is not None:
        last = (datetime.now() - timedelta(hours=hours_ago)).isoformat()
        mpath.write_text(json.dumps({'last_success_time': last,
                                     'consecutive_fails': consecutive_fails}),
                         encoding='utf-8')
    return tc, c


def test_just_below_interval_within_tolerance_collects(tmp_path):
    """真实事故值 5.97h ⇒ 必须采（容差 10min ⇒ 阈值 5h50m）。"""
    tc, c = make(tmp_path, hours_ago=5.97)
    assert c._think() is True


def test_tolerance_zero_restores_strict_skip(tmp_path):
    tc, c = make(tmp_path, hours_ago=5.97)
    tc.COLLECT_INTERVAL_TOLERANCE_MIN = 0.0
    assert c._think() is False


def test_well_below_interval_skips_and_reports_minutes(tmp_path, capsys):
    tc, c = make(tmp_path, hours_ago=5.0)
    assert c._think() is False
    out = capsys.readouterr().out
    assert '分钟' in out, f'文案应给分钟, 实际: {out!r}'
    assert '300' in out, f'5.0h 应显示 300 分钟, 实际: {out!r}'


def test_exact_interval_collects(tmp_path):
    tc, c = make(tmp_path, hours_ago=6.0)
    assert c._think() is True


def test_force_bypasses_interval_even_without_metrics(tmp_path):
    tc, c = make(tmp_path, hours_ago=1.0)
    assert c._think(force=True) is True


def test_missing_metrics_allows_collect(tmp_path):
    tc, c = make(tmp_path)
    assert c._think() is True


def test_corrupt_metrics_allows_collect(tmp_path):
    tc, c = make(tmp_path, broken=True)
    assert c._think() is True


def test_repeated_failures_warn_but_still_collect(tmp_path, capsys):
    tc, c = make(tmp_path, hours_ago=7.0, consecutive_fails=4)
    assert c._think() is True
    assert '连续 4 次失败' in capsys.readouterr().out


def test_env_float_ge_allows_zero_but_rejects_negative(monkeypatch):
    """`ge` 语义（本次新增）：容差允许 0，负数回退默认。"""
    tc = load_module()
    monkeypatch.setenv('LR_PROBE_GE', '0')
    assert tc._env_float('LR_PROBE_GE', 7.0, ge=0) == 0.0
    monkeypatch.setenv('LR_PROBE_GE', '-5')
    assert tc._env_float('LR_PROBE_GE', 7.0, ge=0) == 7.0
    monkeypatch.setenv('LR_PROBE_GE', 'abc')
    assert tc._env_float('LR_PROBE_GE', 7.0, ge=0) == 7.0
    # gt 语义不被破坏
    monkeypatch.setenv('LR_PROBE_GE', '0')
    assert tc._env_float('LR_PROBE_GE', 7.0, gt=0) == 7.0
