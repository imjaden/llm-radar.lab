"""Test timestamp.json health-check endpoint with status fields."""
import json
import pytest
from datetime import datetime, timedelta

# 使用相对日期: 新实体必须落在 14 天新实体过滤窗口内(collector 按当前真实日期过滤)
_RECENT = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
_OLDER = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')


class TestTimestampJson:
    def test_timestamp_generated_after_merge(self, temp_snapshot):
        """merge 后 timestamp.json 包含所有新字段"""
        new = {"providers": [{"id": "ts-test", "name": "TsTest",
                              "last_event_date": _RECENT,
                              "hot_score": 80, "confidence": "high"}]}
        temp_snapshot.merge_entities(new)

        ts_path = temp_snapshot.project_root / 'timestamp.json'
        assert ts_path.exists()

        data = json.loads(ts_path.read_text())
        assert data['version'] == '1.0'
        assert data['generated_at']
        assert data['last_news_date'] >= _RECENT
        assert data['entity_count'] >= 1
        assert data['period']
        # 新字段
        assert data['last_run_at']
        assert data['last_run_status'] in ('success', 'failed')
        assert 'last_run_detail' in data
        assert data['server'] in ('mac', 'linux')
        assert data['hostname']

    def test_last_news_date_is_max(self, temp_snapshot):
        """last_news_date 是所有实体中最新的事件日期"""
        new = {
            "providers": [
                {"id": "old-co", "name": "OldCo",
                 "last_event_date": _OLDER,
                 "hot_score": 50, "confidence": "high"},
                {"id": "new-co", "name": "NewCo",
                 "last_event_date": _RECENT,
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
        assert data['last_news_date'] == _RECENT

    def test_status_success_when_no_issues(self, temp_snapshot):
        """质量门禁通过时 status 为 success"""
        new = {"providers": [{"id": "ok-co", "name": "OkCo",
                              "last_event_date": _RECENT,
                              "hot_score": 80, "confidence": "high"}]}
        temp_snapshot.merge_entities(new, quality_ok=True)

        data = json.loads(
            (temp_snapshot.project_root / 'timestamp.json').read_text())
        assert data['last_run_status'] == 'success'
        assert data['last_run_detail'] == ''

    def test_status_failed_with_detail(self, temp_snapshot):
        """质量门禁失败时 status=failed + detail 非空"""
        temp_snapshot._quality_detail = '空 URL: 8 条; key_people 缺失率 81%'
        new = {"providers": [{"id": "fail-co", "name": "FailCo",
                              "last_event_date": _RECENT,
                              "hot_score": 80, "confidence": "high"}]}
        temp_snapshot.merge_entities(new, quality_ok=False)

        data = json.loads(
            (temp_snapshot.project_root / 'timestamp.json').read_text())
        assert data['last_run_status'] == 'failed'
        assert '空 URL' in data['last_run_detail']
        assert 'key_people' in data['last_run_detail']

    def test_empty_dimensions_works(self, temp_snapshot):
        """空维度数组不崩溃"""
        new = {"providers": [], "people": [], "tools": [], "llms": [],
               "hotspots": []}
        temp_snapshot.merge_entities(new)

        data = json.loads(
            (temp_snapshot.project_root / 'timestamp.json').read_text())
        assert data['entity_count'] >= 1
        assert data['version'] == '1.0'
