"""Test fixtures for llm-radar-collector tests."""
import importlib.util, json, os, tempfile
from pathlib import Path
import pytest

PROJECT_ROOT = Path("/Users/jadenli/CodeSpace/llm-radar.jaden.tech")

def import_collector():
    path = str(PROJECT_ROOT / "llm-radar-collector.py")
    spec = importlib.util.spec_from_file_location("collector", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

SAMPLE_SNAPSHOT = {
    "providers": [{"id": "openai", "name": "OpenAI", "country": "美国",
                   "hot_score": 95, "hot_level": "爆热",
                   "last_event": "GPT-5.5 released", "last_event_date": "2026-06-28",
                   "confidence": "high", "updated_at": "2026-06-28T10:00:00"}],
    "people": [{"id": "sam-altman", "name": "Sam Altman", "title": "OpenAI CEO",
                "hot_score": 90, "confidence": "high", "updated_at": "2026-06-28T10:00:00"}],
    "tools": [], "llms": [], "hotspots": [],
    "changelog": [],
    "stats": {"total_providers": 1, "total_people": 1, "total_tools": 0,
              "total_llms": 0, "total_hotspots": 0, "new_this_period": 0, "updated_this_period": 0},
    "generated_at": "2026-06-28T10:00:00"
}

@pytest.fixture
def collector():
    mod = import_collector()
    c = mod.LLMRadarCollector()
    c.api_key = "test-key"
    c._print_ok = lambda msg: None
    c._print_err = lambda msg: None
    c._print_info = lambda msg: None
    c._print_warn = lambda msg: None
    return c

@pytest.fixture
def temp_snapshot(collector):
    original = collector.SNAPSHOT_PATH
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(SAMPLE_SNAPSHOT, tmp, indent=2, ensure_ascii=False)
    tmp.close()
    collector.SNAPSHOT_PATH = Path(tmp.name)
    collector.DATA_DIR = Path(tmp.name).parent
    yield collector
    os.unlink(tmp.name)
    collector.SNAPSHOT_PATH = original
