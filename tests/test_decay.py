"""Test _apply_time_decay: time-based hot_score decay."""
import pytest
from datetime import datetime, timedelta


class TestTimeDecay:
    def test_recent_1_day_no_decay(self, collector):
        """24小时内事件不减分"""
        today = datetime.now().strftime('%Y-%m-%d')
        item = {
            "id": "test", "name": "Test",
            "hot_score": 80,
            "last_event_date": today,
        }
        result = collector._apply_time_decay(item)
        assert result["hot_score"] == 80
        assert result["hot_level"] == "爆热"

    def test_within_3_days_no_decay(self, collector):
        """3天内事件不减分"""
        dt = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
        item = {
            "id": "test", "name": "Test",
            "hot_score": 75,
            "last_event_date": dt,
        }
        result = collector._apply_time_decay(item)
        assert result["hot_score"] == 75
        assert result["hot_level"] == "高热"

    def test_day_5_decay_4_points(self, collector):
        """第5天事件减 4 分（(5-3) * 2 = 4）"""
        dt = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
        item = {
            "id": "test", "name": "Test",
            "hot_score": 80,
            "last_event_date": dt,
        }
        result = collector._apply_time_decay(item)
        assert result["hot_score"] == 76  # 80 - 4

    def test_day_7_decay_8_points(self, collector):
        """第7天事件减 8 分（(7-3) * 2 = 8）"""
        dt = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        item = {
            "id": "test", "name": "Test",
            "hot_score": 80,
            "last_event_date": dt,
        }
        result = collector._apply_time_decay(item)
        assert result["hot_score"] == 72  # 80 - 8

    def test_day_10_decay_17_points(self, collector):
        """第10天事件减 17 分（8 + (10-7) * 3 = 17）"""
        dt = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        item = {
            "id": "test", "name": "Test",
            "hot_score": 80,
            "last_event_date": dt,
        }
        result = collector._apply_time_decay(item)
        assert result["hot_score"] == 63  # 80 - 17

    def test_floor_10(self, collector):
        """衰减下限为 10 分"""
        dt = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        item = {
            "id": "test", "name": "Test",
            "hot_score": 20,
            "last_event_date": dt,
        }
        result = collector._apply_time_decay(item)
        assert result["hot_score"] == 10

    def test_no_date_skips_decay(self, collector):
        """无日期字段跳过衰减"""
        item = {
            "id": "test", "name": "Test",
            "hot_score": 90,
        }
        result = collector._apply_time_decay(item)
        assert result["hot_score"] == 90

    def test_empty_date_skips_decay(self, collector):
        """空字符串日期跳过衰减"""
        item = {
            "id": "test", "name": "Test",
            "hot_score": 90,
            "last_event_date": "",
        }
        result = collector._apply_time_decay(item)
        assert result["hot_score"] == 90

    def test_recent_activity_date_used_as_fallback(self, collector):
        """使用 recent_activity_date 作为备选日期字段"""
        dt = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
        item = {
            "id": "test", "name": "Test",
            "hot_score": 80,
            "recent_activity_date": dt,
        }
        result = collector._apply_time_decay(item)
        assert result["hot_score"] == 76  # 80 - 4

    def test_level_drops_with_decay(self, collector):
        """hot_level 随衰减下降"""
        dt = (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d')
        item = {
            "id": "test", "name": "Test",
            "hot_score": 85,
            "last_event_date": dt,
        }
        result = collector._apply_time_decay(item)
        assert result["hot_score"] == 68  # 85 - 17
        assert result["hot_level"] == "高热"  # 从爆热降为高热
