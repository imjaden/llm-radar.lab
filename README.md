# LLM Radar

LLM 行业情报仪表盘。6 个数据源，5 维度（工具 / 大模型 / 厂商 / 人物 / 热点），热度排序，跨页签联动，中国/海外筛选。

线上地址：https://llm-radar.lab.jaden.tech

## 结构

```
├── index.html                 # 单体前端
├── changelog.html             # 更新日志（每次采集自动生成）
├── llm-radar-collector.py     # 数据采集脚本
├── llm-news-prompt.md         # 数据规范 & System Prompt
└── data/
    ├── snapshot.json           # 当前快照
    ├── fetch-cache.json        # 抓取缓存
    ├── archive/                # 过期数据归档
    ├── history/                # 按周归档
    └── collector.log           # 采集日志
```

## 快速开始

```bash
# 本地预览
python3 -m http.server 8080
open http://localhost:8080

# 数据采集
python3 llm-radar-collector.py run              # 全量采集（含 auto-push）
python3 llm-radar-collector.py run qbitai       # 指定源
python3 llm-radar-collector.py sources          # 查看源列表

# 手动推送
python3 llm-radar-collector.py commit [message] # 仅 commit
python3 llm-radar-collector.py auto-push        # commit + push

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
| requests | ≥ 2.31.0 |
| beautifulsoup4 | ≥ 4.12.0 |
| DEEPSEEK_API_KEY | 环境变量或 secret-manager |

```bash
export DEEPSEEK_API_KEY="sk-xxx"
pip3 install openai requests beautifulsoup4
```

## 数据留存

- 每维度最多 100 条，超过则保留最近 15 天数据
- 过期数据归档至 `data/archive/`
- 每次采集自动生成 `changelog.html`

## 技术栈

前端：HTML + Vanilla JS + Tailwind CSS CDN
数据：Python + DeepSeek API + requests + BeautifulSoup4
部署：GitHub Pages → https://llm-radar.lab.jaden.tech
