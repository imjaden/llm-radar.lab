"""Test timestamp.json health-check endpoint generation."""
import json
import pytest
from datetime import datetime


class TestTimestampJson:
    def test_timestamp_generated_after_merge(self, temp_snapshot):
        """merge 后 timestamp.json 被生成"""
        new = {"providers": [{"id": "ts-test", "name": "TsTest",
                              "last_event_date": "2026-07-13",
                              "hot_score": 80, "confidence": "high"}]}
        result = temp_snapshot.merge_entities(new)

        ts_path = temp_snapshot.project_root / 'timestamp.json'
        assert ts_path.exists(), f"timestamp.json not found at {ts_path}"

        data = json.loads(ts_path.read_text())
        assert data['version'] == '1.0'
        assert data['generated_at'], "generated_at should not be empty"
        assert data['last_news_date'] >= '2026-07-13', \
            f"Expected >= 2026-07-13, got {data['last_news_date']}"
        assert data['entity_count'] >= 1
        assert data['period'], "period should not be empty"

    def test_last_news_date_is_max(self, temp_snapshot):
        """last_news_date 是所有实体中最新的事件日期"""
        new = {
            "providers": [
                {"id": "old-co", "name": "OldCo",
                 "last_event_date": "2026-07-01",
                 "hot_score": 50, "confidence": "high"},
                {"id": "new-co", "name": "NewCo",
                 "last_event_date": "2026-07-13",
                 "hot_score": 80, "confidence": "high"},
            ],
            "people": [],
            "tools": [],
            "llms": [],
            "hotspots": [],
        }
        temp_snapshot.merge_entities(new)

        data = json.loads(
            (temp_snapshot.project_root / 'timestamp.json').read_text())
        assert data['last_news_date'] == '2026-07-13'

    def test_no_entities_handled(self, temp_snapshot):
        """空维度数组不崩溃，使用已有 snapshot"""
        # merge_entities({}) 提前返回 — 用空维度但非空 dict 触发
        new = {"providers": [], "people": [], "tools": [], "llms": [],
               "hotspots": []}
        temp_snapshot.merge_entities(new)

        data = json.loads(
            (temp_snapshot.project_root / 'timestamp.json').read_text())
        # 至少包含 SAMPLE_SNAPSHOT 的 openai + sam-altman (来自 temp_snapshot 初始化)
        assert data['entity_count'] >= 1
        assert data['version'] == '1.0'
