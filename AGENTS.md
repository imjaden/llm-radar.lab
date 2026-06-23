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

The project has no test suite. Verification is via the embedded quality gate (`_verify()`) and manual inspection of `snapshot.json`.

## Deployment

GitHub Pages with custom domain (`llm-radar.lab.jaden.tech` via `CNAME` file). No CI/CD config. Deploy is manual `git push`.
