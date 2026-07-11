"""Test merge date filtering: reject stale new entities (>14 days)."""
import pytest
from datetime import datetime, timedelta


class TestDateFilter:
    def test_recent_new_entity_accepted(self, temp_snapshot):
        """最近 7 天的新实体正常入库"""
        recent = (datetime.now() - timedelta(days=3)).strftime('%Y-%m-%d')
        new = {"providers": [{"id": "recent-co", "name": "RecentCo",
                              "last_event_date": recent,
                              "hot_score": 80, "confidence": "high"}]}
        result = temp_snapshot.merge_entities(new)
        providers = result["providers"]
        assert any(p["id"] == "recent-co" for p in providers)

    def test_stale_new_entity_rejected(self, temp_snapshot):
        """超过 14 天的新实体被拒绝"""
        stale = (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d')
        new = {"providers": [{"id": "stale-co", "name": "StaleCo",
                              "last_event_date": stale,
                              "hot_score": 80, "confidence": "high"}]}
        result = temp_snapshot.merge_entities(new)
        providers = result["providers"]
        assert not any(p["id"] == "stale-co" for p in providers)

    def test_stale_update_to_existing_accepted(self, temp_snapshot):
        """已有实体的过期更新仍接受（可能补充 key_people 等字段）"""
        stale = (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d')
        new = {"providers": [{"id": "openai", "name": "OpenAI",
                              "last_event_date": stale,
                              "hot_score": 99, "key_people": ["Sam Altman-CEO"],
                              "confidence": "high"}]}
        result = temp_snapshot.merge_entities(new)
        providers = result["providers"]
        updated = [p for p in providers if p["id"] == "openai"]
        assert len(updated) == 1
        assert "Sam Altman-CEO" in updated[0].get("key_people", [])

    def test_exactly_14_days_accepted(self, temp_snapshot):
        """恰好 14 天的新实体接受（边界条件）"""
        boundary = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
        new = {"providers": [{"id": "boundary-co", "name": "BoundaryCo",
                              "last_event_date": boundary,
                              "hot_score": 80, "confidence": "high"}]}
        result = temp_snapshot.merge_entities(new)
        providers = result["providers"]
        assert any(p["id"] == "boundary-co" for p in providers)

    def test_no_date_entity_accepted(self, temp_snapshot):
        """无日期的新实体正常接受（不因缺少日期而拒绝）"""
        new = {"providers": [{"id": "nodate-co", "name": "NoDateCo",
                              "hot_score": 80, "confidence": "high"}]}
        result = temp_snapshot.merge_entities(new)
        providers = result["providers"]
        assert any(p["id"] == "nodate-co" for p in providers)
