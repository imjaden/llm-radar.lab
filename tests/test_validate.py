"""Test _validate_entity_urls: URL quality and data completeness checks."""
import pytest


class TestUrlValidation:
    def test_empty_urls_counted(self, collector):
        """空 URL 被计数"""
        entities = {
            "providers": [
                {"id": "a", "name": "A", "last_event_url": "",
                 "last_event_date": "2026-07-10", "confidence": "high"},
                {"id": "b", "name": "B", "last_event_url": "",
                 "last_event_date": "2026-07-10", "confidence": "high"},
                {"id": "c", "name": "C", "last_event_url": "https://example.com/article",
                 "last_event_date": "2026-07-10", "confidence": "high"},
            ],
            "people": [],
            "tools": [],
            "llms": [],
            "hotspots": [],
        }
        stats = collector._validate_entity_urls(entities)
        assert stats["empty_urls"] == 2

    def test_truncated_urls_detected(self, collector):
        """截断 URL（含 ... ）被检出"""
        entities = {
            "providers": [
                {"id": "a", "name": "A",
                 "last_event_url": "https://infoq.cn/article/...",
                 "last_event_date": "2026-07-10", "confidence": "high"},
            ],
            "people": [],
            "tools": [],
            "llms": [],
            "hotspots": [],
        }
        stats = collector._validate_entity_urls(entities)
        assert stats["truncated_urls"] == 1

    def test_bare_domains_detected(self, collector):
        """裸域名（无路径段）被检出"""
        entities = {
            "providers": [
                {"id": "a", "name": "A",
                 "last_event_url": "https://example.com",
                 "last_event_date": "2026-07-10", "confidence": "high"},
            ],
            "people": [],
            "tools": [],
            "llms": [],
            "hotspots": [],
        }
        stats = collector._validate_entity_urls(entities)
        assert stats["bare_domain_urls"] == 1

    def test_valid_urls_not_flagged(self, collector):
        """完整 URL 不触发任何告警"""
        entities = {
            "providers": [
                {"id": "a", "name": "A",
                 "last_event_url": "https://example.com/articles/123",
                 "last_event_date": "2026-07-10", "confidence": "high"},
                {"id": "b", "name": "B",
                 "last_event_url": "https://qbitai.com/post/456",
                 "last_event_date": "2026-07-10", "confidence": "high"},
            ],
            "people": [],
            "tools": [],
            "llms": [],
            "hotspots": [],
        }
        stats = collector._validate_entity_urls(entities)
        assert stats["empty_urls"] == 0
        assert stats["truncated_urls"] == 0
        assert stats["bare_domain_urls"] == 0

    def test_all_dimensions_scanned(self, collector):
        """所有维度都被扫描"""
        entities = {
            "providers": [{"id": "a", "name": "A", "last_event_url": "",
                           "last_event_date": "2026-07-10", "confidence": "high"}],
            "people": [{"id": "p", "name": "P", "recent_activity_url": "",
                        "recent_activity_date": "2026-07-10", "confidence": "high"}],
            "tools": [{"id": "t", "name": "T", "last_update_url": "...",
                       "last_update_date": "2026-07-10", "confidence": "high"}],
            "llms": [{"id": "l", "name": "L", "last_event_url": "",
                      "last_event_date": "2026-07-10", "confidence": "high"}],
            "hotspots": [{"id": "h", "title": "H", "url": "https://example.com",
                          "date": "2026-07-10", "confidence": "high"}],
        }
        stats = collector._validate_entity_urls(entities)
        assert stats["empty_urls"] == 3  # provider + people + llms
        assert stats["truncated_urls"] == 1  # tools
        assert stats["bare_domain_urls"] == 1  # hotspot


class TestDataCompleteness:
    def test_key_people_empty_ratio(self, collector):
        """key_people 为空的比例被统计"""
        entities = {
            "providers": [
                {"id": "a", "name": "A", "last_event_date": "2026-07-10",
                 "confidence": "high", "key_people": []},
                {"id": "b", "name": "B", "last_event_date": "2026-07-10",
                 "confidence": "high", "key_people": ["Sam-CEO"]},
            ],
            "people": [],
            "tools": [],
            "llms": [],
            "hotspots": [],
        }
        stats = collector._validate_data_completeness(entities)
        assert stats["key_people_empty_ratio"] == 0.5

    def test_focus_areas_empty_ratio(self, collector):
        """focus_areas 为空的比例被统计"""
        entities = {
            "providers": [
                {"id": "a", "name": "A", "last_event_date": "2026-07-10",
                 "confidence": "high", "focus_areas": []},
                {"id": "b", "name": "B", "last_event_date": "2026-07-10",
                 "confidence": "high", "focus_areas": ["NLP"]},
                {"id": "c", "name": "C", "last_event_date": "2026-07-10",
                 "confidence": "high", "focus_areas": []},
            ],
            "people": [],
            "tools": [],
            "llms": [],
            "hotspots": [],
        }
        stats = collector._validate_data_completeness(entities)
        assert stats["focus_areas_empty_ratio"] == 2/3

    def test_low_confidence_count(self, collector):
        """low confidence 条目被计数"""
        entities = {
            "providers": [
                {"id": "a", "name": "A", "last_event_date": "2026-07-10",
                 "confidence": "low", "last_event_url": ""},
                {"id": "b", "name": "B", "last_event_date": "2026-07-10",
                 "confidence": "low", "last_event_url": "https://x.com/article"},
                {"id": "c", "name": "C", "last_event_date": "2026-07-10",
                 "confidence": "high"},
            ],
            "people": [],
            "tools": [],
            "llms": [],
            "hotspots": [],
        }
        stats = collector._validate_data_completeness(entities)
        assert stats["low_confidence_count"] == 2

    def test_all_providers_have_kp_no_issue(self, collector):
        """所有 provider 都有 key_people 时比例为 0"""
        entities = {
            "providers": [
                {"id": "a", "name": "A", "last_event_date": "2026-07-10",
                 "confidence": "high", "key_people": ["X-CTO"]},
                {"id": "b", "name": "B", "last_event_date": "2026-07-10",
                 "confidence": "high", "key_people": ["Y-CEO"]},
            ],
            "people": [],
            "tools": [],
            "llms": [],
            "hotspots": [],
        }
        stats = collector._validate_data_completeness(entities)
        assert stats["key_people_empty_ratio"] == 0.0
