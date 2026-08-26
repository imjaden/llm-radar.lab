"""twitter-collector 单元测试 (CL-SEC19 X热点采集)。

覆盖 (设计 §7.1):
- 配置解析: 正常/缺字段/空文件/非法 yaml
- 36h 窗口过滤: 窗口内/外/边界 + now+5min 容差 (O-2)
- max_tweets 截断: 时间倒序取前 N
- DOM 解析: fixture HTML (文本/时间/指标/图片) + 缺失字段 null
- twitter.json 写盘: schema 字段完整 + null 缺省 + UTC Z 时间格式
- 退出码映射 (O-4): 登录墙 exit-2 / 挑战检测 / 全失败不写盘 / 部分成功写盘+last_error
"""
import importlib.util
import json
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / 'scripts' / 'twitter-collector.py'


def load_module():
    spec = importlib.util.spec_from_file_location('twitter_collector', SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope='module')
def tc():
    return load_module()


# ===== 配置解析 (§3.1) =====

class TestConfigParse:
    def test_normal(self, tc):
        cfg = tc.parse_config('''
targets:
  - name: Peter Steinberger
    handle: steipete
    url: https://x.com/steipete
    enabled: true
    max_tweets: 20
''')
        assert len(cfg) == 1
        t = cfg[0]
        assert t['name'] == 'Peter Steinberger'
        assert t['handle'] == 'steipete'
        assert t['url'] == 'https://x.com/steipete'
        assert t['enabled'] is True
        assert t['max_tweets'] == 20

    def test_missing_optional_defaults(self, tc):
        """enabled/max_tweets 缺失 → 默认 true / 20"""
        cfg = tc.parse_config('''
targets:
  - name: A
    handle: a
    url: https://x.com/a
''')
        assert cfg[0]['enabled'] is True
        assert cfg[0]['max_tweets'] == 20

    def test_disabled(self, tc):
        cfg = tc.parse_config('''
targets:
  - name: A
    handle: a
    url: https://x.com/a
    enabled: false
''')
        assert cfg[0]['enabled'] is False

    def test_max_tweets_zero_falls_back(self, tc):
        cfg = tc.parse_config('''
targets:
  - name: A
    handle: a
    url: https://x.com/a
    max_tweets: 0
''')
        assert cfg[0]['max_tweets'] == 20

    def test_missing_required(self, tc):
        with pytest.raises(tc.ConfigError):
            tc.parse_config('''
targets:
  - handle: a
    url: https://x.com/a
''')

    def test_missing_all_fields(self, tc):
        with pytest.raises(tc.ConfigError):
            tc.parse_config('''
targets:
  - {}
''')

    def test_empty_file(self, tc):
        assert tc.parse_config('') == []
        assert tc.parse_config('# only comments\n') == []

    def test_invalid_yaml(self, tc):
        with pytest.raises(tc.ConfigError):
            tc.parse_config('::: not valid :::')

    def test_targets_not_list(self, tc):
        with pytest.raises(tc.ConfigError):
            tc.parse_config('targets: notalist')

    def test_target_item_not_dict(self, tc):
        with pytest.raises(tc.ConfigError):
            tc.parse_config('targets:\n  - justastring')

    def test_max_tweets_invalid(self, tc):
        with pytest.raises(tc.ConfigError):
            tc.parse_config('''
targets:
  - name: A
    handle: a
    url: https://x.com/a
    max_tweets: abc
''')


# ===== 36h 窗口过滤 (O-2 容差) =====

