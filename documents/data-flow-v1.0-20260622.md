# LLM Radar 数据流程

> 当前数据流：Think → Fetch → Extract → Verify → Merge → Observe → Push

```text
┌────────────────────────────────────────────────┐
│           CRON (9:00 / 21:00)                  │
│    llm-radar-run.sh → collector.py run         │
└──────────────┬─────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────┐
│  [Think] Collection Strategy                   │
│  · Skip if last run < 6h ago                   │
│  · Alert if fails ≥ 3 times                    │
└──────────────┬─────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────┐
│  [Fetch] Scrape 7 News Sources                 │
│  · Skip low-quality sources                    │
│    (3 consecutive failures)                    │
│  · Selenium headless browser                   │
│  · Extract {title,url,date}                    │
│  · Fallback: requests+BS4                      │
└──────────────┬─────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────┐
│  [Extract] LLM Entity Extract                  │
│  · DeepSeek API (deepseek-v4)                  │
│  · Extract JSON by prompt                      │
│  · Parse fail → retry once                     │      
└──────────────┬─────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────┐
│  [Verify] Quality Gate                         │
│  · Median freshness < 7 days                   │
│  · Hotspots ≥ 3 items                          │
│  · Fail → skip auto-push                       │        
└──────────────┬─────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────┐
│  [Merge] Merge to snapshot.json                │
│  · Add / update / archive                      │
│  · Dedup: merge by name                        │
│    (keep highest score)                        │
│  · Retention: 100+15d window                   │
│  · changelog incremental log                   │
└──────────────┬─────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────┐
│  [Observe] Write metrics.json                  │
│  · Source success / entities                   │
│  · Consecutive failure count                   │
│  · Run history (last 30)                       │
└──────────────┬─────────────────────────────────┘
               │
               ▼
┌────────────────────────────────────────────────┐
│  [Push] git commit + push                      │
│  · Fail → dead-letter.json                     │
│  · Quality gate fail → skip                    │
└──────────────┬─────────────────────────────────┘
               │
               ▼
        GitHub Pages deploy (gh-pages)
               │
               ▼
        index.html / changelog.html
        rendered from snapshot.json
```

---

## 1. 调度入口

| 层次 | 文件 | 说明 |
|:---|:---|:---|
| 定时器 | `crontab` | `0 9,21 * * *`，每天 9:00 / 21:00 |
| 启动器 | `llm-radar-run.sh` | 跨平台（Mac/Linux），加载 `.env` + conda环境 |
| 主程序 | `llm-radar-collector.py` | CLI 入口，支持 `run` / `fetch` / `merge` / `sources` 等子命令 |

```bash
# crontab 实际执行
llm-radar-run.sh >> data/collector.log 2>&1

# 手动执行
cd ~/CodeSpace/llm-radar.jaden.tech
python3 llm-radar-collector.py run
```

---

## 2. 数据源（7 个）

| 分类 | 名称 | URL | 抓取方式 |
|:---|:---|:---|:---|
| 中文媒体 | 量子位 | `qbitai.com` | Selenium 无头 (`h2 a`) |
| 中文媒体 | 机器之心 | `jiqizhixin.com` | Selenium 无头（`a.title`，懒加载滚动） |
| 中文技术媒体 | InfoQ | `infoq.cn/topic/AI` | Selenium 无头（`a[href*="/article/"]`，懒加载滚动） |
| 中文科技媒体 | 36氪 | `36kr.com/search/articles/大模型` | Selenium 无头（`a[href*="/article/"]`） |
| 英文媒体 | TechCrunch AI | `techcrunch.com/category/artificial-intelligence/` | Selenium 无头（`a[href*="/2026/"]`） |
| 开发者 | GitHub Trending | `github.com/trending?since=weekly` | Selenium 无头（`article.Box-row`） |
| 研究 | HuggingFace Papers | `huggingface.co/papers` | Selenium 无头（`a[href*="/papers/"]`，懒加载滚动） |

