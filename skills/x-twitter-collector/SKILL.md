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
  常见形态 (2026-10-07 实测): `! [rejected] main -> main (fetch first)` — 主采集/服务器 auto-push 先推了数据 commit,
  X 采集器只做普通 push 不 rebase ⇒ 该轮数据 commit 留在本地, 下一轮 (或人工 fetch+rebase, 禁 force) 再推。
- 全部失败不写盘 (保留上次 twitter.json), 前端展示旧数据。

## cron 每小时 :20 + 节流 + 按需启停 (2026-10-09)

```cron
20 * * * * cd /Users/jadenli/CodeSpace/llm-radar.lab && bash scripts/twitter-collector-cron.sh >> cache/logs/twitter-collector/twitter.log 2>&1 # llm-radar-twitter
```

- 每小时 :20 触发（与主采集 :40 错峰, 防双 Chrome 与 `git add` 竞争）; **实际采集频率由脚本内节流决定**。
- ⚠️ 为什么不能再用固定槽位 `20 9,21`: **Mac 休眠期间错过的 cron 槽位不会补跑**。
  2026-10-07~09 实测: 休眠窗口正好盖住 09:20/21:20 ⇒ 连续 3 天零执行、`twitter.json` 陈旧 46.6h,
  而 crontab 完好（主采集因「每小时 :40 + 6h 节流」天然抗休眠, 所以只有 X 侧断档）。
- 节流: `twitter.json` 生成 < `TWITTER_THROTTLE_HOURS`(默认 5) 则跳过（`--force` 绕过, `0` = 关闭）。
  任意一次唤醒都能补上被错过的窗口。
- Mac 本机部署; Linux 服务器默认不启用 (无人工登录态, 如需由部署方 `--login` 一次)。

### 按需启停生命周期 (2026-10-06, 省 ~660MB 常驻)

`scripts/twitter-collector-cron.sh` = 节流判定 → FlClash 就位 → 检查 CDP → 未就绪拉起 (独立 profile)
→ 等 ready (≤30s) → 采集 → **收尾释放本脚本拉起的 Chrome 与 FlClash**（SIGTERM 优雅, 超时 SIGKILL）,
退出码原样透传。

- 幂等边界: pidfile `cache/pids/twitter-chrome-<port>.pid` 存在 ⇒ 视为本脚本实例 (上轮被强杀
  的遗留) → 本轮收编并释放; 无 pidfile 的就绪实例视为**外部常驻**, 只复用不杀。
- 只关「是 Chrome 程序」的进程: `main_pids` 排除 `--type=` Helper, 并要求命令行含 Chrome 程序名
  ⇒ 仅"提到"端口的旁观进程 (监视脚本/巡检命令) 不会被误杀 (2026-10-09 实测中招后加固)。
- 人工登录/调试需保留窗口: `TWITTER_CHROME_KEEP=1 bash scripts/twitter-collector-cron.sh --force`
  (或直接 `--login`), 保留的资源会在下一轮 cron 被收编释放 (pidfile 已写)。
- 环境变量: `TWITTER_THROTTLE_HOURS` / `TWITTER_FLCLASH_ENSURE` / `TWITTER_FLCLASH_PORT` /
  `TWITTER_FLCLASH_READY_TIMEOUT` / `TWITTER_FLCLASH_GRACE` / `TWITTER_CDP_PORT` /
  `TWITTER_PROFILE_DIR` / `TWITTER_CHROME_BIN` / `TWITTER_CHROME_LOG` /
  `TWITTER_CHROME_SHUTDOWN_TIMEOUT` / `TWITTER_CHROME_READY_TRIES` / `TWITTER_CHROME_KEEP`。
- 不得改回 `exec python3 …`: exec 会顶掉包装进程, 收尾释放永不执行 (测试有回归守卫)。
- 验证 (判据): 采集前/后 `pgrep -f 'remote-debugging-port=9222' | wc -l` 均为 0, 采集期间 ≥1;
  生命周期 + 节流 + FlClash 回归 `python3 -m pytest tests/test_twitter_cron.py -q`
  (19 用例; 桩 Chrome/桩采集器/桩 FlClash, 端口 19222)。

### FlClash 代理生命周期 (X 必需)

真源 = `script-miner/projects/macosx/macosx-service-policy.json` (`services[FlClash].restart`):
stop `osascript -e 'quit app "FlClash"'` / grace 20s / force_fallback `kill -TERM {pid}` /
start `open -a FlClash` / verify.ports `[7890]`。

- 采集前: 未运行 → `open -a FlClash` + 等 **7890 LISTEN** (≤180s) → 采集后**释放**;
  原本就在运行 → 只复用, 采集后**保持运行不动**。
- 就绪判据只用端口, 不判"是否已把系统代理切过去"; 实测 `open -a` 后 7890 很快 LISTEN
  (2026-10-09 14:52 实测: 启动到就绪 <10s)。
- 检测不用 `pgrep -f FlClash`(会被 `osascript -e 'quit app "FlClash"'` 自身命中), 改
  `pgrep -x FlClash` ∨ `pgrep -f '/Applications/FlClash.app'` 双判据。
- `TWITTER_FLCLASH_ENSURE=0` 关闭本层 (退回旧行为: 由 `twitter-collector.py` 的 `_is_flclash_running()`
  检测, 未运行则 exit 1 + 本地通知)。
- 未就绪 → exit 1, 不进入采集 (也不会拉起 Chrome)。

## 观察项 O-X: 收尾兜底缺口 (2026-10-07, 暂不实现)

- 缺口场景: 采集脚本被 `kill -9` (cron 超时 / 人工强杀 / 系统休眠回收进程) ⇒ trap 不执行,
  该轮实例无人回收; 现靠**下一轮 cron** (`20 9,21`, 最坏 ~12h) 经 pidfile 收编后释放;
  若机器长期休眠 + 白天无 cron, 常驻时间可更长 (迁移前 1d7h 案例即此类, 靠人工发现)。
- 自查命令: `pgrep -f 'remote-debugging-port=9222' | wc -l` 非 0 且无采集在跑 = 命中该场景。
- 候选方案 (未采用): 拉起后 spawn 一个 detached 看门狗 (记 port + 最大存活 T, 默认 30min),
  每 30s 检查 (a) 主进程存活 + (b) 「采集中」标记文件 (脚本采集期间 touch / 结束 rm); 两条件皆无
  ⇒ SIGTERM + 清 pidfile + 记日志。双条件是避免误杀进行中的采集。
  代价 = 多一个常驻小进程 + 状态文件; 机器休眠时 sleep 不前进 (唤醒后才计时)。

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
