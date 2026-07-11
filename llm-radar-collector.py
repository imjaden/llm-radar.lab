#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Karpathy Principles - AI编程四大原则
=====================================
1. 先思考 - 不假设，不隐藏困惑 → 不确定就问，多种解释列出
2. 保持简单 - 最小代码解决问题 → 无多余抽象
3. 精准修改 - 只改必须改的 → 不"顺便"改进邻接代码
4. 目标驱动 - 测试先行，验证闭环 → "修bug"→"写测试复现→让测试通过"

Version: 1.0(2026-06-11)
Description
- LLM Radar 数据采集脚本
- 抓取 LLM 行业新闻 → LLM 提取实体 → 合并到 snapshot.json
- 通过 llm-manager 统一调用大模型，支持自动故障切换

Environments:
- Python >= 3.11

Dependency
- openai >= 1.0.0（DeepSeek API 调用）
- requests >= 2.31.0（新闻源抓取）
- beautifulsoup4 >= 4.12.0（HTML 解析）
"""

import os
import re
import json
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from openai import OpenAI
from prettytable import PrettyTable

# ===== Constants =====
PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / 'data'
SNAPSHOT_PATH = DATA_DIR / 'snapshot.json'
FETCH_CACHE_PATH = DATA_DIR / 'fetch-cache.json'

# ===== News Sources =====
SOURCES = {
    'qbitai': {
        'name': '量子位',
        'url': 'https://www.qbitai.com',
        'category': '中文媒体',
        'search_queries': ['大模型', 'LLM', 'AI融资', 'AI发布'],
    },
    'jiqizhixin': {
        'name': '机器之心',
        'url': 'https://www.jiqizhixin.com',
        'category': '中文媒体',
        'search_queries': ['大模型', 'AI', 'LLM', '深度学习'],
    },
    'infoq': {
        'name': 'InfoQ',
        'url': 'https://www.infoq.cn/topic/AI',
        'category': '中文技术媒体',
        'search_queries': ['大模型', 'AI', 'LLM', 'AI 工程化'],
    },
    '36kr': {
        'name': '36氪',
        'url': 'https://36kr.com/search/articles/大模型',
        'category': '中文科技媒体',
        'search_queries': ['大模型', 'AI融资', 'LLM'],
    },
    # techcrunch REMOVED - Selenium page load timeout
    'github-trending': {
        'name': 'GitHub Trending',
        'url': 'https://github.com/trending?since=weekly',
        'category': '开发者',
        'search_queries': ['llm', 'ai', 'gpt', 'transformer'],
    },
    'huggingface': {
        'name': 'HuggingFace Papers',
        'url': 'https://huggingface.co/papers',
        'category': '研究',
        'search_queries': ['llm', 'language model', 'reasoning'],
    },
}

# Selenium 无头抓取配置：每源定义 CSS 选择器（title_sel → 标题, link_sel → 链接, date_sel → 日期）
# 选择器取不到时 fallback 到通用智能链接检测（找页面上所有有效链接）
SCRAPERS = {
    'qbitai': {
        'wait_sel': 'h2 a',  # 等待此元素出现即认为页面加载完成
        'title_sel': 'h2 a',
        'link_sel': 'h2 a',
        'date_sel': '.entry-date, time, .date',
        'link_filter': lambda h: 'qbitai.com' in h,
    },
    'jiqizhixin': {
        'wait_sel': 'body',
        'title_sel': 'a.title, h3 a, h2 a',
        'link_sel': 'a.title, h3 a, h2 a',
        'date_sel': 'time, .date, .time',
        'scroll': True,
    },
    'infoq': {
        'wait_sel': 'body',
        'title_sel': 'a[href*="/article/"], h3 a, h4 a',
        'link_sel': 'a[href*="/article/"], h3 a, h4 a',
        'date_sel': 'time, .date, span.date',
        'scroll': True,
    },
    # techcrunch REMOVED
    '36kr': {
        'wait_sel': 'body',
        'title_sel': 'a[href*="/article/"], h3 a, .title a',
        'link_sel': 'a[href*="/article/"], h3 a, .title a',
    },
    'github-trending': {
        'wait_sel': 'article.Box-row',
        'title_sel': 'h2.h3 a, article.Box-row h2 a',
        'link_sel': 'h2.h3 a, article.Box-row h2 a',
        'date_sel': 'relative-time',
    },
    'huggingface': {
        'wait_sel': 'body',
        'title_sel': 'a[href*="/papers/"], h3 a, article h3 a',
        'link_sel': 'a[href*="/papers/"], h3 a, article h3 a',
        'date_sel': 'time, .date',
        'scroll': True,
    },
}


class LLMRadarCollector:
    """LLM Radar 数据采集器"""

    # 已知别名映射：变体名 → 主条目 id
    KNOWN_ALIASES = {
        'z.ai': 'zhipu-ai',
        'z.AI(智谱)': 'zhipu-ai',
        '阿里巴巴': 'alibaba',
        '阿里云': 'alibaba',
        '阿里千问': 'alibaba',
        '微信': 'tencent',
        '腾讯微信': 'tencent',
    }

    # 规范化时去掉的常见后缀
    NORMALIZE_SUFFIXES = ['科技', '云', 'AI', '大模型', '千问', '研究院', '实验室']

    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.data_dir = DATA_DIR
        self.snapshot_path = SNAPSHOT_PATH
        self.fetch_cache_path = FETCH_CACHE_PATH
        self.api_key = self._load_api_key()
        self.base_url = "https://api.deepseek.com/v1"

    def _load_api_key(self):
        """从环境变量加载 DeepSeek API key"""
        key = os.environ.get('DEEPSEEK_API_KEY', '')
        if key:
            self._print_ok('DeepSeek API key 已从环境变量加载')
        else:
            self._print_err('DEEPSEEK_API_KEY 未配置，请在 .env 文件或环境变量中设置')
        return key

    def _print_ok(self, msg):
        print(f'✅ {msg}')

    def _print_err(self, msg):
        print(f'❌ {msg}')

    def _print_info(self, msg):
        print(f'ℹ️ {msg}')

    def _print_warn(self, msg):
        print(f'⚠️ {msg}')

    def _call_deepseek(self, system_content, user_content, model="deepseek-v4-flash", max_tokens=16000):
        """调用 DeepSeek API"""
        if not self.api_key:
            self._print_err('API key 未配置')
            return None
        try:
            client = OpenAI(api_key=self.api_key, base_url=self.base_url)
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=max_tokens,
                temperature=0.1,
            )
            msg = resp.choices[0].message
            return {"content": msg.content, "prompt_tokens": resp.usage.prompt_tokens, "completion_tokens": resp.usage.completion_tokens} if resp.usage else {"content": msg.content}
        except Exception as e:
            self._print_err(f'DeepSeek API 调用失败: {e}')
            return None

    def _auto_push(self, changelog):
        """有数据更新时自动 commit + push"""
        if getattr(self, '_skip_push', False):
            self._print_info('质量门禁未通过，跳过 auto-push')
            return
        if not changelog:
            self._print_info('无数据更新，跳过 auto-push')
            return
        count = sum(1 for c in changelog if c.get('type') in ('new', 'update'))
        if count == 0:
            self._print_info('无新增/更新实体，跳过 auto-push')
            return
        self._print_info(f'检测到 {count} 条变更，执行 auto-push...')
        try:
            subprocess.run(['git', 'add', '-A'], cwd=self.project_root, check=True, capture_output=True)
            msg = f'auto-push@llm-radar: update data ({count} changes)'
            r = subprocess.run(['git', 'commit', '-m', msg], cwd=self.project_root, capture_output=True, text=True)
            if r.returncode != 0:
                err = r.stderr.strip()
                if 'nothing to commit' in err:
                    self._print_info('无变更需要提交')
                    return
                if 'please tell me who you are' in err.lower() or 'user.name' in err:
                    self._print_err('git 未配置 user 信息，请执行:')
                    self._print_err('  git config user.name "admin"')
                    self._print_err('  git config user.email "admin@llm-radar"')
                    return
                self._print_warn(f'commit 失败: {err[:200]}')
                return
            subprocess.run(['git', 'push'], cwd=self.project_root, check=True, capture_output=True)
            self._print_ok(f'auto-push 完成: {msg}')
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if e.stderr else ''
            self._print_warn(f'auto-push 跳过: {stderr[:200]}')
            # Dead letter: 保存推送失败数据
            dead_path = self.data_dir / 'dead-letter.json'
            try:
                dead = json.loads(dead_path.read_text()) if dead_path.exists() else []
                dead.append({
                    'time': datetime.now().isoformat(),
                    'changelog_count': len(changelog),
                    'error': stderr[:500],
                    'changelog_snapshot': changelog[:20],  # 最多保留 20 条避免失控
                })
                dead = dead[-10:]  # 保留最近 10 次
                dead_path.write_text(json.dumps(dead, ensure_ascii=False, indent=2))
                self._print_info(f'推送失败数据已存档到 dead-letter.json')
            except Exception as dl_err:
                self._print_warn(f'dead letter 写入失败: {dl_err}')

    # ===== Fetch =====

    @staticmethod
    def _resolve_chrome_binary():
        import os, shutil, sys as _sys
        if _sys.platform == "darwin":
            p = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
            return p if os.path.exists(p) else None
        for name in ["google-chrome", "google-chrome-stable", "chromium-browser", "chromium"]:
            found = shutil.which(name)
            if found: return found
        return None

    @staticmethod
    def _resolve_chromedriver():
        import os, glob, shutil
        found = shutil.which("chromedriver")
        if found: return found
        wdm = os.path.expanduser("~/.wdm")
        if not os.path.isdir(wdm): return None
        candidates = []
        for root, dirs, files in os.walk(wdm):
            for f in files:
                if f == "chromedriver":
                    candidates.append(os.path.join(root, f))
        if not candidates: return None
        candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return candidates[0]

    def _init_driver(self):
        """初始化 Selenium 无头浏览器（单例）"""
        if hasattr(self, '_driver') and self._driver:
            return self._driver
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            DRIVER_PATH = self._resolve_chromedriver()

            opts = Options()
            opts.add_argument('--headless=new')
            chrome_bin = self._resolve_chrome_binary()
            if chrome_bin:
                opts.binary_location = chrome_bin
            opts.add_argument('--no-sandbox')
            opts.add_argument('--disable-dev-shm-usage')
            opts.add_argument('--blink-settings=imagesEnabled=false')
            opts.add_argument('--window-size=1920,1080')
            opts.add_argument('--disable-gpu')
            opts.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36')
            opts.add_experimental_option('excludeSwitches', ['enable-automation'])
            service = Service(DRIVER_PATH)
            self._driver = webdriver.Chrome(service=service, options=opts)
            # 反检测：隐藏 webdriver 特征
            self._driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
            })
            self._driver.execute_cdp_cmd("Network.enable", {})
            self._print_ok('Selenium 无头浏览器已启动')
            return self._driver
        except Exception as e:
            err_msg = str(e).split('\n')[0][:120]
            self._print_err(f'Selenium 初始化失败: {err_msg}')
            return None

    def _quit_driver(self):
        """关闭浏览器"""
        if hasattr(self, '_driver') and self._driver:
            try:
                self._driver.quit()
            except:
                pass
            self._driver = None

    def _selenium_extract(self, source_key):
        """用 Selenium 无头浏览器提取结构化文章列表（失败自动重试+重启驱动）"""
        import time
        source = SOURCES.get(source_key)
        scraper = SCRAPERS.get(source_key, {})
        driver = self._init_driver()
        if not driver:
            return None

        url = source['url']
        self._print_info(f'无头浏览器抓取 {source["name"]} ({url})')

        for attempt in range(2):  # 最多重试 1 次（含驱动重启）
            try:
                driver.set_page_load_timeout(25)
                driver.get(url)
                # 等待页面加载
                wait_sel = scraper.get('wait_sel', 'body')
                from selenium.webdriver.common.by import By
                from selenium.webdriver.support.ui import WebDriverWait
                from selenium.webdriver.support import expected_conditions as EC
                WebDriverWait(driver, 25).until(EC.presence_of_element_located((By.CSS_SELECTOR, wait_sel)))
                time.sleep(1)

                # 对 JS 懒加载的页面，滚动到底部触发加载
                if scraper.get('scroll'):
                    driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
                    time.sleep(2)
                    driver.execute_script('window.scrollTo(0, document.body.scrollHeight / 2);')
                    time.sleep(1)

                # 提取文章列表
                articles = []
                seen_urls = set()
                link_filter = scraper.get('link_filter')

                # 先尝试 CSS 选择器精确提取
                title_sel = scraper.get('title_sel')

                if title_sel:
                    title_els = driver.find_elements(By.CSS_SELECTOR, title_sel)
                    for el in title_els:
                        title = el.text.strip()
                        href = el.get_attribute('href') or ''
                        if not title or len(title) < 8 or not href:
                            continue
                        if href in seen_urls:
                            continue
                        if link_filter and not link_filter(href):
                            continue
                        # 尝试取日期
                        date_text = ''
                        date_sel = scraper.get('date_sel')
                        if date_sel:
                            try:
                                parent = el.find_element(By.XPATH, '..')
                                date_el = parent.find_element(By.CSS_SELECTOR, date_sel)
                                date_text = date_el.text.strip() or date_el.get_attribute('datetime') or ''
                            except:
                                pass
                        seen_urls.add(href)
                        articles.append({'title': title, 'url': href, 'date': date_text})

                # 如果选择器没取到，fallback 到通用检测（所有 > 15 字符的链接）
                if len(articles) < 3:
                    all_links = driver.find_elements(By.TAG_NAME, 'a')
                    for el in all_links:
                        title = el.text.strip()
                        href = el.get_attribute('href') or ''
                        if not title or len(title) < 12 or not href or href.startswith('javascript'):
                            continue
                        if href in seen_urls:
                            continue
                        if link_filter and not link_filter(href):
                            continue
                        seen_urls.add(href)
                        articles.append({'title': title, 'url': href, 'date': ''})

                # 格式化输出
                fetched = datetime.now().strftime('%Y-%m-%d')
                lines = [f'# {source["name"]} — {len(articles)} 篇文章（抓取时间: {fetched}）']
                for i, a in enumerate(articles[:20], 1):
                    date_str = f' ({a["date"]})' if a.get('date') else f' ({fetched})'
                    lines.append(f'{i}. [{a["title"]}]({a["url"]}){date_str}')
                structured = '\n'.join(lines)

                # 同时也提取页面纯文本（给 LLM 提供正文上下文）
                page_text = driver.find_element(By.TAG_NAME, 'body').text[:3000]
                # 去除过短的噪音行
                body_lines = [l.strip() for l in page_text.split('\n') if len(l.strip()) > 20]
                page_text_clean = '\n'.join(body_lines[:80])

                text_lines = [f'--- {source["name"]} ({url}) ---']
                for a in articles[:10]:
                    text_lines.append(a['title'])
                text_fallback = '\n'.join(text_lines)

                self._print_ok(f'{source["name"]} 抓取成功，{len(articles)} 篇文章')
                return {
                    'source': source_key,
                    'name': source['name'],
                    'url': url,
                    'articles': articles[:20],
                    'content': structured + '\n\n' + text_fallback + '\n\n' + page_text_clean,
                    'fetched_at': datetime.now().isoformat(),
                }

            except Exception as e:
                err_msg = str(e).split('\n')[0][:100] if str(e) else '驱动崩溃'
                if attempt == 0:
                    self._print_warn(f'Selenium 失败 ({err_msg})，重启驱动重试...')
                    self._quit_driver()
                    driver = self._init_driver()
                    if not driver:
                        break
                else:
                    self._print_err(f'Selenium 重试也失败: {err_msg}')
                    return None

    def fetch_source(self, source_key):
        """抓取单个新闻源（Selenium 无头模式，失败则跳过）"""
        source = SOURCES.get(source_key)
        if not source:
            self._print_err(f'未知新闻源: {source_key}')
            return None

        # 优先 Selenium
        result = self._selenium_extract(source_key)
        if result:
            return result



    def fetch_all(self, source_keys=None):
        """抓取所有新闻源（跳过已降级源）"""
        if source_keys is None:
            source_keys = list(SOURCES.keys())

        # 加载源健康状态
        degraded = set()
        metrics_path = self.data_dir / 'metrics.json'
        if metrics_path.exists():
            try:
                metrics = json.loads(metrics_path.read_text())
                source_health = metrics.get('source_health', {})
                for key, h in source_health.items():
                    if h.get('consecutive_fails', 0) >= 3:
                        degraded.add(key)
            except:
                pass

        if degraded:
            self._print_warn(f'跳过 {len(degraded)} 个已降级源: {", ".join(degraded)}')
            source_keys = [k for k in source_keys if k not in degraded]

        results = []
        for key in source_keys:
            result = self.fetch_source(key)
            if result:
                results.append(result)
            time.sleep(2)  # 避免请求过快

        # 缓存抓取结果
        cache = {
            'fetched_at': datetime.now().isoformat(),
            'sources': results,
        }
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with open(self.fetch_cache_path, 'w', encoding='utf-8') as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

        self._print_ok(f'抓取完成，{len(results)}/{len(source_keys)} 个源成功')
        return results

    # ===== Extract =====
    def extract_entities(self, fetch_results):
        """使用 LLM 从新闻中提取实体"""
        if not self.api_key:
            self._print_err('API key 未配置，无法提取实体')
            return None

        # 合并所有源的内容
        combined = ''
        for r in fetch_results:
            combined += f'\n\n--- {r["name"]} ({r["url"]}) ---\n{r["content"]}'

        # 截取避免 token 超限
        combined = combined[:12000]

        system_prompt = """你是一个 LLM 行业情报分析助手。从新闻内容中提取以下 5 类实体：厂商、人物、工具、大模型、热点。

