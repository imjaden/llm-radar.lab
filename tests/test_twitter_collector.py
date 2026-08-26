"""twitter-collector 单元测试 (CL-SEC19 X热点采集 + CL-SEC20 v1.3 增强)。

覆盖 (设计 v1.3 §7.1):
- 配置解析: data/ 路径 + 10 账号 + 缺字段容错 + max_tweets 默认 30
- 条数窗口 (D1 1A): 三规则 (24h>30 全保留 / ≤30 补足 / 总<30 全保留) + 边界 (=30/=24h 整点)
- forward 解析 (D2 2C): retweet/quote → "by @作者: 原文"; 非转发 None; 无外层文本 text None
- 风控 (RIG-2): 单账号挑战→部分成功; 连续 2 账号挑战→提前终止
- DOM 解析: fixture HTML (文本/时间/指标/图片) + 缺失字段 null
- twitter.json 写盘: schema 字段完整 (retention) + null 缺省 + UTC Z 时间格式
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
        """enabled/max_tweets 缺失 → 默认 true / 30"""
        cfg = tc.parse_config('''
targets:
  - name: A
    handle: a
    url: https://x.com/a
''')
        assert cfg[0]['enabled'] is True
        assert cfg[0]['max_tweets'] == 30

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
        assert cfg[0]['max_tweets'] == 30

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


class TestConfigPathReal:
    """data/twitter-targets.yaml 生效 (RIG-1 §7.1): 10 账号 + 必填字段。"""

    def test_config_path_under_data(self, tc):
        assert str(tc.CONFIG_PATH).endswith('data/twitter-targets.yaml')

    def test_real_config_10_targets(self, tc):
        cfg = tc.load_config(tc.CONFIG_PATH)
        assert len(cfg) == 10
        assert {t['handle'] for t in cfg} == {
            'dhh', 'bcherny', 'sama', 'claudeai', 'openclaw', 'NousResearch',
            'deepseek_ai', 'JeffDean', 'AndrewYNg', 'karpathy'}
        for t in cfg:
            assert t['enabled'] is True
            assert t['max_tweets'] == 30
            assert t['name'] and t['handle']
            assert t['url'].startswith('https://x.com/')


# ===== 24h 窗口判定 (O-2 容差) =====

class TestWindowFilter:
    def _t(self, posted_at):
        return {'id': '1', 'posted_at': posted_at, 'text': 'x'}

    def test_inside_window(self, tc):
        now = tc._to_utc_dt('2026-08-25T12:00:00Z')
        assert tc.within_window('2026-08-25T06:00:00Z', now=now)

    def test_outside_old(self, tc):
        now = tc._to_utc_dt('2026-08-25T12:00:00Z')
        assert not tc.within_window('2026-08-23T23:59:59Z', now=now)

    def test_boundary_exact_24h(self, tc):
        now = tc._to_utc_dt('2026-08-25T12:00:00Z')
        # 恰好在窗口起点 (now - 24h) → 保留 (=24h 整点视为 24h 内)
        assert tc.within_window('2026-08-24T12:00:00Z', now=now)

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

    def test_offset_timezone_normalized(self, tc):
        """+08:00 输入归一化为 UTC Z 后参与窗口判断"""
        now = tc._to_utc_dt('2026-08-25T12:00:00Z')
        # 2026-08-25 20:00 +08:00 = 12:00Z → 窗口内
        assert tc.within_window('2026-08-25T20:00:00+08:00', now=now)


# ===== 条数窗口 (D1 1A, REA-1 三规则) =====

class TestRetentionWindow:
    NOW = '2026-08-25T12:00:00Z'

    def _t(self, tc, i, hours_ago, minutes=0):
        from datetime import timedelta
        now = tc._to_utc_dt(self.NOW)
        dt = now - timedelta(hours=hours_ago, minutes=minutes)
        return {'id': str(i), 'posted_at': dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'text': 'x'}

    def _now(self, tc):
        return tc._to_utc_dt(self.NOW)

    def test_rule_a_inner_gt_max_all_kept(self, tc):
        """24h 内 >30 条 → 全保留 (不截断)"""
        now = self._now(tc)
        tweets = [self._t(tc, i, 0, minutes=i) for i in range(35)]  # 最近 35 分钟, 全 24h 内
        out = tc.apply_retention(tweets, now=now)
        assert len(out) == 35
        assert [t['id'] for t in out] == [str(i) for i in range(35)]

    def test_rule_b_inner_le_max_fill_outer(self, tc):
        """24h 内 ≤30 + 24h 外 → 内全保留 + 外倒序补足至 30"""
        now = self._now(tc)
        inner = [self._t(tc, i, i + 1) for i in range(10)]           # 内 10 条
        outer = [self._t(tc, 100 + i, 24 + i * 2) for i in range(40)]  # 外 40 条
        out = tc.apply_retention(inner + outer, now=now)
        assert len(out) == 30
        # 内 10 条全保留 (id < 100)
        assert all(int(t['id']) < 100 for t in out[:10])
        # 外补 20 条按时间倒序 (最新在外 = i0 → id 100..119)
        assert [t['id'] for t in out[10:]] == [str(100 + i) for i in range(20)]

    def test_rule_c_total_lt_max_all_kept(self, tc):
        """总推文 <30 → 全部保留"""
        now = self._now(tc)
        tweets = [self._t(tc, i, i + 1) for i in range(12)]
        out = tc.apply_retention(tweets, now=now)
        assert len(out) == 12

    def test_boundary_exact_max(self, tc):
        """边界: 24h 内恰好 30 条 + 24h 外 → 全保留 30 (不补外)"""
        now = self._now(tc)
        inner30 = [self._t(tc, i, 0, minutes=i + 1) for i in range(30)]  # 最近 30 分钟 = 恰好 30 条
        outer5 = [self._t(tc, 100 + i, 25 + i) for i in range(5)]        # 严格 24h 外
        out = tc.apply_retention(inner30 + outer5, now=now)
        assert len(out) == 30
        assert all(int(t['id']) < 100 for t in out)   # 外不补, 全为 24h 内

    def test_boundary_exact_24h_edge(self, tc):
        """边界: 恰好 now-24h 整点 → 视为 24h 内 (保留)"""
        now = self._now(tc)
        out = tc.apply_retention([self._t(tc, 1, 24)], now=now)
        assert len(out) == 1

    def test_future_beyond_tolerance_dropped(self, tc):
        now = self._now(tc)
        from datetime import timedelta
        fmt = lambda dt: dt.strftime('%Y-%m-%dT%H:%M:%SZ')
        ok = {'id': '1', 'posted_at': fmt(now - timedelta(hours=1))}
        fut = {'id': '2', 'posted_at': fmt(now + timedelta(minutes=10))}
        out = tc.apply_retention([ok, fut], now=now)
        assert [t['id'] for t in out] == ['1']

    def test_missing_time_dropped(self, tc):
        now = self._now(tc)
        out = tc.apply_retention([{'id': '1', 'posted_at': None},
                                  {'id': '2', 'posted_at': ''}], now=now)
        assert out == []

    def test_max_tweets_override(self, tc):
        """per-account max_tweets override: 窗口按 N 补足 (O-4 残余)"""
        now = self._now(tc)
        inner = [self._t(tc, i, i + 1) for i in range(5)]
        outer = [self._t(tc, 100 + i, 24 + i) for i in range(10)]
        out = tc.apply_retention(inner + outer, now=now, max_tweets=8)
        assert len(out) == 8
        assert all(int(t['id']) < 100 for t in out[:5])


# ===== 去重 (O-3) =====

class TestDedup:
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

# 带评论转推 (D2 2C): socialContext 转推标记 + 外层文本 + 内层原推文
TWEET_RT_HTML = '''
<article data-testid="tweet">
  <div data-testid="socialContext">Alice Reposted</div>
  <a href="/alice/status/111" dir="ltr" role="link">…</a>
  <div data-testid="tweetText">Great point, this changes everything.</div>
  <div data-testid="tweetText">The original post about LLM agents.</div>
  <a href="/openai/status/999" dir="ltr" role="link">…</a>
</article>
'''

# 纯转推 (无外层文本): socialContext 转推 + 单 tweetText = 原文
TWEET_RT_PURE_HTML = '''
<article data-testid="tweet">
  <div data-testid="socialContext">Bob 转推了</div>
  <div data-testid="tweetText">Original tweet only.</div>
  <a href="/karpathy/status/888" dir="ltr" role="link">…</a>
</article>
'''

# 引用推文 (quote, 无 socialContext): 外层 + 内层两个 tweetText
TWEET_QUOTE_HTML = '''
<article data-testid="tweet">
  <a href="/bob/status/222" dir="ltr" role="link">…</a>
  <div data-testid="tweetText">My hot take on this.</div>
  <div data-testid="tweetText">The quoted article text.</div>
  <a href="/deepseek_ai/status/777" dir="ltr" role="link">…</a>
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
        for key in ('id', 'text', 'forward', 'posted_at', 'url', 'views',
                    'replies', 'retweets', 'likes', 'images'):
            assert key in t
        assert t['id'] is None
        assert t['forward'] is None
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


class TestForwardParse:
    """forward 解析 (D2 2C, §7.1): retweet/quote → 'by @作者: 原文'。"""

    def test_retweet_with_comment(self, tc):
        """带评论转推: 外层文本保留 + forward 指向内层原文作者"""
        t = tc.parse_tweet_html(TWEET_RT_HTML, handle='alice')
        assert t['id'] == '111'
        assert t['text'] == 'Great point, this changes everything.'
        assert t['forward'] == 'by @openai: The original post about LLM agents.'

    def test_pure_retweet_text_none(self, tc):
        """纯转推 (无外层文本): text None + forward 有值"""
        t = tc.parse_tweet_html(TWEET_RT_PURE_HTML, handle='bob')
        assert t['id'] == '888'
        assert t['text'] is None
        assert t['forward'] == 'by @karpathy: Original tweet only.'

    def test_quote(self, tc):
        """引用推文 (无 socialContext): 外层 + 内层两个 tweetText → forward"""
        t = tc.parse_tweet_html(TWEET_QUOTE_HTML, handle='bob')
        assert t['text'] == 'My hot take on this.'
        assert t['forward'] == 'by @deepseek_ai: The quoted article text.'

    def test_normal_tweet_forward_none(self, tc):
        """非转发 → forward None"""
        t = tc.parse_tweet_html(TWEET_HTML, handle='steipete')
        assert t['forward'] is None

    def test_author_fallback_avatar_alt(self, tc):
        """作者提取回退: 头像 alt ('X's profile picture') → 显示名"""
        html = '''<article data-testid="tweet">
          <div data-testid="socialContext">Reposted</div>
          <img alt="Sam Altman's profile picture" src="https://pbs.twimg.com/media/x.jpg">
          <div data-testid="tweetText">Original.</div>
        </article>'''
        t = tc.parse_tweet_html(html, handle='bob')
        assert t['text'] is None
        assert t['forward'] == 'by @Sam Altman: Original.'

    def test_author_fallback_unknown(self, tc):
        """作者提取全失败 → unknown (不丢原文, O-2 降级)"""
        html = ('<article data-testid="tweet">'
                '<div data-testid="socialContext">Reposted</div>'
                '<div data-testid="tweetText">X.</div></article>')
        t = tc.parse_tweet_html(html, handle='bob')
        assert t['forward'] == 'by @unknown: X.'

    def test_forward_missing_inner_text_none(self, tc):
        """内层原文缺失 → forward None (不构造半截 forward)"""
        html = ('<article data-testid="tweet">'
                '<div data-testid="socialContext">Reposted</div>'
                '<div data-testid="tweetText"> </div></article>')
        t = tc.parse_tweet_html(html, handle='bob')
        assert t['forward'] is None


# ===== 写盘 schema (§4, RIG-1) =====

class TestSchemaWrite:
    def test_build_document_keys(self, tc):
        doc = tc.build_document([], last_error=None)
        assert sorted(doc.keys()) == ['generated_at', 'last_error', 'retention',
                                      'targets']
        assert doc['retention'] == '30/24h'
        assert doc['last_error'] is None

    def test_generated_at_utc_z(self, tc):
        assert re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z',
                            tc.utc_now_str())

    def test_target_doc_fields(self, tc):
        target = {'name': 'A', 'handle': 'a', 'url': 'https://x.com/a',
                  'enabled': True, 'max_tweets': 30}
        doc = tc.target_doc(target, [])
        assert sorted(doc.keys()) == ['handle', 'name', 'tweets', 'url']

    def test_write_document_roundtrip(self, tc, tmp_path):
        out = tmp_path / 'twitter.json'
        tweets = [tc.parse_tweet_html(TWEET_HTML, handle='steipete')]
        target = {'name': 'Peter Steinberger', 'handle': 'steipete',
                  'url': 'https://x.com/steipete', 'enabled': True, 'max_tweets': 30}
        doc = tc.build_document([tc.target_doc(target, tweets)],
                                last_error='ok: fail')
        tc.write_document(doc, path=out)
        data = json.loads(out.read_text(encoding='utf-8'))
        assert data['generated_at'] == doc['generated_at']
        assert data['retention'] == '30/24h'
        assert data['last_error'] == 'ok: fail'
        tw = data['targets'][0]['tweets'][0]
        # null 缺省键不省略
        assert tw['retweets'] == 3
        assert set(tw.keys()) == {'id', 'text', 'forward', 'posted_at', 'url',
                                  'views', 'replies', 'retweets', 'likes', 'images'}
        assert tw['images'] == [
            'https://pbs.twimg.com/media/abc123.jpg',
            'https://pbs.twimg.com/media/def456.jpg',
        ]


