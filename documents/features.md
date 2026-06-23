# 功能清单

## llm-radar-collector.py

- Agent Loop
  - `run` — Think → Act → Verify → Observe 四阶段闭环
  - `_think()` — 间隔检查（< 6h 跳过）、连续失败（≥ 3 次告警）
  - `_verify()` — 质量门禁（事件中位数新鲜度 < 7 天、热点 ≥ 3 条）
  - `_observe()` — 记录 metrics.json（源成功率、实体数、运行历史 30 次）
- 数据采集
  - `fetch` — 抓取 7 个新闻源（Selenium 无头浏览器提取 `{title,url,date}` + `page_text`，requests+BS4 降级）
  - 源降级：连续 3 次失败的源自动跳过
  - 源健康追踪：`metrics.json` 记录每个源的连续失败次数
  - 重试+重启：Selenium 驱动崩溃自动重启重试 1 次
  - `merge` — 从缓存提取实体并合并到 snapshot
- LLM 交互
  - `_call_deepseek` — 直接调用 DeepSeek API（openai 包），默认 `max_tokens=16000`
  - `_load_api_key` — 从环境变量或 .env 加载
  - 注入当前日期到 user prompt（`当前日期: YYYY-MM-DD`）
  - 支持 Selenium page_text 正文提取，为 LLM 提供文章上下文
- 数据管理
  - 增量合并（按 name 去重，同名合并保留最高 hot_score）
  - 数据留存：每维度最多 100 条，超过则保留最近 15 天数据
  - 过期数据归档至 `data/archive/`
  - `sources` — prettytable 表格输出新闻源
- JSON 解析
  - `_parse_json_output` — 3 层降级解析（代码块提取 → 宽松 strict=False 解析 → 截断修复）
  - `_try_parse_json` — 先 strict=True，失败后 strict=False（容忍控制字符）
  - `_try_fix_truncated_json` — 括号平衡 + 未闭合字符串截断补齐
- LLM 输出截断修复
  - 检测输出 > 7000 字符时，自动以 `max_tokens=16000` 重试
  - 重试 prompt 复用完整 system prompt + user prompt（保留日期上下文）
- Git 集成
  - `commit [message]` — git add + commit（默认带时间戳）
  - `auto-push` — git add + commit + push
  - `_auto_push` — 采集后有更新自动 push，失败存 dead-letter.json
  - 质量门禁未通过跳过 auto-push
- 定时任务
  - `crontab --add|--remove|--list|--update|--status`
  - 动态路径 + 注释说明，支持 llm-radar-run.sh 跨平台执行

## index.html

- 5 维度展示（工具 / 大模型 / 厂商 / 人物 / 热点）
- 表格布局 + 表头排序（per-tab 独立状态）
- 跨页签联动（clickable chips，跳转到对应 tab 高亮）
- 中国 / 海外 / 全部筛选（Unicode 汉字正则 + country 字段，含热点页签）
- 数据源筛选（7 源可点击切换，热点页签同步过滤 + 数量实时更新）
- 浏览器宽度 < 1200px 自动隐藏数据源清单和筛选选项（hide-1200）
- 自动刷新（10 分钟，保存 tab/筛选/排序/滚动位置到 localStorage）
- 热点悬浮框（右下角 FAB，最近 3 小时热点，点击跳转）
- 搜索图标（🔍 → cn.bing.com 站内搜索 `site%3A` + 关键词）
- 时间戳缓存刷新（`?t=` 超过 1 小时自动重定向）
- 更新日志入口（点击 ago-label → changelog.html，附带 🔗 图标）
- 唯一索引（同名实体 hover 显示 id）
- footer 版本号 v1.5

## changelog.html

- 静态模板，JS 动态加载 data/snapshot.json 渲染（非采集时生成）
- 最新 50 条变更记录（时间倒序）
- 日期展示 `YYYY-MM-DD HH:mm:ss`（whitespace-nowrap）
- 摘要可点击跳转至对应页签（`#tab=` hash 路由） + 外链 ↗ 图标（过滤 xxx/xxxx 占位符）
- 数据源清单（标题旁，点击打开新页签跳转至数据源 url）
- 时间戳缓存刷新（与 index.html 相同逻辑，固定 ? 前缀）
- favicon 与主站一致