输出 JSON 格式，严格按以下结构：
```json
{
  "providers": [{"id": "英文标识", "name": "中文名", "country": "国家", "hot_score": 0-100, "hot_level": "爆热/高热/温热/平稳/冷淡", "last_event": "事件摘要", "last_event_date": "YYYY-MM-DD", "last_event_url": "", "flagship_models": [], "key_people": [], "focus_areas": [], "confidence": "high/medium/low"}],
  "people": [{"id": "英文标识", "name": "中文名", "name_en": "英文名", "title": "头衔", "employer_id": "厂商id", "influence_level": "行业领袖/核心人物/活跃人物/新锐", "hot_score": 0-100, "hot_level": "爆热/高热/温热/平稳/冷淡", "recent_activity": "动态摘要", "recent_activity_date": "YYYY-MM-DD", "recent_activity_url": "", "known_for": [], "related_providers": [], "related_llms": [], "confidence": "high/medium/low"}],
  "tools": [{"id": "英文标识", "name": "名称", "category": "分类", "website": "", "github": "", "description": "", "pricing_model": "开源免费/Freemium/商业/API 按量", "maturity": "实验/可用/生产就绪", "hot_score": 0-100, "hot_level": "爆热/高热/温热/平稳/冷淡", "last_update": "更新摘要", "last_update_date": "YYYY-MM-DD", "last_update_url": "", "related_providers": [], "related_llms": [], "confidence": "high/medium/low"}],
  "llms": [{"id": "英文标识", "name": "名称", "provider_id": "厂商id", "family": "系列", "type": "类型", "open_weights": false, "tier": "旗舰/主力/轻量/专用", "capabilities": [], "status": "发布/预览/公测/已下线", "hot_score": 0-100, "hot_level": "爆热/高热/温热/平稳/冷淡", "hot_reason": "热度原因", "last_event": "事件摘要", "last_event_date": "YYYY-MM-DD", "last_event_url": "", "related_people": [], "confidence": "high/medium/low"}]
}
```

