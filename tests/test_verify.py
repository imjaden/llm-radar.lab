"""Test _verify: quality gate (LLM-RADAR-CL005).

质量门禁放宽: 热点数量从阻断项降为 warning; 实体 0（4 维度全空）仍阻断。
"""
import datetime


def _recent():
    return (datetime.datetime.now() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')


class TestVerifyQualityGate:
    def test_hotspots_zero_but_entities_ok(self, collector):
        """热点 0 条但实体>0 → issues 空（通过）; 热点进入 warnings"""
        entities = {
            "providers": [{"id": "p1", "name": "P1", "last_event_date": _recent(),
                           "confidence": "high"}],
            "people": [], "tools": [], "llms": [],
            "hotspots": [],
        }
        issues = collector._verify(entities)
        assert issues == []
        assert any('热点仅 0 条' in w for w in collector._quality_warnings)

    def test_hotspots_below_three_warns(self, collector):
        """热点 1 条 → warning 不阻断"""
        entities = {
            "providers": [{"id": "p1", "name": "P1", "last_event_date": _recent(),
                           "confidence": "high"}],
            "people": [], "tools": [], "llms": [],
            "hotspots": [{"id": "h1", "title": "H1", "date": _recent()}],
        }
        issues = collector._verify(entities)
        assert issues == []
        assert any('热点仅 1 条' in w for w in collector._quality_warnings)

    def test_all_empty_fails(self, collector):
        """4 实体维度全空（热点可有可无）→ issues 非空（阻断, 防空快照覆盖）"""
        entities = {
            "providers": [], "people": [], "tools": [], "llms": [],
            "hotspots": [{"id": "h1", "title": "H1", "date": _recent()}],
        }
        issues = collector._verify(entities)
        assert issues, "实体 0 应阻断"
        assert any('实体提取为空' in i for i in issues)

    def test_hotspot_count_ok_when_three(self, collector):
        """热点 ≥3 → 无热点 warning"""
        entities = {
            "providers": [{"id": "p1", "name": "P1", "last_event_date": _recent(),
                           "confidence": "high"}],
            "people": [], "tools": [], "llms": [],
            "hotspots": [{"id": f"h{i}", "title": f"H{i}", "date": _recent()}
                         for i in range(3)],
        }
        issues = collector._verify(entities)
        assert issues == []
        assert not any('热点仅' in w for w in collector._quality_warnings)
