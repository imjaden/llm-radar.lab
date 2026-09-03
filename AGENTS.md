# LLM Radar — Agent Guide

Compact single-project dashboard. One Python collector, one Vanilla JS frontend, deployed on GitHub Pages.

## Structure

- `llm-radar-collector.py` — sole Python script (~1330 LOC). No package layout, no modules.
- `scripts/twitter-collector.py` — X 热点独立采集器 (Selenium 登录态, 纯抓取 0 token, 设计 x-hotspot v1.3)。
- `data/twitter-targets.yaml` — X 采集目标名单 (可编辑; 10 账号; name/handle/url 必填, enabled/max_tweets 缺省容错, max_tweets 默认 30)。
- `index.html` — single-page frontend, Tailwind CDN, Vanilla JS. No build step.
- `changelog.html` — static template, renders from `data/snapshot.json` at runtime.
- `data/snapshot.json` — primary data artifact (JSON, ~8700 lines). Loaded by both HTML files.
- `data/twitter.json` — X 热点数据 (独立加载, 采集器自带 commit+push 入库)。
- `data/fetch-cache.json` / `data/metrics.json` — auto-generated, gitignored.
- `data/dead-letter.json` — git push failures, gitignored.
- `data/archive/`, `data/history/` — auto-generated archived entities and weekly snapshots.
- `llm-news-prompt.md` — LLM data spec, output schema guidance.
- `features.md` — feature checklist.
- `loop.md` — iteration checklist.
- `skills/` — 项目 skills 供给站 (SKILL.md; AI 对接用 `llm-radar prompt [<name>]` 读取).

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
python3 llm-radar-collector.py prompt [skill]   # 列出/输出项目 skill (AI 对接, 全只读)
python3 scripts/twitter-collector.py            # X 采集 (默认 collect; --login 人工登录 / --dry-run 探测登录态)
./llm-radar-run.sh                              # cross-platform wrapper (auto-detects Mac/Linux)
python3 -m http.server 8080                     # local preview
```

CLI 治理 (2026-08-23 起): 全局注册 `llm-radar` 主名 + `lr` 别名 (`.cli-registry.yaml`, wrapper 生成物在 gitignored `cache/system-command/`)。

```bash
lr help                           # hm-style 分组帮助 (llm-radar / lr 输出一致)
lr status [--json]                # checkpoint 七字段协议 (ok/warning/critical, 全只读)
lr run --force                    # 绕过 6h 节流
lr prompt [skill] [--brief|--json]  # skills/ 供给站: 无参列表 / <name> 全文 (AI 对接, 全只读)
lr run help / lr crontab help     # 单命令用法 (positional help 拦截, exit=0 无副作用)
```

- 空入参 → 打印分组帮助 exit=0 (原 exit=1)。
- `lr status` 阈值: STALE_HOURS=12 (LLM_RADAR_STALE_HOURS 可配) / CRITICAL_HOURS=48 (LLM_RADAR_CRITICAL_HOURS 可配)。
- 数据源全只读: timestamp.json (项目根) + data/metrics.json 全局 `consecutive_fails` + git rev-list 本地 ref (不 fetch) + snapshot.json。
- wrapper fork 模板: `cache/cli-registry/wrapper.sh.tmpl` (移除 script-miner calls.log 段, exec 前加载项目 .env)。
- Linux 主机部署: `.cli-registry.yaml` 的 `env.conda` 需从 `py3.12` 改为 `llm-radar`。

### X 采集 crontab (Mac 本机, x-hotspot 设计 §6)

```cron
20 9,21 * * * cd /Users/jadenli/CodeSpace/llm-radar.lab && python3 scripts/twitter-collector.py >> data/twitter.log 2>&1 # llm-radar-twitter
```

- 错峰 `20 9,21` (09:20/21:20): 避开主采集整点 :00, 防双 Chrome 实例资源竞争与 `git add` 抓取竞争 (REA-2)。
- 采集成功自带 commit + push `auto-push@llm-radar: update twitter (N changes)`; push 失败仅记 cron 日志, 下轮自动重试 (不重试轰炸)。
- 不调 LLM, 无需 .env; Linux 服务器默认不启用 (无人工登录态, 如需由部署方 --login 一次)。
- 注意: 此处为文档说明; 实际 crontab 由 ops 核查阶段接入, dev 不直接改用户 crontab。

## Dependencies

```bash
pip3 install openai selenium webdriver-manager requests beautifulsoup4 prettytable pyyaml
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

