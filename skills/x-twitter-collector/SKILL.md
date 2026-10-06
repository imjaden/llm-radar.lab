---
name: x-twitter-collector
description: Use when operating llm-radar X 热点采集器 — CLI/配置/登录态/故障速查 (浓缩 + 指向 x-twitter-scraping)
category: devops
tags: [twitter, x, collector, selenium, cdp, llm-radar, ops]
triggers:
  - 运维/排查 llm-radar X 热点采集 (scripts/twitter-collector.py)
  - 修改 data/twitter-targets.yaml 增删采集人物
  - 采集退出码非 0 或 data/twitter.json 数据异常
  - 需要向 AI 供给 X 采集器使用说明 (llm-radar prompt x-twitter-collector)
---

# x-twitter-collector

llm-radar X 热点采集器 (`scripts/twitter-collector.py`) 运维速查。
项目专属浓缩版; 通用 X 技术深坑 (虚拟列表 DOM 回收/动态滚动/自动化登录被拦截/降级)
→ Hermes profile skill `x-twitter-scraping`, 此处不复制。

## CLI 签名与退出码

```bash
python3 scripts/twitter-collector.py            默认 = collect
python3 scripts/twitter-collector.py --collect  显式采集 (等价默认)
python3 scripts/twitter-collector.py --login    有头模式打开登录页, 人工登录一次
python3 scripts/twitter-collector.py --dry-run  只解析配置+探测登录态, 不抓取不写盘
python3 scripts/twitter-collector.py --attach   attach 到已运行 Chrome (CDP 9222) 采集
```

退出码:
- 0 = 成功 (含部分成功: 写盘 + last_error)
- 1 = 抓取失败 (全部失败不写盘, 保留上次) / 配置错误 / 未知参数
- 2 = 登录态失效 (需人工重新登录)

环境变量: `TWITTER_PROFILE_DIR` 覆盖 Chrome profile 路径 (默认 `cache/twitter-profile/`)。

## 配置 data/twitter-targets.yaml

- `targets:` 列表, 每条 `name` / `handle` / `url` 必填。
- 可选: `enabled` (默认 true), `max_tweets` (默认 30)。
- 增删人物后采集自动生效, 无需改代码; 当前 10 账号 (DHH/Sam Altman/DeepSeek/Nous 等)。

## 数据 schema data/twitter.json (30/24h)

文档结构:
- `generated_at`: UTC Z 格式 (`2026-08-25T01:00:00Z`)
- `retention`: `"30/24h"` (条数/小时窗口)
- `targets[]`: 每项 `{name, handle, url, tweets[]}`
- `last_error`: 部分失败时的最近错误 (成功时 null)

tweet 字段 (缺失键用 null, 前端渲染稳定):
`id` / `text` / `forward` (转推/引用, 格式 `by @{作者}: {原推文}`) / `posted_at` (UTC Z) /
`url` / `views` / `replies` / `retweets` / `likes` / `images` (pbs.twimg.com URL 列表)。

retention 规则 (条数优先滑动窗口):
- 24h 内 > 30 条 → 全留 24h (不截断);
- 24h 内 ≤ 30 条 → 留全部 24h + 从旧补到 30;
- 总数 < 30 → 全留。

前端 `index.html` X热点 tab 独立加载本文件。

## 登录态与 CDP

两个 profile 概念, 勿混淆:

| 概念 | 路径 | 用途 |
|:---|:---|:---|
| 脚本默认 profile | `cache/twitter-profile/` (DEFAULT_PROFILE_DIR, TWITTER_PROFILE_DIR 可覆盖) | 默认 collect / `--login` 自管理 Chrome 实例 |
| 运维实际登录态 | `~/chrome-twitter-cdp` + CDP 9222 | cron 包装按需启停 (`--attach` 复用登录态, 采集后释放实例); Chrome ≥151 禁止默认 profile 开调试端口, 必须独立 user-data-dir |

- `--login`: 有头模式打开 `x.com/login` 人工登录一次; 登录 cookie 持久化在 profile 内,
  重启 Chrome 不丢。
- `--attach`: attach 到已运行 Chrome (CDP 9222), 复用其登录态, 不传
  `--user-data-dir`/`--headless`; **attach 模式下 `driver.quit()` 只断开 CDP, 调试 Chrome 仍存活**
  (2026-10-06 实测: 曾常驻 1d7h / 家族 10 进程 660MB) ⇒ 释放实例由 `scripts/twitter-collector-cron.sh` 收尾负责。