**抓取规则：**
- 每源间隔 2 秒（`time.sleep(2)`）
- Chrome Headless 无头模式，关闭图片加载提速
- `page_load_strategy = 'normal'`，`WebDriverWait` 等待关键 CSS 元素
- 失败自动重启驱动重试 1 次 → 仍失败则降级到 requests+BS4
- 连续 3 次失败的源自动降级跳过（配置在 `metrics.json`）
- 结构化输出 `{title, url, date}` 列表，拼接后送 LLM 提取实体

---

## 3. LLM 提取

### 调用参数

| 参数 | 值 |
|:---|:---|
| 模型 | `deepseek-v4-flash` |
| Temperature | 0.1 |
| Max tokens | 8000 |
| API Base | `https://api.deepseek.com/v1` |
| 认证 | `DEEPSEEK_API_KEY` 环境变量 |

### 提取流程

```
7 个源的原始 HTML 文本
        │
        ▼
拼接为一个 combined 字符串
        │
        ▼
DeepSeek API 调用（system prompt + user prompt）
        │
        ▼
返回 JSON（5 个数组）
  ├─ providers  — 厂商（名称、国家、热度、旗舰模型等）
  ├─ people     — 人物（姓名、头衔、影响力等级、最近动态等）
  ├─ tools      — 工具（名称、分类、热度、成熟度、定价等）
  ├─ llms       — 大模型（名称、类型、定位、参数规模、定价等）
  └─ hotspots   — 热点事件（标题、摘要、日期、来源、关联实体等）
        │
        ▼
JSON 解析失败 → 重试 1 次（简化 prompt 仅要求纯 JSON）
```

### 实体字段说明

**厂商 (providers)**：name, name_en, country, hot_score, key_people, flagship_models, last_event, last_event_url, last_event_date, official_website, ref(tech_stack, valuation)

**人物 (people)**：name, name_en, title, influence_level, employer_id, hot_score, known_for, recent_activity, recent_activity_url, recent_activity_date, related_llms

**工具 (tools)**：name, description, category, website, hot_score, maturity, pricing_model, last_update, last_update_url, last_update_date, related_llms, ref(stars, stars_weekly_delta, pricing_input, pricing_output, context_window, modalities_input, ...)

**大模型 (llms)**：name, family, version, type, tier, provider_id, hot_score, open_weights, capabilities, last_event, last_event_url, last_event_date, ref(pricing_input, pricing_output, context_window, modalities_input, ...)

**热点 (hotspots)**：title, summary, date, source, url, related_providers, related_people, related_tools, related_llms

---

## 4. 数据合并与去重

### 合并规则

```
新提取的实体列表  ──→  按 name 去重
         │
         ▼
  与现有 snapshot.json 对比
         │
    ┌────┴────┐
    ▼         ▼
  新实体     已存在
  (新增)     (更新 hot_score / last_event)
         │
         ▼
  changelog 增量记录
  (type: new / update / archive)
```

- **去重键**：`name`（字符串精确匹配）
- **优先级**：首次出现的 `id` 保留，`hot_score` 取最高值
- **数据留存**：100+15 天滑动窗口（N=100 per dimension, 超 115 天归档）
- **归档位置**：`data/archive/{dim}/{id}_{date}.json`

### 数据文件

| 文件 | 用途 | 是否提交 | 生成方式 |
|:---|:---|:---|:---:|
| `data/snapshot.json` | 前端渲染数据源 | ✅ 提交 | Merge 阶段写入 |
| `data/fetch-cache.json` | 抓取缓存（避免重复请求） | ❌ .gitignore | Fetch 阶段写入 |
| `data/history/` | 每周历史快照归档 | ❌ .gitignore | Merge 后存档 |
| `data/archive/` | 过期实体归档 | ❌ .gitignore | Merge 中触发 |
| `data/collector.log` | 采集运行日志 | ❌ .gitignore | crontab 重定向 |
| `data/metrics.json` | 运行指标（运维监控） | ❌ .gitignore | Observe 阶段写入 |
| `data/dead-letter.json` | 推送失败存档 | ❌ .gitignore | Push 失败时写入 |

---

## 5. 前端渲染