规则：
1. 只提取有实质动态的实体（新发布、重大更新、融资、人员变动）
2. hot_score 基于新闻出现频率和重要性判断
3. 无法确认的信息标记 confidence: "low"
4. ID 使用英文小写+连字符格式
5. 日期使用 YYYY-MM-DD 格式
6. 不要编造数据，只提取新闻中明确提到的信息
7. **URL 硬规则**：
   - 必须填写完整可访问的文章链接（含协议和路径），如 https://www.qbitai.com/2026/07/12345.html
   - ❌ 禁止：裸域名（qbitai.com）、截断（.../article/...）、占位符（xxx/example/localhost）
   - ❌ 禁止：门户首页 URL —— 必须指向具体文章页面
   - 如果找不到具体文章 URL，留空字符串 ""
8. **时效硬规则**：
   - 日期字段必须使用新闻中明确出现的日期，禁止编造
   - 优先当前日期前后 48h 内的事件
   - 超过 7 天的旧事件【绝对不提取】
   - 示例：今天是 2026-07-11，不要提取任何日期早于 2026-07-04 的事件
9. **key_people 强制规则**：
   - 只要新闻中提到该厂商的高管/创始人/核心研究人员，必须填写 key_people
   - key_people 格式：["姓名-头衔", ...]，如 ["Sam Altman-CEO", "Greg Brockman-董事长"]
   - 头部厂商（OpenAI, Google, 微软, Meta, 阿里, 腾讯, 字节, 百度, 华为等）不要留空"""

        user_prompt = f"""当前日期: {datetime.now().strftime('%Y-%m-%d')}

请从以下 LLM 行业新闻中提取实体，严格使用当前日期判断时效性：

{combined}

请输出 JSON 格式的结果，包含 providers、people、tools、llms、hotspots 五个数组。热点事件的 date 字段必须与新闻中的日期一致。

