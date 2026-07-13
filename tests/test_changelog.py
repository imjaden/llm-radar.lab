"""Test changelog enhancement: sanitize + format + name/dim_label."""
import pytest


class TestSanitizeText:
    def test_html_escaped(self, collector):
        """HTML 特殊字符被转义"""
        result = collector._sanitize_text('<script>alert("xss")</script>')
        assert '<' not in result
        assert '>' not in result
        assert '&lt;' in result
        assert '&gt;' in result

    def test_control_chars_removed(self, collector):
        """Unicode 控制字符被移除（0x00-0x1F）"""
        result = collector._sanitize_text('hello\x00world\x1F!')
        assert '\x00' not in result
        assert '\x1F' not in result
        assert 'helloworld!' in result

    def test_newline_tab_preserved(self, collector):
        """换行和制表符保留"""
        result = collector._sanitize_text('line1\nline2\tindent')
        assert '\n' in result
        assert '\t' in result

    def test_truncate_long_text(self, collector):
        """超长文本截断为 max_len"""
        long_text = 'a' * 300
        result = collector._sanitize_text(long_text, max_len=100)
        assert len(result) == 100
        assert result.endswith('...')

    def test_short_text_unchanged(self, collector):
        """短文本不截断"""
        result = collector._sanitize_text('hello world', max_len=100)
        assert result == 'hello world'

    def test_empty_returns_empty(self, collector):
        assert collector._sanitize_text('') == ''
        assert collector._sanitize_text(None) == ''


class TestFormatChangelogSummary:
    def test_update_with_heat_change(self, collector):
        """update 条目：事件 + 热度变化"""
        item = {
            'name': 'OpenAI', 'last_event': '发布GPT-5.6',
            'hot_score': 90,
        }
        old = {'hot_score': 95}
        result = collector._format_changelog_summary(item, old)
        assert '发布GPT-5.6' in result
        assert '↓5' in result
        assert '95→90' in result

    def test_update_heat_rise(self, collector):
        """update 条目：热度上升"""
        item = {
            'name': 'DeepSeek', 'last_event': '自研芯片',
            'hot_score': 75,
        }
        old = {'hot_score': 60}
        result = collector._format_changelog_summary(item, old)
        assert '↑15' in result
        assert '60→75' in result

    def test_new_entry_format(self, collector):
        """new 条目：仅事件 + 当前热度（无箭头）"""
        item = {
            'name': 'Cursor', 'last_event': '300行代码写个Cursor',
            'hot_score': 85,
        }
        result = collector._format_changelog_summary(item, old=None)
        assert '300行代码写个Cursor' in result
        assert '↑' not in result
        assert '↓' not in result
        assert '热度 85' in result

    def test_no_event_no_heat(self, collector):
        """无事件无热度变化 → 用 name fallback"""
        item = {'name': 'TestCo', 'hot_score': 50}
        old = {'hot_score': 50}
        result = collector._format_changelog_summary(item, old)
        assert result == 'TestCo'

    def test_event_from_recent_activity(self, collector):
        """人物使用 recent_activity"""
        item = {
            'name': 'Sam Altman', 'recent_activity': '澄清ChatGPT Work定位',
            'hot_score': 90,
        }
        old = {'hot_score': 95}
        result = collector._format_changelog_summary(item, old)
        assert '澄清ChatGPT Work定位' in result
