# LLM Radar — Agent Guide

Compact single-project dashboard. One Python collector, one Vanilla JS frontend, deployed on GitHub Pages.

## Structure

- `llm-radar-collector.py` — sole Python script (~1330 LOC). No package layout, no modules.
- `index.html` — single-page frontend, Tailwind CDN, Vanilla JS. No build step.
- `changelog.html` — static template, renders from `data/snapshot.json` at runtime.
- `data/snapshot.json` — primary data artifact (JSON, ~8700 lines). Loaded by both HTML files.
- `data/fetch-cache.json` / `data/metrics.json` — auto-generated, gitignored.
- `data/dead-letter.json` — git push failures, gitignored.
- `data/archive/`, `data/history/` — auto-generated archived entities and weekly snapshots.
- `llm-news-prompt.md` — LLM data spec, output schema guidance.
- `features.md` — feature checklist.
- `loop.md` — iteration checklist.

## Key Commands

```bash
python3 llm-radar-collector.py run              # Think → Act → Verify → Observe + push
python3 llm-radar-collector.py run <source>     # single source (e.g. qbitai, techcrunch)
python3 llm-radar-collector.py sources          # list sources (prettytable)
python3 llm-radar-collector.py fetch [source]   # fetch only (Selenium → requests fallback)
python3 llm-radar-collector.py merge            # merge from fetch cache
python3 llm-radar-collector.py crontab --add    # schedule daily 09:00, 21:00
python3 llm-radar-collector.py commit [msg]     # git add + commit
python3 llm-radar-collector.py auto-push        # git add + commit + push
./llm-radar-run.sh                              # cross-platform wrapper (auto-detects Mac/Linux)
python3 -m http.server 8080                     # local preview
```

## Dependencies

```bash
pip3 install openai selenium webdriver-manager requests beautifulsoup4 prettytable
```

`DEEPSEEK_API_KEY` required via `export` or `.env` file in project root. Chrome browser required for Selenium headless mode.

## Execution Flow — Agent Loop

```
run() ordered as:

[Think]   _think()          检查 6h 间隔、连续失败 ≥ 3
[Act]     fetch_all()       Selenium 无头抓取 7 源（chromedriver，page_text），失败降级 requests
[Act]     extract_entities() DeepSeek API（max_tokens=16000, deepseek-v4-flash）
[Verify]  _verify()         质量门禁：事件中位数新鲜度 < 7 天，热点 ≥ 3 条
[Act]     merge_entities()  按 name 去重 + 合并 + 过期归档（100+15d 滑动窗口）
[Observe] _observe()        写 metrics.json（源健康、连续失败、运行历史 30 次）
[Act]     _auto_push()      git commit + push（质量门禁未通过则跳过）
```

- Detects LLM output truncation (content > 7000 chars), auto-retries with `max_tokens=16000`
- JSON parsing: 3-level fallback (code block → strict=False relaxed parse → bracket balancing truncation fix)
- Retry prompt reuses the full prompt with date context (not a stripped version)
- Push failures go to `data/dead-letter.json` (last 10)

## Frontend (index.html)

- 5 tabs: tools / llms / providers / people / hotspots. Default: llms.
- Country filter: all / China / global (Unicode Han script detection). Applies to all 5 tabs including hotspots.
- Source filter: 7 clickable source chips, filters entities by source domain match. Applies to all tabs including hotspots.
- Tab counts update in real-time when filters change (including `tc-hotspots`).
- Responsive: data sources and filter chips auto-hide below 1200px (`hide-1200`).
- Auto-refresh: 10 min interval, saves tab/filter/sort/scroll to localStorage.
- Cache busting: `?t=<timestamp>` in data fetch URLs.
- Cross-tab linking: click entity chips to jump to another tab with highlight.
- Search icon (🔍) on entity names and event URLs: `cn.bing.com/search?q=keyword+site%3Adomain`.
- Hotspot FAB: shows events from last 3 hours.
- Click ago-label on localhost → copies `run` command; on production → navigates to `changelog.html`.
- Version: v1.5 in footer.

### Console 规范 (2026-08-15 起)

- **必要性分级**:
  - `error`: 仅异常终止路径（数据加载彻底失败）
  - `warn`: 可恢复异常（如 overview.json 加载失败回退 snapshot）
  - `info`/`log`: 有意义的里程碑（如"数据加载完成 N 实体"）
  - `debug`: 开发调试用 — 生产代码**不保留**调试 log（历史 423/424 行已删）
