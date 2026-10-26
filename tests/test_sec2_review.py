#!/usr/bin/env python3
"""`llm-radar-sec2-review.py` 的钉子：30 天窗口 + 命中计数 + 升级阈值（≥2 才建议升级）。

被测文件在 ops profile（不入本仓 git），用 importlib 直接加载真实文件。
"""
import importlib.util
from datetime import datetime, timedelta
from pathlib import Path

import pytest

SCRIPT = Path.home() / '.hermes' / 'profiles' / 'ops' / 'scripts' / 'llm-radar-sec2-review.py'
pytestmark = pytest.mark.skipif(not SCRIPT.is_file(), reason='ops 脚本不在本机')
PHRASE = '在运行但 7890 不可达'


@pytest.fixture(scope='module')
def sec2():
    spec = importlib.util.spec_from_file_location('llm_radar_sec2_review', SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _write(root, job, days_ago, text):
    d = root / job
    d.mkdir(parents=True, exist_ok=True)
    day = (datetime.now() - timedelta(days=days_ago)).strftime('%Y-%m-%d')
    (d / f'{day}_12-00-00.md').write_text(text, encoding='utf-8')


def test_counts_only_inside_window(sec2, tmp_path):
    root = tmp_path / 'out'
    _write(root, '4fb95acd0f81', 1, f'- 代理：{PHRASE}')     # 命中
    _write(root, 'e4bae95a6a40', 5, f'代理异常：{PHRASE}')    # 命中
    _write(root, '4fb95acd0f81', 45, f'- 代理：{PHRASE}')    # 窗口外, 不计
    _write(root, '4fb95acd0f81', 2, '- 代理：运行中・7890 可用')  # 无命中
    hits = sec2.occurrences(days=30, root=root)
    assert len(hits) == 2, hits


def test_ignores_unparsable_names(sec2, tmp_path):
    root = tmp_path / 'out'
    _write(root, '4fb95acd0f81', 1, f'- 代理：{PHRASE}')
    (root / '4fb95acd0f81' / 'latest.md').write_text(f'- 代理：{PHRASE}', encoding='utf-8')
    assert len(sec2.occurrences(days=30, root=root)) == 1, '无日期前缀的档不应计入'


def test_main_verdict_threshold(sec2, monkeypatch, capsys):
    monkeypatch.setattr(sec2, 'occurrences', lambda *a, **k: [('a', '日报')])
    assert sec2.main() == 0
    assert '维持现状' in capsys.readouterr().out

    monkeypatch.setattr(sec2, 'occurrences', lambda *a, **k: [('a', '日报'), ('b', '告警')])
    assert sec2.main() == 0
    out = capsys.readouterr().out
    assert '建议升级' in out and '命中次数：2' in out
