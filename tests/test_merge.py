"""Test merge_entities: normal merge, missing id, name dedup, edge cases."""
import pytest

class TestMergeEntities:
    def test_normal_merge(self, collector):
        new = {"providers": [{"id": "anthropic", "name": "Anthropic",
                              "country": "美国", "hot_score": 90,
                              "confidence": "high"}]}
        result = collector.merge_entities(new)
        assert result is not None
        assert result["stats"]["new_this_period"] >= 1

    def test_merge_existing_id(self, collector):
        new = {"providers": [{"id": "openai", "name": "OpenAI",
                              "country": "美国", "hot_score": 99,
                              "confidence": "high"}]}
        result = collector.merge_entities(new)
        providers = result["providers"]
        updated = [p for p in providers if p["id"] == "openai"]
        assert updated[0]["hot_score"] == 99
        assert result["stats"]["updated_this_period"] >= 1

    def test_merge_no_id(self, collector):
        new = {"providers": [{"name": "NoID", "country": "中国",
                              "hot_score": 50, "confidence": "medium"}]}
        result = collector.merge_entities(new)
        assert result is not None

    def test_merge_empty(self, collector):
        assert collector.merge_entities({}) is None
        assert collector.merge_entities(None) is None

    def test_merge_name_dedup(self, collector):
        new = {"providers": [{"id": "openai-2", "name": "OpenAI",
                              "country": "美国", "hot_score": 92,
                              "confidence": "high"}]}
        result = collector.merge_entities(new)
        count = sum(1 for p in result["providers"] if p["name"] == "OpenAI")
        assert count == 1

    def test_merge_all_dimensions(self, collector):
        new = {
            "providers": [{"id": "tp", "name": "TP", "confidence": "high"}],
            "people": [{"id": "tpe", "name": "TPe", "confidence": "high"}],
            "tools": [{"id": "tt", "name": "TT", "confidence": "high"}],
            "llms": [{"id": "tl", "name": "TL", "confidence": "high"}],
            "hotspots": [{"id": "th", "title": "TH", "date": "2026-06-28",
                          "summary": "t", "confidence": "high"}],
        }
        result = collector.merge_entities(new)
        for dim in ["providers", "people", "tools", "llms", "hotspots"]:
            assert result["stats"][f"total_{dim}"] >= 1

    def test_changelog_on_new(self, collector):
        new = {"providers": [{"id": "cl-test", "name": "CLTest",
                              "confidence": "high"}]}
        result = collector.merge_entities(new)
        assert any(e["type"] == "new" for e in result.get("changelog", []))
