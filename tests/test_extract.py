"""Test JSON parsing: 3-level fallback for LLM output."""
import pytest

class TestJsonParsing:
    def test_parse_clean_json(self, collector):
        r = collector._parse_json_output('{"providers": [{"id": "t1", "name": "T"}]}')
        assert r is not None and r["providers"][0]["id"] == "t1"

    def test_parse_code_block(self, collector):
        r = collector._parse_json_output(
            'text\n```json\n{"tools": [{"id": "t2"}]}\n```\nend')
        assert r is not None and "tools" in r

    def test_parse_truncated(self, collector):
        r = collector._parse_json_output('{"people": [{"id": "p1", "name": "P"')
        assert r is None or isinstance(r, dict)

    def test_parse_invalid(self, collector):
        assert collector._parse_json_output("garbage") is None

    def test_parse_empty(self, collector):
        assert collector._parse_json_output("") is None

    def test_parse_large(self, collector):
        items = ','.join(f'{{"id":"i{i}","name":"n{i}"}}' for i in range(100))
        r = collector._parse_json_output('{"tools": [' + items + ']}')
        assert r is not None and len(r["tools"]) == 100