- **格式**: 统一前缀 `[llm-radar] `，如 `console.warn('[llm-radar] overview.json load failed:', e.message)`
- 对象展开打印，不用字符串拼接；不打印敏感信息（token/key）
- CSS 规则：属性**不得用引号包裹**（`'font-size':0.7rem` 是无效 CSS，浏览器丢弃该声明 — 2026-08-15 修复 52 处）

## `_verify()` Quality Gate

- Event median freshness: extracted entity `last_event_date` median must be < 7 days old. If older, quality gate fails (skips auto-push).
- Hotspot count: newly extracted hotspots must be ≥ 3. If fewer, quality gate fails.
- Failure does NOT prevent data save — `merge` still runs, `snapshot.json` is updated. Only `auto-push` is skipped.

## JSON Parsing

```python
# _parse_json_output 3-level fallback:
1. re.search(r'```json\s*([\s\S]*?)\s*```', content)  # extract code block
2. json.loads(text, strict=False)                      # relaxed: allow control chars
3. _try_fix_truncated_json(text)                        # bracket balancing + string truncation

# _try_parse_json:
- json.loads(text)          # strict first
- json.loads(text, strict=False)  # relax on failure
```

## Data Retention

- Max 100 entities per dimension.
- 15-day sliding window: entities without recent events (> 15 days) are archived.
- Archive: `data/archive/{dim}.json` (deduplicated by id).
- Weekly snapshots: `data/history/{week}.json`.

## Scraping

**Default**: Selenium headless Chrome (chromedriver managed by webdriver-manager).

| Source | Selector | Notes |
|:---|:---|:---|
| 量子位 | `h2 a` | filter: qbitai.com |
| 机器之心 | `a.title, h3 a, h2 a` | scroll for lazy load |
| InfoQ | `a[href*="/article/"]` | scroll for lazy load |
| TechCrunch | `a[href*="/2026/"]` | filter: techcrunch.com + /2026/ |
| 36氪 | `a[href*="/article/"]` | — |
| GitHub Trending | `article.Box-row h2 a` | — |
| HuggingFace | `a[href*="/papers/"]` | scroll for lazy load |

**Fallback**: requests + BeautifulSoup (when chromedriver unavailable/crashing). Extracts raw page text, truncated to 5000 chars.

**Source health tracking**: consecutive failures tracked in `metrics.json`. Sources with ≥ 3 consecutive fails are auto-skipped in `fetch_all()`.

## Git

- Commit messages use `type@scope: subject` format.
- Auto-push uses `auto-push@llm-radar: update data (N changes)`.
- `run` does `git pull --rebase` first, then auto-commits+pushes if quality gate passes.
- Push failures go to `data/dead-letter.json` (last 10).

## `llm-radar-run.sh`

Cross-platform launcher: auto-detects Mac (system Python) vs Linux (conda `llm-radar` env). Sources `.env` file. Used by crontab.

## No Tests

The project has no formal test suite, but CI (GitHub Actions) runs `pytest tests/` on every push to main. Tests cover collector logic, git-flow recovery, HTML JS-syntax, and timestamp/overview generation.

### 前端文件变更验证要求 (2026-08-15 起, 机制 2/3)

- 任何对 `index.html` / `changelog.html` / `tests/test_html.py` 的改动, 提交前必须跑:
  ```bash
  python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q
  ```
- 浏览器 Selenium 渲染验证是**补充**, 不能替代 pytest — 它标记了 `@pytest.mark.selenium`, CI 上可能因 chromedriver 缺失而 skip
- 本地验证命令集合必须覆盖 CI 会跑的非 selenium 部分 (CI: `pytest tests/`; 本地至少跑同一集合去掉 selenium/cli)
- 测试断言必须精确匹配意图: `test_html.py` 只扫 `<script>` 块, 排除 `<style>` 块 (CSS 属性不带引号是合法写法, 不属于 JS key 检查范围)
- 防假阳性: 测试通过 ≠ 行为正确。当断言依赖被检查对象的巧合形态时 (如带引号恰好绕过正则), 要警惕 — 测试可能在保护一个不存在的保证。改动实现时必须同步审视测试是否仍成立

### 后端/数据文件变更验证要求

- collector / git-flow 改动: `python3 -m pytest tests/test_gitflow.py -q` (14 用例)
- 全量回归: 同上非 selenium 命令
- 注意: 全量测试会写脏 `timestamp.json` / `overview.json` / `data/snapshot.json` (test_timestamp 用真实 project_root), 跑完需 `git checkout --` 还原

## Deployment

GitHub Pages with custom domain (`llm-radar.lab.jaden.tech` via `CNAME` file). No CI/CD config. Deploy is manual `git push`.
