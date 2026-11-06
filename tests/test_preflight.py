"""preflight 钉子: 配置面自检的判据、判别力与「永不假 OK」。

覆盖 2026-11-02~11-04 的 401 事件形态: key 失效必须落在 key_auth=fail（带换 key 指令），
不依赖「数据是否陈旧」这种滞后信号。全部用例零网络：_http_json / 端口探测 / 驱动查询均替身。
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / 'scripts' / 'llm-radar-preflight.py'


@pytest.fixture
def pf():
    spec = importlib.util.spec_from_file_location('llm_radar_preflight', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def no_key(monkeypatch):
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    monkeypatch.delenv('LLM_RADAR_MCP_KEY', raising=False)


@pytest.fixture
def with_key(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'sk-unit-test')


class TestKeyAuth:
    def test_no_key_is_fail_with_env_hint(self, pf, no_key):
        r = pf.check_key_auth({})
        assert (r['status'], r['value']) == ('fail', 'no key')
        assert '.env' in r['remedy']

    def test_401_is_fail_auth_with_rekey_remedy(self, pf, with_key, monkeypatch):
        monkeypatch.setattr(pf, '_http_json', lambda *a, **k: (
            401, {'error': {'message': 'Authentication Fails, Your api key: ****3f06 is invalid'}}))
        r = pf.check_key_auth({})
        assert (r['status'], r['value']) == ('fail', 'auth 401')
        assert '换 key' in r['remedy']
        # 根因原文可读, 但不含完整 key
        assert '****3f06' in r['detail']

    def test_200_ok_and_populates_catalog(self, pf, with_key, monkeypatch):
        monkeypatch.setattr(pf, '_http_json', lambda *a, **k: (
            200, {'data': [{'id': 'deepseek-flash'}, {'id': 'deepseek-v4-pro'}]}))
        ctx = {}
        r = pf.check_key_auth(ctx)
        assert (r['status'], r['value']) == ('ok', 'ok')
        assert ctx['catalog'] == ['deepseek-flash', 'deepseek-v4-pro']

    def test_quota_is_warn_not_fail(self, pf, with_key, monkeypatch):
        monkeypatch.setattr(pf, '_http_json', lambda *a, **k: (402, {}))
        r = pf.check_key_auth({})
        assert r['status'] == 'warn'
        assert r['value'].startswith('quota')

    def test_unreachable_is_skip_never_ok(self, pf, with_key, monkeypatch):
        monkeypatch.setattr(pf, '_http_json', lambda *a, **k: (None, {'error': 'timeout'}))
        r = pf.check_key_auth({})
        assert r['status'] == 'skip'
        assert 'FlClash' in r['remedy']


class TestModel:
    def test_skipped_without_catalog(self, pf):
        r = pf.check_model({})
        assert r['status'] == 'skip'

    def test_alias_ok_reports_served_model(self, pf, with_key, monkeypatch):
        monkeypatch.setattr(pf, '_http_json', lambda *a, **k: (200, {'model': 'deepseek-flash'}))
        r = pf.check_model({'catalog': ['deepseek-flash']})
        assert (r['status'], r['value']) == ('ok', 'deepseek-flash')

    def test_400_model_is_fail(self, pf, with_key, monkeypatch):
        monkeypatch.setattr(pf, '_http_json', lambda *a, **k: (
            400, {'error': {'message': 'Model Not Exist'}}))
        r = pf.check_model({'catalog': ['deepseek-flash']})
        assert r['status'] == 'fail'
        assert '_call_deepseek' in r['remedy']


class TestXSide:
    def test_cdp_down_fails_both_checks(self, pf, monkeypatch):
        monkeypatch.setattr(pf, '_port_open', lambda *a, **k: False)
        assert pf.check_cdp_page({})['status'] == 'fail'
        mod = type('M', (), {'_chrome_state': staticmethod(lambda p: (False, False, 'CDP 未就绪'))})
        monkeypatch.setattr(pf, '_load_collector', lambda: mod)
        r = pf.check_x_login({})
        assert r['status'] == 'fail'
        assert 'lr chrome --wait' in r['remedy']

    def test_logged_out_fails(self, pf, monkeypatch):
        mod = type('M', (), {'_chrome_state': staticmethod(lambda p: (True, False, '31 个 cookie'))})
        monkeypatch.setattr(pf, '_load_collector', lambda: mod)
        assert pf.check_x_login({})['status'] == 'fail'

    def test_logged_in_ok(self, pf, monkeypatch):
        mod = type('M', (), {'_chrome_state': staticmethod(lambda p: (True, True, '31 个 cookie'))})
        monkeypatch.setattr(pf, '_load_collector', lambda: mod)
        assert pf.check_x_login({})['status'] == 'ok'

    def test_no_page_target_is_fail(self, pf, monkeypatch):
        monkeypatch.setattr(pf, '_port_open', lambda *a, **k: True)
        monkeypatch.setattr(pf, '_http_json', lambda *a, **k: (200, [{'type': 'browser_ui'}]))
        r = pf.check_cdp_page({})
        assert (r['status'], r['value']) == ('fail', '0 page')
        assert '/json/new' in r['remedy']


class TestMisc:
    def test_flclash_closed_is_warn(self, pf, monkeypatch):
        monkeypatch.setattr(pf, '_port_open', lambda *a, **k: False)
        assert pf.check_flclash({})['status'] == 'warn'

    def test_mcp_key_absent_is_info_not_fail(self, pf, no_key):
        assert pf.check_mcp_key({})['status'] == 'info'

    def test_df_facts_uses_capacity_column_semantics(self, pf, monkeypatch):
        """pct = used/(used+avail)（= df 的 Capacity 列），不是 used/total。"""
        fake = ("Filesystem 1024-blocks Used Available Capacity iused ifree %iused Mounted on\n"
                "/dev/disk3s5 971298980 520646964 418217056 56% 6262183 4182170560 0% /System/Volumes/Data\n")
        monkeypatch.setattr(pf.subprocess, 'run',
                            lambda *a, **k: type('R', (), {'returncode': 0, 'stdout': fake, 'stderr': ''}))
        f = pf._df_facts('/System/Volumes/Data')
        assert f['mount'] == '/System/Volumes/Data'
        assert round(f['used_gib'], 1) == 496.5
        assert round(f['avail_gib'], 1) == 398.8
        assert round(f['pct'], 1) == 55.5          # 520646964/(520646964+418217056)
        # 判别力: 与 used/total(53.6%) 必须不同, 否则口径改没改都"过"
        assert round(f['pct'], 1) != round(520646964 / 971298980 * 100, 1)

    def test_df_facts_none_when_df_fails(self, pf, monkeypatch):
        monkeypatch.setattr(pf.subprocess, 'run',
                            lambda *a, **k: type('R', (), {'returncode': 2, 'stdout': '', 'stderr': 'x'}))
        assert pf._df_facts('/') is None

    def test_disk_uses_df_not_shutil(self, pf, monkeypatch):
        """判别力: 两个数据源给出不同 pct 时, 必须取 df（shutil 会多算同容器其他卷）。"""
        monkeypatch.setattr(pf, '_df_facts', lambda p: {
            'total_gib': 926.3, 'used_gib': 496.5, 'avail_gib': 398.9, 'pct': 55.5, 'mount': '/System/Volumes/Data'})
        monkeypatch.setattr(pf.shutil, 'disk_usage',
                            lambda *a, **k: (_ for _ in ()).throw(AssertionError('不应走 shutil')))
        r = pf.check_disk({})
        assert (r['status'], r['value']) == ('ok', '55.5%')
        assert '/System/Volumes/Data' in r['detail']

    def test_disk_threshold_fail(self, pf, monkeypatch):
        monkeypatch.setattr(pf, '_df_facts', lambda p: {
            'total_gib': 926.0, 'used_gib': 880.0, 'avail_gib': 46.0, 'pct': 95.0, 'mount': '/data'})
        r = pf.check_disk({})
        assert (r['status'], r['value']) == ('fail', '95.0%')
        assert 'df' in r['remedy']

    def test_disk_falls_back_to_shutil(self, pf, monkeypatch):
        monkeypatch.setattr(pf, '_df_facts', lambda p: None)
        usage = type('U', (), {'total': 100 * 1048576, 'used': 40 * 1048576, 'free': 60 * 1048576})
        monkeypatch.setattr(pf.shutil, 'disk_usage', lambda *a, **k: usage)
        r = pf.check_disk({})
        assert (r['status'], r['value']) == ('ok', '40.0%')
        assert 'shutil' in r['detail']

    def test_driver_uses_stable_compatible_not_verdict(self, pf, monkeypatch):
        """manager verdict=compatible 但稳定路径不兼容 ⇒ 必须 fail（采集器只吃稳定路径）。"""
        boot = type('B', (), {
            'check': staticmethod(lambda **k: {'chrome_version': '156.0.8078.80', 'verdict': 'compatible'}),
            'state_summary': staticmethod(lambda st: {'stable_compatible': False, 'good': ['156.0.8078.47']}),
        })
        real_spec = importlib.util.spec_from_file_location

        def fake_spec(name, path, *a, **k):
            if str(path).endswith('chromedriver_bootstrap.py'):
                return type('S', (), {'loader': type('L', (), {'exec_module': staticmethod(lambda m: None)})})
            return real_spec(name, path, *a, **k)

        monkeypatch.setattr(pf.importlib.util, 'spec_from_file_location', fake_spec)
        monkeypatch.setattr(pf.importlib.util, 'module_from_spec', lambda spec: boot)
        r = pf.check_driver({})
        assert r['status'] == 'fail'


class TestDotenv:
    def test_loads_missing_key_without_overriding(self, pf, tmp_path, monkeypatch):
        env = tmp_path / '.env'
        env.write_text('# comment\nDEEPSEEK_API_KEY="sk-from-dotenv"\nLLM_RADAR_MCP_KEY=keep\n\nBAD LINE\n')
        monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
        monkeypatch.setenv('LLM_RADAR_MCP_KEY', 'already-set')
        pf._load_dotenv(env)
        assert os.environ['DEEPSEEK_API_KEY'] == 'sk-from-dotenv'      # 引号被剥
        assert os.environ['LLM_RADAR_MCP_KEY'] == 'already-set'        # 不覆盖既有

    def test_missing_file_is_noop(self, pf, tmp_path):
        pf._load_dotenv(tmp_path / 'nope.env')   # 不抛


class TestEntry:
    def test_summarize_ok_only_without_fails(self, pf):
        checks = [pf._result('a', 'ok', 'x'), pf._result('b', 'warn', 'y'), pf._result('c', 'skip', 'z')]
        s = pf.summarize(checks)
        assert s == {'ok': True, 'fails': [], 'warns': ['b'], 'skips': ['c']}
        checks.append(pf._result('d', 'fail', 'w'))
        assert pf.summarize(checks)['ok'] is False

    def test_main_always_exits_zero_and_records(self, pf, tmp_path, monkeypatch, no_key):
        monkeypatch.setattr(pf, 'RECORD_DIR', tmp_path)
        monkeypatch.setattr(pf, 'RECORD', tmp_path / 'preflight.log')
        monkeypatch.setattr(pf, 'CACHE_FILE', tmp_path / 'preflight-cache.json')
        monkeypatch.setattr(pf, 'run_checks', lambda only=None: [
            pf._result('key_auth', 'fail', 'auth 401', 'x', '换 key'),
            pf._result('disk', 'ok', '40%'),
        ])
        assert pf.main(['--json', '--record']) == 0   # 有 fail 也 exit 0（no_agent 契约）
        out = (tmp_path / 'preflight.log').read_text().strip()
        assert 'ok=False' in out and 'key_auth=auth 401' in out
        payload = json.loads((tmp_path / 'preflight-cache.json').read_text())
        assert payload['fails'] == ['key_auth']

    def test_text_render_includes_remedy(self, pf):
        text = pf.render_text({'generated_at': 'x', 'ok': False, 'fails': ['key_auth'], 'checks': [
            pf._result('key_auth', 'fail', 'auth 401', 'invalid', '换 key')]})
        assert '修复: 换 key' in text


class TestXReach:
    """x.com 可达性项: 只读探测（preflight 不得拉起代理）。"""

    def test_direct_ok(self, pf, monkeypatch):
        monkeypatch.setattr(pf, '_probe_best', lambda timeout=None: {
            'ok': True, 'class': 'http_ok', 'via': 'direct', 'elapsed': 0.4, 'detail': ''})
        r = pf.check_x_reach({})
        assert (r['status'], r['value']) == ('ok', '直连')
        assert '0.4s' in r['detail']

    def test_via_proxy_is_ok_but_labelled(self, pf, monkeypatch):
        monkeypatch.setattr(pf, '_probe_best', lambda timeout=None: {
            'ok': True, 'class': 'http_ok', 'via': 'proxy', 'elapsed': 0.9, 'detail': ''})
        r = pf.check_x_reach({})
        assert (r['status'], r['value']) == ('ok', '经代理')

    def test_unreachable_is_warn_with_remedy(self, pf, monkeypatch):
        monkeypatch.setattr(pf, '_probe_best', lambda timeout=None: {
            'ok': False, 'class': 'timeout', 'via': 'direct', 'elapsed': 5.0, 'detail': 'boom'})
        r = pf.check_x_reach({})
        assert r['status'] == 'warn'
        assert 'unreachable timeout' in r['value'] and 'flclash_proxy' in r['remedy']

    def test_missing_helper_is_skip_not_ok(self, pf, monkeypatch):
        monkeypatch.setattr(pf, '_probe_best', None)
        assert pf.check_x_reach({})['status'] == 'skip'

    def test_registered_in_check_list(self, pf):
        assert 'x_reach' in pf.CHECK_NAMES
