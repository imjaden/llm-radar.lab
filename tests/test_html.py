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
        """twitter.json 加载失败 console.warn + 不阻断页面 (D2 条件缓存: 无 ?t= + {cache:'no-cache'})"""
        js = '\n'.join(self._js_blocks())
        assert '?t=' not in js
        assert "'data/twitter.json', {cache:'no-cache'}" in js
        assert "console.warn('[llm-radar] twitter.json load failed:', e.message)" in js

    def test_null_metric_dash(self):
        """指标 null 显示 — (num helper 复用)"""
        js = '\n'.join(self._js_blocks())
        assert 'num(t.views)' in js
        assert 'num(t.replies)' in js
        assert 'num(t.likes)' in js


class TestCopyTweetFallback:
    """拷贝降级链 (llm-radar-CL003, RIG-001): copyTweet 段函数体级断言。

    必须 scope 到 copyTweet 区域: 全文件裸匹配 navigator.clipboard.writeText
    会被 ago.onclick (index.html 尾部) 的裸 writeText 假绿 (RIG-001 修正)。
    截取范围: function copyTweet 段至下一个函数 (spNav) 前, 含 copyTextFallback。
    """

    def _content(self):
        return (PROJECT_ROOT / 'index.html').read_text()

    def _copy_region(self):
        """截取 function copyTweet 段至下一个函数声明前 (含 copyTextFallback)。"""
        js = '\n'.join(re.findall(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", self._content(), re.S))
        m = re.search(r'function copyTweet[\s\S]*?(?=\nfunction spNav)', js)
        assert m, 'copyTweet region not found (copyTextFallback 需位于 copyTweet 与 spNav 之间)'
        return m.group(0)

    def test_copy_clipboard_guard(self):
        """(a) copyTweet 内 clipboard 防御: navigator.clipboard 判空后才调 writeText (兼容 && 与 ?.)"""
        region = self._copy_region()
        assert re.search(
            r"navigator\.clipboard(?:\?\.|\s*&&)\s*navigator\.clipboard\.writeText", region
        ), 'copyTweet 缺少 navigator.clipboard 防御 (非安全上下文裸 writeText 抛 TypeError)'

    def test_copy_execcommand_fallback(self):
        """(b) 降级存在: copyTweet 段 (含 copyTextFallback) 使用 execCommand('copy')"""
        region = self._copy_region()
        assert "execCommand('copy')" in region, 'copyTweet 段缺少 execCommand 降级'

    def test_copy_orig_icon_restore(self):
        """D2 B2: 反馈复原为纯图标 📋 (与按钮图标化一致, 不残留 '📋 拷贝')"""
        region = self._copy_region()
        assert "const orig = '📋'" in region
        assert "const orig = '📋 拷贝'" not in region

    def test_sp_action_button_titles(self):
        """三按钮纯图标 + title 悬停提示 (D3 B3)"""
        c = self._content()
        assert 'title="打开原文"' in c
        assert 'title="作者主页"' in c
        assert 'title="拷贝推广内容"' in c


class TestSearchFeature:
    """全站搜索 (D4 4B, SEC-1) + forward 渲染 (D2 2C) 存在性断言 (设计 §7.2)。

    - header-search 元素 + doSearch + 防抖 + Cmd+F 拦截
    - 高亮结构化 DOM (span + textContent 分片, 禁 innerHTML)
    - forward 表格/分栏渲染 + esc/textContent 覆盖 (O-1 forward XSS)
    """

    def _content(self):
        return (PROJECT_ROOT / 'index.html').read_text()

    def _js_blocks(self):
        content = self._content()
        return re.findall(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", content, re.S)

    def _js(self):
        return '\n'.join(self._js_blocks())

    def test_search_input_present(self):
        """header-search 输入框 + oninput/onkeydown 挂钩存在"""
        c = self._content()
        assert 'id="header-search"' in c
        assert 'oninput="onSearchInput()"' in c
        assert 'onkeydown="onSearchKey(event)"' in c

    def test_search_functions(self):
        """搜索函数族存在: doSearch / 计数 / 行过滤 / 高亮"""
        js = self._js()
        for fn in ('function onSearchInput', 'function onSearchKey',
                   'function doSearch', 'function updateSearchSummary',
                   'function countSearchMatches', 'function applySearchFilter',
                   'function highlightMatches', 'function searchHaystack'):
            assert fn in js, f'missing {fn}'

    def test_search_debounce(self):
        """输入防抖 ~200ms (D4 4B)"""
        js = self._js()
        assert 'setTimeout(doSearch, 200)' in js
        assert 'clearTimeout(searchTimer)' in js

    def test_search_summary_cross_tab(self):
        """跨 tab 计数: 当前 N + 其他 tab 跳转按钮 (textContent 构建)"""
        js = self._js()
        assert 'SEARCH_TAB_LABELS' in js
        assert 'search-jump-btn' in js
        assert "b.textContent = (SEARCH_TAB_LABELS[tab] || tab)" in js
        assert "b.onclick = () => switchTab(tab)" in js

    def test_cmd_f_intercept(self):
        """Cmd+F (metaKey) / Ctrl+F (ctrlKey) 拦截 → preventDefault + 聚焦"""
        js = self._js()
        assert 'e.metaKey || e.ctrlKey' in js
        assert "e.key === 'f' || e.key === 'F'" in js
        assert 'e.preventDefault()' in js
        assert 'document.activeElement !== input' in js
        assert "getElementById('header-search')" in js

    def test_highlight_structured_dom_no_innerhtml(self):
        """高亮结构化 DOM (SEC-1): span + textContent 分片, highlightMatches 禁 innerHTML"""
        js = self._js()
        m = re.search(r'function highlightMatches[\s\S]*?\n\}', js)
        assert m, 'highlightMatches function not found'
        body = m.group(0)
        assert 'createTextNode' in body
        assert "span.className = 'search-hl'" in body
        assert 'span.textContent' in body
        assert 'innerHTML' not in body

    def test_search_highlight_query_text_node(self):
        """查询词按文本节点渲染 (SEC-1 防回归): 查询含 <script> 不执行"""
        js = self._js()
        assert 'document.createTextNode(v.slice(i, idx))' in js
        assert 'createDocumentFragment' in js

    def test_forward_summary_format(self):
        """摘要: {text}\\nforward: {forward} 截断 (text 空则仅 forward), esc 覆盖"""
        js = self._js()
        assert 'function xSummaryText(t, limit)' in js
        assert "lines.push('forward: ' + t.forward)" in js
        assert 'esc(raw)' in js
        assert 'esc(title)' in js

    def test_forward_split_textcontent(self):
        """分栏 forward 行: sp-forward 元素 + textContent 渲染 (SEC-1)"""
        c = self._content()
        js = self._js()
        assert 'id="sp-forward"' in c
        assert "getElementById('sp-forward').textContent" in js
        assert "document.getElementById('sp-forward').innerHTML" not in js

    def test_forward_xss_text_only(self):
        """O-1: forward 含 <img onerror> → 纯文本渲染 (textContent/esc, 无 img 执行)"""
        js = self._js()
        # 分栏: forward 经 textContent 赋值, 不经 innerHTML
        assert "t.forward ? 'forward: ' + t.forward : ''" in js
        assert 'sp-forward' in js
        # 表格: 摘要统一 esc() 后注入 innerHTML (query/片段均文本节点)
        assert 'esc(raw)' in js


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


class TestPerfOptimize:
    """页面加载优化 (llm-radar-CL002): D1 预编译 CSS / D2 条件缓存 / D4 渲染缓存 (防回归)。

    - (a) index.html/changelog.html 无 cdn.tailwindcss.com 引用 (运行时 JIT 编译已移除)
    - (b) 存在 <link rel="stylesheet" href="static/tailwind.css"> (预编译产物入库)
    - D2: 数据 fetch 无 ?t= 缓存击穿, 统一 {cache:'no-cache'} (index 4 + changelog 2 = 6)
    - D4: RENDER_CACHE 复合 key 存在
    """

    def _content(self, name):
        return (PROJECT_ROOT / name).read_text()

    def _js(self, name):
        return '\n'.join(re.findall(r"<script(?![^>]*src=)[^>]*>(.*?)</script>", self._content(name), re.S))

    def test_no_tailwind_cdn(self):
        """双文件无 cdn.tailwindcss.com"""
        for html_file in ['index.html', 'changelog.html']:
            assert 'cdn.tailwindcss.com' not in self._content(html_file), f'{html_file} 仍引用 Tailwind CDN'

    def test_precompiled_css_link(self):
        """双文件存在预编译 CSS link"""
        for html_file in ['index.html', 'changelog.html']:
            assert '<link rel="stylesheet" href="static/tailwind.css">' in self._content(html_file), \
                f'{html_file} 缺少预编译 CSS link'

    def test_data_fetch_no_cache_buster(self):
        """D2: 数据 fetch 无 ?t=, 统一 {cache:'no-cache'} (4 index + 2 changelog)"""
        for html_file, n in [('index.html', 4), ('changelog.html', 2)]:
            js = self._js(html_file)
            assert '?t=' not in js, f'{html_file} 仍有 ?t= 缓存击穿'
            assert js.count("{cache:'no-cache'}") == n, f"{html_file} {{cache:'no-cache'}} 数量 != {n}"

    def test_render_cache_present(self):
        """D4: RENDER_CACHE 复合 key + 数据刷新失效 (RIG-2)"""
        js = self._js('index.html')
        assert 'const RENDER_CACHE = {}' in js
        assert "tab + '|' + (filterMode||'')" in js
        assert 'clearRenderCache()' in js
