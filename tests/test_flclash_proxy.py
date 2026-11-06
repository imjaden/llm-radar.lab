"""scripts/flclash_proxy.py (FlClash 生命周期唯一真源) 单元测试。

覆盖:
- 探测口径: 精确名 ∪ 应用路径双判据 (合并去重) / 非 Darwin 恒 True / 探测异常 → False
- **判别力反例**: 命令行含 `osascript -e 'quit app "FlClash"'` 的进程
  ⇒ 新口径不命中, 而修复前的单一 `-f FlClash` 会命中 (用例内含旧口径对照断言, 保证它不是空护栏)
- ensure_ready: 已在运行 → 零动作复用; 未运行 → 拉起 + 等端口 LISTEN; 超时 → not_ready
- release: 优雅退出成功 / 超时 kill -TERM 兜底 / 未运行空操作
- notify: 非 Darwin 不动作; 失败静默
- CLI 子命令契约 (退出码) + 阈值/命令与声明层 policy 对齐 (本机有 script-miner 时才跑)
"""
import importlib.util
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HELPER = PROJECT_ROOT / 'scripts' / 'flclash_proxy.py'
POLICY = (Path.home() / 'CodeSpace' / 'script-miner' / 'projects' / 'macosx'
          / 'macosx-service-policy.json')


