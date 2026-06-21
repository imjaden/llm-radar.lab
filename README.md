# LLM Radar

LLM 行业情报仪表盘。5 维度（工具 / 大模型 / 厂商 / 人物 / 热点）表格+卡片展示，热度排序，跨页签联动，中国/海外筛选。

## 结构

```
├── index.html                 # 单体前端（Vanilla JS + Tailwind）
├── llm-radar-collector.py     # 数据采集脚本
├── llm-news-prompt.md         # 数据规范 & System Prompt
└── data/
    ├── snapshot.json           # 当前快照
    ├── fetch-cache.json        # 抓取缓存
    └── history/                # 按周归档
```

## 快速开始

```bash
# 本地预览
python3 -m http.server 8080
open http://localhost:8080

# 数据采集
python3 llm-radar-collector.py run                    # 全量采集
python3 llm-radar-collector.py run qbitai             # 指定源
python3 llm-radar-collector.py sources                # 查看源列表

# 定时任务（默认每 60 分钟）
python3 llm-radar-collector.py crontab --add          # 启用
python3 llm-radar-collector.py crontab --status       # 查看状态
python3 llm-radar-collector.py crontab --remove       # 移除
```

## 数据源

量子位 · 机器之心 · TechCrunch · GitHub Trending · HuggingFace Papers

## 技术栈

前端：HTML + Vanilla JS + Tailwind CSS CDN
数据：Python + requests + BeautifulSoup4 + llm-manager
部署：GitHub Pages + llm-radar.jaden.tech