hotspots 数组中每个元素格式：
```json
{{"id": "英文标识", "title": "中文标题", "summary": "50-100字简报", "date": "YYYY-MM-DD", "source": "来源名称", "url": "完整原文链接(必须包含完整路径，不能只是门户首页)", "related_providers": ["厂商id"], "related_people": ["人物id"], "related_tools": ["工具id"], "related_llms": ["模型id"]}}
```
热点为近期最重要/最受关注的 3-5 条行业事件（优先提取最近 48 小时内的，超过 7 天的不提取）。"""

        self._print_info('调用 LLM 提取实体...')
        start_time = time.time()

        # 直接调用 DeepSeek API
        result = self._call_deepseek(system_prompt, user_prompt)

        # 如果 LLM 回复较大，增加 max_tokens 重试保证完整性
        content = result.get('content', '') if result else ''
        if content and len(content) > 7000:
            self._print_info(f'LLM 输出较大 ({len(content)} 字符)，使用高 token 限制重试...')
            retry = self._call_deepseek(system_prompt, user_prompt, max_tokens=16000)
            if retry and not retry.get('error'):
                result = retry
                content = retry.get('content', '')

        duration = round(time.time() - start_time, 1)

        if not result or result.get('error'):
            self._print_err(f'LLM 调用失败: {result.get("error") if result else "未知错误"}')
            return None

        # 解析 JSON 输出
        if not content:
            content = result.get('content', '')
        entities = self._parse_json_output(content)
        if entities:
            total = sum(len(entities.get(k, [])) for k in ['providers', 'people', 'tools', 'llms'])
            self._print_ok(f'实体提取完成，耗时 {duration}s，共 {total} 个实体')
            return entities
        else:
            # 重试 1 次：复用完整 prompt，末尾强调纯 JSON
            self._print_warn('JSON 解析失败，重试...')
            retry_prompt = user_prompt + '\n\n只输出 JSON，不要使用 markdown 代码块包裹，不要添加任何说明文字。'
            retry_result = self._call_deepseek(system_prompt, retry_prompt)
            if retry_result and not retry_result.get('error'):
                retry_content = retry_result.get('content', '')
                retry_entities = self._parse_json_output(retry_content)
                if retry_entities:
                    self._print_ok(f'重试成功，耗时 {round(time.time() - start_time, 1)}s')
                    return retry_entities
            self._print_err(f'实体提取失败（已重试）')
            self._print_info(f'LLM 输出前 500 字符: {content[:500]}')
            return None

    def _parse_json_output(self, content):
        """尝试多种方式解析 LLM 输出的 JSON，支持截断修复"""
        import re
        if not content:
            return None
        # 1. 提取 ```json ... ``` 块
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', content)
        if json_match:
            text = json_match.group(1).strip()
            result = self._try_parse_json(text)
            if result:
                return result
        # 2. 尝试直接解析全文
        result = self._try_parse_json(content.strip())
        if result:
            return result
        # 3. 尝试修复截断的 JSON
        result = self._try_fix_truncated_json(content)
        if result:
            return result
        return None

    def _try_parse_json(self, text):
        """尝试解析 JSON，成功返回对象，失败返回 None"""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # 尝试宽松模式：允许控制字符
        try:
            return json.loads(text, strict=False)
        except json.JSONDecodeError:
            return None

    def _try_fix_truncated_json(self, text):
        """修复截断的 JSON：补齐缺失的结束括号"""
        start = text.find('{')
        if start == -1:
            return None
        text = text[start:]
        stack = []
        i = 0
        in_string = False
        escape = False
        last_good_end = 0
        while i < len(text):
            ch = text[i]
            if escape:
                escape = False
                i += 1
                continue
            if ch == '\\' and in_string:
                escape = True
                i += 1
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                i += 1
                continue
            if in_string:
                i += 1
                continue
            if ch in '{[':
                stack.append(ch)
            elif ch == '}':
                if stack and stack[-1] == '{':
                    stack.pop()
                    last_good_end = i + 1
                else:
                    break
            elif ch == ']':
                if stack and stack[-1] == '[':
                    stack.pop()
                    last_good_end = i + 1
                else:
                    break
            i += 1
        # 如果没有任何闭合括号，尝试从字符串边界截断
        if not last_good_end:
            # 找到最后一个完整键值对的位置，截断未闭合的字符串
            i = len(text) - 1
            while i >= 0 and text[i] != '"':
                i -= 1
            if i > 0:
                candidate = text[:i]  # 去掉未闭合的字符串内容
                candidate += '"'      # 闭合字符串
            else:
                candidate = text
        else:
            candidate = text[:last_good_end]
        # 补齐 stack 中缺失的结束符
        for ch in reversed(stack):
            candidate += '}' if ch == '{' else ']'
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            return None

    # ===== Merge =====
    def merge_entities(self, new_entities):
        """将新实体合并到 snapshot.json"""
        if not new_entities:
            self._print_warn('无新实体可合并')
            return None

        # 读取现有快照
        snapshot = self._load_snapshot()

        now = datetime.now().isoformat()
        today = datetime.now().strftime('%Y-%m-%d')
        changelog = []

        for dimension in ['providers', 'people', 'tools', 'llms', 'hotspots']:
            existing = {e["id"]: e for e in snapshot.get(dimension, []) if e.get("id")}
            new_items = new_entities.get(dimension, [])

            for item in new_items:
                item_id = item.get('id')
                if not item_id:
                    continue

                if item_id in existing:
                    # 更新现有实体（按 id 匹配）
                    old = existing[item_id]
                    updated = self._merge_single(old, item)
                    updated['updated_at'] = now
                    existing[item_id] = updated

                    # 记录变更
                    changes = self._diff_fields(old, updated)
                    if changes:
                        changelog.append({
                            'type': 'update',
                            'dimension': dimension,
                            'id': item_id,
                            'summary': changes,
                            'date': today,
                            'time': datetime.now().strftime('%H:%M:%S'),
                            'url': item.get('last_event_url') or item.get('recent_activity_url') or item.get('last_update_url') or '',
                        })
                else:
                    # 按 name 匹配：不同 ID 但同名的实体合并
                    item_name = item.get('name', '')
                    matched = None
                    if item_name:
                        for eid, e in existing.items():
                            if e.get('name') == item_name:
                                matched = e
                                break
                    if matched:
                        # 合并到已有实体，保留原 ID
                        old = matched
                        updated = self._merge_single(old, item)
                        updated['updated_at'] = now
                        existing[old['id']] = updated
                        changes = self._diff_fields(old, updated)
                        if changes:
                            changelog.append({'type': 'update', 'dimension': dimension, 'id': old['id'], 'summary': changes, 'date': today, 'time': datetime.now().strftime('%H:%M:%S'), 'url': item.get('last_event_url') or item.get('recent_activity_url') or item.get('last_update_url') or ''})
                    else:
                        # 新增实体
                        item['updated_at'] = now
                        existing[item_id] = item
                        changelog.append({
                            'type': 'new',
                            'dimension': dimension,
                            'id': item_id,
                            'summary': item.get('last_event') or item.get('recent_activity') or item.get('last_update') or f"{item.get('name','')} ({item_id})",
                            'date': today,
                            'time': datetime.now().strftime('%H:%M:%S'),
                            'url': item.get('last_event_url') or item.get('recent_activity_url') or item.get('last_update_url') or '',
                        })

            snapshot[dimension] = list(existing.values())

        # ---- 模糊名称去重: 合并别名/变体 ----
        dedup_count = 0
        for dim in ['providers', 'people', 'tools', 'llms']:
            before = len(snapshot.get(dim, []))
            snapshot[dim] = self._fuzzy_name_dedup(snapshot.get(dim, []))
            after = len(snapshot.get(dim, []))
            dedup_count += (before - after)
        if dedup_count:
            self._print_info(f'模糊去重: 合并 {dedup_count} 个重复实体')

        # ---- 时间衰减: 对所有实体应用热度时间衰减 ----
        decay_count = 0
        for dim in ['providers', 'people', 'tools', 'llms']:
            items = snapshot.get(dim, [])
            for item in items:
                old_score = item.get('hot_score', 0)
                self._apply_time_decay(item)
                if item.get('hot_score', 0) != old_score:
                    decay_count += 1
        if decay_count:
            self._print_info(f'时间衰减: {decay_count} 个实体热度已调整')

        # ---- 数据留存: 最多 100 条 + 最近 15 天滑动窗口 ----
        retention_dims = ['providers', 'people', 'tools', 'llms', 'hotspots']
        archive_count = 0
        for dim in retention_dims:
            items = snapshot.get(dim, [])
            if len(items) <= 100:
                continue
            # 转成 (item, 日期) 列表，日期取 last_event_date / recent_activity / last_update / date / updated_at
            _cutoff = (datetime.now() - timedelta(days=15)).strftime('%Y-%m-%d')
            kept = []
            removed = []
            for item in items:
                d = item.get('last_event_date') or item.get('recent_activity_date') or item.get('last_update_date') or item.get('date') or item.get('updated_at', '')
                d_str = d[:10] if d and len(d) >= 10 else ''
                if d_str >= _cutoff:
                    kept.append(item)
                else:
                    removed.append(item)
            # 如果 15 天内数据仍超 100，按时间倒序取最新 100 条
            if len(kept) > 100:
                kept.sort(key=lambda x: (
                    x.get('last_event_date') or x.get('recent_activity_date') or
                    x.get('last_update_date') or x.get('date') or x.get('updated_at', '')
                ) or '', reverse=True)
                kept = kept[:100]
            # 归档移除的数据
            if removed:
                archive_count += len(removed)
                self._archive_items(dim, removed)
            snapshot[dim] = kept

        self._print_info(f'数据留存: {archive_count} 条过期数据已归档')

        # 过滤 changelog：实体已归档的条目丢弃
        active_ids = {}
        for dim in ['providers', 'people', 'tools', 'llms', 'hotspots']:
            active_ids[dim] = {e.get('id', '') for e in snapshot.get(dim, []) if e.get('id')}
        existing_changelog = snapshot.get('changelog', [])
        existing_changelog.extend(changelog)
        filtered = [
            e for e in existing_changelog
            if not e.get('id')  # 无 id 的摘要保留（旧格式兼容，不可跳转）
            or (e.get('dimension', '') and e.get('id') in active_ids.get(e.get('dimension', ''), set()))
        ]
        snapshot['changelog'] = filtered[-100:]

        # 更新 stats
        snapshot['stats'] = {
            'total_providers': len(snapshot.get('providers', [])),
            'total_people': len(snapshot.get('people', [])),
            'total_tools': len(snapshot.get('tools', [])),
            'total_llms': len(snapshot.get('llms', [])),
            'total_hotspots': len(snapshot.get('hotspots', [])),
            'new_this_period': len([c for c in changelog if c['type'] == 'new']),
            'updated_this_period': len([c for c in changelog if c['type'] == 'update']),
            'removed_this_period': 0,
        }

        snapshot['generated_at'] = now
        snapshot['period'] = f'{(datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")} ~ {today}'

        # 保存
        self._save_snapshot(snapshot)

        total_new = len([c for c in changelog if c['type'] == 'new'])
        total_update = len([c for c in changelog if c['type'] == 'update'])
        self._print_ok(f'合并完成：新增 {total_new}，更新 {total_update}')

        # 归档历史快照
        self._archive_snapshot(snapshot)

        # changelog.html 为静态模板，数据通过 snapshot.json 加载
        # 无需额外生成操作

        # auto-push
        self._auto_push(changelog)

        return snapshot

    def _merge_single(self, old, new):
        """合并单个实体：新数据覆盖旧数据中的空字段"""
        merged = old.copy()
        for key, value in new.items():
            if key in ('updated_at',):
                continue
            if value is not None and value != '' and value != [] and value != 0:
                merged[key] = value
        return merged

    def _apply_time_decay(self, item):
        """对热度过期的事件进行时间衰减。

        衰减规则:
        - 1 天内: 不减分
        - 2-3 天: 不减分
        - 4-7 天: 每天 -2 分
        - >7 天: 基础 -8 分 + 每天额外 -3 分
        - 下限: 10 分
        - 无日期字段: 跳过衰减
        """
        date_str = item.get('last_event_date') or item.get('recent_activity_date') or item.get('last_update_date') or ''
        if not date_str or len(date_str) < 10:
            return item

        try:
            event_date = datetime.strptime(date_str[:10], '%Y-%m-%d')
            days_old = (datetime.now() - event_date).days
        except (ValueError, TypeError):
            return item

        if days_old <= 3:
            item['hot_level'] = self._score_to_level(item.get('hot_score', 50))
            return item

        score = item.get('hot_score', 50)

        if days_old <= 7:
            decay = (days_old - 3) * 2
        else:
            decay = 8 + (days_old - 7) * 3

        new_score = max(10, score - decay)
        item['hot_score'] = new_score
        item['hot_level'] = self._score_to_level(new_score)
        return item

    @staticmethod
    def _score_to_level(score):
        """将 hot_score 映射为 hot_level 文本。"""
        if score >= 80:
            return '爆热'
        if score >= 60:
            return '高热'
        if score >= 30:
            return '温热'
        if score >= 10:
            return '平稳'
        return '冷淡'

    def _diff_fields(self, old, new):
        """对比两个实体的字段差异，返回变更摘要"""
        changes = []
        for key in ['name', 'title', 'hot_score', 'hot_level', 'last_event', 'recent_activity', 'last_update', 'status', 'tier']:
            old_val = old.get(key)
            new_val = new.get(key)
            if old_val != new_val and new_val is not None:
                changes.append(f'{key}: {old_val} → {new_val}')
        return '; '.join(changes[:3]) if changes else ''

    def _load_snapshot(self):
        """加载现有快照"""
        if self.snapshot_path.exists():
            with open(self.snapshot_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            'version': '1.0',
            'generated_at': datetime.now().isoformat(),
            'period': '',
            'execution_mode': 'auto',
            'providers': [],
            'people': [],
            'tools': [],
            'llms': [],
            'changelog': [],
            'stats': {},
        }

    def _save_snapshot(self, snapshot):
        """保存快照"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with open(self.snapshot_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        self._print_ok(f'快照已保存: {self.snapshot_path}')

    def _archive_snapshot(self, snapshot):
        """归档历史快照"""
        history_dir = self.data_dir / 'history'
        history_dir.mkdir(parents=True, exist_ok=True)
        week_str = datetime.now().strftime('%Y-W%W')
        archive_path = history_dir / f'{week_str}.json'
        with open(archive_path, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)
        self._print_info(f'历史快照已归档: {archive_path}')

    def _archive_items(self, dimension, items):
        """归档过期的实体数据到 archive/ 目录"""
        archive_dir = self.data_dir / 'archive'
        archive_dir.mkdir(parents=True, exist_ok=True)
        archive_path = archive_dir / f'{dimension}.json'
        # 追加到已有归档文件
        existing = []
        if archive_path.exists():
            with open(archive_path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        existing.extend(items)
        # 去重（按 id）
        seen = {}
        for item in existing:
            seen[item.get('id', '')] = item
        with open(archive_path, 'w', encoding='utf-8') as f:
            json.dump(list(seen.values()), f, ensure_ascii=False, indent=2)
        self._print_info(f'{dimension} 归档: {len(items)} 条 → {archive_path}')

    def _write_changelog_html(self, changelog):
        """changelog.html 为静态模板，JS 动态加载 snapshot.json 渲染"""
        pass

    # ===== Agent Loop: Think =====
    def _think(self):
        """采集策略决策：检查过短间隔和连续失败"""
        metrics_path = self.data_dir / 'metrics.json'
        if not metrics_path.exists():
            # 首次运行，允许
            return True

        try:
            metrics = json.loads(metrics_path.read_text())
        except:
            return True

        now = datetime.now()

        # 1. 间隔检查：上次成功 < 6h 则跳过
        last_success = metrics.get('last_success_time')
        if last_success:
            try:
                last_dt = datetime.fromisoformat(last_success)
                hours_since = (now - last_dt).total_seconds() / 3600
                if hours_since < 6:
                    self._print_info(f'距上次成功采集仅 {hours_since:.1f}h，跳过（最短间隔 6h）')
                    return False
            except:
                pass

        # 2. 连续失败检查
        consec_fails = metrics.get('consecutive_fails', 0)
        if consec_fails >= 3:
            self._print_warn(f'连续 {consec_fails} 次失败，本次仍将继续尝试')

        return True

    # ===== Agent Loop: Verify =====
    def _verify(self, entities):
        """质量门禁：检查提取结果的新鲜度和完整性"""
        issues = []
        if not entities:
            return ['实体提取为空']
        # 1. 计算事件新鲜度
        from statistics import median
        ages = []
        for dim in ['providers', 'people', 'tools', 'llms']:
            for item in entities.get(dim, []):
                d = item.get('last_event_date') or item.get('recent_activity_date') or item.get('last_update_date') or ''
                if d and len(d) >= 10:
                    try:
                        dt = datetime.strptime(d[:10], '%Y-%m-%d')
                        ages.append((datetime.now() - dt).total_seconds() / 3600)
                    except:
                        pass
        if ages:
            median_age = median(ages)
            if median_age > 168:  # 7天
                issues.append(f'事件中位数新鲜度 {median_age:.0f}h > 168h')
        # 2. 热点数量
        hotspots = entities.get('hotspots', [])
        if len(hotspots) < 3:
            issues.append(f'热点仅 {len(hotspots)} 条')
        # 3. URL 质量
        url_stats = self._validate_entity_urls(entities)
        if url_stats.get('empty_urls', 0) > 5:
            issues.append(f'空 URL: {url_stats["empty_urls"]} 条')
        if url_stats.get('truncated_urls', 0) > 0:
            issues.append(f'截断 URL: {url_stats["truncated_urls"]} 条')
        if url_stats.get('bare_domain_urls', 0) > 2:
            issues.append(f'裸域名 URL: {url_stats["bare_domain_urls"]} 条')
        # 4. 数据完整性
        comp = self._validate_data_completeness(entities)
        if comp.get('key_people_empty_ratio', 0) > 0.5:
            issues.append(f'key_people 缺失率 {comp["key_people_empty_ratio"]:.0%}')
        # 5. 去重比异常（仅当有存量数据时）
        return issues

    def _validate_entity_urls(self, entities):
        """检查实体 URL 质量：空、截断、裸域名。

        Returns:
            dict with keys: empty_urls, truncated_urls, bare_domain_urls
        """
        empty = 0
        truncated = 0
        bare_domain = 0

        url_keys_by_dim = {
            'providers': 'last_event_url',
            'people': 'recent_activity_url',
            'tools': 'last_update_url',
            'llms': 'last_event_url',
            'hotspots': 'url',
        }

        for dim, url_key in url_keys_by_dim.items():
            for item in entities.get(dim, []):
                url = item.get(url_key, '')
                if not url or not url.strip():
                    empty += 1
                elif '...' in url:
                    truncated += 1
                else:
                    # 检查是否为裸域名（去掉协议后无路径段）
                    stripped = re.sub(r'^https?://', '', url)
                    if '/' not in stripped:
                        bare_domain += 1

        return {
            'empty_urls': empty,
            'truncated_urls': truncated,
            'bare_domain_urls': bare_domain,
        }

    def _validate_data_completeness(self, entities):
        """检查数据完整性：key_people, focus_areas, low confidence。

        Returns:
            dict with keys: key_people_empty_ratio, focus_areas_empty_ratio,
                           low_confidence_count
        """
        providers = entities.get('providers', [])
        total = len(providers)

        kp_empty = sum(1 for p in providers if not p.get('key_people'))
        fa_empty = sum(1 for p in providers if not p.get('focus_areas'))

        low_conf = 0
        for dim in ['providers', 'people', 'tools', 'llms', 'hotspots']:
            for item in entities.get(dim, []):
                if item.get('confidence') == 'low':
                    low_conf += 1

        return {
            'key_people_empty_ratio': kp_empty / total if total > 0 else 0,
            'focus_areas_empty_ratio': fa_empty / total if total > 0 else 0,
            'low_confidence_count': low_conf,
        }

    def _fuzzy_name_dedup(self, items):
        """对实体列表进行模糊名称去重。

        去重策略（按优先级）：
        1. 已知别名映射（KNOWN_ALIASES）
        2. 精确同名合并
        3. 去掉括号内容后同名
        4. 去掉常见后缀后同名

        合并规则：保留先出现的条目 ID，取最新的事件日期和最高热度分，
        新数据字段覆盖旧数据中的空字段。
        """
        if len(items) <= 1:
            return items

        seen_ids = set()

        def normalize(name):
            """规范化名称：去括号、去后缀、去空格、小写"""
            n = re.sub(r'\(.*?\)', '', name)  # 去掉括号及内容
            n = re.sub(r'（.*?）', '', n)       # 中文括号
            n = n.strip()                        # 去括号后的空格
            for suffix in self.NORMALIZE_SUFFIXES:
                if n.endswith(suffix) and len(n) > len(suffix):
                    n = n[:-len(suffix)]
            return n.strip().lower()

        # 第一步：别名映射
        alias_ids = {}
        for item in items:
            name = item.get('name', '')
            if name in self.KNOWN_ALIASES:
                alias_ids[item['id']] = self.KNOWN_ALIASES[name]

        # 第二步：规范化去重
        norms = {}  # normalized_name -> primary item
        order = []  # preserve insertion order

        for item in items:
            item_id = alias_ids.get(item['id'], item['id'])
            name = item.get('name', '')
            norm_name = normalize(name)
            norm_id = normalize(item_id)

            # 尝试匹配：
            # a) 精确同名
            # b) 规范化同名
            # c) 别名映射指向同一个主 ID
            matched = None

            if name in norms:
                matched = norms[name]
            elif norm_name in norms:
                matched = norms[norm_name]
            elif norm_id in norms:
                matched = norms[norm_id]
            else:
                # 查找是否有其他条目规范化后匹配
                for existing_norm, existing_primary in norms.items():
                    if existing_norm == norm_name or existing_norm == norm_id:
                        matched = existing_primary
                        break

            if matched:
                # 合并：保留旧 key_people（非空不覆盖）
                old_kp = matched.get('key_people', [])
                # 先保存需要特殊处理的字段旧值
                old_score = matched.get('hot_score', 0)
                old_date = matched.get('last_event_date') or matched.get('recent_activity_date') or ''
                # 合并通用字段（排除 hot_score 和日期字段）
                for key, value in item.items():
                    if key in ('id', 'updated_at', 'hot_score',
                               'last_event_date', 'recent_activity_date', 'last_update_date'):
                        continue
                    if key == 'key_people' and old_kp:
                        continue  # 保留原有的非空 key_people
                    if value is not None and value != '' and value != [] and value != 0:
                        matched[key] = value
                if old_kp:
                    matched['key_people'] = old_kp
                # 取最高热度
                matched['hot_score'] = max(old_score, item.get('hot_score', 0))
                # 取最新日期
                for dk in ['last_event_date', 'recent_activity_date', 'last_update_date']:
                    new_d = item.get(dk, '')
                    cur_d = matched.get(dk, '')
                    if new_d and new_d > (cur_d or ''):
                        matched[dk] = new_d
                matched['hot_level'] = self._score_to_level(matched['hot_score'])
            else:
                norms[name] = item
                norms[norm_name] = item
                norms[norm_id] = item
                order.append(item)

        return order

    # ===== Agent Loop: Observe =====
    def _observe(self, run_result, fetch_results=None, entities=None, snapshot=None):
        """记录运行指标到 metrics.json"""
        metrics_path = self.data_dir / 'metrics.json'
        try:
            metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
        except:
            metrics = {}

        now = datetime.now()
        now_iso = now.isoformat()

        # 基础指标
        metrics['last_run_time'] = now_iso
        metrics['total_runs'] = metrics.get('total_runs', 0) + 1

        if run_result:
            metrics['last_success_time'] = now_iso
            metrics['consecutive_fails'] = 0
        else:
            metrics['consecutive_fails'] = metrics.get('consecutive_fails', 0) + 1

        # 源成功率
        if fetch_results:
            source_health = metrics.get('source_health', {})
            success_count = 0
            total = 0
            for key, r in fetch_results.items():
                if key.startswith('_'):
                    continue
                total += 1
                ok = r.get('success', False) if isinstance(r, dict) else bool(r)
                sh = source_health.setdefault(key, {'consecutive_fails': 0, 'last_result': None})
                if ok:
                    sh['consecutive_fails'] = 0
                    success_count += 1
                else:
                    sh['consecutive_fails'] = sh.get('consecutive_fails', 0) + 1
                sh['last_result'] = 'ok' if ok else 'fail'
                sh['last_time'] = now_iso
            metrics['source_health'] = source_health
            metrics['source_success_rate'] = round(success_count / total, 3) if total else 0

        # 实体统计
        if entities:
            total_ents = sum(len(entities.get(k, [])) for k in ['providers', 'people', 'tools', 'llms'])
            metrics['extracted_entities'] = total_ents

        # 快照统计
        if snapshot and 'stats' in snapshot:
            for k, v in snapshot['stats'].items():
                metrics[f'snapshot_{k}'] = v

        # 数据新鲜度
        if entities:
            from statistics import median
            ages = []
            for dim in ['providers', 'people', 'tools', 'llms']:
                for item in entities.get(dim, []):
                    d = item.get('last_event_date') or item.get('recent_activity_date') or ''
                    if d and len(d) >= 10:
                        try:
                            dt = datetime.strptime(d[:10], '%Y-%m-%d')
                            ages.append((datetime.now() - dt).total_seconds() / 3600)
                        except:
                            pass
            if ages:
                metrics['median_event_age_hours'] = round(median(ages), 1)
                metrics['min_event_age_hours'] = round(min(ages), 1)

        # 保留最近 N 次运行历史
        history = metrics.get('run_history', [])
        history.append({
            'time': now_iso,
            'success': bool(run_result),
            'entities': metrics.get('extracted_entities', 0),
            'source_rate': metrics.get('source_success_rate', 0),
        })
        metrics['run_history'] = history[-30:]  # 保留最近 30 次

        metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2))
        self._print_info(f'指标已记录到 metrics.json')

    # ===== Run =====
    def run(self, source_keys=None):
        """完整流程：Think → Act → Verify → Observe"""
        self._print_info('=== LLM Radar 数据采集 ===')
        self._print_info(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        self._print_info(f'数据目录: {self.data_dir}')
        print()

        # [Think] 采集策略决策
        if not self._think():
            return False

        # Step 1: Fetch
        self._print_info('[1/3] 抓取新闻源...')
        target_keys = source_keys or list(SOURCES.keys())
        fetch_results = self.fetch_all(source_keys)
        # 构建源级结果字典（用于指标跟踪）
        source_results = {}
        successful = {r['source'] for r in fetch_results} if fetch_results else set()
        for k in target_keys:
            source_results[k] = {'success': k in successful}
        source_results['_source_keys'] = target_keys  # 调试信息

        if not fetch_results:
            self._print_err('所有新闻源抓取失败')
            self._observe(False, fetch_results=source_results)
            return False
        print()

        # Step 2: Extract
        self._print_info('[2/3] LLM 提取实体...')
        entities = self.extract_entities(fetch_results)
        if not entities:
            self._print_err('实体提取失败')
            self._observe(False, fetch_results=source_results)
            return False

        # [Verify] 质量门禁
        issues = self._verify(entities)
        if issues:
            self._print_warn(f'质量门禁: {"; ".join(issues)}')
            self._skip_push = True
        else:
            self._skip_push = False
            self._print_ok('质量门禁通过')
        print()

        # Step 3: Merge
        self._print_info('[3/3] 合并到快照...')
        snapshot = self.merge_entities(entities)
        if not snapshot:
            self._print_err('合并失败')
            self._observe(False, fetch_results=source_results, entities=entities)
            return False

        # [Observe] 记录本次运行指标
        self._observe(True, fetch_results=source_results, entities=entities, snapshot=snapshot)

        print()
        stats = snapshot.get('stats', {})
        self._print_ok(f'完成！当前数据: {stats.get("total_providers",0)} 厂商 / {stats.get("total_people",0)} 人物 / {stats.get("total_tools",0)} 工具 / {stats.get("total_llms",0)} 模型 / {stats.get("total_hotspots",0)} 热点')
        return True

    # ===== Selenium Check =====
    def check_selenium(self):
        """检查 Selenium 环境是否满足抓取要求"""
        import subprocess, os, shutil

        print("\n🔍 Selenium 环境检查")
        print("=" * 40)
        all_pass = True

        # 1. Chrome binary
        chrome_path = self._resolve_chrome_binary()
        if chrome_path and os.path.exists(chrome_path):
            r = subprocess.run([chrome_path, "--version"], capture_output=True, text=True, timeout=10)
            chrome_ver = r.stdout.strip() if r.stdout else "unknown"
            print(f"  ✅ Chrome: {chrome_ver}")
        else:
            print(f"  ❌ Chrome: 未找到 ({chrome_path})")
            print(f"     解决方案: 安装 Google Chrome")
            all_pass = False

        # 2. Chromedriver
        driver_path = self._resolve_chromedriver()
        if driver_path and os.path.exists(driver_path):
            r = subprocess.run([driver_path, "--version"], capture_output=True, text=True, timeout=5)
            driver_ver = r.stdout.strip() if r.stdout else "unknown"
            print(f"  ✅ ChromeDriver: {driver_ver}")
            # Check version match (use regex, not split)
            import re as _re
            chrome_m = _re.search(r"(\d+\.\d+\.\d+\.\d+)", chrome_ver if chrome_ver != "unknown" else "")
            driver_m = _re.search(r"(\d+\.\d+\.\d+\.\d+)", driver_ver if driver_ver != "unknown" else "")
            chrome_num = chrome_m.group(1) if chrome_m else ""
            driver_num = driver_m.group(1) if driver_m else ""
            if chrome_num[:2] != driver_num[:2]:
                print(f"  ❌ Chrome ({chrome_num}) 与 ChromeDriver ({driver_num}) 主版本不匹配")
                print(f"     解决方案（Linux）: sudo yum install -y google-chrome-stable")
                print(f"     或使用 pip install webdriver-manager 自动匹配")
                all_pass = False
            elif chrome_num != driver_num:
                print(f"  ⚠️  版本不完全匹配: Chrome={chrome_num}, Driver={driver_num}（小版本差异，可尝试运行）")
        else:
            print(f"  ❌ ChromeDriver: 未找到")
            print(f"     解决方案: python3 -c \"from webdriver_manager.chrome import ChromeDriverManager; print(ChromeDriverManager().install())\"")
            all_pass = False

        # 3. Selenium import
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            print(f"  ✅ Selenium 库: 可用 (webdriver {webdriver.__version__})")
        except ImportError as e:
            print(f"  ❌ Selenium 库: 缺失 ({e})")
            print(f"     解决方案: pip3 install selenium webdriver-manager")
            all_pass = False

        # 4. Actual browser launch test
        if os.path.exists(driver_path):
            try:
                from selenium import webdriver
                from selenium.webdriver.chrome.options import Options
                opts = Options()
                opts.add_argument("--headless=new")
                opts.add_argument("--no-sandbox")
                opts.add_argument("--disable-dev-shm-usage")
                driver = webdriver.Chrome(service=Service(driver_path), options=opts)
                import time
                t1 = time.time()
                driver.get("data:text/html,<h1>Selenium OK</h1>")
                elapsed = time.time() - t1
                driver.quit()
                print(f"  ✅ 浏览器启动测试: 通过 ({elapsed:.1f}s)")
            except Exception as e:
                err = str(e).split("\\n")[0][:80]
                print(f"  ❌ 浏览器启动测试: 失败 ({err})")
                print(f"     解决方案: 检查是否有残留 chromedriver 进程 (pkill -9 -f chromedriver) 后重试")
                all_pass = False

        # Summary
        print("\n" + "=" * 40)
        if all_pass:
            print("✅ Selenium 环境满足要求")
        else:
            print("❌ Selenium 环境不满足要求，请按上述解决方案修复")

    # ===== Sources =====
    def list_sources(self):
        """列出所有新闻源"""
        table = PrettyTable()
        table.field_names = ["分类", "名称", "URL"]
        table.align = "l"
        for key, src in SOURCES.items():
            table.add_row([src['category'], src['name'], src['url']])
        print(f'\n📰 新闻源 ({len(SOURCES)} 个)\n')
        print(table)

CRON_TAG = '# llm-radar-collector'
RUN_SCRIPT = PROJECT_ROOT / 'llm-radar-run.sh'
CRON_CMD = f'{RUN_SCRIPT} >> {DATA_DIR}/collector.log 2>&1'
CRON_SCHEDULE = '0 7,14,21 * * *'  # 每天 7:00、14:00、21:00
CRON_HELP = f'crontab --add [schedule] - 添加定时任务（默认 {CRON_SCHEDULE}）'

def crontab_add(schedule=None):
    """添加定时任务"""
    import subprocess
    sched = schedule or CRON_SCHEDULE
    entry = f'{sched} {CRON_CMD} {CRON_TAG}'
    # 读取现有 crontab
    result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    lines = result.stdout.splitlines() if result.returncode == 0 else []
    # 检查是否已存在
    if any(CRON_TAG in line for line in lines):
        print(f'⚠️ 定时任务已存在，使用 crontab --update 更新')
        return
    # 添加注释说明
    if not any(CRON_TAG in line for line in lines):
        lines.append('')
        lines.append('# === LLM Radar 定时采集任务 ===')
        lines.append(f'# 项目目录: {PROJECT_ROOT}')
        lines.append(f'# 依赖: DEEPSEEK_API_KEY 环境变量需在 crontab 文件头设置')
        lines.append(f'# 依赖: conda 环境 llm-radar (Linux) 或 python3 (macOS)')
        lines.append('#')
    lines.append(entry)
    proc = subprocess.run(['crontab', '-'], input='\n'.join(lines) + '\n', text=True)
    if proc.returncode == 0:
        print(f'✅ 定时任务已添加: {sched}')
    else:
        print(f'❌ 添加失败: {proc.stderr}')


def crontab_remove():
    """移除定时任务"""
    import subprocess
    result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    if result.returncode != 0:
        print('⚠️ 无 crontab 任务')
        return
    lines = [l for l in result.stdout.splitlines() if CRON_TAG not in l]
    proc = subprocess.run(['crontab', '-'], input='\n'.join(lines) + '\n', text=True)
    if proc.returncode == 0:
        print('✅ 定时任务已移除')
    else:
        print(f'❌ 移除失败: {proc.stderr}')


def crontab_list():
    """列出定时任务"""
    import subprocess
    result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    if result.returncode != 0:
        print('⚠️ 无 crontab 任务')
        return
    for line in result.stdout.splitlines():
        if CRON_TAG in line:
            print(f'  {line}')
    else:
        if not any(CRON_TAG in l for l in result.stdout.splitlines()):
            print('⚠️ 未找到 llm-radar 定时任务')


def crontab_update(schedule=None):
    """更新定时任务"""
    crontab_remove()
    crontab_add(schedule)


def crontab_status():
    """查看定时任务状态"""
    import subprocess
    result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    found = any(CRON_TAG in line for line in result.stdout.splitlines()) if result.returncode == 0 else False
    if found:
        print('✅ 定时任务: 已启用')
        # 检查最近日志
        log_path = DATA_DIR / 'collector.log'
        if log_path.exists():
            with open(log_path, 'r') as f:
                lines = f.readlines()
            last_lines = lines[-3:] if lines else []
            print(f'📋 最近日志 ({log_path}):')
            for l in last_lines:
                print(f'  {l.rstrip()}')
    else:
        print('⚪ 定时任务: 未启用')


def main():
    """主函数"""
    if len(sys.argv) < 2:
        print('Usage: python3 llm-radar-collector.py <command> [args]')
        print('Commands: fetch [source], merge, run [source], sources, help')
        sys.exit(1)

    command = sys.argv[1]
    args = sys.argv[2:]

    collector = LLMRadarCollector()

    if command == 'fetch':
        source_keys = args if args else None
        collector.fetch_all(source_keys)

    elif command == 'merge':
        # 从缓存读取上次 fetch 结果
        if collector.fetch_cache_path.exists():
            with open(collector.fetch_cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)
            entities = collector.extract_entities(cache.get('sources', []))
            collector.merge_entities(entities)
        else:
            collector._print_err('无 fetch 缓存，请先执行 fetch')

    elif command == 'run':
        # 先检查 remote 更新
        try:
            r = subprocess.run(['git', 'pull', '--rebase'], cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=30)
            if r.returncode == 0:
                out = r.stdout.strip()
                if 'Already up to date' in out:
                    print('ℹ️ remote 无更新')
                else:
                    print('✅ remote 已同步')
            else:
                print(f'⚠️ git pull 跳过: {r.stderr[:100]}')
        except Exception as e:
            print(f'⚠️ git pull 失败: {e}')
        source_keys = args if args else None
        collector.run(source_keys)

    elif command == 'selenium-check':
        collector.check_selenium()

    elif command == 'sources':
        collector.list_sources()

    elif command == 'crontab':
        if not args or args[0] == '--status':
            crontab_status()
        elif args[0] == '--add':
            crontab_add(args[1] if len(args) > 1 else None)
        elif args[0] == '--remove':
            crontab_remove()
        elif args[0] == '--list':
            crontab_list()
        elif args[0] == '--update':
            crontab_update(args[1] if len(args) > 1 else None)
        else:
            print('Usage: crontab --add|--remove|--list|--update|--status [schedule]')

    elif command == 'commit':
        msg = ' '.join(args) if args else f'manual@llm-radar: update data ({datetime.now().strftime("%Y-%m-%d %H:%M")})'
        try:
            subprocess.run(['git', 'add', '-A'], cwd=PROJECT_ROOT, check=True, capture_output=True)
            r = subprocess.run(['git', 'commit', '-m', msg], cwd=PROJECT_ROOT, capture_output=True, text=True)
            if r.returncode == 0:
                print(f'✅ commit 完成: {msg}')
            else:
                print(f'ℹ️ {r.stderr.strip()}')
        except Exception as e:
            print(f'❌ commit 失败: {e}')

    elif command == 'auto-push':
        try:
            subprocess.run(['git', 'add', '-A'], cwd=PROJECT_ROOT, check=True, capture_output=True)
            msg = f'manual@llm-radar: auto push ({datetime.now().strftime("%Y-%m-%d %H:%M")})'
            subprocess.run(['git', 'commit', '-m', msg], cwd=PROJECT_ROOT, capture_output=True)
            subprocess.run(['git', 'push'], cwd=PROJECT_ROOT, check=True, capture_output=True)
            print('✅ auto-push 完成')
        except subprocess.CalledProcessError as e:
            print(f'ℹ️ auto-push 跳过: {e.stderr.decode()[:200] if e.stderr else str(e)}')

    elif command == 'help':
        print('\n📖 LLM Radar 数据采集脚本\n')
        print('Usage: python3 llm-radar-collector.py <command> [args]\n')
        print('Commands:')
        print('  fetch [source]           - 抓取新闻并提取实体（默认全部源）')
        print('  merge                    - 将 fetch 结果合并到 snapshot.json')
        print('  run [source]             - fetch + merge 一步完成（含 auto-push）')
        print('  selenium-check           - 检查 Selenium 环境是否满足要求')
        print('  sources                  - 列出所有新闻源')
        print(f'  {CRON_HELP}')
        print('  crontab --remove         - 移除定时任务')
        print('  crontab --list           - 列出定时任务')
        print('  crontab --update [sched] - 更新定时任务')
        print('  crontab --status         - 查看定时任务状态')
        print('  commit [message]         - git add + commit（默认 message: manual@llm-radar）')
        print('  auto-push                - git add + commit + push')
        print('  help                     - 显示帮助信息\n')
        print('Examples:')
        print('  python3 llm-radar-collector.py run                    # 全量采集+推送')
        print('  python3 llm-radar-collector.py run qbitai             # 只采集量子位')
        print('  python3 llm-radar-collector.py commit                 # 仅 commit')
        print('  python3 llm-radar-collector.py auto-push              # 手动推送')
        print('  python3 llm-radar-collector.py crontab --add          # 每天9:00、21:00采集')

    else:
        collector._print_err(f'未知命令: {command}')
        sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\n用户中断操作')
        sys.exit(1)
    except Exception as e:
        print(f'\n❌ 错误: {e}')
        sys.exit(1)