def load_module():
    spec = importlib.util.spec_from_file_location('flclash_proxy_under_test', HELPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Recorder:
    """替身 _run: 记录 argv, 按 ' '.join(argv)' 返回预设 (rc, stdout)。"""

    def __init__(self, outputs=None, default_rc=1):
        self.calls = []
        self.outputs = outputs or {}
        self.default_rc = default_rc

    def __call__(self, argv, timeout=30):
        argv = list(argv)
        self.calls.append(argv)
        rc, out = self.outputs.get(' '.join(argv), (self.default_rc, ''))
        return subprocess.CompletedProcess(argv, rc, out, '')

    def issued(self, joined):
        return [c for c in self.calls if ' '.join(c) == joined]


@pytest.fixture
def fp(monkeypatch):
    """被测真源 + _run 记录器 (默认 rc=1 无输出 = 探测不到)。"""
    mod = load_module()
    rec = Recorder()
    monkeypatch.setattr(mod, '_run', rec)
    mod.rec = rec
    return mod


@pytest.fixture
def fpreal():
    """不带替身的真源 (用于需要真实 pgrep 的判别力用例)。"""
    return load_module()


def _wait_visible(pid, timeout=5.0):
    """等 pgrep 能看到该 pid (进程创建到 argv 可见有极小延迟)。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = subprocess.run(['pgrep', '-f', 'FlClash'], capture_output=True, text=True)
        if str(pid) in r.stdout.split():
            return True
        time.sleep(0.1)
    return False


# ===== 探测口径 =====

def test_pids_union_of_two_judgements_deduped(fp):
    """双判据: 精确名 ∪ 应用路径, 且去重排序。"""
    fp.rec.outputs = {
        'pgrep -x FlClash': (0, '111\n'),
        'pgrep -f /Applications/FlClash.app': (0, '111\n222\n'),
    }
    assert fp.flclash_pids() == [111, 222]
    assert [c for c in fp.rec.calls] == [
        ['pgrep', '-x', 'FlClash'],
        ['pgrep', '-f', '/Applications/FlClash.app'],
    ]


def test_pids_empty_when_no_match(fp):
    assert fp.flclash_pids() == []


def test_probe_exception_returns_false(fp, monkeypatch):
    """探测异常 → False (fail-closed, 保留既有语义)。"""
    monkeypatch.setattr(fp, '_is_darwin', lambda: True)

    def boom():
        raise OSError('pgrep 炸了')

    monkeypatch.setattr(fp, 'flclash_pids', boom)
    assert fp.is_running() is False


def test_is_running_follows_probe(fp, monkeypatch):
    monkeypatch.setattr(fp, '_is_darwin', lambda: True)
    monkeypatch.setattr(fp, 'flclash_pids', lambda: [])
    assert fp.is_running() is False
    monkeypatch.setattr(fp, 'flclash_pids', lambda: [1234])
    assert fp.is_running() is True


def test_non_darwin_is_running_true(fp, monkeypatch):
    """非 macOS 恒 True (跳过探测) —— 既有语义, 勿改。"""
    monkeypatch.setattr(fp, '_is_darwin', lambda: False)
    assert fp.is_running() is True


def test_counterexample_osascript_shaped_process_not_matched(fpreal):
    """判别力反例: 命令行含 `osascript -e 'quit app "FlClash"'` 的进程不算 FlClash 在跑。

    修复前口径 = 单一 `pgrep -f` + 应用名, 会被这类进程(以及 osascript 自命中)骗到 ⇒
    下面的旧口径对照断言必须为真, 否则本用例没有判别力 (等于空护栏)。
    """
    proc = subprocess.Popen(
        [sys.executable, '-c', 'import time; time.sleep(60)',
         'osascript', '-e', 'quit app "FlClash"'])
    try:
        assert _wait_visible(proc.pid), '反例进程未出现在 pgrep 视野内'
        legacy = subprocess.run(['pgrep', '-f', 'FlClash'], capture_output=True, text=True)
        assert str(proc.pid) in legacy.stdout.split(), \
            '反例进程须能被旧口径命中 (证明用例有判别力)'
        assert proc.pid not in fpreal.flclash_pids(), \
            '仅"提到 FlClash 的应用名"的进程被误判为 FlClash 在跑'
    finally:
        proc.kill()
        proc.wait(timeout=10)


# ===== ensure_ready =====

def test_ensure_ready_skips_when_already_running(fp, monkeypatch):
    """已在运行且端口通 → 零动作复用 (不动外部实例)。"""
    monkeypatch.setattr(fp, '_is_darwin', lambda: True)
    monkeypatch.setattr(fp, 'is_running', lambda: True)
    monkeypatch.setattr(fp, 'is_port_listening', lambda port=fp.READY_PORT: True)
    monkeypatch.setattr(fp, 'flclash_pids', lambda: [42])
    res = fp.ensure_ready()
    assert res == {'ok': True, 'started': False, 'reason': 'already_running', 'pids': [42]}
    assert fp.rec.calls == [], '已在运行却发了动作命令'


def test_ensure_ready_running_but_port_closed_is_not_ready(fp, monkeypatch):
    """Q-1: 进程在但端口不通 ⇒ 短预算等待后判 not_ready (reason=port_closed), 且不重复拉起。"""
    monkeypatch.setattr(fp, '_is_darwin', lambda: True)
    monkeypatch.setattr(fp, 'is_running', lambda: True)
    monkeypatch.setattr(fp, 'is_port_listening', lambda port=fp.READY_PORT: False)
    monkeypatch.setattr(fp, 'flclash_pids', lambda: [42])
    monkeypatch.setattr(fp, 'POLL_INTERVAL', 0.01)
    res = fp.ensure_ready(running_grace=0.05)
    assert res['ok'] is False and res['reason'] == 'port_closed'
    assert res['started'] is False and res['pids'] == [42]
    assert fp.rec.calls == [], f'端口不通时不得再发 open (会变成两个实例): {fp.rec.calls}'


def test_ensure_ready_starts_and_waits_for_port(fp, monkeypatch):
    monkeypatch.setattr(fp, '_is_darwin', lambda: True)
    monkeypatch.setattr(fp, 'is_running', lambda: False)
    monkeypatch.setattr(fp, 'is_port_listening', lambda port=fp.READY_PORT: True)
    monkeypatch.setattr(fp, 'flclash_pids', lambda: [7])
    res = fp.ensure_ready(timeout=1, port=fp.READY_PORT)
    assert res['ok'] is True and res['started'] is True and res['reason'] == 'started'
    assert fp.rec.issued('open -g -a FlClash'), '未发出启动命令 (CL151 要求 -g 不抢焦点)'


def test_ensure_ready_times_out_when_port_never_listens(fp, monkeypatch):
    monkeypatch.setattr(fp, '_is_darwin', lambda: True)
    monkeypatch.setattr(fp, 'is_running', lambda: False)
    monkeypatch.setattr(fp, 'is_port_listening', lambda port=fp.READY_PORT: False)
    monkeypatch.setattr(fp, 'flclash_pids', lambda: [])
    monkeypatch.setattr(fp, 'POLL_INTERVAL', 0.01)
    res = fp.ensure_ready(timeout=0.05)
    assert res['ok'] is False and res['reason'] == 'not_ready'
    assert res['port'] == fp.READY_PORT


def test_ensure_ready_non_darwin_noop(fp, monkeypatch):
    monkeypatch.setattr(fp, '_is_darwin', lambda: False)
    res = fp.ensure_ready()
    assert res['ok'] is True and res['reason'] == 'non_darwin'
    assert fp.rec.calls == []


# ===== release =====

def test_release_graceful_quit(fp, monkeypatch):
    """优雅退出成功: 发 osascript quit, 无需 kill。"""
    monkeypatch.setattr(fp, '_is_darwin', lambda: True)
    seq = iter([True, False])
    monkeypatch.setattr(fp, 'is_running', lambda: next(seq, False))
    monkeypatch.setattr(fp, 'flclash_pids', lambda: [])
    res = fp.release(grace=0)
    assert res['ok'] is True and res['force_kill_issued'] is False
    assert fp.rec.issued('osascript -e quit app "FlClash"'), fp.rec.calls


def test_release_force_kill_fallback(fp, monkeypatch):
    """优雅退出超时 → kill -TERM {pid} 兜底; 仍在运行则 ok=False。"""
    monkeypatch.setattr(fp, '_is_darwin', lambda: True)
    monkeypatch.setattr(fp, 'is_running', lambda: True)
    monkeypatch.setattr(fp, 'flclash_pids', lambda: [4242])
    monkeypatch.setattr(fp, 'TERM_WAIT', 0)
    res = fp.release(grace=0)
    assert res['ok'] is False and res['force_kill_issued'] is True
    assert res['reason'] == 'still_running' and res['pids'] == [4242]
    assert fp.rec.issued('kill -TERM 4242'), fp.rec.calls


def test_release_noop_when_not_running(fp, monkeypatch):
    monkeypatch.setattr(fp, '_is_darwin', lambda: True)
    monkeypatch.setattr(fp, 'is_running', lambda: False)
    res = fp.release()
    assert res == {'ok': True, 'stopped': False, 'reason': 'not_running'}
    assert fp.rec.calls == []


# ===== 通知面: CL151 R3 —— 采集侧不得反向发 FlClash 通知 =====

def test_no_notify_surface_left(fp):
    """CL151 R3 钉子: 模块不得再暴露任何通知入口（历史 `notify` 子命令已删）。
    「代理未就绪」是跳过, 不是异常; FlClash 侧只有 daily-checker 的「超时重启」一条通知。
    """
    assert not hasattr(fp, 'notify_required'), 'notify_required 残留'
    assert not hasattr(fp, 'NOTIFY_CMD'), 'NOTIFY_CMD 残留（可被误触发）'
    r = subprocess.run([sys.executable, str(HELPER), 'notify'], capture_output=True, text=True)
    assert r.returncode != 0, '`notify` 子命令仍可用: ' + r.stdout + r.stderr
    src = HELPER.read_text(encoding='utf-8')
    assert 'display notification' not in src, '源码里仍有本地通知文案'


# ===== CLI 契约 =====

def test_cli_is_running_matches_pgrep_truth():
    """CLI is-running 的结论必须与 `pgrep -x FlClash` 一致 (跨入口同结论)。"""
    r = subprocess.run([sys.executable, str(HELPER), 'is-running'], capture_output=True, text=True)
    truth = subprocess.run(['pgrep', '-x', 'FlClash'], capture_output=True, text=True).returncode == 0
    assert (r.returncode == 0) is truth, r.stdout + r.stderr


def test_cli_pids_and_help_contract():
    r = subprocess.run([sys.executable, str(HELPER), 'pids'], capture_output=True, text=True)
    assert r.returncode == 0
    assert all(tok.isdigit() for tok in r.stdout.split())
    h = subprocess.run([sys.executable, str(HELPER), '--help'], capture_output=True, text=True)
    assert h.returncode == 0
    for cmd in ('is-running', 'pids', 'ensure', 'release'):
        assert cmd in h.stdout
    assert 'notify' not in h.stdout, 'CL151 R3: 不得再有 notify 子命令'


# ===== 与声明层真源对齐 =====

def test_entry_points_delegate_to_helper():
    """两个 python 入口的探测必须与真源同结论 (跨入口一致, 防止再次漂移)。"""
    helper = load_module()
    for path in (PROJECT_ROOT / 'llm-radar-collector.py',
                 PROJECT_ROOT / 'scripts' / 'twitter-collector.py'):
        spec = importlib.util.spec_from_file_location(f'entry_{path.stem.replace("-", "_")}', path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        assert mod._is_flclash_running() == helper.is_running(), f'{path.name} 与真源结论不一致'


@pytest.mark.skipif(not POLICY.exists(), reason='跨项目声明层真源不在本机 (CI 等)')
def test_commands_and_thresholds_match_declaration_policy(fpreal):
    """helper 的命令与阈值必须与 macosx-service-policy.json 的 FlClash.restart 一致 (只读对照)。"""
    svc = next(s for s in json.loads(POLICY.read_text(encoding='utf-8'))['services']
               if s['name'] == 'FlClash')
    restart = svc['restart']

    def seconds(text):
        return float(str(text).rstrip('s'))

    # 上游 policy 与 CL151 口径一致 = `open -g -a FlClash`; 本仓曾漏 `-g`(已对齐), 此断言防再次漂移
    assert fpreal.START_CMD == tuple(shlex.split(restart['start'])), fpreal.START_CMD
    assert '-g' in fpreal.START_CMD
    assert fpreal.STOP_CMD == tuple(shlex.split(restart['stop']))
    assert fpreal.READY_PORT == int(restart['verify']['ports'][0])
    assert fpreal.READY_TIMEOUT == seconds(restart['verify']['wait'])
    assert fpreal.STOP_GRACE == seconds(restart['grace'])
    assert str(restart['force_fallback']).split()[0] == 'kill'
    assert restart['force_fallback'].split()[1:2] == ['-TERM']
    assert svc['match']['path'] == fpreal.APP_PATH


def test_running_port_grace_is_declared_and_bounded(fpreal):
    """Q-1 短预算: 本仓自定 (上游 policy 无对应项) ⇒ 锁区间, 防被误改回 0 或拉长。

    - `>0`: 0 = 取消等待, 与「刚 open 完端口还没起」的窗口冲突（旧短路只是不探, 0 则是探一次就判死）;
    - `>= 3×POLL_INTERVAL`: 至少 3 次探测, 否则等于只探一次;
    - `< READY_TIMEOUT/4`: 一轮采集不得为「代理暂停」多等 ≥45s（180s 预算是「要拉起」分支的冷启动用）。
    """
    grace = fpreal.RUNNING_PORT_GRACE
    assert grace > 0, grace
    assert grace >= fpreal.POLL_INTERVAL * 3, (grace, fpreal.POLL_INTERVAL)
    assert grace < fpreal.READY_TIMEOUT / 4, (grace, fpreal.READY_TIMEOUT)


# ===== x.com 可达性门 (probe_url / ensure_for_url, 2026-11-04) =====

class _Resp:
    def __init__(self, status=200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def reach(monkeypatch, fp):
    """把 probe_url 换成脚本化序列: 传入若干 dict, 依次返回。"""
    def install(seq, proxy_seq=None):
        """脚本化 probe_url; 经代理的那次单独用 proxy_seq（默认与 seq 同源、但强制失败）。"""
        calls = []

        def fake(url=None, timeout=None, proxy=None):
            calls.append({'url': url or fp.REACH_URL, 'timeout': timeout, 'proxy': proxy})
            if proxy:
                item = (proxy_seq or [{'ok': False, 'class': 'timeout'}])[0]
            else:
                item = seq[min(sum(1 for c in calls if not c['proxy']) - 1, len(seq) - 1)]
            d = dict(item)
            d.setdefault('url', url or fp.REACH_URL)
            d.setdefault('elapsed', 0.1)
            d.setdefault('via', 'proxy' if proxy else 'direct')
            d.setdefault('status', 200 if d.get('ok') else None)
            return d
        monkeypatch.setattr(fp, 'probe_url', fake)
        return calls
    return install


def _ok():
    return {'ok': True, 'class': 'http_ok'}


def _fail(cls='timeout'):
    return {'ok': False, 'class': cls, 'detail': 'boom'}


class TestProbeUrl:
    def test_http_error_counts_as_reachable(self, fp, monkeypatch):
        """403/401 也代表链路可达（Cloudflare 挑战常见）——不能判不可达。"""
        def boom(req, timeout=None):
            raise fp.urllib.error.HTTPError(req.full_url, 403, 'Forbidden', {}, None)
        monkeypatch.setattr(fp.urllib.request, 'build_opener',
                            lambda *h: type('O', (), {'open': staticmethod(boom)}))
        r = fp.probe_url('https://x.com/', timeout=1)
        assert (r['ok'], r['class'], r['status']) == (True, 'http_ok', 403)

    @pytest.mark.parametrize('kind,cls', [
        ('timeout', 'timeout'),
        ('dns', 'dns'),
        ('reset', 'connect'),
        ('ssl', 'tls'),
        ('other', 'other'),
    ])
    def test_error_classification(self, fp, monkeypatch, kind, cls):
        exc = {
            'timeout': TimeoutError('timed out'),
            'dns': fp.socket.gaierror(8, 'nodename nor servname provided'),
            'reset': ConnectionResetError('connection reset by peer'),
            'ssl': fp.ssl.SSLError('certificate verify failed'),
            'other': RuntimeError('weird'),
        }[kind]

        def boom(req, timeout=None):
            raise exc
        monkeypatch.setattr(fp.urllib.request, 'build_opener',
                            lambda *h: type('O', (), {'open': staticmethod(boom)}))
        r = fp.probe_url('https://x.com/', timeout=1)
        assert (r['ok'], r['class']) == (False, cls)

    def test_probe_ignores_env_proxy(self, fp, monkeypatch):
        """判的是「直连能不能通」: shell 里有 http_proxy 也不能让它带偏。"""
        seen = {}

        def fake_build(*handlers):
            seen['proxies'] = handlers[0].proxies if handlers else None
            return type('O', (), {'open': staticmethod(lambda req, timeout=None: _Resp(200))})
        monkeypatch.setattr(fp.urllib.request, 'build_opener', fake_build)
        monkeypatch.setenv('https_proxy', 'http://127.0.0.1:7890')
        assert fp.probe_url('https://x.com/', timeout=1)['ok'] is True
        assert seen['proxies'] == {}


class TestEnsureForUrl:
    def _ensure_recorder(self, fp, monkeypatch, result):
        calls = []
        monkeypatch.setattr(fp, 'ensure_ready', lambda **kw: calls.append(kw) or result)
        return calls

    def test_direct_ok_never_touches_flclash(self, fp, monkeypatch, reach):
        """核心护栏: 直连可达 ⇒ 绝不起代理（VPN/TUN 场景）。"""
        reach([_ok()])
        monkeypatch.setattr(fp, 'ensure_ready',
                            lambda **kw: (_ for _ in ()).throw(AssertionError('不得调用 ensure_ready')))
        res = fp.ensure_for_url('https://x.com/', settle=0)
        assert (res['ok'], res['state'], res['started']) == (True, 'direct_ok', False)

    def test_slow_direct_success_via_retry(self, fp, monkeypatch, reach):
        calls = reach([_fail('timeout'), _ok()])
        monkeypatch.setattr(fp, 'ensure_ready',
                            lambda **kw: (_ for _ in ()).throw(AssertionError('复探成功就不该起代理')))
        res = fp.ensure_for_url('https://x.com/', probe_timeout=5, retry_timeout=8, settle=0)
        assert res['state'] == 'direct_ok'
        assert [c['timeout'] for c in calls] == [5, 8]

    def test_starts_proxy_then_reachable(self, fp, monkeypatch, reach):
        calls = reach([_fail(), _ok()])
        # 端口设为未监听 ⇒ 复探走 prefer='proxy' 的直连兜底分支, 序列可预测
        monkeypatch.setattr(fp, 'is_port_listening', lambda *a, **k: False)
        ens = self._ensure_recorder(fp, monkeypatch, {'ok': True, 'started': True, 'reason': 'started'})
        res = fp.ensure_for_url('https://x.com/', settle=0)
        assert (res['ok'], res['state'], res['started']) == (True, 'proxy_started', True)
        assert len(ens) == 1
        assert [c['proxy'] for c in calls] == [None, None]

    def test_already_running_proxy_is_not_claimed(self, fp, monkeypatch, reach):
        reach([_fail(), _ok()])
        self._ensure_recorder(fp, monkeypatch, {'ok': True, 'started': False, 'reason': 'already_running'})
        res = fp.ensure_for_url('https://x.com/', settle=0)
        assert (res['state'], res['started']) == ('proxy_ok', False)

    def test_port_closed_is_reported_distinctly(self, fp, monkeypatch, reach):
        reach([_fail('connect'), _fail('connect')])
        self._ensure_recorder(fp, monkeypatch, {'ok': False, 'started': False, 'reason': 'port_closed'})
        res = fp.ensure_for_url('https://x.com/', settle=0)
        assert (res['ok'], res['state']) == (False, 'port_closed')

    def test_proxy_up_but_upstream_dead_is_unreachable(self, fp, monkeypatch, reach):
        reach([_fail(), _fail('timeout')])
        self._ensure_recorder(fp, monkeypatch, {'ok': True, 'started': True, 'reason': 'started'})
        res = fp.ensure_for_url('https://x.com/', settle=0)
        assert (res['ok'], res['state']) == (False, 'unreachable')

    def test_ensure_disabled_only_probes(self, fp, monkeypatch, reach):
        calls = reach([_fail('timeout')])
        monkeypatch.setattr(fp, 'ensure_ready',
                            lambda **kw: (_ for _ in ()).throw(AssertionError('--no-ensure 不得拉起')))
        res = fp.ensure_for_url('https://x.com/', ensure=False, retry_timeout=None, settle=0)
        assert (res['ok'], res['state'], res['started']) == (False, 'ensure_disabled', False)
        assert len(calls) == 1

    def test_cli_reach_exit_codes(self, fp, monkeypatch, capsys):
        monkeypatch.setattr(fp, 'ensure_for_url', lambda *a, **k: {
            'ok': True, 'state': 'direct_ok', 'started': False, 'probe': {'class': 'http_ok', 'elapsed': 0.1}})
        assert fp.main(['reach']) == 0
        assert capsys.readouterr().out.strip() == 'direct_ok'
        monkeypatch.setattr(fp, 'ensure_for_url', lambda *a, **k: {
            'ok': False, 'state': 'port_closed', 'started': False, 'probe': {'class': 'connect', 'elapsed': 0.1}})
        assert fp.main(['reach']) == 1
        assert 'port_closed' in capsys.readouterr().out


class TestProbeBest:
    """复探语义: 「直连不通 + 代理通」必须判可达（FlClash 多为系统代理模式）。"""

    def test_direct_ok_short_circuits(self, fp, monkeypatch, reach):
        """直连可达时不得再走代理（多探一次会掩盖「直连其实通」这个事实）。"""
        calls = reach([_ok()])
        monkeypatch.setattr(fp, 'is_port_listening', lambda *a, **k: True)
        r = fp.probe_best('https://x.com/', timeout=1)
        assert r['ok'] and r['via'] == 'direct'
        assert len(calls) == 1 and all(c['proxy'] is None for c in calls)

    def test_falls_back_to_proxy_when_port_listening(self, fp, monkeypatch):
        seen = []

        def fake_probe(url=None, timeout=None, proxy=None):
            seen.append(proxy)
            ok = proxy is not None
            return {'ok': ok, 'class': 'http_ok' if ok else 'timeout', 'via': 'proxy' if proxy else 'direct',
                    'elapsed': 0.1, 'status': 200 if ok else None, 'detail': ''}
        monkeypatch.setattr(fp, 'probe_url', fake_probe)
        monkeypatch.setattr(fp, 'is_port_listening', lambda *a, **k: True)
        r = fp.probe_best('https://x.com/', timeout=1)
        assert r['ok'] and r['via'] == 'proxy'
        assert seen == [None, 'http://127.0.0.1:7890']

    def test_port_closed_returns_direct_failure(self, fp, monkeypatch):
        monkeypatch.setattr(fp, 'probe_url', lambda url=None, timeout=None, proxy=None: {
            'ok': False, 'class': 'timeout', 'via': 'direct', 'elapsed': 0.1, 'detail': ''})
        monkeypatch.setattr(fp, 'is_port_listening', lambda *a, **k: False)
        r = fp.probe_best('https://x.com/', timeout=1)
        assert r['ok'] is False and r['via'] == 'direct'

    def test_environment_proxy_is_ignored_for_direct_probe(self, fp, monkeypatch):
        """direct 探测必须显式清空环境代理（否则 shell 里带 http_proxy 就永远判通）。"""
        seen = {}

        def fake_build(*handlers):
            seen['proxies'] = handlers[0].proxies
            return type('O', (), {'open': staticmethod(lambda req, timeout=None: _Resp(200))})
        monkeypatch.setattr(fp.urllib.request, 'build_opener', fake_build)
        monkeypatch.setenv('http_proxy', 'http://127.0.0.1:7890')
        fp.probe_url('https://x.com/', timeout=1)
        assert seen['proxies'] == {}
