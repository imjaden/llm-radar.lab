# 功能清单

## llm-radar-collector.py

- 数据采集
  - `fetch` — 抓取 7 个新闻源（requests + BeautifulSoup）
  - `merge` — 从缓存提取实体并合并到 snapshot
  - `run` — fetch + merge + auto-push，执行前先 git pull
- LLM 交互
  - `_call_deepseek` — 直接调用 DeepSeek API（openai 包）
  - `_load_api_key` — 从环境变量或 .env 加载
- 数据管理
  - 增量合并（按 id 匹配，同名实体合并去重）
  - 数据留存（最多 100 条 + 15 天滑动窗口）
  - `sources` — prettytable 表格输出新闻源
- Git 集成
  - `commit [message]` — git add + commit
  - `auto-push` — git add + commit + push
  - `_auto_push` — 采集后有更新自动 push
- 定时任务
  - `crontab --add|--remove|--list|--update|--status`

## index.html

- 5 维度展示（工具 / 大模型 / 厂商 / 人物 / 热点）
- 表格布局 + 表头排序（per-tab 独立状态）
- 跨页签联动（clickable chips，跳转到对应 tab 高亮）
- 中国 / 海外 / 全部筛选（Unicode 汉字正则 + country 字段）
- 自动刷新（10 分钟，保存 tab/筛选/排序/滚动位置到 localStorage）
- 热点悬浮框（右下角 FAB，最近 3 小时热点，点击跳转）
- 时间戳缓存刷新（`?t=` 超过 1 小时自动重定向）
- 数据源标签（7 个，顶部 header）
- 更新日志入口（点击 ago-label → changelog.html）

## changelog.html

- 静态模板，JS 动态加载 data/snapshot.json 渲染
- 最新 50 条变更记录（时间倒序）
- 日期调整为日期+时间，格式为 `YYYY-MM-DD HH:mm:ss`，展示不换行，摘要可点击跳转至对应页签 + 外链 ↗ 图标
- BUG: 摘要外链接（http://jaden.local:8081/?tab=hotspots），点击后跳转至对应页签加载时间戳导致无法方法访问页面（http://jaden.local:8081/&tab=hotspots&t=1782110758751）
- 时间戳缓存刷新（与 index.html 相同逻辑）