class TestWindowFilter:
    def _t(self, posted_at):
        return {'id': '1', 'posted_at': posted_at, 'text': 'x'}

    def test_inside_window(self, tc):
        now = tc._to_utc_dt('2026-08-25T12:00:00Z')
        assert tc.within_window('2026-08-25T06:00:00Z', now=now)

    def test_outside_old(self, tc):
        now = tc._to_utc_dt('2026-08-25T12:00:00Z')
        assert not tc.within_window('2026-08-23T23:59:59Z', now=now)

    def test_boundary_exact_36h(self, tc):
        now = tc._to_utc_dt('2026-08-25T12:00:00Z')
        # 恰好在窗口起点 (now - 36h) → 保留
        assert tc.within_window('2026-08-24T00:00:00Z', now=now)

    def test_future_within_tolerance(self, tc):
        now = tc._to_utc_dt('2026-08-25T12:00:00Z')
        assert tc.within_window('2026-08-25T12:04:00Z', now=now)

    def test_future_beyond_tolerance(self, tc):
        now = tc._to_utc_dt('2026-08-25T12:00:00Z')
        assert not tc.within_window('2026-08-25T12:10:00Z', now=now)

    def test_missing_time_dropped(self, tc):
        now = tc._to_utc_dt('2026-08-25T12:00:00Z')
        assert not tc.within_window(None, now=now)
        assert not tc.within_window('', now=now)

    def test_invalid_time_dropped(self, tc):
        now = tc._to_utc_dt('2026-08-25T12:00:00Z')
        assert not tc.within_window('not-a-date', now=now)

    def test_filter_window_combined(self, tc):
        now = tc._to_utc_dt('2026-08-25T12:00:00Z')
        tweets = [
            self._t('2026-08-25T10:00:00Z'),   # in
            self._t('2026-08-23T10:00:00Z'),   # out (>36h)
            self._t('2026-08-25T12:04:00Z'),   # in (容差)
            self._t(None),                     # out (无时间)
        ]
        out = tc.filter_window(tweets, now=now)
        assert [t['id'] for t in out] == ['1', '1']

    def test_offset_timezone_normalized(self, tc):
        """+08:00 输入归一化为 UTC Z 后参与窗口判断"""
        now = tc._to_utc_dt('2026-08-25T12:00:00Z')
        # 2026-08-25 20:00 +08:00 = 12:00Z → 窗口内
        assert tc.within_window('2026-08-25T20:00:00+08:00', now=now)


# ===== 去重 / 截断 (O-3) =====

class TestDedupTruncate:
    def test_dedup_by_id(self, tc):
        tweets = [
            {'id': '1', 'text': 'a'}, {'id': '1', 'text': 'a dup'},
            {'id': '2', 'text': 'b'}, {'id': '2', 'text': 'b dup'},
        ]
        out = tc.dedup_tweets(tweets)
        assert [t['id'] for t in out] == ['1', '2']

    def test_dedup_keeps_no_id(self, tc):
        tweets = [{'id': None, 'text': 'x'}, {'id': '1', 'text': 'a'},
                  {'id': '1', 'text': 'a dup'}]
        out = tc.dedup_tweets(tweets)
        assert len(out) == 2
        assert out[0]['id'] is None

    def test_truncate_newest_first(self, tc):
        tweets = [
            {'id': '1', 'posted_at': '2026-08-25T10:00:00Z'},
            {'id': '2', 'posted_at': '2026-08-25T12:00:00Z'},
            {'id': '3', 'posted_at': '2026-08-25T08:00:00Z'},
            {'id': '4', 'posted_at': '2026-08-25T11:00:00Z'},
            {'id': '5', 'posted_at': '2026-08-25T09:00:00Z'},
        ]
        out = tc.truncate_tweets(tweets, 3)
        assert [t['id'] for t in out] == ['2', '4', '1']

    def test_truncate_missing_time_last(self, tc):
        tweets = [
            {'id': '1', 'posted_at': '2026-08-25T10:00:00Z'},
            {'id': '2', 'posted_at': None},
        ]
        out = tc.truncate_tweets(tweets, 5)
        assert [t['id'] for t in out] == ['1', '2']

    def test_truncate_default_20(self, tc):
        tweets = [{'id': str(i), 'posted_at': f'2026-08-25T{i:02d}:00:00Z'}
                  for i in range(25)]
        assert len(tc.truncate_tweets(tweets)) == 20


# ===== DOM 解析 (§3.4) =====

