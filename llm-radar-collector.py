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

【指令清单】
| 指令 | 参数 | 功能说明 |
|------|------|---------|
| fetch | [source] | 抓取新闻并提取实体（默认全部源） |
| merge | - | 将 fetch 结果合并到 snapshot.json |
| run | [source] | fetch + merge 一步完成 |
| sources | - | 列出所有新闻源 |
| help | - | 显示帮助信息 |

Related Paths
- 数据目录: ~/CodeSpace/llm-radar.jaden.tech/data
- Web2MD目录: ~/CodeSpace/script-miner/project/web2md
- LLM Manager: ~/CodeSpace/script-miner/llm-manager

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

# ===== Constants =====
PROJECT_ROOT = Path.home() / 'CodeSpace' / 'llm-radar.jaden.tech'
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
    'techcrunch': {
        'name': 'TechCrunch AI',
        'url': 'https://techcrunch.com/category/artificial-intelligence/',
        'category': '英文媒体',
        'search_queries': ['LLM', 'AI model', 'AI funding', 'OpenAI', 'Anthropic'],
    },
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


class LLMRadarCollector:
    """LLM Radar 数据采集器"""

    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.data_dir = DATA_DIR
        self.snapshot_path = SNAPSHOT_PATH
        self.fetch_cache_path = FETCH_CACHE_PATH
        self.api_key = self._load_api_key()
        self.base_url = "https://api.deepseek.com/v1"

    def _load_api_key(self):
        """从环境变量或 secret-manager 加载 DeepSeek API key"""
        key = os.environ.get('DEEPSEEK_API_KEY', '')
        if key:
            self._print_ok('DeepSeek API key 已从环境变量加载')
            return key
        try:
            sm_path = Path.home() / 'CodeSpace' / 'script-miner' / 'efficiency' / 'secret_manager.py'
            if sm_path.exists():
                sys.path.insert(0, str(sm_path.parent))
                from secret_manager import SecretManager
                sm = SecretManager()
                key = sm._secrets.get('DEEPSEEK_API_KEY', {}).get('secret', '')
        except Exception:
            pass
        if key:
            self._print_ok('DeepSeek API key 已从 secret-manager 加载')
        else:
            self._print_err('DEEPSEEK_API_KEY 未配置，请在环境变量中设置')
        return key

    def _print_ok(self, msg):
        print(f'✅ {msg}')

    def _print_err(self, msg):
        print(f'❌ {msg}')

    def _print_info(self, msg):
        print(f'ℹ️ {msg}')

    def _print_warn(self, msg):
        print(f'⚠️ {msg}')

    def _call_deepseek(self, system_content, user_content, model="deepseek-v4-flash"):
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
                max_tokens=8000,
                temperature=0.1,
            )
            msg = resp.choices[0].message
            return {"content": msg.content, "prompt_tokens": resp.usage.prompt_tokens, "completion_tokens": resp.usage.completion_tokens} if resp.usage else {"content": msg.content}
        except Exception as e:
            self._print_err(f'DeepSeek API 调用失败: {e}')
            return None

    def _auto_push(self, changelog):
        """有数据更新时自动 commit + push"""
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
            subprocess.run(['git', 'commit', '-m', msg], cwd=self.project_root, capture_output=True)
            subprocess.run(['git', 'push'], cwd=self.project_root, capture_output=True)
            self._print_ok(f'auto-push 完成: {msg}')
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if e.stderr else ''
            if 'nothing to commit' in stderr or 'no changes' in stderr:
                self._print_info('无变更需要提交')
            else:
                self._print_warn(f'auto-push 跳过: {stderr[:200]}')

    # ===== Fetch =====
    def fetch_source(self, source_key):
        """抓取单个新闻源"""
        source = SOURCES.get(source_key)
        if not source:
            self._print_err(f'未知新闻源: {source_key}')
            return None

        self._print_info(f'抓取 {source["name"]} ({source["url"]})')

        try:
            import requests
            from bs4 import BeautifulSoup

            resp = requests.get(source['url'], timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            resp.raise_for_status()
            resp.encoding = resp.apparent_encoding or 'utf-8'

            soup = BeautifulSoup(resp.text, 'html.parser')

            # 提取页面文本（简化处理）
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()

            text = soup.get_text(separator='\n', strip=True)
            # 截取前 5000 字符避免 token 超限
            text = text[:5000]

            self._print_ok(f'{source["name"]} 抓取成功，{len(text)} 字符')
            return {
                'source': source_key,
                'name': source['name'],
                'url': source['url'],
                'content': text,
                'fetched_at': datetime.now().isoformat(),
            }

        except Exception as e:
            self._print_err(f'{source["name"]} 抓取失败: {e}')
            return None

    def fetch_all(self, source_keys=None):
        """抓取所有新闻源"""
        if source_keys is None:
            source_keys = list(SOURCES.keys())

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
        if not self._llm_manager:
            self._print_err('llm-manager 未加载，无法提取实体')
            return None

        # 合并所有源的内容
        combined = ''
        for r in fetch_results:
            combined += f'\n\n--- {r["name"]} ({r["url"]}) ---\n{r["content"]}'

        # 截取避免 token 超限
        combined = combined[:12000]

        system_prompt = """你是一个 LLM 行业情报分析助手。从新闻内容中提取以下 4 类实体。

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
6. 不要编造数据，只提取新闻中明确提到的信息"""

        user_prompt = f"""请从以下 LLM 行业新闻中提取实体：

{combined}

请输出 JSON 格式的结果，包含 providers、people、tools、llms、hotspots 五个数组。

hotspots 数组中每个元素格式：
```json
{{"id": "英文标识", "title": "中文标题", "summary": "50-100字简报", "date": "YYYY-MM-DD", "source": "来源名称", "url": "原文链接", "related_providers": ["厂商id"], "related_people": ["人物id"], "related_tools": ["工具id"], "related_llms": ["模型id"]}}
```
热点为近期最重要/最受关注的 3-5 条行业事件。"""

        self._print_info('调用 LLM 提取实体...')
        start_time = time.time()

        # 直接调用 DeepSeek API
        result = self._call_deepseek(system_prompt, user_prompt)

        duration = round(time.time() - start_time, 1)

        if not result or result.get('error'):
            self._print_err(f'LLM 调用失败: {result.get("error") if result else "未知错误"}')
            return None

        # 解析 JSON 输出
        content = result.get('content', '')
        try:
            # 尝试提取 JSON 块
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                entities = json.loads(json_match.group(1))
            else:
                # 尝试直接解析
                entities = json.loads(content)

            total = sum(len(entities.get(k, [])) for k in ['providers', 'people', 'tools', 'llms'])
            self._print_ok(f'实体提取完成，耗时 {duration}s，共 {total} 个实体')
            return entities

        except json.JSONDecodeError as e:
            self._print_err(f'JSON 解析失败: {e}')
            self._print_info(f'LLM 输出前 500 字符: {content[:500]}')
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
            existing = {e['id']: e for e in snapshot.get(dimension, [])}
            new_items = new_entities.get(dimension, [])

            for item in new_items:
                item_id = item.get('id')
                if not item_id:
                    continue

                if item_id in existing:
                    # 更新现有实体
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
                        })
                else:
                    # 新增实体
                    item['updated_at'] = now
                    existing[item_id] = item
                    changelog.append({
                        'type': 'new',
                        'dimension': dimension,
                        'id': item_id,
                        'summary': item.get('last_event') or item.get('recent_activity') or item.get('last_update') or '新实体',
                        'date': today,
                    })

            snapshot[dimension] = list(existing.values())

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

        # 更新 changelog（保留最近 100 条）
        existing_changelog = snapshot.get('changelog', [])
        existing_changelog.extend(changelog)
        snapshot['changelog'] = existing_changelog[-100:]

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

        # 生成 changelog.html
        self._write_changelog_html(snapshot.get('changelog', []))

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
        """从 changelog 数组生成 changelog.html"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        rows = ''.join(
            f'<tr><td class="p-2 border-b border-gray-800 text-xs text-gray-500">{c.get("date","")}</td>'
            f'<td class="p-2 border-b border-gray-800"><span class="badge {"bg-green-600" if c["type"]=="new" else "bg-blue-600" if c["type"]=="update" else "bg-red-600"} text-white text-xs">{c["type"]}</span></td>'
            f'<td class="p-2 border-b border-gray-800 text-xs text-gray-400">{c.get("dimension","")}</td>'
            f'<td class="p-2 border-b border-gray-800 text-xs text-white">{c.get("summary","")}</td></tr>\n'
            for c in reversed(changelog[-50:])
        )
        html = f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>LLM Radar — 更新日志</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>var p=new URLSearchParams(window.location.search),t=p.get('t'),oh=3600000;(!t||Date.now()-parseInt(t)>oh)&&(p.set('t',Date.now()),window.location.replace(window.location.pathname+(window.location.search?'&':'?')+p.toString()+(window.location.hash||'')))</script>
<style>body{{font-family:Inter,sans-serif;background:#0a0a14;color:#e0e0e0}}
.badge{{display:inline-block;padding:1px 6px;border-radius:4px;font-size:0.6rem;font-weight:600}}
</style></head>
<body class="min-h-screen p-6">
<div class="max-w-4xl mx-auto">
<div class="flex items-center justify-between mb-6">
<h1 class="text-lg font-bold text-white">📋 更新日志</h1>
<a href="./" class="text-xs text-cobalt-400 hover:text-cobalt-300">← 返回仪表盘</a>
</div>
<p class="text-xs text-gray-500 mb-4">数据更新时间: {now} · 共 {len(changelog)} 条记录</p>
<div class="overflow-x-auto">
<table class="w-full"><thead><tr class="text-xs text-gray-500 uppercase">
<th class="p-2 text-left">日期</th><th class="p-2 text-left">类型</th><th class="p-2 text-left">维度</th><th class="p-2 text-left">摘要</th>
</tr></thead><tbody>{rows}</tbody></table>
</div>
</div>
</body></html>'''
        changelog_path = self.project_root / 'changelog.html'
        with open(changelog_path, 'w', encoding='utf-8') as f:
            f.write(html)
        self._print_ok(f'changelog.html 已生成: {changelog_path}')

    # ===== Run =====
    def run(self, source_keys=None):
        """完整流程：fetch → extract → merge"""
        self._print_info('=== LLM Radar 数据采集 ===')
        self._print_info(f'时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        self._print_info(f'数据目录: {self.data_dir}')
        print()

        # Step 1: Fetch
        self._print_info('[1/3] 抓取新闻源...')
        fetch_results = self.fetch_all(source_keys)
        if not fetch_results:
            self._print_err('所有新闻源抓取失败')
            return False
        print()

        # Step 2: Extract
        self._print_info('[2/3] LLM 提取实体...')
        entities = self.extract_entities(fetch_results)
        if not entities:
            self._print_err('实体提取失败')
            return False
        print()

        # Step 3: Merge
        self._print_info('[3/3] 合并到快照...')
        snapshot = self.merge_entities(entities)
        if not snapshot:
            self._print_err('合并失败')
            return False

        print()
        stats = snapshot.get('stats', {})
        self._print_ok(f'完成！当前数据: {stats.get("total_providers",0)} 厂商 / {stats.get("total_people",0)} 人物 / {stats.get("total_tools",0)} 工具 / {stats.get("total_llms",0)} 模型 / {stats.get("total_hotspots",0)} 热点')
        return True

    # ===== Sources =====
    def list_sources(self):
        """列出所有新闻源"""
        print('\n📰 新闻源列表\n')
        for key, src in SOURCES.items():
            print(f'  {key:15} {src["name"]:12} {src["category"]:8} {src["url"]}')
        print(f'\n共 {len(SOURCES)} 个新闻源')


CRON_TAG = '# llm-radar-collector'
RUN_SCRIPT = PROJECT_ROOT / 'llm-radar-run.sh'
CRON_CMD = f'{RUN_SCRIPT} >> {DATA_DIR}/collector.log 2>&1'
CRON_SCHEDULE = '0 9,21 * * *'  # 每天 9:00、21:00

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
        source_keys = args if args else None
        collector.run(source_keys)

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
        msg = ' '.join(args) if args else 'manual@llm-radar: update data'
        try:
            subprocess.run(['git', 'add', '-A'], cwd=PROJECT_ROOT, check=True, capture_output=True)
            r = subprocess.run(['git', 'commit', '-m', msg], cwd=PROJECT_ROOT, capture_output=True, text=True)
            if r.returncode == 0:
                print(f'✅ commit 完成: {msg}')
            else:
                print(f'ℹ️  {r.stderr.strip()}')
        except Exception as e:
            print(f'❌ commit 失败: {e}')

    elif command == 'auto-push':
        try:
            subprocess.run(['git', 'add', '-A'], cwd=PROJECT_ROOT, check=True, capture_output=True)
            msg = 'manual@llm-radar: auto push'
            subprocess.run(['git', 'commit', '-m', msg], cwd=PROJECT_ROOT, capture_output=True)
            subprocess.run(['git', 'push'], cwd=PROJECT_ROOT, check=True, capture_output=True)
            print('✅ auto-push 完成')
        except subprocess.CalledProcessError as e:
            print(f'ℹ️  auto-push 跳过: {e.stderr.decode()[:200] if e.stderr else str(e)}')

    elif command == 'help':
        print('\n📖 LLM Radar 数据采集脚本\n')
        print('Usage: python3 llm-radar-collector.py <command> [args]\n')
        print('Commands:')
        print('  fetch [source]           - 抓取新闻并提取实体（默认全部源）')
        print('  merge                    - 将 fetch 结果合并到 snapshot.json')
        print('  run [source]             - fetch + merge 一步完成（含 auto-push）')
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
