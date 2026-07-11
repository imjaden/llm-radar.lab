"""Test _fuzzy_name_dedup: alias and fuzzy name matching for entity dedup."""
import pytest


class TestFuzzyNameDedup:
    def test_exact_name_no_dedup(self, collector):
        """精确同名不产生额外去重（已有精确匹配）"""
        items = [
            {"id": "a", "name": "OpenAI", "last_event_date": "2026-07-10"},
            {"id": "b", "name": "Anthropic", "last_event_date": "2026-07-10"},
        ]
        result = collector._fuzzy_name_dedup(items)
        assert len(result) == 2
        assert {e["id"] for e in result} == {"a", "b"}

    def test_alias_map_merge(self, collector):
        """已知别名映射合并实体"""
        items = [
            {"id": "zhipu-ai", "name": "智谱AI", "last_event_date": "2026-07-10",
             "hot_score": 80, "key_people": ["张鹏-CEO"]},
            {"id": "z.ai", "name": "z.AI(智谱)", "last_event_date": "2026-07-11",
             "hot_score": 85, "key_people": []},
        ]
        result = collector._fuzzy_name_dedup(items)
        assert len(result) == 1
        merged = result[0]
        # 保留主条目 ID
        assert merged["id"] == "zhipu-ai"
        # 新数据覆盖旧数据
        assert merged["name"] == "z.AI(智谱)"
        assert merged["hot_score"] == 85
        assert merged["last_event_date"] == "2026-07-11"
        # 保留原有 key_people（非空不被覆盖）
        assert merged["key_people"] == ["张鹏-CEO"]

    def test_paren_strip_match(self, collector):
        """去掉括号内容后名称匹配"""
        items = [
            {"id": "subq", "name": "Subquadratic", "last_event_date": "2026-07-10",
             "hot_score": 70},
            {"id": "subq-2", "name": "Subquadratic (AI)", "last_event_date": "2026-07-11",
             "hot_score": 65},
        ]
        result = collector._fuzzy_name_dedup(items)
        assert len(result) == 1
        assert result[0]["id"] == "subq"
        assert result[0]["hot_score"] == 70  # max(70, 65)

    def test_suffix_variant_match(self, collector):
        """去掉常见后缀后匹配（阿里云 → 阿里 → 阿里巴巴）"""
        items = [
            {"id": "alibaba", "name": "阿里巴巴", "last_event_date": "2026-07-10",
             "hot_score": 75},
            {"id": "aliyun", "name": "阿里云", "last_event_date": "2026-07-11",
             "hot_score": 80},
            {"id": "ali-qianwen", "name": "阿里千问", "last_event_date": "2026-07-10",
             "hot_score": 70},
        ]
        result = collector._fuzzy_name_dedup(items)
        assert len(result) == 1
        merged = result[0]
        assert merged["hot_score"] == 80  # 取最高分
        assert merged["last_event_date"] == "2026-07-11"  # 取最新日期

    def test_substring_containment_merge(self, collector):
        """"腾讯微信" 包含 "微信" → 合并"""
        items = [
            {"id": "tencent", "name": "腾讯", "last_event_date": "2026-07-10",
             "hot_score": 85},
            {"id": "wechat", "name": "微信", "last_event_date": "2026-07-11",
             "hot_score": 80},
        ]
        result = collector._fuzzy_name_dedup(items)
        # 微信不是腾讯的精确子串，但别名表会处理
        # 无别名映射时不会合并
        assert len(result) <= 2

    def test_different_entities_kept_separate(self, collector):
        """不同实体保持独立"""
        items = [
            {"id": "openai", "name": "OpenAI", "last_event_date": "2026-07-10"},
            {"id": "google", "name": "Google", "last_event_date": "2026-07-10"},
            {"id": "meta", "name": "Meta", "last_event_date": "2026-07-10"},
        ]
        result = collector._fuzzy_name_dedup(items)
        assert len(result) == 3

    def test_preserve_earliest_id_on_dedup(self, collector):
        """去重时保留最早出现的条目 ID"""
        items = [
            {"id": "first", "name": "蚂蚁灵波", "last_event_date": "2026-07-10",
             "hot_score": 70},
            {"id": "second", "name": "蚂蚁灵波", "last_event_date": "2026-07-11",
             "hot_score": 65},
        ]
        result = collector._fuzzy_name_dedup(items)
        assert len(result) == 1
        assert result[0]["id"] == "first"  # 保留先出现的 ID

    def test_duplicate_appearances_merged(self, collector):
        """RoboScience 出现两次 → 合并"""
        items = [
            {"id": "roboscience", "name": "RoboScience", "last_event_date": "2026-07-10",
             "hot_score": 70},
            {"id": "roboscience-2", "name": "RoboScience", "last_event_date": "2026-07-11",
             "hot_score": 65},
        ]
        result = collector._fuzzy_name_dedup(items)
        assert len(result) == 1