TWEET_HTML = '''
<article data-testid="tweet">
  <div data-testid="tweetText">Building a tiny LLM dashboard. It scans 7 sources every hour.</div>
  <a href="/steipete/status/123456789" dir="ltr" role="link">…</a>
  <time datetime="2026-08-25T00:30:00.000Z">…</time>
  <div role="group" aria-label="1,234 views, 12 replies, 3 reposts, 45 likes"></div>
  <button data-testid="reply" aria-label="12 replies"></button>
  <button data-testid="retweet" aria-label="3 reposts"></button>
  <button data-testid="like" aria-label="45 likes"></button>
  <img src="https://pbs.twimg.com/media/abc123.jpg">
  <img src="https://pbs.twimg.com/media/def456.jpg">
</article>
'''


class TestDomParse:
    def test_full_extraction(self, tc):
        t = tc.parse_tweet_html(TWEET_HTML, handle='steipete')
        assert t['id'] == '123456789'
        assert 'LLM dashboard' in t['text']
        assert t['posted_at'] == '2026-08-25T00:30:00Z'
        assert t['url'] == 'https://x.com/steipete/status/123456789'
        assert t['views'] == 1234
        assert t['replies'] == 12
        assert t['retweets'] == 3
        assert t['likes'] == 45
        assert t['images'] == [
            'https://pbs.twimg.com/media/abc123.jpg',
            'https://pbs.twimg.com/media/def456.jpg',
        ]

    def test_missing_fields_null(self, tc):
        """字段缺失 → null, 不省略键"""
        t = tc.parse_tweet_html('<article><div>no structure at all</div></article>')
        for key in ('id', 'text', 'posted_at', 'url', 'views', 'replies',
                    'retweets', 'likes', 'images'):
            assert key in t
        assert t['id'] is None
        assert t['views'] is None
        assert t['images'] is None

    def test_empty_html(self, tc):
        t = tc.parse_tweet_html('', handle='steipete')
        assert t['id'] is None
        assert t['url'] is None

    def test_url_normalization_handle_strip(self, tc):
        t = tc.parse_tweet_html('<article><a href="/steipete/status/42">x</a></article>',
                                handle='@steipete')
        assert t['id'] == '42'
        assert t['url'] == 'https://x.com/steipete/status/42'

    def test_text_fallback_whole_card(self, tc):
        t = tc.parse_tweet_html('<article><div>plain card text</div></article>')
        assert t['text'] == 'plain card text'

    def test_views_chinese(self, tc):
        html = '<article><div aria-label="3,210 次查看"></div></article>'
        assert tc.parse_tweet_html(html)['views'] == 3210

    def test_metrics_chinese(self, tc):
        html = ('<article>'
                '<button data-testid="reply" aria-label="5 回复"></button>'
                '<button data-testid="retweet" aria-label="6 转推"></button>'
                '<button data-testid="like" aria-label="7 喜欢"></button>'
                '</article>')
        t = tc.parse_tweet_html(html)
        assert t['replies'] == 5
        assert t['retweets'] == 6
        assert t['likes'] == 7

    def test_views_zero_kept(self, tc):
        """'0 views' → 0 (非 null)"""
        html = '<article><div aria-label="0 views"></div></article>'
        assert tc.parse_tweet_html(html)['views'] == 0

    def test_parse_posted_at_offset(self, tc):
        assert tc.parse_posted_at('2026-08-25T08:30:00+08:00') == '2026-08-25T00:30:00Z'

    def test_parse_posted_at_invalid(self, tc):
        assert tc.parse_posted_at('garbage') is None
        assert tc.parse_posted_at(None) is None


# ===== 写盘 schema (§4) =====

