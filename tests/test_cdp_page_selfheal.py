#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X 采集侧的「0 page target 自愈」钉子（CL015）。

与 CL014（`lr chrome` 侧兜底）同一语义、不同入口：collector 的 `--attach` 失败时如果 page 数为 0，
不能只重试 attach（会再失败一次），必须先补页面。事故：2026-11-10 Chrome 自更新后以
`--no-startup-window` 自重启 ⇒ page=0 ⇒ `unable to discover open page` 连败 10 轮、数据停 24.9h。

判据：复用 / 新建 / CDP 不可达 / PUT 失败 四态 + 接线存在（防止只加 helper 不调用）。
"""
import importlib.util
import json
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / 'scripts' / 'twitter-collector.py'


def load_module():
    spec = importlib.util.spec_from_file_location('twitter_collector_page', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Resp:
    def __init__(self, payload):
        self._b = payload if isinstance(payload, bytes) else json.dumps(payload).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_existing_page_reused_without_put(monkeypatch):
    tc = load_module()
    monkeypatch.setattr(tc, '_cdp_page_count', lambda port, timeout=3.0: 2)
    called = []
    monkeypatch.setattr(urllib.request, 'urlopen',
                        lambda *a, **k: called.append(a) or _Resp({}))
    assert tc._ensure_cdp_page(9222) == (True, 2, 'reuse')
    assert called == [], '已有页面时不得再建页'


def test_zero_pages_creates_one(monkeypatch):
    tc = load_module()
    seq = [0, 1]
    monkeypatch.setattr(tc, '_cdp_page_count', lambda port, timeout=3.0: seq.pop(0) if seq else 1)
    passed = []

    def fake_urlopen(req, timeout=5):
        passed.append((getattr(req, 'method', 'GET'), req.full_url))
        return _Resp({})

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)
    assert tc._ensure_cdp_page(9222, url='https://x.com/home') == (True, 1, 'created')
    method, url = passed[0]
    assert method == 'PUT', '新版 Chrome 建页必须 PUT（GET 回 405）'
    assert urlparse(url).path == '/json/new'


def test_cdp_down_reported_separately(monkeypatch):
    tc = load_module()
    monkeypatch.setattr(tc, '_cdp_page_count', lambda port, timeout=3.0: None)
    assert tc._ensure_cdp_page(9222) == (False, 0, 'cdp_down')


def test_page_put_failure_reported(monkeypatch):
    tc = load_module()
    monkeypatch.setattr(tc, '_cdp_page_count', lambda port, timeout=3.0: 0)

    def boom(*a, **k):
        raise OSError('connection refused')

    monkeypatch.setattr(urllib.request, 'urlopen', boom)
    assert tc._ensure_cdp_page(9222, timeout=0) == (False, 0, 'failed')


def test_cmd_collect_wires_selfheal_before_attach():
    """接线钉子：补页必须在 **attach 之前**（实测教训）。

    第一版把补页放在 FetchError 分支里 ⇒ 太晚：start_driver 在显式 chromedriver 失败后会先回退
    Selenium Manager（实测 stall 数分钟），补页那行根本没机会打印。
    """
    src = SCRIPT.read_text(encoding='utf-8')
    assert src.count('page target=0 ⇒ 补页') >= 1
    i = src.index('page target=0 ⇒ 补页')
    attach = src.index('driver = start_driver(profile_dir', i)
    assert i < attach, '补页必须先于 start_driver（attach）'
    j = src.index('_ensure_proxy_ready()', i)
    assert i < j, '补页也要先于「确保代理 → 重试 attach」'
