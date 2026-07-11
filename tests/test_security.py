"""Test security fixes: MCP API Key handling, no hardcoded defaults."""
import os
import sys
import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestMCPApiKey:
    """LR-SEC-001: MCP Server API Key 不从硬编码默认值启动."""

    def test_key_from_env_used(self, monkeypatch):
        """设置环境变量时使用正确的 key"""
        monkeypatch.setenv('LLM_RADAR_MCP_KEY', 'my-secure-test-key')

        # 重新导入以获取新 key
        spec = importlib.util.spec_from_file_location(
            "mcp_server", str(PROJECT_ROOT / "llm-radar-mcp-server.py"))
        # monkeypatch stdin 避免阻塞
        import io
        monkeypatch.setattr(sys, 'stdin', io.StringIO(""))

        mod = importlib.util.module_from_spec(spec)
        # 不清除 os.environ — 使用已注入的 monkeypatch 值
        spec.loader.exec_module(mod)

        assert mod.API_KEY == 'my-secure-test-key', \
            f"Expected 'my-secure-test-key', got '{mod.API_KEY}'"

    def test_no_key_auto_generates(self, monkeypatch):
        """未设置环境变量时自动生成随机 key"""
        monkeypatch.delenv('LLM_RADAR_MCP_KEY', raising=False)

        import io
        monkeypatch.setattr(sys, 'stdin', io.StringIO(""))
        # 也重定向 stderr 避免警告刷屏
        monkeypatch.setattr(sys, 'stderr', io.StringIO())

        spec = importlib.util.spec_from_file_location(
            "mcp_server2", str(PROJECT_ROOT / "llm-radar-mcp-server.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # 应该生成了一个非空的随机 key（64 hex chars）
        assert mod.API_KEY, "API_KEY should not be empty"
        assert len(mod.API_KEY) == 64, \
            f"Expected 64-char hex key, got {len(mod.API_KEY)}: '{mod.API_KEY[:8]}...'"
        # 确认只有 hex 字符
        assert all(c in '0123456789abcdef' for c in mod.API_KEY), \
            f"Key should be hex only, got: {mod.API_KEY[:8]}..."

    def test_no_default_hardcoded_key(self, monkeypatch):
        """确认没有硬编码的默认 key（已移除 'llm-radar-mcp-2026'）"""
        monkeypatch.delenv('LLM_RADAR_MCP_KEY', raising=False)

        import io
        monkeypatch.setattr(sys, 'stdin', io.StringIO(""))
        monkeypatch.setattr(sys, 'stderr', io.StringIO())

        spec = importlib.util.spec_from_file_location(
            "mcp_server3", str(PROJECT_ROOT / "llm-radar-mcp-server.py"))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        assert mod.API_KEY != 'llm-radar-mcp-2026', \
            "Hardcoded default key should be removed"


class TestMCPSubmitNoHardcode:
    """LR-SEC-001: scripts/mcp_submit_update.py 不硬编码 key."""

    def test_no_hardcoded_key_in_source(self):
        """确认源码中不含硬编码的默认 key"""
        path = PROJECT_ROOT / "scripts" / "mcp_submit_update.py"
        content = path.read_text()
        assert "llm-radar-mcp-2026" not in content, \
            "Hardcoded key should not appear in submit script"


class TestMCPDemoNoHardcode:
    """LR-SEC-001: scripts/mcp-protocol-demo.py 不硬编码 key."""

    def test_no_hardcoded_key_in_source(self):
        """确认源码中不含硬编码的默认 key"""
        path = PROJECT_ROOT / "scripts" / "mcp-protocol-demo.py"
        content = path.read_text()
        assert "llm-radar-mcp-2026" not in content, \
            "Hardcoded key should not appear in demo script"
