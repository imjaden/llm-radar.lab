---
author: hermes-v0.20.6(2026.8.27)
profile: dev
type: summary
date: 2026-09-08
---

# llm-radar ops handbook v1.0（部署/cron/探针）

> documents-consolidation phase-2 草稿（只写文件，未 commit）。素材全文（gitignored）：
> `cache/doc-consolidation/llm-radar-ops-extract.md`。
> 代码行号核实基准：2026-09-08 工作区 HEAD 7e2c3b5。素材分散于 linux-deployment（仅环境/部署）+ github-ci-issues（CI）+ health-probe 族（6 份，含双机 cron/域名事实源）——部署文档不含 cron/域名章节，本手册为多源拼接。

## 一、定位

本手册覆盖 llm-radar 生产运维三块：阿里云 Linux 部署环境（linux-deployment）、GitHub Actions CI 故障记录（github-ci-issues）、线上数据新鲜度探针 health watchdog 全生命周期（health-probe 族）。

素材：8 份 = linux-deployment 1 + github-ci-issues 1 + health-probe 6（design v1.2 + impl + review/rereview/ops-verify + stale-hours-audit）。

## 二、功能概述

- **双机拓扑**：本机 macOS（`~/CodeSpace/llm-radar.lab`，每小时 + 6h 防抖 → 实际约每 6-7h 有效一次）+ 阿里云 Linux（59.110.66.1，`/home/admin/codespace/llm-radar.lab`，7×24 cron `0 7,14,21 * * *` 主源），同推一个 repo，GitHub Pages 站点 `llm-radar.lab.jaden.tech`。
- **Linux 部署环境（linux-deployment v1.0, 2026-07-01）**：Alibaba Cloud Linux 3；conda env `llm-radar`（Python 3.11，本机为 py3.12——`.cli-registry.yaml` env.conda=py3.12 仅本 Mac）；`google-chrome-stable` 150.0.7871.46 + Selenium 4.45.0；代码目录 `/home/admin/codespace/llm-radar.lab`；启动器 `llm-radar-run.sh`（跨平台路径假设 L14-16）。
- **CI 现状（github-ci-issues v1.1, 2026-07-04）**：`tests/` 用 `Path(__file__).resolve().parent.parent` 相对化（#1 ✅）；selenium 测试 `GITHUB_ACTIONS` skipif（#2 ✅）；**`secrets.DEEPSEEK_API_KEY` 未创建（#3 🔴 P0，需用户 GitHub 网页操作，未修复）**。记录另有 http-server-cli/MCP 侧问题 #4-8（跨仓，非本主题）。
- **探针（health watchdog）**：`scripts/llm-radar-health.py`（纯 stdlib 105 行）请求线上 `timestamp.json?t=<epoch>` 验证「采集→push→GitHub Pages→CDN」全链新鲜度；hermes cron job `llm-radar-freshness`（ops profile **02a2cdc5db20**，原 dev 534bea76c7eb 迁移，`0 3,9,15,21 * * *` no_agent deliver=local）。

## 三、机制与指令说明

### 3.1 探针三态退出契约（code 实核 scripts/llm-radar-health.py，docstring L8-15，O-1 编号出处）

| 状态 | 判定 | 退出 |
|---|---|---|
| 数据过期 | `now - last_run_at > STALE_HOURS`（严格大于，L75-79） | **exit 1** + 硬告警（消息含 last_run_at/h 数/last_news_date/status） |
| 探针错误 | 网络失败/JSON 解析失败/字段缺失/时间戳无法解析（L64-70/L93-96） | **exit 1** + 告警（不静默） |
| 质量软告警 | `last_run_status != 'success'` 但数据新鲜（L82-84） | **exit 0** + 告警文本（stdout 投递路径） |
| 健康 | 新鲜且 success（L87） | **exit 0** + 空（静默） |

