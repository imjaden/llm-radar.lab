"""twitter-collector-cron.sh 按需启停生命周期测试 (2026-10-06)。

覆盖 (判据: 采集前 0 进程 / 采集期间 ≥1 / 采集后 0):
- 未就绪 → 拉起 → 采集 → 释放 (全程 pid 观察 + pidfile 清理 + 退出码 0)
- 就绪 (外部常驻) → 复用不重复拉起, 且不释放他人实例
- 就绪 + 上轮遗留 pidfile → 复用并释放 (幂等自愈)
- 优雅退出超时 → SIGKILL 兜底, 最终仍 0
- TWITTER_CHROME_KEEP=1 → 保留实例
- 启动失败 → exit 1 且不残留
- 回归守卫: 不得用 `exec` 调采集器 (会吞掉收尾释放), 语法检查

隔离: 全程用独立端口 19222 + tmp 沙箱 (脚本副本/桩 Chrome/桩采集器), 不碰真实 9222 与真实 profile。
"""
import os
import re
import shutil
import signal
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CRON_SH = PROJECT_ROOT / 'scripts' / 'twitter-collector-cron.sh'
PORT = 19222
BASE_URL = f'http://127.0.0.1:{PORT}/json/version'

# 桩 Chrome: 只服务 /json/version 的极简 CDP 端点 (命令行保留 --remote-debugging-port, 供 pgrep 命中)
STUB_CHROME = '''#!/usr/bin/env python3
"""CDP 桩: 仅供 twitter-collector-cron.sh 生命周期测试。"""
import http.server, os, signal, socketserver, sys

port = 0
for a in sys.argv[1:]:
    if a.startswith('--remote-debugging-port='):
        port = int(a.split('=', 1)[1])
if os.environ.get('STUB_IGNORE_TERM') == '1':
    signal.signal(signal.SIGTERM, signal.SIG_IGN)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        body = b'{"Browser": "stub/1.0"}'
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


socketserver.TCPServer.allow_reuse_address = True
with socketserver.TCPServer(('127.0.0.1', port), Handler) as srv:
    srv.serve_forever()
'''

# 桩采集器: 睡 1s 后正常退出 (替代真实 Selenium 采集)
COLLECTOR_STUB = '''import time
print('[stub-collector] run', flush=True)
time.sleep(1.0)
'''


def _pids():
    """与 twitter-collector-cron.sh 同口径取调试 Chrome 主进程 pid。"""
    r = subprocess.run(['pgrep', '-f', f'remote-debugging-port={PORT}'],
                       capture_output=True, text=True)
    pids = []
    for token in r.stdout.split():
        cmd = subprocess.run(['ps', '-o', 'command=', '-p', token],
                             capture_output=True, text=True).stdout
        if not cmd.strip() or '--type=' in cmd:
            continue
        pids.append(int(token))
    return pids


def _wait_ready(timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE_URL, timeout=1):
                return True
        except Exception:
            time.sleep(0.2)
    return False


@pytest.fixture(autouse=True)
def reap_leftovers():
    """任何断言失败也保证不把桩 Chrome 留在机器上。"""
    yield
    for pid in _pids():
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


@pytest.fixture
def sandbox(tmp_path):
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    cron = scripts / 'twitter-collector-cron.sh'
    shutil.copy2(CRON_SH, cron)
    (scripts / 'twitter-collector.py').write_text(COLLECTOR_STUB, encoding='utf-8')
    stub = tmp_path / 'stub-chrome'
    stub.write_text(STUB_CHROME, encoding='utf-8')
    stub.chmod(0o755)
    return {
        'root': tmp_path,
        'cron': cron,
        'stub': stub,
        'pidfile': tmp_path / 'cache' / 'pids' / f'twitter-chrome-{PORT}.pid',
    }


def env_for(sandbox, **extra):
    env = dict(os.environ)
    env.update({
        'TWITTER_CDP_PORT': str(PORT),
        'TWITTER_PROFILE_DIR': str(sandbox['root'] / 'profile'),
        'TWITTER_CHROME_BIN': str(sandbox['stub']),
        'TWITTER_CHROME_LOG': str(sandbox['root'] / 'chrome.log'),
        'TWITTER_CHROME_SHUTDOWN_TIMEOUT': '3',
        'TWITTER_CHROME_READY_TRIES': '3',
    })
    env.update({k: str(v) for k, v in extra.items()})
    return env


def run_cron(sandbox, env, timeout=60):
    return subprocess.run(['bash', str(sandbox['cron'])], env=env,
                          capture_output=True, text=True, timeout=timeout)


