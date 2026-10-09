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
    """已在运行 → 零动作复用 (不动外部实例)。"""
    monkeypatch.setattr(fp, '_is_darwin', lambda: True)
    monkeypatch.setattr(fp, 'is_running', lambda: True)
    monkeypatch.setattr(fp, 'flclash_pids', lambda: [42])
    res = fp.ensure_ready()
    assert res == {'ok': True, 'started': False, 'reason': 'already_running', 'pids': [42]}
    assert fp.rec.calls == [], '已在运行却发了动作命令'


def test_ensure_ready_starts_and_waits_for_port(fp, monkeypatch):
    monkeypatch.setattr(fp, '_is_darwin', lambda: True)
    monkeypatch.setattr(fp, 'is_running', lambda: False)
    monkeypatch.setattr(fp, 'is_port_listening', lambda port=fp.READY_PORT: True)
    monkeypatch.setattr(fp, 'flclash_pids', lambda: [7])
    res = fp.ensure_ready(timeout=1, port=fp.READY_PORT)
    assert res['ok'] is True and res['started'] is True and res['reason'] == 'started'
    assert fp.rec.issued('open -a FlClash'), '未发出启动命令'


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


# ===== notify =====

def test_notify_non_darwin_and_failure_silent(fp, monkeypatch):
    monkeypatch.setattr(fp, '_is_darwin', lambda: False)
    assert fp.notify_required() is False
    monkeypatch.setattr(fp, '_is_darwin', lambda: True)

    def boom(argv, timeout=30):
        raise OSError('osascript 不可用')

    monkeypatch.setattr(fp, '_run', boom)
    assert fp.notify_required() is False, '通知失败必须静默 (best-effort)'


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
    for cmd in ('is-running', 'pids', 'ensure', 'release', 'notify'):
        assert cmd in h.stdout


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

    assert fpreal.START_CMD == tuple(shlex.split(restart['start']))
    assert fpreal.STOP_CMD == tuple(shlex.split(restart['stop']))
    assert fpreal.READY_PORT == int(restart['verify']['ports'][0])
    assert fpreal.READY_TIMEOUT == seconds(restart['verify']['wait'])
    assert fpreal.STOP_GRACE == seconds(restart['grace'])
    assert str(restart['force_fallback']).split()[0] == 'kill'
    assert restart['force_fallback'].split()[1:2] == ['-TERM']
    assert svc['match']['path'] == fpreal.APP_PATH