常量：`STALE_HOURS = int(os.environ.get('LLM_RADAR_STALE_HOURS','12'))`（L38，默认 **12**——2026-09-03 commit 2ff9b51 由 7 放宽覆盖跨夜空窗；docstring L28 仍写「默认 7」未修，AGENTS.md L50 同）；`ENDPOINT`（L41）= `https://llm-radar.lab.jaden.tech/timestamp.json`；`TIMEOUT = 15`（L42）；cache-busting（L47）`?t={int(time.time())}` 绕 CDN。时区契约（O-2 编号出处）：`last_run_at` = 采集机 `datetime.now().isoformat()` naive 本地时间（collector L1628），探针同机解析，双机均 +08:00。

### 3.2 cron 机制（code 实核 llm-radar-collector.py）

- `CRON_SCHEDULE`（L2389）：`'0 * * * *' if platform.system() == 'Darwin' else '0 7,14,21 * * *'`；`CRON_TAG = '# llm-radar-collector'`、`CRON_CMD = f'{RUN_SCRIPT} >> {COLLECTOR_LOG} 2>&1'`（L2385-2390，日志在 cache/logs/）。
- `crontab` 子命令（L2392-2474）：`--add [schedule]`（CRON_TAG 已存在提示 --update；追加依赖注释头 DEEPSEEK_API_KEY/conda env）/ `--remove` / `--list` / `--update [schedule]` / `--status`（默认，打印 COLLECTOR_LOG 末 3 行）；分发 L2730-2742。
- 6h 防抖在 `_think()`（L1708-1743）：`--force` 跳过间隔检查；`metrics.json` 无 → 放行；`hours_since < 6` → 跳过 return False；连续失败 ≥3 仍尝试仅告警。（design 引「collector.py:1391-1393」行号已漂移——该处今为时间衰减。）
- 双写 STALE_HOURS：collector L70 与 health.py L38 各自读同一 `LLM_RADAR_STALE_HOURS` env（status checkpoint warning 阈值）；collector 另增 `CRITICAL_HOURS=48`（L71）。

### 3.3 hermes cron 注册要点（探针部署胶水）

- hermes cron no_agent 的 `script` 字段**只接受 profile scripts/ 目录下文件名，拒绝项目绝对路径**（实测解析到 `~/.hermes/profiles/<profile>/scripts/`）→ 项目脚本保持 repo 版本化，profile scripts/ 放 `os.execv(sys.executable, [sys.executable, PROJECT_SCRIPT])` 薄 wrapper 委派（单一逻辑源，无副本漂移）；wrapper 非 repo 内容。
- **监控职责归 ops profile**：job 由 dev（534bea76c7eb）迁 ops（02a2cdc5db20），与 health-daily/health-weekly 同 profile（ops-verify 修正决策）。
- 注册形态：`no_agent=true`、`schedule 0 3,9,15,21 * * *`、`deliver=local`（告警投递暂忽略，RIG-3 🟢 观察）。

### 3.4 启动器（llm-radar-run.sh, 68 行）

Darwin → `PYTHON="python3"`（conda 需用户先行 activate）；Linux → 优先 `/root/miniconda3/bin/activate llm-radar` → `PYTHON="python"`，兜底 `/root/miniconda3/envs/llm-radar/bin/python`，无则报错 exit 1；DEEPSEEK_API_KEY 缺失 → 报错 exit 1；`.env` 同目录加载（set -a 模式）；无参 → run，有参透传。

## 四、用法示例

```bash
# 探针手动验证（三态）
python3 scripts/llm-radar-health.py                 # 健康 → exit 0 空输出
LLM_RADAR_STALE_HOURS=0 python3 scripts/llm-radar-health.py   # 过期 → exit 1 「数据过期: …」

# Linux 部署（阿里云）
cd /home/admin/codespace/llm-radar.lab && git pull
pip install openai selenium webdriver-manager requests beautifulsoup4 prettytable
yum install -y google-chrome-stable
bash llm-radar-run.sh selenium-check                # 验证浏览器链路
bash llm-radar-run.sh run                           # 手动采集

# 运维/排障
python3 llm-radar-collector.py selenium-check
tail -f cache/logs/llm-radar-collector/collector.log   # 现行日志路径（linux-deployment doc 的 data/collector.log 已过期）
pkill -9 -f chromedriver
lr crontab --status                                 # 定时任务状态 + 日志末 3 行

# CI 复现
GITHUB_ACTIONS=true python3 -m pytest tests/ -v --tb=short   # 模拟 CI（跳过 selenium）
# GitHub 网页操作（待办 #3）：Settings → Secrets and variables → Actions → New repository secret DEEPSEEK_API_KEY
```

