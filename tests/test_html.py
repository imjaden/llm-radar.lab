"""Selenium tests: verify HTML pages load without JavaScript errors."""
import json
import re
import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _check_js_syntax(html_path):
    """Check HTML for obvious JavaScript syntax errors without browser.

    仅检查 <script> 块(JS 对象字面量);排除 <style> 块 —— CSS 属性
    (如 font-size:0.7rem) 不带引号是合法写法, 不属于 JS 语法检查范围。
    2026-08-15 修复: 此前正则扫描整个文件, 把 CSS 属性/伪类误判为 unquoted key。
    """
    content = html_path.read_text()
    errors = []

    # 剔除 <style>...</style> 块, 仅保留 <script> 块内容供扫描
    js_blocks = re.findall(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", content, re.S)

    # 1. Unquoted object keys with hyphens
    for bi, block in enumerate(js_blocks, 1):
        for i, line in enumerate(block.split('\n'), 1):
            # Find unquoted keys with hyphens in object literals
            matches = re.findall(r"(?<!['\"\w])([a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)+)\s*:", line)
            for m in matches:
                errors.append(f"L{bi}:{i}: unquoted hyphen key '{m}'")

    # 2. Trailing commas in object literals (仅 script 块)
    for bi, block in enumerate(js_blocks, 1):
        for i, line in enumerate(block.split('\n'), 1):
            if re.search(r",\s*}", line.strip()):
                errors.append(f"L{bi}:{i}: trailing comma before }}")

    return errors


class TestHtmlJsSyntax:
    def test_changelog_html_no_js_errors(self):
        """changelog.html 无 JS 语法错误"""
        path = PROJECT_ROOT / 'changelog.html'
        errors = _check_js_syntax(path)
        assert not errors, f"JS syntax errors in changelog.html:\n" + "\n".join(errors)

    def test_index_html_no_js_errors(self):
        """index.html 无 JS 语法错误"""
        path = PROJECT_ROOT / 'index.html'
        errors = _check_js_syntax(path)
        assert not errors, f"JS syntax errors in index.html:\n" + "\n".join(errors)

    def test_emoji_map_keys_all_quoted(self):
        """EMOJI_MAP 中所有含连字符的 key 都已加引号"""
        for html_file in ['changelog.html', 'index.html']:
            content = (PROJECT_ROOT / html_file).read_text()
            # 仅扫描 <script> 块(排除 <style> 块: CSS 属性不带引号合法)
            js_blocks = re.findall(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", content, re.S)
            bad = []
            for block in js_blocks:
                for m in re.finditer(
                        r"(?<!['\"\w])([a-zA-Z0-9]+(?:-[a-zA-Z0-9]+)+)\s*:",
                        block):
                    if not block[max(0, m.start()-1):m.start()].endswith(("'", '"')):
                        bad.append(m.group(1))
            assert not bad, f"{html_file}: unquoted keys: {bad}"


class TestSeleniumPageLoad:
    """Browser-based test: load pages and check for console errors.
    Requires: selenium, webdriver-manager, Chrome.
    """

    @pytest.mark.selenium
    def test_changelog_loads_without_js_errors(self):
        """changelog.html 在浏览器中无 console 错误"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
        except ImportError:
            pytest.skip("selenium not installed")

        import tempfile, os, subprocess

        opts = Options()
        opts.add_argument('--headless=new')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')

        # Collect console logs
        opts.set_capability('goog:loggingPrefs', {'browser': 'SEVERE'})

        try:
            driver = webdriver.Chrome(options=opts)
        except Exception:
            pytest.skip("Chrome/ChromeDriver not available")

        try:
            # Start a simple HTTP server
            import http.server
            import threading
            server = http.server.HTTPServer(('', 0), http.server.SimpleHTTPRequestHandler)
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            url = f'http://localhost:{port}/changelog.html'
            driver.get(url)

            # Wait for page load
            import time
            time.sleep(2)

            # Check console for SEVERE errors
            logs = driver.get_log('browser')
            severe = [l for l in logs if l['level'] == 'SEVERE']

            assert not severe, f"JS errors in changelog.html:\n" + "\n".join(
                f"  {l['level']}: {l['message']}" for l in severe
            )
        finally:
            driver.quit()
            server.shutdown()

    @pytest.mark.selenium
    def test_index_loads_without_js_errors(self):
        """index.html 在浏览器中无 console 错误"""
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
        except ImportError:
            pytest.skip("selenium not installed")

        opts = Options()
        opts.add_argument('--headless=new')
        opts.add_argument('--no-sandbox')
        opts.add_argument('--disable-dev-shm-usage')
        opts.set_capability('goog:loggingPrefs', {'browser': 'SEVERE'})

        try:
            driver = webdriver.Chrome(options=opts)
        except Exception:
            pytest.skip("Chrome/ChromeDriver not available")

        try:
            import http.server, threading
            server = http.server.HTTPServer(('', 0), http.server.SimpleHTTPRequestHandler)
            port = server.server_address[1]
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()

            url = f'http://localhost:{port}/index.html'
            driver.get(url)
            import time
            time.sleep(2)

            logs = driver.get_log('browser')
            severe = [l for l in logs if l['level'] == 'SEVERE']
            assert not severe, f"JS errors in index.html:\n" + "\n".join(
                f"  {l['level']}: {l['message']}" for l in severe
            )
        finally:
            driver.quit()
            server.shutdown()
