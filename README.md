# LLM Radar

LLM 行业情报仪表盘。7 个数据源，5 维度（工具 / 大模型 / 厂商 / 人物 / 热点），热度排序，跨页签联动，中国/海外筛选。

线上地址：https://llm-radar.lab.jaden.tech

## 快速开始

```bash
# 本地预览
python3 -m http.server 8080
open http://localhost:8080

# 数据采集
./llm-radar-run.sh                    # 自动识别环境运行
python3 llm-radar-collector.py run              # 全量采集（含 auto-push）
python3 llm-radar-collector.py sources          # 查看源列表（prettytable）

# 手动推送
python3 llm-radar-collector.py commit [message] # git add + commit
python3 llm-radar-collector.py auto-push        # git add + commit + push

# 定时任务
python3 llm-radar-collector.py crontab --add          # 每天9:00、21:00采集
python3 llm-radar-collector.py crontab --status       # 查看状态
python3 llm-radar-collector.py crontab --remove       # 移除
```

## 数据源

量子位 · 机器之心 · InfoQ · 36氪 · TechCrunch · GitHub Trending · HuggingFace Papers

## 环境要求

| 依赖 | 版本 |
|:---|:---|
| Python | ≥ 3.7.1（openai 包要求） |
| openai | ≥ 1.0.0 |
| selenium | ≥ 4.0.0 |
| webdriver-manager | ≥ 4.0.0 |
| requests | ≥ 2.31.0（Selenium 降级备用） |
| beautifulsoup4 | ≥ 4.12.0（Selenium 降级备用） |
| prettytable | ≥ 3.0.0 |
| DEEPSEEK_API_KEY | 环境变量或 .env 文件 |

```bash
echo 'DEEPSEEK_API_KEY="sk-xxx"' >> .env
pip3 install openai selenium webdriver-manager requests beautifulsoup4 prettytable
```

## 数据采集

采用 **Selenium 无头浏览器**（Chrome Headless）提取结构化文章列表 `{title, url, date}`，失败时自动降级到 requests+BeautifulSoup。

```bash
# 手动触发全量采集
python3 llm-radar-collector.py run

# 仅抓取（不合并）
python3 llm-radar-collector.py fetch [source_key]
```

7 个源各自定义了 CSS 选择器（`SCRAPERS` 配置），精确提取文章标题、链接和发布日期后，拼接为结构化文本送入 DeepSeek API 提取实体。

## 功能清单

各文件详细功能清单见 [features.md](documents/features.md)。涵盖：

- **llm-radar-collector.py** — 数据采集、LLM 交互、数据管理、Git 集成、定时任务、JSON 截断修复
- **index.html** — 5 维度表格展示、筛选/排序/联动、自动刷新、热点悬浮框、搜索按钮
- **changelog.html** — 静态模板动态渲染、外链图标、缓存刷新

## 结构

```
├── index.html                 # 单体前端（表格布局，Vanilla JS）
├── changelog.html             # 更新日志（静态模板，JS 动态加载渲染）
├── llm-radar-collector.py     # 数据采集脚本
├── llm-radar-run.sh           # 跨平台执行器（自动识别 Mac/Linux）
├── llm-news-prompt.md         # 数据规范文档
├── features.md                # 功能清单
└── data/
    ├── snapshot.json           # 当前快照
    ├── fetch-cache.json        # 抓取缓存
    ├── archive/                # 过期数据归档
    ├── history/                # 按周归档
    └── collector.log           # 采集日志
```

## 技术栈

- 前端：HTML + Vanilla JS + Tailwind CSS CDN
- 数据采集：Selenium 无头浏览器（Chrome Headless）+ requests/BS4 降级
- 实体提取：DeepSeek API（deepseek-v4-flash）
- 部署：GitHub Pages → https://llm-radar.lab.jaden.tech
