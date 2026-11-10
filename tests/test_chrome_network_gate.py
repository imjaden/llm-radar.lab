"""`lr chrome` 的 x.com 网络门（2026-11-04）。

背景: 旧实现直接起 Chrome 指向 https://x.com/login, 代理没起时页面空白, 但 `--wait`
仍然白等 600s, 最后只报「超时仍未检测到登录 cookie」——把「没网」误述成「没登录」。

钉子:
  1) 门的文案/状态映射（direct_ok / proxy_ok / proxy_started / port_closed / unreachable / ensure_disabled）
  2) 不可达 ⇒ exit 2 且**不启动 Chrome**、不进入等待（与登录超时 exit 1 区分）
  3) 直连可达 ⇒ 不调用代理（`--no-ensure` 与 env 两条关闭路径都要生效）
  4) `--status` 只探测、零副作用（不得拉起代理）
"""
import pytest

from conftest import import_collector


@pytest.fixture
def mod():
    return import_collector()


def _res(state, *, started=False, cls='timeout', elapsed=0.4, ok=None, detail='boom'):
    probe = {'ok': bool(ok if ok is not None else state in ('direct_ok', 'proxy_ok', 'proxy_started')),
             'class': 'http_ok' if state in ('direct_ok', 'proxy_ok', 'proxy_started') else cls,
             'elapsed': elapsed, 'detail': detail, 'status': 200}
    return {'ok': probe['ok'], 'state': state, 'started': started, 'probe': probe,
            'first_probe': probe, 'ensure': None, 'url': 'https://x.com/robots.txt',
            'elapsed': elapsed + 0.5}


class TestGateFormatting:
    def _gate(self, mod, monkeypatch, res):
        monkeypatch.setattr(mod, '_flclash_ensure_for_url', lambda **kw: res)
        return mod._x_network_gate()

    def test_direct_ok(self, mod, monkeypatch):
        ok, line, _ = self._gate(mod, monkeypatch, _res('direct_ok'))
        assert ok is True and '直连可达' in line

    def test_proxy_started_line_mentions_elapsed(self, mod, monkeypatch):
        ok, line, res = self._gate(mod, monkeypatch, _res('proxy_started', started=True))
        assert ok is True and '已拉起 FlClash' in line and 'x.com 可达' in line
        assert res['started'] is True

    def test_proxy_already_running(self, mod, monkeypatch):
        ok, line, _ = self._gate(mod, monkeypatch, _res('proxy_ok'))
        assert ok is True and '已在运行' in line

    def test_port_closed_is_actionable(self, mod, monkeypatch):
        ok, line, _ = self._gate(mod, monkeypatch, _res('port_closed', cls='connect'))
        assert ok is False and '7890' in line

    def test_unreachable_mentions_class(self, mod, monkeypatch):
        ok, line, _ = self._gate(mod, monkeypatch, _res('unreachable', cls='dns'))
        assert ok is False and 'dns' in line

    def test_ensure_disabled_explains_itself(self, mod, monkeypatch):
        ok, line, _ = self._gate(mod, monkeypatch, _res('ensure_disabled'))
        assert ok is False and '已禁用自动拉起' in line

    def test_probe_exception_never_crashes(self, mod, monkeypatch):
        monkeypatch.setattr(mod, '_flclash_ensure_for_url',
                            lambda **kw: (_ for _ in ()).throw(RuntimeError('boom')))
        ok, line, _ = mod._x_network_gate()
        assert ok is False and '探测异常' in line