def test_launch_collect_release(sandbox):
    """判据主路径: 采集前 0 → 拉起 → 采集期间 ≥1 → 采集后 0。"""
    assert _pids() == []
    proc = subprocess.Popen(['bash', str(sandbox['cron'])], env=env_for(sandbox),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    peak = 0
    deadline = time.time() + 30
    while proc.poll() is None and time.time() < deadline:
        peak = max(peak, len(_pids()))
        time.sleep(0.2)
    out, _ = proc.communicate(timeout=30)

    assert proc.returncode == 0, out
    assert peak >= 1, f'采集期间未见调试 Chrome: {out}'
    assert _pids() == [], f'采集后仍残留: {_pids()}'
    assert not sandbox['pidfile'].exists(), 'pidfile 未清理'
    assert '未就绪, 启动调试 Chrome' in out
    assert '[stub-collector] run' in out          # 采集确实执行
    assert '已释放' in out


def test_reuse_external_instance_not_released(sandbox):
    """外部常驻实例: 复用不重复拉起, 且采集后不动它。"""
    stub = subprocess.Popen([str(sandbox['stub']), f'--remote-debugging-port={PORT}',
                             f'--user-data-dir={sandbox["root"] / "profile2"}'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        assert _wait_ready(), '桩 Chrome 未就绪'
        r = run_cron(sandbox, env_for(sandbox))
        assert r.returncode == 0, r.stdout + r.stderr
        assert '外部常驻实例' in r.stdout
        assert '启动调试 Chrome' not in r.stdout       # 未重复拉起
        assert stub.poll() is None, '外部实例被误杀'
    finally:
        stub.kill()
        stub.wait(timeout=10)


def test_adopts_and_releases_orphan(sandbox):
    """上轮遗留 (pidfile 存活): 复用并在本轮收尾释放, 删 pidfile。"""
    stub = subprocess.Popen([str(sandbox['stub']), f'--remote-debugging-port={PORT}',
                             f'--user-data-dir={sandbox["root"] / "profile3"}'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert _wait_ready(), '桩 Chrome 未就绪'
    sandbox['pidfile'].parent.mkdir(parents=True, exist_ok=True)
    sandbox['pidfile'].write_text(f'{stub.pid}\n', encoding='utf-8')

    r = run_cron(sandbox, env_for(sandbox))
    assert r.returncode == 0, r.stdout + r.stderr
    assert '上轮遗留' in r.stdout
    assert not sandbox['pidfile'].exists()
    assert _pids() == []


@pytest.mark.parametrize('record', ['{dead}\n{live}\n', '{dead}\n'])
def test_adopts_orphan_with_stale_pid_record(sandbox, record):
    """pidfile 含已退出的 bootstrap pid (真实运行见过的形态) 仍须收编释放, 不得误判为外部实例。"""
    stub = subprocess.Popen([str(sandbox['stub']), f'--remote-debugging-port={PORT}',
                             f'--user-data-dir={sandbox["root"] / "profile4"}'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    assert _wait_ready(), '桩 Chrome 未就绪'
    sandbox['pidfile'].parent.mkdir(parents=True, exist_ok=True)
    sandbox['pidfile'].write_text(record.format(dead=990001, live=stub.pid), encoding='utf-8')

    r = run_cron(sandbox, env_for(sandbox))
    assert r.returncode == 0, r.stdout + r.stderr
    assert '上轮遗留' in r.stdout
    assert '外部常驻实例' not in r.stdout
    assert _pids() == [], f'采集后仍残留: {_pids()}'
    assert not sandbox['pidfile'].exists()


def test_sigkill_fallback_on_graceful_timeout(sandbox):
    """桩忽略 SIGTERM → 超时 SIGKILL, 最终仍 0。"""
    env = env_for(sandbox, STUB_IGNORE_TERM='1', TWITTER_CHROME_SHUTDOWN_TIMEOUT='2')
    r = run_cron(sandbox, env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert 'SIGKILL' in r.stdout
    assert _pids() == [], f'采集后仍残留: {_pids()}'


def test_keep_flag_retains_instance(sandbox):
    """TWITTER_CHROME_KEEP=1 → 采集后保留实例 (人工登录/调试用)。"""
    env = env_for(sandbox, TWITTER_CHROME_KEEP='1')
    r = run_cron(sandbox, env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert '保留调试 Chrome' in r.stdout
    assert len(_pids()) >= 1, '应保留实例'
    assert sandbox['pidfile'].exists(), '保留时应留 pidfile 供下轮收编'


def test_launch_failure_exits_1(sandbox):
    """Chrome 起不来 → exit 1 + 提示, 不残留。"""
    false_bin = shutil.which('false') or '/usr/bin/false'
    env = env_for(sandbox, TWITTER_CHROME_BIN=false_bin, TWITTER_CHROME_READY_TRIES='1')
    r = run_cron(sandbox, env)
    assert r.returncode == 1, r.stdout + r.stderr
    assert '启动失败' in r.stdout + r.stderr
    assert _pids() == []


def test_regression_guard_no_exec_and_syntax():
    """守卫: 采集器不得用 exec 调用 (否则收尾释放永不执行); 脚本语法必须合法。"""
    src = CRON_SH.read_text(encoding='utf-8')
    assert not re.search(r'^\s*exec\s', src, re.M), 'exec 会吞掉收尾释放'
    assert 'trap cleanup EXIT' in src
    assert 'set -u' in src
    r = subprocess.run(['bash', '-n', str(CRON_SH)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
