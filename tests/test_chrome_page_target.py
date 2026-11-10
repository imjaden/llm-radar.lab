#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`lr chrome` 的 page target 兜底 + 幂等就绪（CL014 钉子）。

事故形态（2026-11-10 实测）：Chrome 自更新后以 `--no-startup-window` 自重启，绕过 launchd plist 的
URL 参数；KeepAlive 见 9222 仍在监听、进程仍在，不判失败 ⇒ page target = 0，而 chromedriver attach
报 `unable to discover open page` ⇒ X 采集连续 10 轮失败、`data/twitter.json` 停更 24.9h。
`lr chrome --status` 此刻仍报「CDP 就绪 / 已登录」（登录判据走浏览器级 `Storage.getCookies`），
所以这个故障**只能靠 page 计数发现**。

判据（每条可独立变红）：
1. 已有页面 ⇒ 复用，不调 PUT（幂等，不制造重复 tab）；
2. 0 页面 ⇒ PUT /json/new?<url>，等到列表出现页面 ⇒ created；
3. CDP 不可达 ⇒ cdp_down（与「0 页面」区分，否则会对着死端口一直建页）；
4. PUT 报错 ⇒ failed；
5. 建页后等不到页面 ⇒ failed（timeout=0 让循环不进）；
6. `--open` 被接受且走同一条幂等路径（rc=0，输出含页面行）；
7. 兜底失败时 rc=1（不能假装就绪）；
8. help/usage 文案含 `--open`（别只加代码不加说明）。
"""
import importlib.util
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / 'llm-radar-collector.py'


def load_module():
    spec = importlib.util.spec_from_file_location('llm_radar_collector_page', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PAGE = {'type': 'page', 'title': 'Home / X', 'url': 'https://x.com/home'}


def test_existing_page_is_reused_without_creating(tmp_path):
    tc = load_module()
    calls = []
    tc._cdp_page_targets = lambda port, timeout=3: [PAGE]
    tc._cdp_http = lambda *a, **k: calls.append(a)
    ok, n, action = tc._ensure_page_target(9222)
    assert (ok, n, action) == (True, 1, 'reuse')
    assert calls == [], '已有页面时不得再 PUT /json/new'


def test_zero_pages_creates_one_and_confirms():
    tc = load_module()
    seq = [[], [PAGE]]
    puts = []

    def fake_pages(port, timeout=3):
        return seq.pop(0) if seq else [PAGE]

    def fake_http(port, path, method='GET', timeout=3):
        puts.append((path, method))
        return {}

    tc._cdp_page_targets = fake_pages
    tc._cdp_http = fake_http
    ok, n, action = tc._ensure_page_target(9222, url='https://x.com/home')
    assert (ok, n, action) == (True, 1, 'created')
    assert puts and puts[0][1] == 'PUT', '新版 Chrome 必须 PUT（GET 回 405）'
    assert puts[0][0].startswith('/json/new?https://x.com/home')


def test_cdp_down_is_reported_separately_and_never_puts():
    tc = load_module()
    puts = []
    tc._cdp_page_targets = lambda port, timeout=3: None
    tc._cdp_http = lambda *a, **k: puts.append(a)
    ok, n, action = tc._ensure_page_target(9222)
    assert (ok, n, action) == (False, 0, 'cdp_down')
    assert puts == []


def test_put_failure_is_reported():
    tc = load_module()
    tc._cdp_page_targets = lambda port, timeout=3: []

    def boom(*a, **k):
        raise RuntimeError('CDP HTTP 405')

    tc._cdp_http = boom
    ok, n, action = tc._ensure_page_target(9222)
    assert (ok, n, action) == (False, 0, 'failed')


def test_page_never_appears_times_out():
    tc = load_module()
    tc._cdp_page_targets = lambda port, timeout=3: []
    tc._cdp_http = lambda *a, **k: {}
    ok, n, action = tc._ensure_page_target(9222, timeout=0)
    assert (ok, n, action) == (False, 0, 'failed')


def _stub_chrome_env(tc, monkeypatch, page_result):
    monkeypatch.setattr(tc, '_x_network_gate',
                        lambda ensure=True, probe_timeout=None, retry_timeout=None:
                        (True, '🌐 x.com 可达 (0.2s)', {}), raising=True)
    monkeypatch.setattr(tc, '_cdp_ready', lambda port, timeout=0.6: True, raising=True)
    monkeypatch.setattr(tc, '_chrome_profile_dir', lambda args: Path('/tmp/prof'), raising=True)
    monkeypatch.setattr(tc, '_ensure_page_target',
                        lambda port, url=None, timeout=10, settle=0.4: page_result, raising=True)


def test_open_alias_runs_idempotent_path(monkeypatch, capsys):
    tc = load_module()
    _stub_chrome_env(tc, monkeypatch, (True, 1, 'reuse'))
    rc = tc._cmd_chrome(['chrome', '--open'])
    out = capsys.readouterr().out
    assert rc == 0
    assert '页面' in out and '复用' in out


def test_page_failure_makes_exit_nonzero(monkeypatch, capsys):
    tc = load_module()
    _stub_chrome_env(tc, monkeypatch, (False, 0, 'cdp_down'))
    rc = tc._cmd_chrome(['chrome', '--open'])
    assert rc == 1


def test_help_documents_open_alias():
    tc = load_module()
    src = SCRIPT.read_text(encoding='utf-8')
    assert 'chrome [--open|--wait|--status]' in src
    assert '--open       同义别名' in src