```
data/snapshot.json
        │
  index.html 读取（?t= 缓存爆破）
        │
        ▼
  JS 按 5 个页签渲染
  ├─ 🔧 工具    — 按分类/热度/成熟度/Stars 排序
  ├─ 🤖 大模型  — 按热度/定位/上下文/定价 排序
  ├─ 🏢 厂商    — 按热度/旗舰模型/估值 排序
  ├─ 👤 人物    — 按影响力/热度/关联模型 排序
  └─ 🔥 热点    — 卡片式布局，按日期排序
        │
        ▼
  交互功能
  ├─ CN/Global 筛选
  ├─ 数据源筛选（选中后仅显示该源相关实体）
  ├─ 列排序（点击表头）
  ├─ 跨页签跳转（点击关联实体 chip）
  ├─ 搜索图标（🔍 → cn.bing.com 站内搜索）
  ├─ 自动刷新（每 10 分钟 re-fetch snapshot.json）
  └─ 热点浮动面板（3 小时内热点）
```

---

## 6. 部署架构

```text
┌──────────────────────────────────────────────────┐
│         GitHub (imjaden/llm-radar.lab)           │
│  ┌────────────┐  ┌──────────┐  ┌───────────────┐ │
│  │ index.html │  │changelog │  │ snapshot.json │ │
│  │  (frontend)│  │(frontend)│  │  (data file)  │ │
│  └────────────┘  └──────────┘  └───────────────┘ │
└─────────────────────┬────────────────────────────┘
                      │ GitHub Pages
                      ▼
┌─────────────────────────────────────────────────┐
│            GitHub Pages (gh-pages)              │
│       https://llm-radar.lab.jaden.tech          │
└─────────────────────┬───────────────────────────┘
                      │
        Collector (2 machines,各自 crontab)
         │
    ┌────┴────┐
    ▼         ▼
  Mac local   Alibaba Cloud Linux
  (dev/debug) (production)
         │
  Push to same GitHub repo
  collector.py run → commit → push → GH Pages auto-update
```

**采集端对比：**

| 环境 | 位置 | Python | 触发 |
|:---|:---|:---|:---|
| Mac 本地 | `~/CodeSpace/llm-radar.jaden.tech` | 系统 Python 3.11 | crontab 9:00/21:00 |
| 阿里云 Linux | `/home/admin/codespace/llm-radar.lab` | conda `llm-radar` 环境 | crontab 9:00/21:00 |

---

## 7. 关键文件清单

| 文件 | 角色 | 大约行数 |
|:---|:---|:---:|
| `llm-radar-collector.py` | 采集主程序（Think → Fetch → Extract → Merge → Observe → Push） | 1111 |
| `llm-radar-run.sh` | 跨平台启动器（加载 .env + conda） | 68 |
| `llm-news-prompt.md` | LLM 提取用的 system prompt 定义 | 160 |
| `index.html` | 前端仪表盘（5 tab + 筛选 + 搜索） | 777 |
| `changelog.html` | 更新日志页（从 snapshot.json 渲染） | 73 |
| `data/snapshot.json` | 核心数据文件（前端唯一数据源） | 动态 |
| `.env` | API Key（不提交） | 1 |
| `.gitignore` | 排除运行时文件 | 16 |
| `README.md` | 项目说明 | 77 |
| `features.md` | 功能清单 | 55 |
| `loop.md` | 迭代检查清单 | 13 |
| `agent-loop-plan.md` | Agent Loop 升级规划 | — |

---

## 8. 一次完整采集的时间线

```text
T+0s     [Think]    检查间隔 > 6h，连续失败计数
T+0s     [Fetch]    7 源并行抓取（实际串行，sleep 2s/个）→ ~15s
T+15s    [Extract]  DeepSeek API 调用 → ~45s
T+60s    [Verify]   质量门禁（新鲜度、热点数量）
T+60s    [Merge]    对比 snapshot + 去重 + 归档 → ~2s
T+62s    [Observe]  写 metrics.json
T+62s    [Push]     git commit + push → ~5s
────────────────────────────────────
T+67s    完成
```

---

## 📋 元信息

| 项目 | 内容 |
|:---|:---|
| 助手名称 | IRIS (byHermes) |
| 创建时间 | 2026-06-22 21:50:00 |
| 信息来源 | `llm-radar-collector.py` / `index.html` / `changelog.html` / `llm-radar-run.sh` |