# ===== 退出码映射 (O-4) =====

class TestExitMapping:
    def _res(self, name='steipete', tweets=None, error=None):
        return {'target': {'name': name, 'handle': name, 'url': f'https://x.com/{name}',
                           'enabled': True, 'max_tweets': 30},
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
        """全部成功但无 24h 窗口推文 → 不写盘 exit 1 (保留上次)"""
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


class TestRiskControl:
    """风控 (RIG-2, §3.6): cmd_collect 循环语义 (不启动浏览器)。"""

    def _targets(self, n=3):
        return [{'name': f'A{i}', 'handle': f'a{i}',
                 'url': f'https://x.com/a{i}', 'enabled': True,
                 'max_tweets': 30} for i in range(n)]

    def _patch_collect(self, tc, monkeypatch, fetch_fn, tmp_path):
        calls = []

        def fake_fetch(driver, target, **kw):
            calls.append(target['handle'])
            return fetch_fn(target)

        monkeypatch.setattr(tc, 'start_driver', lambda *a, **k: object())
        monkeypatch.setattr(tc, 'fetch_target', fake_fetch)
        written = {}
        monkeypatch.setattr(tc, 'write_document',
                            lambda doc, path=None: written.update(doc))
        monkeypatch.setattr(tc, 'commit_and_push', lambda n: None)
        return calls, written

    def test_single_challenge_partial_success(self, tc, monkeypatch, tmp_path):
        """单账号挑战 → 记 error 继续下一账号; 部分成功写盘 + last_error; exit 0"""
        targets = self._targets(2)

        def fetch_fn(t):
            if t['handle'] == 'a0':
                raise tc.ChallengeError('验证挑战')
            return [{'id': '1', 'text': 'ok'}]

        calls, written = self._patch_collect(tc, monkeypatch, fetch_fn, tmp_path)
        code = tc.cmd_collect(targets, tmp_path)
        assert code == 0
        assert calls == ['a0', 'a1']          # 继续下一账号
        assert len(written['targets']) == 1   # 成功账号数据落盘
        # build_last_error 用 name (A0) 记录失败账号 + 原因
        assert 'A0' in written['last_error'] and '验证挑战' in written['last_error']

    def test_two_consecutive_challenges_early_terminate(self, tc, monkeypatch, tmp_path):
        """连续 2 账号挑战 → 提前终止本轮 (第三个不抓); 全部未抓成 → 不写盘 exit 1"""
        targets = self._targets(3)

        def fetch_fn(t):
            raise tc.ChallengeError('验证挑战')

        calls, written = self._patch_collect(tc, monkeypatch, fetch_fn, tmp_path)
        code = tc.cmd_collect(targets, tmp_path)
        assert code == 1
        assert calls == ['a0', 'a1']          # 第三个账号未抓
        assert written == {}                   # 全部失败不写盘

    def test_challenge_then_success_no_early_terminate(self, tc, monkeypatch, tmp_path):
        """挑战-成功-挑战 → 非连续, 不提前终止 (全部抓完, 部分成功)"""
        targets = self._targets(3)

        def fetch_fn(t):
            if t['handle'] in ('a0', 'a2'):
                raise tc.ChallengeError('验证挑战')
            return [{'id': '1', 'text': 'ok'}]

        calls, written = self._patch_collect(tc, monkeypatch, fetch_fn, tmp_path)
        code = tc.cmd_collect(targets, tmp_path)
        assert code == 0
        assert calls == ['a0', 'a1', 'a2']    # 全部抓完 (非连续不提前终止)
        assert len(written['targets']) == 1   # 仅 a1 成功

    def test_partial_success_after_early_terminate(self, tc, monkeypatch, tmp_path):
        """已抓账号写盘: 成功 1 个后连续 2 挑战 → 写盘成功账号, exit 0"""
        targets = self._targets(3)

        def fetch_fn(t):
            if t['handle'] == 'a0':
                return [{'id': '1', 'text': 'ok'}]
            raise tc.ChallengeError('验证挑战')

        calls, written = self._patch_collect(tc, monkeypatch, fetch_fn, tmp_path)
        code = tc.cmd_collect(targets, tmp_path)
        assert code == 0                       # 部分成功
        assert calls == ['a0', 'a1', 'a2']     # a0 成功; a1/a2 挑战 → 连续 2 → 终止
        assert len(written['targets']) == 1
        assert 'A1' in written['last_error'] and 'A2' in written['last_error']


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
        assert written.get('retention') == '30/24h'

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
