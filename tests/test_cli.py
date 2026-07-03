"""Test CLI command dispatch."""
import sys, subprocess
from pathlib import Path

COLLECTOR = str(Path(__file__).resolve().parent.parent / "llm-radar-collector.py")

def test_cli_sources():
    r = subprocess.run(
        ["python3", COLLECTOR, "sources"],
        capture_output=True, text=True, timeout=30)
    assert r.returncode == 0
    assert "新闻源" in r.stdout

def test_cli_help():
    r = subprocess.run(
        ["python3", COLLECTOR, "help"],
        capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    assert "selenium-check" in r.stdout

def test_cli_selenium_check():
    r = subprocess.run(
        ["python3", COLLECTOR, "selenium-check"],
        capture_output=True, text=True, timeout=60)
    # Should complete without crash (may pass or fail checks)
    assert r.returncode == 0
