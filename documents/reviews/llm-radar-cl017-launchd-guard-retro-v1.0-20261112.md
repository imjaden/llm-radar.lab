---
loop: LLM-RADAR-CL017
title: CDP Chrome 常驻守护幂等化（CL017 复盘）
date: 2026-11-12
level: L1
---

# LLM-RADAR-CL017 复盘 · CDP Chrome 常驻守护幂等化

## 1. 现象

2026-11-12 上午，调试 Chrome 上每 **30 秒**冒出一个 `https://x.com/home` 新页签，十几分钟堆到 16+ 个。
同期 `launchctl print` 显示：`runs = 465~477`、`last exit code = 0`、`job state = exited`、
`state = spawn scheduled`；`~/Library/Logs/llm-radar/twitter-chrome.log` 尾部连续刷
`Opening in existing browser session.`。

进一步取证：端口 9222 的持有者是 **pid 90340**（`--remote-allow-origins=*`，Chrome 自更新后自重启而来），
而 plist 拉起的进程都不是它；页签创建时刻（`performance.timeOrigin`）严格 30 秒一个，与 `ThrottleInterval` 一致。

## 2. 根因

LaunchAgent 的 `ProgramArguments` 直接 `exec Chrome … https://x.com/home`，且 `KeepAlive = true`。
当**另一个** Chrome 已经占住同一 `user-data-dir` 与 9222 时，新进程只能把 URL「转发给已有会话」然后 **exit 0**；
launchd 看到 exit 0 且 KeepAlive 为真 ⇒ 30 秒后再拉一次 ⇒ 循环。
**每次循环 = 一个垃圾页签**，但端口始终在监听，所以从「CDP 是否就绪」这一侧看不出异常。

这与 11-10 的「page target=0 导致 X 采集连败 24.9h」是同一根因家族（Chrome 自重启绕过 plist），
只是那次表现为「页面丢失」，这次表现为「页签暴增」。

## 3. 改动

- 新增 `scripts/twitter-chrome-agent.sh`（launchd 入口，幂等）：
  - 端口已在监听 ⇒ 补一次 page target（0 页才补）后 **exit 0**；
  - 端口空闲 ⇒ `exec` Chrome（带 `--remote-debugging-port`、`--user-data-dir`、窗口位置，URL 取 `TWITTER_CDP_PAGE_URL`，默认 `https://x.com/home`）；
  - 依赖 `/dev/tcp` 探测端口，不依赖 lsof/nc。
- plist `~/Library/LaunchAgents/com.jaden.llm-radar-twitter-chrome.plist`：
  `ProgramArguments = [/bin/bash, <repo>/scripts/twitter-chrome-agent.sh]`，
  `KeepAlive = { SuccessfulExit = false }`（正常退出不再重启，异常退出仍拉起），`ThrottleInterval` 保留 30。
- 原 plist 备份：`cache/scratch/twitter-chrome.plist.bak.20261112-085028`。

## 4. 验证

- `pytest tests/test_chrome_agent_guard.py -q -n0` → **5 passed**（监听 no-op 不 spawn / 0 页补一次 /
  空闲 exec 的 argv 拼接 / 探测失败仍 exit 0 / plist 契约注释）。
- 处置现场：`kill -TERM 90340` → 22 秒内 launchd 实例接管（pid 7109），`runs` 477 → 478 后**冻结**，
  页签稳定 1 个；Terminal 重载新 plist 后 `runs = 1`、`last exit = (never exited)`、转发行计数 `54 → 54` 不再增长。
- `lr chrome --status` → `CDP 就绪 / 已登录（42 cookie）/ 经 FlClash 可达`。
- 全量 `pytest -m "not selenium"` → **602 passed**；门禁 `中断收敛 10/10`。

## 5. 经验

1. **`KeepAlive=true` + 直接 exec 一个会「立刻失败退出」的进程 = 定时炸弹**；常驻入口必须幂等（先判端口再决定 exec 还是 exit 0）。
2. Chrome 自更新会以 `--no-startup-window` 自重启并抢走 9222；此时 plist 里的 URL 参数只会变成垃圾页签，不会帮你恢复页面。
3. 只监控「端口在监听」不足以发现这类故障；**页签/目标计数**才是判别信号（与 CL014/CL015 的教训一致）。
4. `kill` 现有实例让 launchd 接管，比「先 bootout 再 bootstrap」风险更低 —— 后者要动 launchd 注册，前者只换进程。

## 6. 遗留

- 无。plist 已重载生效；`CL-SEC11` 的跨仓修法是另一笔（`hermes-manager` a07f3949），与本条无关。
