"""Test CLI command dispatch."""
import json
import sys
import subprocess
from pathlib import Path

COLLECTOR = str(Path(__file__).resolve().parent.parent / "llm-radar-collector.py")

GROUPS = ["【采集执行】", "【数据管理】", "【Git 集成】", "【定时任务】", "【其他】"]


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


def test_cli_no_args_grouped_help():
    """验收 #5: 空入参 → 打印分组 help exit=0"""
    r = subprocess.run(
        ["python3", COLLECTOR],
        capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    for g in GROUPS:
        assert g in r.stdout


def test_cli_help_grouped():
    """验收 #1: help 输出 hm-style 分组 (5 组)"""
    r = subprocess.run(
        ["python3", COLLECTOR, "help"],
        capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    for g in GROUPS:
        assert g in r.stdout
    assert "📖 LLM Radar" in r.stdout
    assert "status [--json]" in r.stdout


def test_cli_run_help_intercepted():
    """positional help 拦截: run help 不触发采集"""
    r = subprocess.run(
        ["python3", COLLECTOR, "run", "help"],
        capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    assert "用法" in r.stdout


def test_cli_fetch_help_intercepted():
    r = subprocess.run(
        ["python3", COLLECTOR, "fetch", "help"],
        capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    assert "用法" in r.stdout


def test_cli_commit_help_intercepted():
    """commit help 不会真的 commit (禁止当参数执行)"""
    r = subprocess.run(
        ["python3", COLLECTOR, "commit", "help"],
        capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    assert "用法" in r.stdout
    assert "commit 完成" not in r.stdout


def test_cli_crontab_help_no_side_effect():
    """验收 #6: crontab help 显示用法 exit=0, 不执行任何副作用"""
    r = subprocess.run(
        ["python3", COLLECTOR, "crontab", "help"],
        capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    assert "crontab" in r.stdout


def test_cli_status_json():
    """验收 #2: status --json 七字段齐全, stdout 纯 JSON"""
    r = subprocess.run(
        ["python3", COLLECTOR, "status", "--json"],
        capture_output=True, text=True, timeout=30)
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert set(data) == {"id", "label", "status", "icon", "message", "checks", "actions"}
    assert data["status"] in ("ok", "warning", "critical", "info")
    assert data["id"] == "llm-radar"
    assert len(data["checks"]) >= 1
    assert len(data["actions"]) >= 1
    assert "🟢🟡🔴ℹ️".find(data["icon"]) >= 0


def test_cli_status_text():
    """无 --json → 单行文本摘要"""
    r = subprocess.run(
        ["python3", COLLECTOR, "status"],
        capture_output=True, text=True, timeout=30)
    assert r.returncode == 0
    assert r.stdout.startswith("LLM Radar: ")