- 登录墙检测: URL 重定向 `/login` 或出现登录按钮 → exit 2 + 提示
  `python3 scripts/twitter-collector.py --login`。
- Profile 互斥: `cache/twitter-profile/.collector.lock` pidfile 防 --login 与 cron 并发双 Chrome。

## 入库 auto-push 语义

- 采集成功自带 commit + push: `auto-push@llm-radar: update twitter (N changes)`。
- `git add` 范围限定 `data/twitter.json` (勿 `git add -A` 顺带)。
- push 失败仅记 cron 日志, 不重试轰炸, 下一轮自动再试。
- 全部失败不写盘 (保留上次 twitter.json), 前端展示旧数据。

## cron 20 9,21 错峰 + 按需启停

```cron
20 9,21 * * * cd /Users/jadenli/CodeSpace/llm-radar.lab && bash scripts/twitter-collector-cron.sh >> cache/logs/twitter-collector/twitter.log 2>&1 # llm-radar-twitter
```

- 09:20 / 21:20, 避开主采集整点 :00 — 防双 Chrome 实例资源竞争与 `git add` 抓取竞争。
- Mac 本机部署; Linux 服务器默认不启用 (无人工登录态, 如需由部署方 `--login` 一次)。

### 按需启停生命周期 (2026-10-06, 省 ~660MB 常驻)

`scripts/twitter-collector-cron.sh` = 检查 CDP → 未就绪拉起 (独立 profile) → 等 ready (≤30s)
→ 采集 → **采集结束释放实例** (SIGTERM 优雅退出, 超时 SIGKILL), 退出码原样透传。

- 幂等边界: pidfile `cache/pids/twitter-chrome-<port>.pid` 存在 ⇒ 视为本脚本实例 (上轮被强杀
  的遗留) → 本轮收编并释放; 无 pidfile 的就绪实例视为**外部常驻**, 只复用不杀。
- 人工登录/调试需保留窗口: `TWITTER_CHROME_KEEP=1 bash scripts/twitter-collector-cron.sh`
  (或直接 `--login`), 保留的实例会在下一轮 cron 被收编释放 (pidfile 已写)。
- 环境变量: `TWITTER_CDP_PORT` / `TWITTER_PROFILE_DIR` / `TWITTER_CHROME_BIN` /
  `TWITTER_CHROME_LOG` / `TWITTER_CHROME_SHUTDOWN_TIMEOUT` / `TWITTER_CHROME_READY_TRIES` /
  `TWITTER_CHROME_KEEP`。
- 不得改回 `exec python3 …`: exec 会顶掉包装进程, 收尾释放永不执行 (测试有回归守卫)。
- 验证 (判据): 采集前/后 `pgrep -f 'remote-debugging-port=9222' | wc -l` 均为 0, 采集期间 ≥1;
  生命周期回归 `python3 -m pytest tests/test_twitter_cron.py -q` (桩 Chrome/桩采集器, 端口 19222)。

## 故障排查

浓缩速查 (详细过程与根因见 x-twitter-scraping):

1. 残留 Chrome / Singleton 锁: 杀掉采集进程后 Chrome 子进程常存活, 下次启动
   chromedriver 崩溃 (native stack)。清理: `pkill -f "chrome-twitter-cdp"` +
   删 profile 目录 `Singleton*` 文件; 若 SIGKILL 过, 同步清 `.collector.lock` pidfile。
2. chromedriver pin: attach 卡死数分钟即使 9222 活着 — Selenium Manager 版本匹配下载
   stall。显式 `Service('/path/to/chromedriver')` 绕过 (attach 变 <1s)。
3. attach 后零页面: 上次 `driver.close()` 关掉最后一个 tab → `curl -X PUT
   "http://127.0.0.1:9222/json/new?https://x.com"` 开新 tab 再 attach。
4. 通用 X 深坑 (虚拟列表 DOM 回收 / 动态滚动 / 自动化登录被拦截 / 无限滚动降级) →
   Hermes skill `x-twitter-scraping`, 不在此复制。

验证: 登录态 `curl -s http://127.0.0.1:9222/json/version`; 注意 shell 管道取退出码用
`${PIPESTATUS[0]}`。
