---
title: X热点功能验证指令 (CL-SEC19)
topic: llm-radar
type: verify
version: 1.0
date: 2026-08-26
author: hermes-1.2.0
tags: [llm-radar, x, twitter, verify, cl-sec19]
profile: ops
provider: deepseek
model: deepseek-v4-flash
---

# X热点功能验证指令 (CL-SEC19)

> 验证对象: scripts/twitter-collector.py / twitter-collector-cron.sh /
> twitter-targets.yaml / data/twitter.json / index.html X热点 tab + 分栏。
> 设计: documents/solutions/x-hotspot-design-v1.1-20260825.md (PASS 100/A)。
> 实现审计: documents/reviews/x-hotspot-impl-audit-v1.0-20260826.md (PASS 100/A)。

## A. 前置检查

A1 调试 Chrome 就绪 (--attach 依赖)

```bash
curl -s --max-time 2 http://127.0.0.1:9222/json/version | head -2
```

预期: 返回 JSON 含 "Chrome/151..."。

若失败 (机器重启后): 执行

```bash
bash ~/CodeSpace/llm-radar.lab/scripts/twitter-collector-cron.sh
```

(自动拉起调试 Chrome, 已验证 ~1s 就绪; 登录态在 ~/chrome-twitter-cdp)。

A2 配置文件存在

```bash
cat ~/CodeSpace/llm-radar.lab/twitter-targets.yaml
```

预期: targets 含 Peter Steinberger / steipete / x.com/steipete / enabled: true。

## B. 采集器功能

B1 CLI 签名 (--dry-run / 未知参数)

```bash
cd ~/CodeSpace/llm-radar.lab && python3 scripts/twitter-collector.py --dry-run
```

预期: 配置解析 1 目标 + 登录态探测输出, exit 0。

```bash
python3 scripts/twitter-collector.py --badflag
```

预期: 打印用法, exit 1。

B2 真实采集 (--attach, 核心项, 耗时约 3-4 分钟)

```bash
cd ~/CodeSpace/llm-radar.lab && python3 scripts/twitter-collector.py --attach
```

预期:

```text
[twitter-collector] attach 模式: CDP 127.0.0.1:9222
[twitter-collector] 抓取: Peter Steinberger (@steipete)
[twitter-collector]   → ≥1 条 36h 窗口内推文
[twitter-collector] ✅ 写盘 data/twitter.json (N 条推文)
[twitter-collector] ✅ commit: auto-push@llm-radar: update twitter (N changes)
[twitter-collector] ✅ push 成功
```

说明: 若当天 steipete 无新推文或全在 36h 窗外, 可能 0 条 → 不写盘 exit 1
(保留旧数据, 属设计行为, 非故障)。

B3 attach 失败友好提示 (D4)

```bash
cd ~/CodeSpace/llm-radar.lab && TWITTER_CDP_PORT=9299 python3 scripts/twitter-collector.py --attach
```

预期: `❌ 无法连接调试 Chrome (127.0.0.1:9299) ... 请先启动: bash scripts/twitter-collector-cron.sh`, exit 1 (无 traceback)。

B4 自动拉起包装 (D1A)

```bash
pkill -f "chrome-twitter-cdp"; sleep 2; curl -s --max-time 2 http://127.0.0.1:9222/json/version >/dev/null || echo "9222 down"
cd ~/CodeSpace/llm-radar.lab && bash scripts/twitter-collector-cron.sh
```

预期: `[twitter-cron] 9222 未就绪, 启动调试 Chrome` → 等 ready → 采集 → commit → push。

幂等: 再次运行 (9222 已就绪) → 无启动提示直接采集。

B5 登录态恢复 (仅失效时需做)

失效特征: B2 输出 `❌ 登录态失效` / attach 打开 x.com 被重定向 login。
恢复: 在调试 Chrome 窗口 (bash scripts/twitter-collector-cron.sh 拉起) 手动
登录一次 x.com; 普通浏览器环境, 不遇反爬。

## C. 数据产物 (data/twitter.json)

C1 schema 合规

```bash
python3 -c "
import json; d=json.load(open('/Users/jadenli/CodeSpace/llm-radar.lab/data/twitter.json'))
print('generated_at:', d['generated_at']); print('window:', d['window_hours'])
for t in d['targets']:
    print(t['name'], len(t['tweets']), 'tweets')
    for tw in t['tweets']:
        print(' ', tw['id'], tw['posted_at'], 'views=', tw['views'], 'likes=', tw['likes'], 'text=', tw['text'][:40])"
```

预期: generated_at 为 UTC (Z) 格式; 每条推文含
id/text/posted_at/url/views/replies/retweets/likes/images;
posted_at 在 now-36h 窗口内。

## D. 前端 (X热点 tab + 分栏)

D1 本地渲染验证

```bash
cd ~/CodeSpace/llm-radar.lab && python3 -m http.server 8767
```

浏览器打开 http://localhost:8767/ → 点击 "X热点" tab。
预期: 表格显示 twitter.json 推文 (时间/人物/摘要/指标/详情按钮);
默认 tab 仍为 大模型; 其他 5 tab 正常。

D2 分栏交互

操作: 点击推文行 (或"详情"按钮)。
预期: 右侧分栏打开, 含 上一/下一条 nav、关闭 ✕、推文全文、指标
(浏览/回复/转推/点赞)、原文链接 (新标签打开, rel=noopener)。
关闭: ✕ / 点击背景 / Esc 均可。
窄屏: 浏览器窗口 <1200px → 分栏变底部全屏抽屉。

D3 数据加载失败回退 (可选)

操作: 临时改名 data/twitter.json → 刷新。
预期: X热点 tab 空态, console 有 `[llm-radar] twitter.json load failed:`,
页面其他功能正常。

## E. 测试套件

E1 非 selenium 全量

```bash
cd ~/CodeSpace/llm-radar.lab && python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q
```

预期: 184 passed, 2 deselected。
注意: 跑完还原测试污染:

```bash
git checkout -- data/snapshot.json overview.json timestamp.json
```

## F. crontab 接入

F1 检查定时行

```bash
crontab -l | grep -E "llm-radar"
```

预期两行:

```text
0 * * * * cd /Users/jadenli/CodeSpace/llm-radar.lab && ./llm-radar-run.sh run >> ... # llm-radar-collector
20 9,21 * * * cd /Users/jadenli/CodeSpace/llm-radar.lab && bash scripts/twitter-collector-cron.sh >> data/twitter.log 2>&1 # llm-radar-twitter
```

说明: 主采集每小时 (路径已修复 llm-radar.lab); twitter 每日 9:20/21:20
自动拉起采集; 采集日志: data/twitter.log。

## G. 闭环状态

G1 远端同步

```bash
cd ~/CodeSpace/llm-radar.lab && git fetch origin -q && git rev-list --left-right --count origin/main...HEAD
```

预期: `0 0`。

## 验证顺序建议

A1 → A2 → B1 → E1 → B2 → C1 → D1/D2 → F1 → G1
(核心链路 B2 + C1 + D2; 全套约 15-20 分钟, 含采集耗时)。
