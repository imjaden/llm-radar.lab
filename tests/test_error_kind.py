"""S1 钉子: LLM 失败分类与 metrics 留痕。

背景: 2026-11-02~11-04 的 DEEPSEEK_API_KEY 401 持续 ~39h，采集器只累加
`consecutive_fails`（6→30），status/告警无法点出「鉴权失败」这一根因。
本文件的判据:
  1) `_classify_llm_error` 把异常映射到稳定类别（401/400/429/超时/其它）；
  2) `_call_deepseek` 失败时落 `_last_error`，且 detail 内不含明文 key；
  3) `_observe` 失败时把 `last_error` 写进 metrics.json，成功时清除；
  4) kind 非法值归一为 other，detail 截断 120 字并去换行。
"""
import json
import sys
import types

import pytest

from conftest import import_collector


class _FakeStatusError(Exception):
    def __init__(self, msg, status_code=None):
        super().__init__(msg)
        if status_code is not None:
            self.status_code = status_code


class _FakeOpenAI:
    """替身: 构造成功, chat.completions.create 抛指定异常。"""

    def __init__(self, exc):
        self._exc = exc
        self.chat = types.SimpleNamespace(
            completions=types.SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        raise self._exc


@pytest.fixture
def quiet_collector():
    mod = import_collector()
    c = mod.LLMRadarCollector()
    c.api_key = 'sk-testkey-0123456789abcdef'
    c._skip_push = True
    for m in ('_print_ok', '_print_err', '_print_info', '_print_warn'):
        setattr(c, m, lambda msg: None)
    return c, mod


@pytest.fixture
def fake_openai(monkeypatch):
    """注入 openai 替身; 返回安装器 (exc) -> None。"""
    def install(exc):
        mod = types.SimpleNamespace(OpenAI=lambda **kw: _FakeOpenAI(exc))
        monkeypatch.setitem(sys.modules, 'openai', mod)
    return install


class TestClassify:
    @pytest.mark.parametrize('exc,kind', [
        (_FakeStatusError('Authentication Fails, Your api key: ****3f06 is invalid', 401), 'auth'),
        (_FakeStatusError('Forbidden', 403), 'auth'),
        (_FakeStatusError('invalid api key', None), 'auth'),
        (_FakeStatusError('Model Not Exist: deepseek-chat', 400), 'model'),
        (_FakeStatusError('Error code: 400 - model_not_found', None), 'model'),
        (_FakeStatusError('Insufficient Balance', 402), 'quota'),
        (_FakeStatusError('rate limit exceeded', 429), 'quota'),
        (_FakeStatusError('HTTPSConnectionPool: Read timed out. (read timeout=600)', None), 'network'),
        (_FakeStatusError('ProxyError: connect error', None), 'network'),
        (_FakeStatusError('weird internal failure', None), 'other'),
    ])
    def test_kind_mapping(self, quiet_collector, exc, kind):
        c, _ = quiet_collector
        assert c._classify_llm_error(exc) == kind

    def test_real_401_payload_string(self, quiet_collector):
        """线上原文（openai SDK 拼出的字符串, 无 status_code 属性也要判 auth）。"""
        c, _ = quiet_collector
        raw = ("Error code: 401 - {'error': {'message': 'Authentication Fails, "
               "Your api key: ****3f06 is invalid (request_id: 0e31…)', "
               "'type': 'authentication_error'}}")
        assert c._classify_llm_error(RuntimeError(raw)) == 'auth'


class TestCallDeepseekNotes:
    def test_auth_error_notes_kind_and_masks_key(self, quiet_collector, fake_openai):
        c, _ = quiet_collector
        exc = _FakeStatusError(f'Authentication Fails, Your api key: {c.api_key} is invalid', 401)
        fake_openai(exc)
        assert c._call_deepseek('sys', 'user') is None
        err = c._last_error
        assert err['kind'] == 'auth'
        assert c.api_key not in err['detail'], 'detail 不得含明文 key'
        assert 'sk-***' in err['detail']

    def test_missing_key_notes_auth_missing(self, quiet_collector, fake_openai):
        c, _ = quiet_collector
        c.api_key = ''
        assert c._call_deepseek('sys', 'user') is None
        assert c._last_error['kind'] == 'auth_missing'

    def test_network_timeout_noted(self, quiet_collector, fake_openai):
        c, _ = quiet_collector
        fake_openai(_FakeStatusError('Read timed out.', None))
        c._call_deepseek('sys', 'user')
        assert c._last_error['kind'] == 'network'


class TestNoteNormalization:
    def test_unknown_kind_falls_back_to_other(self, quiet_collector):
        c, _ = quiet_collector
        c._note_error('not-a-kind', 'x')
        assert c._last_error['kind'] == 'other'

    def test_detail_truncated_and_single_line(self, quiet_collector):
        c, _ = quiet_collector
        c._note_error('other', 'line1\n' + 'x' * 400)
        assert '\n' not in c._last_error['detail']
        assert len(c._last_error['detail']) == 120


class TestObservePersistence:
    def _metrics(self, c, data_dir):
        return json.loads((data_dir / 'metrics.json').read_text())

    def test_failure_writes_last_error(self, quiet_collector, tmp_path):
        c, _ = quiet_collector
        c.data_dir = tmp_path
        c._note_error('auth', 'auth fail')
        c._observe(False, fetch_results=None)
        m = self._metrics(c, tmp_path)
        assert m['last_error']['kind'] == 'auth'
        assert m['consecutive_fails'] == 1

    def test_success_clears_last_error(self, quiet_collector, tmp_path):
        c, _ = quiet_collector
        c.data_dir = tmp_path
        c._note_error('auth', 'auth fail')
        c._observe(False, fetch_results=None)
        c._observe(True, fetch_results=None)
        m = self._metrics(c, tmp_path)
        assert 'last_error' not in m
        assert m['consecutive_fails'] == 0

    def test_unclassified_failure_not_silent(self, quiet_collector, tmp_path):
        c, _ = quiet_collector
        c.data_dir = tmp_path
        c._last_error = None
        c._observe(False, fetch_results=None)
        m = self._metrics(c, tmp_path)
        assert m['last_error']['kind'] == 'other'