- 6 tabs: tools / llms / providers / people / hotspots / xhotspots (X热点). Default: llms.
- Country filter: all / China / global (Unicode Han script detection). Applies to 5 个实体 tab;
  X热点 tab 无 country 字段 → 国家 chips 置灰 (仅源 chips 生效)。
- Source filter: 8 clickable source chips (含 X), filters entities by source domain match.
  Applies to all tabs including hotspots; X tab 按 handle/url 域名过滤 (源筛选非 X 时显示空态)。
- X热点 tab: 独立加载 `data/twitter.json?t=<ts>` (失败 console.warn 回退空态, 不阻断页面);
  表格列 = 时间(MM-DD HH:MM, UTC→本地) / 人物 / 推文摘要(截断) / 指标(浏览/回复/点赞, null 显示 —);
  摘要含 forward 时显示 `{text}\nforward: {forward}` (text 空则仅 forward 行);
  单击行或行内"详情"按钮 → split-preview 分栏 (header 上一/下一 + 关闭, body 全文/forward 行
  (区分样式)/指标 kv/图片, 图片直引 pbs.twimg.com + onerror 占位 + https:// 二次校验);
  <1200px 变全屏抽屉 (底部滑出); 关闭: 关闭按钮 / 点击空白 / Esc。渲染路径全字段 esc()/textContent 转义 (SEC-1)。
- 全站搜索 (D4 4B): header-search 输入框 (防抖 ~200ms + Enter) 过滤当前 tab 表格行
  (匹配 name/文本/forward/人物/链接) + 跨 tab 计数 (如 "工具 3 · 模型 5", 点击跳转);
  清空/Esc 恢复全表; Cmd+F (metaKey) / Ctrl+F (ctrlKey) 拦截 preventDefault + 聚焦;
  高亮用结构化 DOM 构建 (span + textContent 分片), 禁 innerHTML 拼接 (SEC-1)。
- Tab counts update in real-time when filters change (including `tc-hotspots` / `tc-xhotspots`).
- Responsive: data sources and filter chips auto-hide below 1200px (`hide-1200`).
- Auto-refresh: 10 min interval, saves tab/filter/sort/scroll to localStorage.
- Cache: 页面级 `?t` 重定向保留 (页刷新机制, index 337-345 / changelog 12-15); 数据 fetch 用 `{cache:'no-cache'}` 条件缓存 (LLM-RADAR-CL002 D2), ETag/Last-Modified 命中 → 304 零传输。
- Cross-tab linking: click entity chips to jump to another tab with highlight.
- Search icon (🔍) on entity names and event URLs: `cn.bing.com/search?q=keyword+site%3Adomain`.
- Hotspot FAB: shows events from last 3 hours.
- Click ago-label on localhost → copies `run` command; on production → navigates to `changelog.html`.
- Version: v1.5 in footer.

### 样式构建 (Tailwind 预编译, LLM-RADAR-CL002 D1/A1)

- 运行时不再引 cdn.tailwindcss.com (CDN 运行时 JIT 编译已移除); 样式来自入库产物 `static/tailwind.css`。
- 自定义色 (colors.cobalt/accent) 定义在 `tailwind.config.js` (提取自原内联 config); 页面未用类 (如 cobalt-300/500) 不生成, 与 CDN 行为一致。
- **新增 Tailwind 类后必须重构建并提交产物** (防漂移 O-2):
  ```bash
  npx tailwindcss@3.4.17 -c tailwind.config.js -i cache/build/tailwind-input.css \
    -o static/tailwind.css --minify --content "index.html,changelog.html"
  ```
- 构建输入 `cache/build/tailwind-input.css` 不入库 (cache/ gitignored); 产物 `static/tailwind.css` 提交。

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
- `run` 前先 `_sync_remote()` 同步（fetch + `merge --ff-only`，分叉时本地优先），质量门禁通过后 auto-commit+push；push rejected 时走 `_push_with_recovery()`（rebase 重试 → `--force-with-lease` → dead-letter）。
- Push failures go to `data/dead-letter.json` (last 10).

## `llm-radar-run.sh`

Cross-platform launcher: auto-detects Mac (system Python) vs Linux (conda `llm-radar` env). Sources `.env` file. Used by crontab.

## Tests

Test suite under `tests/`, run by CI (GitHub Actions) via `pytest tests/` on every push to main. Covers collector logic, git-flow recovery, HTML JS-syntax, and timestamp/overview generation.

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