## 五、关键决策（原文编号）

### 族 A linux-deployment（2026-07-01，经验记录型，无编号体系）

- Chrome/ChromeDriver 跨平台自动检测 + 版本号 regex `(\d+\.\d+\.\d+\.\d+)` 提取（修旧 `split()[-1]` 在 Linux 返回 "Project"）；统一 `google-chrome-stable` 而非 yum Chromium 133（与 wdm ChromeDriver 150 匹配）；浏览器启动测试导航改本地 `data:text/html,<h1>Selenium OK</h1>`（google.com 被墙 ERR_CONNECTION_TIMED_OUT）。
- 已知问题表：qbitai Selenium 超时 25s 不够 ⏳ / chrome 版本显示 "Project" ✅ / Google URL 被墙 ✅ / ChromeDriver 版本不匹配 ✅。

### 族 B github-ci-issues（2026-07-04，总览表 #1-8 + P0-P3）

- **#1** tests 硬编码 Mac 绝对路径 → `Path(__file__).resolve().parent.parent`，✅ 7bdebd5（P0）；**#2** CI 无 Chrome → `pytestmark = skipif(GITHUB_ACTIONS=="true")`，✅ 436c61e（P1）；**#3** `secrets.DEEPSEEK_API_KEY` 未创建 🔴 P0 **未修复**（需用户操作）。#4-8 为 http-server-cli/MCP 侧记录（#4 local 越作用域 ⏳P2 / #5 daemon 无限 fork ⏳P2 / #6 MCP stdio PID 覆盖 🟡P3 / #7 HTTP 无标准 /mcp 端点 🟡P3 / #8 merge_entities 无 100 条滑动窗口 ✅P2——该条已过时，留存窗口已实施）。
- 文档命名规范（本文产物）：问题记录用 `issues` 前缀、操作速查 `ops`、教程 `guide`，模板 `{domain}-issues-v{major}.{minor}-{YYYYMMDD}.md`。

### 族 C health-probe（2026-08-13 ~ 09-03）

- 触发频率三方案（方案 A 每小时 / **方案 B 每 6h `0 3,9,15,21 * * *`** ✅ / 方案 C 服务器采集后 1h）——6h 间隔 < 7h 阈值，任何过期必被捕获。⚠️ 编号陷阱：方案 B（整体频率）与确认项 B1（阈值）无对应关系（见 §六-1）。
- 用户确认清单（"用户回复: A1 B1 C2"）：**A1** 每 6h（与采集 6h 防抖对齐）/ **B1** 阈值 7h（用户指定「至少最新数据时间控制在 7 小时内」，后放宽 12）/ **C2** 探针脚本放项目内 scripts/（随 repo 版本化）。
- review 80/100 CONDITIONAL（**REA-1** 脚本路径 dev/ops profile 矛盾 → 统一项目内 scripts/；**REA-2** `status != success` 误报（当时本地/线上 failed 但新鲜）→ 新鲜度主 + 质量辅语义分离；**RIG-1** naive 时区歧义 → 文档声明时区契约（O-2）；**RIG-2** 无 cache-busting → 线上实测 **30 天陈旧副本**（last_run_at=2026-07-13！）→ `?t=<epoch>`；RIG-3 🟢 deliver=local 告警不投递）→ v1.2 复审 100/100 PASS（附注 **O-1** 三态退出契约 / **O-2** 时区契约编号出处）。
- 实现 294bfd1 + dev job 534bea76c7eb → ops-verify **PASS**（实测 + 修正 job profile dev→ops，ops job 02a2cdc5db20）。
- **STALE_HOURS 7→12**（2026-09-03, commit 2ff9b51，跨夜空窗：21:00→次日 09:00=12h，实测 13.7h/14.0h 覆盖余量 2h）：**PASS 98/100**（50/50 代码 + 28/28 测试 + 20/22 文档；🟡 minor=health.py docstring L28 仍写 7 + AGENTS.md L50 protected 待用户改）。

