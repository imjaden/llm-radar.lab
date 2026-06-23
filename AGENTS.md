# LLM Radar — Agent Guide

Compact single-project dashboard. One Python collector, one Vanilla JS frontend, deployed on GitHub Pages.

## Structure

- `llm-radar-collector.py` — sole Python script (1125 LOC). No package layout, no modules.
- `index.html` — single-page frontend, Tailwind CDN, Vanilla JS. No build step.
- `changelog.html` — static template, renders from `data/snapshot.json` at runtime.
- `data/snapshot.json` — primary data artifact (JSON, ~8700 lines). Loaded by both HTML files.
- `data/fetch-cache.json` / `data/metrics.json` — auto-generated, gitignored.
- `data/archive/`, `data/history/` — auto-generated archived entities and weekly snapshots.

## Key Commands

```bash
python3 llm-radar-collector.py run              # fetch + extract + merge + auto-push
python3 llm-radar-collector.py run <source>     # single source (e.g. qbitai, techcrunch)
python3 llm-radar-collector.py sources          # list sources (prettytable)
python3 llm-radar-collector.py fetch [source]   # fetch only
python3 llm-radar-collector.py merge            # merge from fetch cache
python3 llm-radar-collector.py crontab --add    # schedule daily 09:00, 21:00
python3 llm-radar-collector.py commit [msg]     # git add + commit
python3 llm-radar-collector.py auto-push        # git add + commit + push
./llm-radar-run.sh                              # cross-platform wrapper (auto-detects Mac/Linux)
python3 -m http.server 8080                     # local preview
```

## Dependencies

Python >= 3.11. Install: `pip3 install openai requests beautifulsoup4 prettytable`

`DEEPSEEK_API_KEY` required via `export` or `.env` file in project root.

## Execution Flow

`run` orders: `git pull --rebase` → **Think** (check 6h interval, source health) → **Act** (fetch 7 sources, LLM extract, merge) → **Verify** (event freshness, hotspot count) → **Observe** (write `metrics.json`) → auto-push if quality gate passes.

## Git

- Commit messages use `type@llm-radar:` prefix (e.g., `fixed@llm-radar:`, `optimized@llm-radar:`, `docs@llm-radar:`).
- Auto-push uses `auto-push@llm-radar: update data (N changes)`.
- `run` does `git pull --rebase` first, then auto-commits+pushes if quality gate passes.
- Push failures go to `data/dead-letter.json` (last 10).

## `.gitignore` Caveat

`*.md` is gitignored by default. Only `README.md`, `llm-news-prompt.md`, `features.md`, and `agent-loop-plan.md` are whitelisted. Any new `.md` file (including this one) needs a `!` exception added.

## Architecture Notes

- LLM extraction uses DeepSeek API via the `openai` Python package (`api.deepseek.com/v1`).
- JSON truncation auto-repair: 3-level fallback (code block → direct parse → bracket balancing + string truncation fix).
- Agent loop embedded in collector: `_think()` (6h cooldown, source health), `_verify()` (median freshness < 7d, hotspots >= 3), `_observe()` (writes `metrics.json`).
- Data retention: max 100 entities per dimension, 15-day sliding window. Expired data → `data/archive/`.
- Quality gate failure skips auto-push but does not prevent data save.

## Frontend

- 5 tabs: tools / llms / providers / people / hotspots. Default: llms.
- Country filter: all / China / global (Unicode Han script detection).
- Auto-refresh: 10 min interval, saves tab/filter/sort/scroll to localStorage.
- Cache busting: `?t=<timestamp>` in data fetch URLs.
- Hotspot FAB: shows events from last 3 hours.
- Click ago-label on localhost → copies `run` command; on production → navigates to `changelog.html`.

## No Tests

The project has no test suite. Verification is via the embedded quality gate (`_verify()`) and manual inspection of `snapshot.json`.

## Deployment

GitHub Pages with custom domain (`llm-radar.lab.jaden.tech` via `CNAME` file). No CI/CD config. Deploy is manual `git push`.
