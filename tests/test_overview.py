"""Test overview.json generation."""
import json
import pytest


class TestOverviewJson:
    def test_overview_generated_after_merge(self, temp_snapshot):
        """merge 后 overview.json 被生成"""
        new = {"providers": [{"id": "ov-test", "name": "OvTest",
                              "last_event_date": "2026-07-14",
                              "hot_score": 80, "confidence": "high"}]}
        temp_snapshot.merge_entities(new)

        path = temp_snapshot.project_root / 'overview.json'
        assert path.exists()

        data = json.loads(path.read_text())
        assert data['v'] == 1
        assert data['t']
        assert data['p']
        assert 's' in data
        assert data['s']['pr'] >= 1  # at least openai from SAMPLE
        assert 'h' in data
        assert 'r' in data
        assert data['r'] in ('success', 'failed')

    def test_overview_stats_counts(self, temp_snapshot):
        """各维度计数正确"""
        new = {
            "providers": [{"id": "p1", "name": "P1", "confidence": "high"}],
            "people": [{"id": "e1", "name": "E1", "confidence": "high"},
                       {"id": "e2", "name": "E2", "confidence": "high"}],
            "tools": [{"id": "t1", "name": "T1", "confidence": "high"}],
            "llms": [],
            "hotspots": [{"id": "h1", "title": "H1", "date": "2026-07-14",
                         "summary": "test"}],
        }
        temp_snapshot.merge_entities(new)

        data = json.loads(
            (temp_snapshot.project_root / 'overview.json').read_text())
        s = data['s']
        assert s['pr'] >= 2   # SAMPLE openai + new p1
        assert s['pe'] >= 3   # SAMPLE sam-altman + e1 + e2
        assert s['to'] >= 1
        assert s['ho'] >= 1

    def test_overview_hotspots_top3(self, temp_snapshot):
        """h 数组包含 Top 3 热点"""
        new = {
            "providers": [], "people": [], "tools": [], "llms": [],
            "hotspots": [
                {"id": "h1", "title": "Hot 1", "date": "2026-07-14",
                 "summary": "t1", "hot_score": 90},
                {"id": "h2", "title": "Hot 2", "date": "2026-07-13",
                 "summary": "t2", "hot_score": 80},
                {"id": "h3", "title": "Hot 3", "date": "2026-07-12",
                 "summary": "t3", "hot_score": 70},
                {"id": "h4", "title": "Hot 4", "date": "2026-07-11",
                 "summary": "t4", "hot_score": 60},
            ],
        }
        temp_snapshot.merge_entities(new)

        data = json.loads(
            (temp_snapshot.project_root / 'overview.json').read_text())
        assert len(data['h']) == 3
        assert data['h'][0]['t'] == 'Hot 1'
        assert data['h'][2]['t'] == 'Hot 3'

    def test_overview_failed_status(self, temp_snapshot):
        """gate fail → r='failed' + rd 非空"""
        temp_snapshot._quality_detail = '空 URL: 5 条'
        new = {"providers": [{"id": "fail", "name": "Fail",
                              "confidence": "high"}]}
        temp_snapshot.merge_entities(new, quality_ok=False)

        data = json.loads(
            (temp_snapshot.project_root / 'overview.json').read_text())
        assert data['r'] == 'failed'
        assert '空 URL' in data['rd']

    def test_overview_compact_format(self, temp_snapshot):
        """输出为紧凑 JSON（无缩进空格）"""
        new = {"providers": [{"id": "cmp", "name": "Cmp",
                              "confidence": "high"}]}
        temp_snapshot.merge_entities(new)

        raw = (temp_snapshot.project_root / 'overview.json').read_text()
        assert raw.count('\n') <= 1  # at most 1 line or compact
        assert len(raw) < 2000  # under 2KB
