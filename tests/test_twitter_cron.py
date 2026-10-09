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
import datetime
import json
import os
import re
import shutil
import signal
import subprocess
import sys
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

# ── FlClash 桩: 唯一真源 scripts/flclash_proxy.py 的替身 (状态目录模拟运行态) ──
# 运行态 = state/flclash.running 标记 ∧ state/flclash.pid 记录的进程存活;
# 每次调用把 argv 追加到 state/argv.log (断言 shell 编排的实参)。
# 标记文件: flclash.no_ready = ensure 就绪失败; flclash.ignore_quit = release 杀不掉。
STUB_FLCLASH_PY = '''#!/usr/bin/env python3
import os, subprocess, sys

STATE = os.environ['STUB_STATE']


def _path(name):
    return os.path.join(STATE, name)


def _flag(name):
    return os.path.exists(_path(name))


def _pid():
    try:
        with open(_path('flclash.pid')) as fh:
            pid = int(fh.read().strip())
        os.kill(pid, 0)
        return pid
    except Exception:
        return None


def running():
    return _flag('flclash.running') and _pid() is not None


def main(argv):
    with open(_path('argv.log'), 'a') as fh:
        fh.write(' '.join(argv) + '\\n')
    cmd = argv[0] if argv else ''
    if cmd == 'pids':
        pid = _pid() if running() else None
        print(pid if pid else '')
        return 0
    if cmd == 'is-running':
        print('running' if running() else 'stopped')
        return 0 if running() else 1
    if cmd == 'ensure':
        if running():
            print('ready')
            return 0
        if _flag('flclash.no_ready'):
            print('not-ready')
            return 1
        proc = subprocess.Popen(['/bin/sleep', '211'],   # 假代理进程 (独特时长便于回收)
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                stdin=subprocess.DEVNULL)
        with open(_path('flclash.pid'), 'w') as fh:
            fh.write(str(proc.pid))
        open(_path('flclash.running'), 'w').close()
        open(_path('flclash.ready'), 'w').close()
        print('ready')
        return 0
    if cmd == 'release':
        if not running():
            print('released')
            return 0
        if _flag('flclash.ignore_quit'):
            print('still-running')
            return 1
        for name in ('flclash.running', 'flclash.ready', 'flclash.pid'):
            try:
                os.remove(_path(name))
            except OSError:
                pass
        print('released')
        return 0
    if cmd == 'notify':
        return 0
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
'''
FAKE_PROXY_PATTERN = 'sleep 211'


def _pids():
    """与 twitter-collector-cron.sh 同口径取调试 Chrome 主进程 pid (含"须是 Chrome 程序"这条)。"""
    r = subprocess.run(['pgrep', '-f', f'remote-debugging-port={PORT}'],
                       capture_output=True, text=True)
    pids = []
    for token in r.stdout.split():
        cmd = subprocess.run(['ps', '-o', 'command=', '-p', token],
                             capture_output=True, text=True).stdout.strip()
        if not cmd or '--type=' in cmd:
            continue
        if 'stub-chrome' not in cmd and 'Google Chrome' not in cmd:
            continue          # 旁观进程 (只"提到"端口的监视脚本等) 不算实例
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
    """任何断言失败也保证不把桩 Chrome / 桩代理进程留在机器上。"""
    yield
    for pid in _pids():
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    subprocess.run(['pkill', '-f', FAKE_PROXY_PATTERN], capture_output=True)


@pytest.fixture
def sandbox(tmp_path):
    scripts = tmp_path / 'scripts'
    scripts.mkdir()
    cron = scripts / 'twitter-collector-cron.sh'
    shutil.copy2(CRON_SH, cron)
    (scripts / 'twitter-collector.py').write_text(COLLECTOR_STUB, encoding='utf-8')
    # FlClash 唯一真源的替身: shell 只做编排, 每次调用的实参记入 state/argv.log
    (scripts / 'flclash_proxy.py').write_text(STUB_FLCLASH_PY, encoding='utf-8')
    stub = tmp_path / 'stub-chrome'
    stub.write_text(STUB_CHROME, encoding='utf-8')
    stub.chmod(0o755)
    state = tmp_path / 'state'
    state.mkdir()
    return {
        'root': tmp_path,
        'cron': cron,
        'stub': stub,
        'state': state,
        'argv_log': state / 'argv.log',
        'pidfile': tmp_path / 'cache' / 'pids' / f'twitter-chrome-{PORT}.pid',
    }


def flclash_calls(sandbox):
    """shell 对真源 helper 的调用流水 (每行一个 argv)。"""
    f = sandbox['argv_log']
    return f.read_text(encoding='utf-8').splitlines() if f.exists() else []


