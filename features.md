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
  - 数据留存：每维度最多 100 条，超过则保留最近 15 天数据
  - 过期数据归档至 `data/archive/`
  - `sources` — prettytable 表格输出新闻源
- Git 集成
  - `commit [message]` — git add + commit（默认带时间戳）
  - `auto-push` — git add + commit + push
  - `_auto_push` — 采集后有更新自动 push，失败时给出明确提示（git user 缺失等）
- 定时任务
  - `crontab --add|--remove|--list|--update|--status`
  - 动态路径 + 注释说明，支持 llm-radar-run.sh 跨平台执行
- JSON 修复
  - `_parse_json_output` — 3 层降级解析（代码块提取 → 直接解析 → 截断修复）
  - `_try_fix_truncated_json` — 括号平衡 + 未闭合字符串截断补齐

## index.html

- 5 维度展示（工具 / 大模型 / 厂商 / 人物 / 热点）
- 表格布局 + 表头排序（per-tab 独立状态）
- 跨页签联动（clickable chips，跳转到对应 tab 高亮）
- 中国 / 海外 / 全部筛选（Unicode 汉字正则 + country 字段）
- 自动刷新（10 分钟，保存 tab/筛选/排序/滚动位置到 localStorage）
- 热点悬浮框（右下角 FAB，最近 3 小时热点，点击跳转）
- 热点卡片 🔍 搜索按钮（Bing 搜索标题 + 来源域名）
- 时间戳缓存刷新（`?t=` 超过 1 小时自动重定向，修复参数拼接顺序）
- 数据源标签（7 个，顶部 header，标签样式）
- 更新日志入口（点击 ago-label → changelog.html）
- 唯一索引（同名实体 hover 显示 id）
- footer 版本号 v1.1

## changelog.html

- 静态模板，JS 动态加载 data/snapshot.json 渲染（非采集时生成）
- 最新 50 条变更记录（时间倒序）
- 日期展示 `YYYY-MM-DD HH:mm:ss`（whitespace-nowrap）
- 摘要可点击跳转至对应页签 + 外链 ↗ 图标（过滤 xxx/xxxx 占位符）
- 时间戳缓存刷新（与 index.html 相同逻辑，固定 ? 前缀）
- favicon 与主站一致
