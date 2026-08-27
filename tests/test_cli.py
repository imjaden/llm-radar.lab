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


def test_cli_run_force_help_intercepted():
    """LR-SEC-011: run --force help 绕过首位检查, 全 args 扫描仍拦截"""
    r = subprocess.run(
        ["python3", COLLECTOR, "run", "--force", "help"],
        capture_output=True, text=True, timeout=10)
    assert r.returncode == 0
    assert "用法" in r.stdout
    assert "DEEPSEEK" not in r.stdout  # 未触发采集


def test_cli_fetch_source_help_intercepted():
    """LR-SEC-011: fetch qbitai help 非首位参数, 仍拦截"""
    r = subprocess.run(
        ["python3", COLLECTOR, "fetch", "qbitai", "help"],
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


# ===== prompt 子命令 (LLM-RADAR-CL004: skills 供给站, 对齐 hs _cmd_prompt) =====
EXPECTED_SKILLS = {"github-workflow", "x-twitter-collector"}


def _run_prompt(*args):
    return subprocess.run(
        ["python3", COLLECTOR, "prompt", *args],
        capture_output=True, text=True, timeout=30)


def test_cli_prompt_list():
    """无参: 列出双 skill + 用法行"""
    r = _run_prompt()
    assert r.returncode == 0
    assert "可用 skills:" in r.stdout
    for name in EXPECTED_SKILLS:
        assert name in r.stdout
        assert f"llm-radar prompt {name}" in r.stdout


def test_cli_prompt_detail():
    """<name>: SKILL.md 全文 + 关键章节"""
    r = _run_prompt("x-twitter-collector")
    assert r.returncode == 0
    assert "# x-twitter-collector" in r.stdout
    assert "CLI 签名" in r.stdout
    assert "登录态" in r.stdout


def test_cli_prompt_brief():
    """--brief: description + 章节:"""
    r = _run_prompt("x-twitter-collector", "--brief")
    assert r.returncode == 0
    assert "Use when operating" in r.stdout
    assert "章节:" in r.stdout
    assert "CLI 签名" in r.stdout


def test_cli_prompt_json_list():
    """--json 无参: status ok + 精确集合 {github-workflow, x-twitter-collector}"""
    r = _run_prompt("--json")
    assert r.returncode == 0
    d = json.loads(r.stdout)
    assert d["status"] == "ok"
    assert d["error"] == ""
    names = {item["name"] for item in d["data"]}
    assert names == EXPECTED_SKILLS
    assert all(item["description"] for item in d["data"])


def test_cli_prompt_json_detail():
    """<name> --json: data.name + data.content 含正文"""
    r = _run_prompt("x-twitter-collector", "--json")
    assert r.returncode == 0
    d = json.loads(r.stdout)
    assert d["status"] == "ok"
    assert d["data"]["name"] == "x-twitter-collector"
    assert "CLI 签名" in d["data"]["content"]


def test_cli_prompt_not_found():
    """<不存在>: exit 1 + stderr 报错 + stdout 可用列表"""
    r = _run_prompt("nope")
    assert r.returncode == 1
    assert "skill 'nope' 不存在" in r.stderr
    for name in EXPECTED_SKILLS:
        assert name in r.stdout


def test_cli_prompt_json_not_found():
    """RIG-002: <不存在> --json → status error 信封 + exit 1"""
    r = _run_prompt("nope", "--json")
    assert r.returncode == 1
    d = json.loads(r.stdout)
    assert d["status"] == "error"
    assert d["data"] is None
    assert "不存在" in d["error"]


def test_cli_prompt_no_key_log():
    """prompt 不实例化 collector: stdout/stderr 无 'DeepSeek API key'"""
    r = _run_prompt()
    assert r.returncode == 0
    assert "DeepSeek API key" not in (r.stdout + r.stderr)