def env_for(sandbox, **extra):
    env = dict(os.environ)
    env.update({
        'STUB_STATE': str(sandbox['state']),
        'TWITTER_CDP_PORT': str(PORT),
        'TWITTER_PROFILE_DIR': str(sandbox['root'] / 'profile'),
        'TWITTER_CHROME_BIN': str(sandbox['stub']),
        'TWITTER_CHROME_LOG': str(sandbox['root'] / 'chrome.log'),
        'TWITTER_CHROME_SHUTDOWN_TIMEOUT': '3',
        'TWITTER_CHROME_READY_TRIES': '3',
        'TWITTER_FLCLASH_ENSURE': '0',        # 默认隔离 FlClash; 专项用例显式打开
    })
    env.update({k: str(v) for k, v in extra.items()})
    return env


def run_cron(sandbox, env, args=(), timeout=60):
    return subprocess.run(['bash', str(sandbox['cron']), *args], env=env,
                          capture_output=True, text=True, timeout=timeout)


def _seed_flclash_running(sandbox):
    """预置「FlClash 已在运行」: 拉起假代理进程 + 运行态/就绪标记。"""
    # 必须断开 stdout/stderr: 否则假代理会一直持有 cron 的管道, run_cron 读不到 EOF 直到超时
    proc = subprocess.Popen(['/bin/sleep', '211'], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    (sandbox['state'] / 'flclash.pid').write_text(f'{proc.pid}\n', encoding='utf-8')
    (sandbox['state'] / 'flclash.running').write_text('', encoding='utf-8')
    (sandbox['state'] / 'flclash.ready').write_text('', encoding='utf-8')
    return proc


def _write_twitter_json(sandbox, age_hours):
    """写一份 generated_at = now - age_hours 的 twitter.json (节流判定输入)。"""
    d = sandbox['root'] / 'data'
    d.mkdir(exist_ok=True)
    ts = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=age_hours)
    (d / 'twitter.json').write_text(
        json.dumps({'generated_at': ts.strftime('%Y-%m-%dT%H:%M:%SZ'), 'targets': []}),
        encoding='utf-8')


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