class TestCmdChromeGate:
    @pytest.fixture(autouse=True)
    def _stub_page_fallback(self, mod, monkeypatch):
        """page 兜底单列在 tests/test_chrome_page_target.py；本类只测网络门，
        默认桩成「已有页面复用」，否则无 CDP 的用例会因兜底失败拿到 rc=1。"""
        monkeypatch.setattr(mod, '_ensure_page_target',
                            lambda *a, **k: (True, 1, 'reuse'), raising=False)

    def test_unreachable_exits_2_and_does_not_launch(self, mod, monkeypatch, capsys):
        monkeypatch.setattr(mod, '_x_network_gate',
                            lambda **kw: (False, '网络: x.com 不可达 (timeout, 5.0s)', {}))
        monkeypatch.setattr(mod.subprocess, 'Popen',
                            lambda *a, **k: (_ for _ in ()).throw(AssertionError('不得启动 Chrome')))
        rc = mod._cmd_chrome(['--port', '19998'])
        out = capsys.readouterr()
        assert rc == 2
        assert '不进入登录等待' in out.err
        assert '排查:' in out.err

    def test_direct_ok_reuses_instance_and_returns_0(self, mod, monkeypatch):
        monkeypatch.setattr(mod, '_x_network_gate',
                            lambda **kw: (True, '网络: x.com 直连可达 (0.4s)', {'started': False}))
        monkeypatch.setattr(mod, '_cdp_ready', lambda port, timeout=0.6: True)
        assert mod._cmd_chrome(['--port', '19997']) == 0

    def test_started_proxy_is_announced_as_owned(self, mod, monkeypatch, capsys):
        monkeypatch.setattr(mod, '_x_network_gate',
                            lambda **kw: (True, '网络: 直连不通 → 已拉起 FlClash → x.com 可达', {'started': True}))
        monkeypatch.setattr(mod, '_cdp_ready', lambda port, timeout=0.6: True)
        mod._cmd_chrome(['--port', '19996'])
        out = capsys.readouterr().out
        assert '由本次命令拉起（未释放）' in out and 'release' in out

    def test_wait_regates_and_bails_without_600s_wait(self, mod, monkeypatch, capsys):
        calls = []

        def gate(**kw):
            calls.append(kw)
            if len(calls) == 1:
                return True, '网络: x.com 直连可达 (0.4s)', {'started': False}
            return False, '网络: x.com 经代理仍不可达 (timeout, 2.0s)', {}
        monkeypatch.setattr(mod, '_x_network_gate', gate)
        monkeypatch.setattr(mod, '_cdp_ready', lambda port, timeout=0.6: True)
        rc = mod._cmd_chrome(['--wait', '--timeout', '600', '--port', '19995'])
        assert rc == 2, '不可达必须快速失败, 不进 600s 等待'
        assert '等待前复判' in capsys.readouterr().err

    def test_no_ensure_flag_passes_ensure_false(self, mod, monkeypatch):
        seen = {}

        def gate(**kw):
            seen.update(kw)
            return True, '网络: ok', {'started': False}
        monkeypatch.setattr(mod, '_x_network_gate', gate)
        monkeypatch.setattr(mod, '_cdp_ready', lambda port, timeout=0.6: True)
        mod._cmd_chrome(['--no-ensure', '--port', '19994'])
        assert seen['ensure'] is False

    def test_env_disables_ensure(self, mod, monkeypatch):
        seen = {}
        monkeypatch.setenv('TWITTER_PROXY_NO_ENSURE', '1')

        def gate(**kw):
            seen.update(kw)
            return True, '网络: ok', {'started': False}
        monkeypatch.setattr(mod, '_x_network_gate', gate)
        monkeypatch.setattr(mod, '_cdp_ready', lambda port, timeout=0.6: True)
        mod._cmd_chrome(['--port', '19993'])
        assert seen['ensure'] is False


class TestStatusIsZeroSideEffect:
    def test_status_probes_but_never_ensures(self, mod, monkeypatch, capsys):
        monkeypatch.setattr(mod, '_chrome_state', lambda port: (False, False, '0 个 cookie'))
        monkeypatch.setattr(mod, '_x_probe_only', lambda timeout=2.0: {'ok': True, 'class': 'http_ok',
                                                                      'elapsed': 0.3})
        monkeypatch.setattr(mod, '_x_network_gate',
                            lambda **kw: (_ for _ in ()).throw(AssertionError('--status 不得拉起代理')))
        rc = mod._cmd_chrome(['--status', '--port', '19992'])
        out = capsys.readouterr().out
        assert rc == 1
        assert '直连可达' in out

    def test_status_reports_unreachable_without_failing_faster(self, mod, monkeypatch, capsys):
        monkeypatch.setattr(mod, '_chrome_state', lambda port: (True, True, '2 个 cookie'))
        monkeypatch.setattr(mod, '_x_probe_only',
                            lambda timeout=2.0: {'ok': False, 'class': 'timeout', 'elapsed': 2.0})
        rc = mod._cmd_chrome(['--status', '--port', '19991'])
        out = capsys.readouterr().out
        assert rc == 0, 'CDP+登录态正常时退出码不被网络行影响'
        assert 'x.com 不可达 (timeout)' in out