class TestSchemaWrite:
    def test_build_document_keys(self, tc):
        doc = tc.build_document([], last_error=None)
        assert sorted(doc.keys()) == ['generated_at', 'last_error', 'targets',
                                      'window_hours']
        assert doc['window_hours'] == 36
        assert doc['last_error'] is None

    def test_generated_at_utc_z(self, tc):
        assert re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',
                            tc.utc_now_str())

    def test_target_doc_fields(self, tc):
        target = {'name': 'A', 'handle': 'a', 'url': 'https://x.com/a',
                  'enabled': True, 'max_tweets': 20}
        doc = tc.target_doc(target, [])
        assert sorted(doc.keys()) == ['handle', 'name', 'tweets', 'url']

    def test_write_document_roundtrip(self, tc, tmp_path):
        out = tmp_path / 'twitter.json'
        tweets = [tc.parse_tweet_html(TWEET_HTML, handle='steipete')]
        target = {'name': 'Peter Steinberger', 'handle': 'steipete',
                  'url': 'https://x.com/steipete', 'enabled': True, 'max_tweets': 20}
        doc = tc.build_document([tc.target_doc(target, tweets)],
                                last_error='ok: fail')
        tc.write_document(doc, path=out)
        data = json.loads(out.read_text(encoding='utf-8'))
        assert data['generated_at'] == doc['generated_at']
        assert data['window_hours'] == 36
        assert data['last_error'] == 'ok: fail'
        tw = data['targets'][0]['tweets'][0]
        # null 缺省键不省略
        assert tw['retweets'] == 3
        assert set(tw.keys()) == {'id', 'text', 'posted_at', 'url', 'views',
                                  'replies', 'retweets', 'likes', 'images'}
        assert tw['images'] == [
            'https://pbs.twimg.com/media/abc123.jpg',
            'https://pbs.twimg.com/media/def456.jpg',
        ]


# ===== 退出码映射 (O-4) =====

class TestExitMapping:
    def _res(self, name='steipete', tweets=None, error=None):
        return {'target': {'name': name, 'handle': name, 'url': f'https://x.com/{name}',
                           'enabled': True, 'max_tweets': 20},
                'tweets': tweets if tweets is not None else [],
                'error': error}

    def test_all_success(self, tc):
        write, err, code = tc.evaluate_results(
            [self._res(tweets=[{'id': '1'}]), self._res(tweets=[{'id': '2'}])])
        assert write is True
        assert err is None          # last_error 清空
        assert code == 0

    def test_partial_success(self, tc):
        write, err, code = tc.evaluate_results([
            self._res(tweets=[{'id': '1'}]),
            self._res(name='other', error='timeout'),
        ])
        assert write is True
        assert code == 0
        assert 'other' in err and 'timeout' in err

    def test_all_failed_no_write(self, tc):
        write, err, code = tc.evaluate_results([
            self._res(error='timeout'),
            self._res(name='other', error='challenge'),
        ])
        assert write is False
        assert err is None          # 全失败不入盘
        assert code == 1

    def test_all_empty_no_write(self, tc):
        """全部成功但无 36h 窗口推文 → 不写盘 exit 1 (保留上次)"""
        write, err, code = tc.evaluate_results([self._res(), self._res()])
        assert write is False
        assert code == 1

    def test_login_wall_exit2(self, tc):
        write, err, code = tc.evaluate_results([self._res()], login_wall=True)
        assert write is False
        assert code == 2

    def test_build_last_error_none_when_no_failures(self, tc):
        assert tc.build_last_error([]) is None


class TestChallengeLoginWall:
    """登录墙 / 挑战检测 (FakeDriver, 不需浏览器)"""

    class FakeDriver:
        def __init__(self, url='https://x.com/steipete', page_source='<html></html>',
                     login_buttons=False):
            self.current_url = url
            self.page_source = page_source
            self._login_buttons = login_buttons

        def find_elements(self, by, selector):
            return ['<fake>'] if self._login_buttons else []

    def test_login_wall_by_url(self, tc):
        d = self.FakeDriver(url='https://x.com/login')
        assert tc.detect_login_wall(d) is True

    def test_login_wall_by_button(self, tc):
        d = self.FakeDriver(login_buttons=True)
        assert tc.detect_login_wall(d) is True

    def test_no_wall(self, tc):
        d = self.FakeDriver()
        assert tc.detect_login_wall(d) is False

    def test_wall_failsafe_on_exception(self, tc):
        class Broken:
            current_url = None
            page_source = None
            def find_elements(self, by, selector):
                raise RuntimeError('boom')
        assert tc.detect_login_wall(Broken()) is True

    def test_challenge_detected(self, tc):
        d = self.FakeDriver(page_source='<html>cf-challenge</html>')
        assert tc.detect_challenge(d) is True

    def test_challenge_something_went_wrong(self, tc):
        d = self.FakeDriver(page_source='<html>Something went wrong. Try again.</html>')
        assert tc.detect_challenge(d) is True

    def test_no_challenge(self, tc):
        d = self.FakeDriver()
        assert tc.detect_challenge(d) is False