## 六、已知坑

1. **design 文档字母三重复用**：方案 B（探针整体）/ 频率对比方案 A/B/C / 确认项 A1 B1 C2——三种语义并存，抄录防串号。
2. **STALE_HOURS 文档残留**：docstring L28 与 AGENTS.md L50 仍写 7，code 实值 12（2026-09-08 未修）；引用以 code + env 为准。
3. **collector 与 health.py 双写 STALE_HOURS**（同一 env 各自独立读），语义同为新鲜度阈值但用途不同（health=告警、collector=status checkpoint warning）；collector 另有 CRITICAL_HOURS=48。
4. **cron 节奏叙事并存 [待核]**：design 记服务器 `0 7,14,21`（与 code 一致）；stale-hours-audit 论证用「~7h (09:00, 21:00)」+ 跨夜 12h——两组时刻并存未指明机器归属，引用并列原文勿二选一。
5. **日志路径 doc 过期**：linux-deployment 运维命令 `tail -f data/collector.log` → 现行 cache/logs/llm-radar-collector/collector.log（cli-runtime-files 迁移后；远端 59.110.66.1 重部署为 OBS-2 开放项）。
6. **旧仓库名残留**：review 头注 `~/CodeSpace/llm-radar.jaden.tech` 与引用的旧行号（collector.py:1285-1292 等）为写作期坐标；现行 llm-radar.lab + 2026-09-08 行号。
7. **探针入口在 profile 不在 repo**：wrapper（os.execv 薄委派）是部署胶水非 repo 内容；hermes cron job 状态无法从仓库核实（注册于 Hermes profile 运行时）。
8. **CI 开放缺口**：secrets.DEEPSEEK_API_KEY（#3 🔴 P0）需用户 GitHub 网页操作；本地无 key 时 test_cli 的 no-key 断言有假绿风险（AUD-001 类，见 cli-governance handbook）。

## 七、参考文档

| 源文件（原位 documents/…） | 角色 | 处置 |
|---|---|---|
| ops/linux-deployment-v1.0-20260701.md | 现行部署环境速查 | **保留原位**（运维命令日志路径已过期见 §六-5） |
| ops/github-ci-issues-v1.0-20260704.md | CI 故障记录（现行开放项 #3） | **保留原位** |
| solutions/llm-radar-health-probe-design-v1.2-20260813.md | health design 终版 | 待归档 → archive/solutions-{date}/ |
| solutions/llm-radar-health-probe-impl-v1.0-20260814.md | health 实现报告 | 待归档 → archive/solutions-{date}/ |
| reviews/llm-radar-health-probe-review-v1.0-20260813.md | health 评审（80/B） | 待归档 → archive/reviews-{date}/ |
| reviews/llm-radar-health-probe-rereview-v1.2-20260813.md | health 复审（100/A） | 待归档 → archive/reviews-{date}/ |
| reviews/llm-radar-health-probe-ops-verify-v1.0-20260814.md | ops 独立验证（族终审） | 待归档 → archive/reviews-{date}/ |
| reviews/llm-radar-stale-hours-audit-20260903.md | STALE_HOURS 放宽审计 | 待归档 → archive/reviews-{date}/ |

交叉引用：`cache/doc-consolidation/llm-radar-ops-extract.md`（gitignored 提炼产物）；阈值常量/CLI 命令面细节见 cli-governance handbook；采集器数据流与 git 自愈见 collector-pipeline / git-sync handbook。
