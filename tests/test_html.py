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


class TestXHotspotFrontend:
    """X热点 tab + renderXHotspots + split-preview + esc() 存在性断言 (设计 §7.2)。

    按既有规则: JS 相关断言只扫 <script> 块 (排除 <style> 块);
    元素/属性存在性断言直接扫全文。
    """

    def _content(self):
        return (PROJECT_ROOT / 'index.html').read_text()

    def _js_blocks(self):
        content = self._content()
        return re.findall(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", content, re.S)

    def test_xhotspot_tab_present(self):
        """X热点 tab 按钮 + 计数元素存在"""
        c = self._content()
        assert 'data-tab="xhotspots"' in c
        assert 'id="tc-xhotspots"' in c
        assert 'X热点' in c

    def test_xhotspot_render_functions(self):
        """renderXHotspots / 分栏 / 数据加载函数存在"""
        js = '\n'.join(self._js_blocks())
        for fn in ('function renderXHotspots', 'function openSplitPreview',
                   'function spNav', 'function closeSplitPreview',
                   'async function loadTwitterData', 'function flattenTwitter'):
            assert fn in js, f'missing {fn}'

    def test_split_preview_elements(self):
        """split-preview 元素/类存在 (header nav/close + body)"""
        c = self._content()
        assert 'id="split-preview"' in c
        assert 'id="split-backdrop"' in c
        assert 'split-preview-header' in c
        assert 'split-preview-body' in c
        assert 'onclick="closeSplitPreview()"' in c

    def test_esc_helper_present(self):
        """esc() helper 存在且转义字符集完整 (SEC-1: & < > " ' `)"""
        js = '\n'.join(self._js_blocks())
        assert 'function esc(' in js
        assert "'&':'&amp;'" in js
        assert "'<':'&lt;'" in js
        assert "'>':'&gt;'" in js
        assert "'&quot;'" in js
        assert "'&#39;'" in js
        assert "'&#96;'" in js

    def test_existing_render_points_backfilled(self):
        """既有 innerHTML 直插点已回填 esc (SEC-1 顺带收敛)"""
        js = '\n'.join(self._js_blocks())
        assert 'esc(h.title' in js            # renderHotspotPanel / renderHotspots
        assert 'esc(h.id)' in js              # renderHotspots / renderHotspotPanel
        assert 'esc(label)' in js             # chip()
        assert 'esc(text)' in js              # eventCell / smartEventCell

    def test_x_source_chip(self):
        """源 filter chips 扩展 X (按 handle/url 域名过滤)"""
        js = '\n'.join(self._js_blocks())
        assert "{name:'X', url:'https://x.com'}" in js

    def test_country_filter_disabled_on_x_tab(self):
        """国家过滤对 X tab 置灰 (O-6)"""
        js = '\n'.join(self._js_blocks())
        assert "tab==='xhotspots'" in js
        assert 'filter-chip.disabled' in self._content()

    def test_images_https_guard(self):
        """图片 src 前端二次校验 https:// 前缀 + 占位 (SEC-1/O-7)"""
        js = '\n'.join(self._js_blocks())
        assert "s.startsWith('https://')" in js
        assert 'imgFail(this)' in js
        assert '图片加载失败' in js

    def test_twitter_fetch_warn(self):
        """twitter.json 加载失败 console.warn + 不阻断页面"""
        js = '\n'.join(self._js_blocks())
        assert "'data/twitter.json?t=' + Date.now()" in js
        assert "console.warn('[llm-radar] twitter.json load failed:', e.message)" in js

    def test_null_metric_dash(self):
        """指标 null 显示 — (num helper 复用)"""
        js = '\n'.join(self._js_blocks())
        assert 'num(t.views)' in js
        assert 'num(t.replies)' in js
        assert 'num(t.likes)' in js


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
