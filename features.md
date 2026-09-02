---
title: llm-radar
description: LLM Radar 行业情报仪表盘 — 采集管线/LLM 交互/数据管理/前端展示功能清单
---

# LLM Radar — Features

<!--
⚠️  AI 指令: 如需更新此文件，请直接编辑本 features.md，
   不要创建新文件（如 documents/features-v1.0.md）。
   此文件遵循风格 B（无版本号、项目根、持续更新）。
-->

> 产出文档的元信息必须遵循 `skills-governance/document-frontmatter.md` 规范。

> 项目功能框架。由 dev profile 维护，新增需求以 flat line-level 格式追加。
>
> 文件命名: 固定为 `features.md`，小写，无版本号。
>
> 适用: 风格 B 文件（无版本号，持续更新），存放在项目根目录。

## 功能域划分

按模块划分: 采集管线 / LLM 交互 / 数据管理 / 质量门禁 / 数据产出 / Git 集成 / 定时任务 / 前端展示 / 更新日志。

## 采集管线

1. Agent Loop: `run` — Think → Act → Verify → Observe 闭环 ✅ — llm-radar-collector.py
2. 间隔检查: `_think()` 6h 内跳过 + 连续失败 ≥3 告警 ✅ — llm-radar-collector.py
3. 多源抓取: `fetch [source]` 7 源 Selenium 无头（requests+BS4 降级）✅ — llm-radar-collector.py
4. 驱动容错: chromedriver 崩溃自动重启重试 1 次 ✅ — llm-radar-collector.py
5. 源健康追踪: metrics.json 连续失败 ≥3 自动跳过 ✅ — data/metrics.json
6. 源清单: `sources` prettytable 表格输出 ✅
7. Selenium 体检: `check_selenium` ✅

## LLM 交互

1. DeepSeek 调用: `_call_deepseek`（openai 包，默认 max_tokens=16000）✅ — llm-radar-collector.py
2. API key 加载: 环境变量或 .env ✅
3. 日期上下文: 注入「当前日期: YYYY-MM-DD」到 user prompt ✅
4. 截断检测: 输出 >7000 字符自动以 max_tokens=16000 重试 ✅
5. 热点摘要增强: `_enhance_hotspots` Top-N 全文抓取 + LLM 摘要 ✅
6. JSON 解析 3 层降级: 代码块提取 → strict=False 宽松 → 括号平衡截断修复 ✅ — llm-radar-collector.py【_parse_json_output】

## 数据管理

1. 增量合并: `merge` 按 name 去重 + 同名保留最高 hot_score ✅ — llm-radar-collector.py
2. 留存上限: 每维度最多 100 条 ✅
3. 滑动窗口: 15 天无新事件实体归档 ✅ — data/archive/{dim}.json
4. 周快照: data/history/{week}.json ✅
5. 时间衰减: `_apply_time_decay` 热点评分衰减 ✅
6. 模糊去重: `_fuzzy_name_dedup` 归一化名称去重 ✅

## 质量门禁

1. 事件新鲜度: `_verify` 中位数 <7 天，不达标跳过 auto-push（仍保存数据）✅ — llm-radar-collector.py
2. 实体数: 实体 >0 通过（4 维度 providers/people/tools/llms，排除热点）；实体 0 全源失败阻断 ✅ — LLM-RADAR-CL005
3. 热点数量: 热点 <3 仅 warning 不阻断 push ✅ — LLM-RADAR-CL005
4. URL 校验: `_validate_entity_urls` ✅
5. 完整性校验: `_validate_data_completeness` ✅

## 数据产出

1. 主数据产物: data/snapshot.json（两 HTML 共用）✅
2. 轻量预览: overview.json（<2KB 秒开，各维度计数 + Top3 热点）✅ — 6cd75f8
3. 健康端点: data/timestamp.json（quality 状态）✅
4. 运行指标: data/metrics.json（源健康/连续失败/运行历史 30 次）✅
5. 失败隔离: data/dead-letter.json（push 失败最后 10 条）✅

## Git 集成

1. 提交: `commit [msg]`（默认带时间戳）✅
2. 自动推送: `auto-push` + `_auto_push`（质量门禁通过才 push）✅
3. 同步: `_sync_remote`（run 前 fetch + merge --ff-only，分叉本地优先）✅ — llm-radar-collector.py
4. 推送自愈: `_push_with_recovery`（rejected → rebase 重试 → --force-with-lease → dead-letter）✅
5. 冲突标记防护: `_clean_conflict_file`（tracked → checkout --theirs；untracked → os.remove）✅
6. 失败隔离: data/dead-letter.json（push 失败最后 10 条）✅

## 定时任务

1. crontab 管理: `crontab --add|--remove|--list|--update|--status` ✅
2. 跨平台执行: llm-radar-run.sh（Mac 系统 Python / Linux conda env）✅
3. 平台感知调度: CRON_SCHEDULE Darwin 每小时 / Linux 7,14,21（配合 6h 防抖）✅
4. 数据新鲜度探针: scripts/llm-radar-health.py + hermes cron llm-radar-freshness（每 6h watchdog，三态退出）✅

## 前端展示

1. 5 维度页签: tools / llms / providers / people / hotspots，默认 llms ✅ — index.html
2. 国家筛选: all / China / global（Unicode Han 检测，含热点页签）✅
3. 源筛选: 7 源 chips，过滤 + 实时计数（含热点页签）✅
4. 排序: 表头点击排序（per-tab 独立状态）✅
5. 自动刷新: 10 分钟 + tab/筛选/排序/滚动 localStorage 保存 ✅
6. 缓存破坏: `?t=<timestamp>` ✅
7. 跨页签联动: 实体 chips 跳转 + 高亮 ✅
8. 搜索图标: 🔍 → cn.bing.com 站内搜索 `site%3A` ✅
9. 热点 FAB: 右下角悬浮，最近 3 小时热点 ✅
10. 两阶段加载: overview.json 渐进预览 + snapshot 骨架屏 ✅ — 6cd75f8
11. ago-label: 本地复制 run 命令 / 生产跳转 changelog.html ✅
12. 响应式: <1200px 自动隐藏数据源与筛选（hide-1200）✅
13. Emoji 映射: 各维度实体 emoji ✅ — 486c72f
14. 版本: footer v1.5 ✅

## 更新日志

1. 动态渲染: changelog.html 静态模板 + JS 加载 snapshot.json ✅
2. 最新 50 条: 时间倒序 + `YYYY-MM-DD HH:mm:ss` ✅
3. 摘要跳转: `#tab=` hash 路由 + 外链 ↗ 图标 ✅
4. 数据源清单: 标题旁链接跳转源 url ✅
5. 缓存刷新: 与 index.html 相同 `?t=` 逻辑 ✅
6. 摘要净化: `_sanitize_text` + textContent 渲染防注入 ✅ — e1de781

## 待定/规划

1. hotspot enhance 全部完成（摘要增强 + 时间衰减 + 排序 + 模糊去重 + URL 校验, 见各功能域 ✅）✅ — 2026-08-15 核对
2. 旧功能清单（documents/archive/features.md）迁移核对完成: 53/54 项已覆盖, 2 项旧功能（1h 自动重定向、hover 唯一索引）已在代码中移除 ✅ — 2026-08-15

---

## 📋 元信息

| 项目 | 内容 |
|:-----|:------|
| 版本 | 1.2 |
| 最后更新 | 2026-08-15 |
| 作者 | hermes-1.2.0 |
| Session | dev/llm-radar.lab-dev |
| Model | deepseek-v4-pro |
