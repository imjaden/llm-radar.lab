#!/usr/bin/env python3
"""env 安全解析口径（CL151 §3）：空串 / 非数字 / 越界不得在 import 期打死进程。

背景（2026-10-26 review 实测）：`9a50cee` 只把 **int** 类收口成 `_env_int`，而
`llm-radar-collector.py` 仍有两处**模块级** `float(os.environ[...])`：
  `LLM_RADAR_FLCLASH_READY_TIMEOUT=''`（或 `abc`）⇒ `ValueError` at import ⇒ 整轮采集失败。
本文件锁住两条口径：
  1) `_env_int` / `_env_float` 对脏值一律回退默认（不抛）；
  2) 脏 env 下模块**仍能 import 成功**（回归钉子，防再次写回裸 float()/int()）。
"""
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
COLLECTOR = ROOT / 'llm-radar-collector.py'
HEALTH = ROOT / 'scripts' / 'llm-radar-health.py'


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)      # 模块级 env 解析在此发生
    return mod


@pytest.fixture(scope='module')
def col():
    return _load(COLLECTOR, 'collector_env_probe')


# ---------- 纯函数口径 ----------
@pytest.mark.parametrize('raw,expected', [('', 3), ('abc', 3), ('0', 3), ('-2', 3), ('5', 5)])
def test_env_int_falls_back_on_dirty_values(col, monkeypatch, raw, expected):
    monkeypatch.setenv('PROBE_INT', raw)
    assert col._env_int('PROBE_INT', 3, lo=1) == expected


@pytest.mark.parametrize('raw,expected', [('', 180.0), ('abc', 180.0), ('0', 180.0),
                                          ('-1.5', 180.0), ('2.5', 2.5), (' 30 ', 30.0)])
def test_env_float_falls_back_on_dirty_values(col, monkeypatch, raw, expected):
    monkeypatch.setenv('PROBE_FLOAT', raw)
    assert col._env_float('PROBE_FLOAT', 180.0, gt=0) == expected


def test_env_float_unset_uses_default(col, monkeypatch):
    monkeypatch.delenv('PROBE_FLOAT', raising=False)
    assert col._env_float('PROBE_FLOAT', 6.0, gt=0) == 6.0


# ---------- 回归钉子: 脏 env 下 import 不得炸 ----------
@pytest.mark.parametrize('name,raw', [
    ('LLM_RADAR_FLCLASH_READY_TIMEOUT', ''),
    ('LLM_RADAR_FLCLASH_READY_TIMEOUT', 'abc'),
    ('LLM_RADAR_DEGRADED_RETRY_HOURS', ''),
    ('LLM_RADAR_DEGRADED_RETRY_HOURS', 'six'),
    ('LLM_RADAR_DEGRADED_FAILS', ''),
    ('LLM_RADAR_DEGRADED_FAILS', 'many'),
])
def test_collector_imports_with_dirty_env(monkeypatch, name, raw):
    monkeypatch.setenv(name, raw)
    mod = _load(COLLECTOR, f'collector_env_{name}_{abs(hash(raw))}')
    assert mod.FLCLASH_READY_TIMEOUT > 0
    assert mod.DEGRADED_RETRY_HOURS > 0
    assert mod.DEGRADED_FAILS >= 1


def test_health_imports_with_dirty_env(monkeypatch):
    monkeypatch.setenv('LLM_RADAR_STALE_HOURS', '')
    mod = _load(HEALTH, 'health_env_probe_empty')
    assert mod.STALE_HOURS == 12
    monkeypatch.setenv('LLM_RADAR_STALE_HOURS', 'nope')
    assert _load(HEALTH, 'health_env_probe_bad').STALE_HOURS == 12