class TestCliArgs:
    def test_default_collect(self, tc):
        assert tc.parse_args([]) == {'mode': 'collect'}

    def test_explicit_collect(self, tc):
        assert tc.parse_args(['--collect']) == {'mode': 'collect'}

    def test_login(self, tc):
        assert tc.parse_args(['--login']) == {'mode': 'login'}

    def test_dry_run(self, tc):
        assert tc.parse_args(['--dry-run']) == {'mode': 'dry-run'}

    def test_help_exit0(self, tc):
        with pytest.raises(SystemExit) as e:
            tc.parse_args(['--help'])
        assert e.value.code == 0

    def test_unknown_exit1(self, tc):
        with pytest.raises(SystemExit) as e:
            tc.parse_args(['--frobnicate'])
        assert e.value.code == 1

    def test_extra_args_exit1(self, tc):
        with pytest.raises(SystemExit) as e:
            tc.parse_args(['--collect', 'extra'])
        assert e.value.code == 1


class TestMainPaths:
    """main() 关键路径 (不启动浏览器; 用 monkeypatch 隔离 git/写盘)。

    覆盖复审注记 O-12 (空 targets/全 disabled → 写空文件 exit 0 + 提示)
    与配置错误 exit 1 / 未知参数 exit 1。
    """

    def test_help_exit0(self, tc):
        assert tc.main(['--help']) == 0

    def test_unknown_arg_exit1(self, tc):
        assert tc.main(['--frobnicate']) == 1

    def test_config_error_exit1(self, tc, monkeypatch, tmp_path):
        cfg = tmp_path / 'bad.yaml'
        cfg.write_text('::: bad :::')
        monkeypatch.setattr(tc, 'CONFIG_PATH', cfg)
        assert tc.main(['--collect']) == 1

    def test_all_disabled_writes_empty(self, tc, monkeypatch, tmp_path):
        """O-12: 全 disabled → 写空文件 exit 0 + 提示 (mock 写盘/commit)"""
        cfg = tmp_path / 'disabled.yaml'
        cfg.write_text('''
targets:
  - name: A
    handle: a
    url: https://x.com/a
    enabled: false
''')
        monkeypatch.setattr(tc, 'CONFIG_PATH', cfg)
        written = {}
        monkeypatch.setattr(tc, 'write_document',
                            lambda doc, path=None: written.update(doc))
        monkeypatch.setattr(tc, 'commit_and_push', lambda n: None)
        assert tc.main(['--collect']) == 0
        assert written.get('targets') == []
        assert written.get('window_hours') == 36

    def test_empty_targets_writes_empty(self, tc, monkeypatch, tmp_path):
        """O-12: 空 targets → 写空文件 exit 0"""
        cfg = tmp_path / 'empty.yaml'
        cfg.write_text('targets: []\n')
        monkeypatch.setattr(tc, 'CONFIG_PATH', cfg)
        written = {}
        monkeypatch.setattr(tc, 'write_document',
                            lambda doc, path=None: written.update(doc))
        monkeypatch.setattr(tc, 'commit_and_push', lambda n: None)
        assert tc.main(['--collect']) == 0
        assert written.get('targets') == []

    def test_dry_run_no_enabled_exit1(self, tc, monkeypatch, tmp_path):
        cfg = tmp_path / 'disabled.yaml'
        cfg.write_text('targets:\n  - name: A\n    handle: a\n    url: https://x.com/a\n    enabled: false\n')
        monkeypatch.setattr(tc, 'CONFIG_PATH', cfg)
        assert tc.main(['--dry-run']) == 1