def test_release_ignores_bystander_mentioning_port(sandbox):
    """收尾只关 Chrome 实例: 仅"提到"端口的旁观进程 (监视脚本/巡检命令) 不得被误杀。"""
    bystander = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(45)',
                                  f'--remote-debugging-port={PORT}'])
    try:
        time.sleep(0.5)
        assert bystander.poll() is None
        r = run_cron(sandbox, env_for(sandbox))
        out = r.stdout + r.stderr
        assert r.returncode == 0, out
        assert bystander.poll() is None, '旁观进程被误杀'
        assert _pids() == [], f'采集后仍残留: {_pids()}'
    finally:
        bystander.kill()
        bystander.wait(timeout=10)


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
    for knob in ('TWITTER_FLCLASH_ENSURE', 'TWITTER_THROTTLE_HOURS', 'twitter_age_hours'):
        assert knob in src, f'缺能力开关/函数: {knob}'
    # FlClash 唯一真源: 本脚本只编排, 不得自持探测/起停逻辑 (口径漂移的根源)
    # 只查"命令位"行: 注释与 echo 文案里提到命令名是允许的 (提示信息)
    code = '\n'.join(l for l in src.splitlines()
                     if not l.lstrip().startswith('#') and 'echo' not in l)
    assert 'flclash_proxy.py' in code, 'FlClash 逻辑须走唯一真源'
    # 字面量拼写: 让本文件自身不出现旧口径字符串 (验收 grep 口径干净), 但仍然拦得住
    legacy_token = 'pgrep -f ' + 'FlClash'
    for forbidden in ('pgrep -x FlClash', legacy_token, 'nc -z', 'osascript', 'open -a FlClash'):
        assert forbidden not in code, f'须只存在于唯一真源, 本脚本命令位出现: {forbidden}'
    r = subprocess.run(['bash', '-n', str(CRON_SH)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ===== FlClash 代理生命周期 (§3 FlClash 起停; 唯一真源 = scripts/flclash_proxy.py) =====
# shell 侧只编排: 由 argv.log 断言它把正确的子命令/阈值交给了真源, 逻辑本身在 tests/test_flclash_proxy.py。

def test_flclash_started_then_released(sandbox):
    """原本没运行: helper ensure (拉起 + 等 7890 LISTEN) → 采集后 helper release。"""
    env = env_for(sandbox, TWITTER_FLCLASH_ENSURE='1')
    r = run_cron(sandbox, env)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert 'FlClash 未运行, 启动' in out
    assert 'FlClash 就绪 (7890 LISTEN), 采集后释放' in out
    assert '✅ FlClash 已释放' in out
    calls = flclash_calls(sandbox)
    assert 'is-running' in calls, calls
    assert 'ensure --timeout 180 --port 7890' in calls, calls   # 默认值 = policy 口径
    assert 'release --grace 20' in calls, calls
    assert not (sandbox['state'] / 'flclash.running').exists(), '运行态标记未清'
    assert _pids() == []


def test_flclash_kept_if_already_running(sandbox):
    """原本就在运行: 只探测, 不由本脚本拉起/释放 (不调 ensure/release)。"""
    proc = _seed_flclash_running(sandbox)
    try:
        env = env_for(sandbox, TWITTER_FLCLASH_ENSURE='1')
        r = run_cron(sandbox, env)
        out = r.stdout + r.stderr
        assert r.returncode == 0, out
        assert 'FlClash 已在运行' in out and '⇒ 采集后保持运行' in out
        assert '启动 (open -a FlClash' not in out
        assert '释放 FlClash' not in out
        calls = flclash_calls(sandbox)
        assert 'is-running' in calls and 'pids' in calls, calls   # 只为把 pid 写进日志
        assert not [c for c in calls if c.startswith(('ensure', 'release'))], calls
        assert (sandbox['state'] / 'flclash.running').exists(), '不该动外部实例'
        assert proc.poll() is None, '外部 FlClash 被误杀'
    finally:
        proc.kill()
        proc.wait(timeout=10)


def test_flclash_release_failure_warns(sandbox):
    """本脚本拉起的 FlClash 释放失败(优雅退出+兜底均未杀成) → 只告警, 不改采集结果。"""
    (sandbox['state'] / 'flclash.ignore_quit').write_text('1', encoding='utf-8')
    env = env_for(sandbox, TWITTER_FLCLASH_ENSURE='1')
    r = run_cron(sandbox, env)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert 'ensure --timeout 180 --port 7890' in flclash_calls(sandbox)
    assert 'release --grace 20' in flclash_calls(sandbox)
    assert '仍在运行' in out
    assert '✅ FlClash 已释放' not in out
    assert '[stub-collector] run' in out, '释放失败不得影响采集结果'


def test_flclash_start_not_ready_exits_1(sandbox):
    """helper ensure 报未就绪 → exit 1, 且不进入采集 (不拉起 Chrome)。"""
    (sandbox['state'] / 'flclash.no_ready').write_text('1', encoding='utf-8')
    env = env_for(sandbox, TWITTER_FLCLASH_ENSURE='1', TWITTER_FLCLASH_READY_TIMEOUT='2')
    r = run_cron(sandbox, env)
    out = r.stdout + r.stderr
    assert r.returncode == 1, out
    assert '未 LISTEN, 无法访问 X' in out
    assert 'ensure --timeout 2 --port 7890' in flclash_calls(sandbox)
    assert '[stub-collector] run' not in out
    assert _pids() == []


def test_flclash_ensure_disabled_keeps_legacy_behavior(sandbox):
    """TWITTER_FLCLASH_ENSURE=0: 不碰代理 (一次 helper 都不调), 直接采集。"""
    env = env_for(sandbox, TWITTER_FLCLASH_ENSURE='0')
    r = run_cron(sandbox, env)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert '不管理 FlClash 生命周期' in out
    assert 'FlClash 未运行, 启动' not in out
    assert flclash_calls(sandbox) == [], flclash_calls(sandbox)


# ===== 节流 (§0 数据新鲜度, 支撑 cron 每小时尝试) =====

def test_throttle_skips_when_fresh(sandbox):
    """数据 < 阈值: 跳过采集, 不拉起 Chrome / 不动 FlClash。"""
    _write_twitter_json(sandbox, age_hours=1)
    env = env_for(sandbox, TWITTER_THROTTLE_HOURS='5')
    r = run_cron(sandbox, env)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert '跳过: twitter.json 生成于' in out
    assert '[stub-collector] run' not in out
    assert _pids() == []


def test_throttle_runs_when_stale(sandbox):
    """数据 ≥ 阈值: 正常采集。"""
    _write_twitter_json(sandbox, age_hours=10)
    env = env_for(sandbox, TWITTER_THROTTLE_HOURS='5')
    r = run_cron(sandbox, env)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert '距上次采集 10' in out and '执行采集' in out
    assert '[stub-collector] run' in out


def test_force_bypasses_throttle(sandbox):
    """--force: 数据新鲜也照样采集 (手动补采用)。"""
    _write_twitter_json(sandbox, age_hours=1)
    env = env_for(sandbox, TWITTER_THROTTLE_HOURS='5')
    r = run_cron(sandbox, env, args=('--force',))
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert '跳过' not in out
    assert '[stub-collector] run' in out


def test_throttle_disabled_when_zero(sandbox):
    """TWITTER_THROTTLE_HOURS=0: 关闭节流, 每轮都采集。"""
    _write_twitter_json(sandbox, age_hours=0.1)
    env = env_for(sandbox, TWITTER_THROTTLE_HOURS='0')
    r = run_cron(sandbox, env)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out
    assert '[stub-collector] run' in out
