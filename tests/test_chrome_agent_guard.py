#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`scripts/twitter-chrome-agent.sh`（launchd 守护入口）的幂等契约钉子（CL017）。

事故形态（2026-11-12 实测）：plist 直接 exec Chrome + KeepAlive=true，当已有**别的** Chrome 占着
同一 user-data-dir 时，每次 spawn 都被「转发 URL 后退出 0」⇒ launchd 每 30s 再 spawn ⇒
每 30 秒多一个 https://x.com/home 页签（实测 runs 477 / 16+ 页签 / 日志刷
`Opening in existing browser session.`）。

契约（每条独立可红）：
1. 端口在监听 ⇒ no-op：不 spawn Chrome、exit 0（配合 KeepAlive={SuccessfulExit=false} 不再重启）；
2. 端口空闲 ⇒ 走 exec 分支（用 /bin/echo 假 Chrome 断言 argv 拼接）；
3. 监听中但 page targets=0 ⇒ 补一次页（PUT /json/new），有页则**绝不**建页；
4. /json/list 不可读 ⇒ 跳过补页、仍 exit 0（不能因为探测失败就杀守护）。
"""
import http.server
import os
import socket
import subprocess
import threading
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / 'scripts' / 'twitter-chrome-agent.sh'


def run_guard(**env):
    e = dict(os.environ)
    e.pop('TWITTER_CDP_PORT', None)
    e.update({k: str(v) for k, v in env.items()})
    return subprocess.run(['/bin/bash', str(SCRIPT)], capture_output=True, text=True,
                          env=e, timeout=30)


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


class _Handler(http.server.BaseHTTPRequestHandler):
    pages = 1
    puts = []

    def do_GET(self):  # noqa: N802
        body = ('[{"type": "page", "url": "https://x.com/home"}]' if self.pages
                else '[]').encode()
        self.send_response(200)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_PUT(self):  # noqa: N802
        _Handler.puts.append(self.path)
        self.send_response(200)
        self.send_header('Content-Length', '2')
        self.end_headers()
        self.wfile.write(b'{}')

    def log_message(self, *a):
        pass


def serve(pages):
    _Handler.pages = pages
    _Handler.puts = []
    srv = http.server.HTTPServer(('127.0.0.1', 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def test_listening_port_is_noop_and_never_spawns_chrome():
    srv, port = serve(pages=1)
    try:
        r = run_guard(TWITTER_CDP_PORT=port, TWITTER_CHROME_BIN='/bin/echo')
        assert r.returncode == 0
        assert '已在监听' in r.stdout
        assert '--remote-debugging-port=' not in r.stdout.split('page targets')[0], '不得 spawn Chrome'
        assert _Handler.puts == [], '有页面时不得建页'
    finally:
        srv.shutdown()


def test_listening_with_zero_pages_creates_exactly_one():
    srv, port = serve(pages=0)
    try:
        r = run_guard(TWITTER_CDP_PORT=port, TWITTER_CHROME_BIN='/bin/echo')
        assert r.returncode == 0
        assert '补页' in r.stdout
        assert len(_Handler.puts) == 1 and _Handler.puts[0].startswith('/json/new?')
    finally:
        srv.shutdown()


def test_free_port_execs_chrome_with_expected_argv():
    port = free_port()
    r = run_guard(TWITTER_CDP_PORT=port, TWITTER_CHROME_BIN='/bin/echo',
                  TWITTER_CDP_PAGE_URL='https://x.com/home')
    assert r.returncode == 0
    assert f'--remote-debugging-port={port}' in r.stdout
    assert '--user-data-dir=' in r.stdout
    assert r.stdout.strip().split()[-1] == 'https://x.com/home'


def test_unreadable_json_list_still_exits_zero():
    # 端口在监听但不是 CDP（用裸 socket 监听），/json/list 拿不到 ⇒ 跳过补页
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    s.listen(1)
    port = s.getsockname()[1]
    try:
        r = run_guard(TWITTER_CDP_PORT=port, TWITTER_CHROME_BIN='/bin/echo')
        assert r.returncode == 0
        assert '已在监听' in r.stdout
    finally:
        s.close()


def test_plist_contract_is_documented_in_script():
    """注入点：脚本必须写明与 KeepAlive={SuccessfulExit=false} 的配套关系。"""
    src = SCRIPT.read_text(encoding='utf-8')
    assert 'SuccessfulExit' in src
    assert 'KeepAlive' in src
