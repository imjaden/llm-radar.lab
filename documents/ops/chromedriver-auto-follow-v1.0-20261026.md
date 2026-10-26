# chromedriver 自动跟随（Chrome 升级不再打穿采集）· v1.0
- 日期：2026-10-26
- 范围：`llm-radar.lab`（采集侧）+ `~/.hermes/profiles/ops`（告警脚本 / cron）
- 前置：`chromedriver-manager`（script-miner，CLI `~/.local/bin/chromedriver-manager`）为唯一真源

## 1. 两个问题（都已在 2026-10-26 修复）

### 1.1 假告警：Feishu 报「chromedriver 154 与本机 Chrome 155 不匹配」
真实状态是 **Chrome 156.0.8078.47 + driver 156**（`chromedriver-manager check --json` ⇒
`verdict: compatible`）。告警里的 154/155 来自 **2026-10-21 17:40 的历史日志行**。根因三条叠加：

1. `llm-radar-collect-report.py::health_facts()` 用 `tail_lines(1200)` **正序**扫、命中即 `break`
   ⇒ 报的是窗口内**最老**一条，不是当前状态；
2. 窗口 1200 行 ≈ 5 天（`collector.log` 25k 行 / 1.4MB，无轮转）⇒ 问题修好后仍持续复报；
3. 判据来源错：用日志正则猜版本，而不是问权威工具。

修法：`driver_facts()` 改以 `chromedriver-manager check --json` 为准（`compatible` ⇒ 不报，
否则报 `driver X ≠ Chrome Y（chromedriver-manager 判定）`）；回退分支改为**倒序取最新**且只认
**最近 24h** 的命中，文案由「起持续告警」改为「最近一次 MM-DD HH:MM」；告警指纹加入
`v`（`ok:chrome:driver`）字段，状态变化即重报。

### 1.2 Chrome 自动升级打穿采集（10-23 实测：6 源全降级 12 连败）
`~/.wdm` / `~/.cache/selenium` 里的驱动按**版本目录**存放，Chrome 一升级就找不到匹配版本，
采集器 `_resolve_chromedriver` 只能退回旧驱动（日志 `主版本 154 与本机 Chrome 156 不匹配`）。

## 2. 方案（三层，互相兜底）

```
① 稳定指针  ~/Library/Application Support/llm-radar/chromedriver/chromedriver
            （不带版本 → 已用 `chromedriver-manager add --path` 注册; manager 的 upgrade 会写它）
② 采集注入  llm-radar-run.sh / scripts/twitter-collector-cron.sh 调
            scripts/chromedriver_bootstrap.py --print-path → export CHROMEDRIVER / TWITTER_CHROMEDRIVER
            （两采集器的候选序第一位; 只有「已验证兼容」才注入, 拿不到就回退原有扫描逻辑）
            **前置守卫**: print-path 为空（所有注册路径都不兼容/manager 不在）时才跑 --ensure 再问一次
            ⇒ 不等每小时 :05 的 cron, 当场跟随; 取不到就静默回退, 绝不阻断采集
③ cron 守卫  llm-radar-chromedriver-guard（每 :05）→ --watch
            不就绪 ⇒ iCloud 有匹配版则只 upgrade, 否则先 download(重试 1 次) 再 upgrade, 最后复核
            状态不变 ⇒ 空输出（静默）; 升级/失败/恢复 ⇒ 单条飞书
```

设计与实现要点：
- **非交互**：一律 `upgrade --all --json`（不加 `--json` 时 manager 会 `input()` 等选择，cron 会挂住）。
- **采集侧只认稳定路径**：manager 的 `verdict=compatible` 只要任一注册路径兼容即成立，
  所以守卫用 `stable_compatible` 判定「采集是否真的可用」（稳定路径旧了 ⇒ 必须 upgrade）。
- **不自己下载驱动**：下载/校验/iCloud 归档全部交给 manager，本仓不引入第二套真源。
- **失败仍可采集**：注入失败只是回退到原扫描逻辑，不会阻断采集；海外源不就绪按「跳过」处理。

## 3. 实测证据（2026-10-26，真机）

| 场景 | 操作 | 结果 |
|:---|:---|:---|
| 注册稳定路径 | `chromedriver-manager add --path ~/Library/Application Support/llm-radar/chromedriver/chromedriver` | 注册成功；`check --json` 两条路径均 `compatible` |
| 版本旧了能否自愈 | 把 154 驱动覆盖到稳定路径 → `chromedriver_bootstrap.py --ensure` | `action: upgraded`（`upgrade rc=0`），稳定路径回到 `156.0.8078.47`，**离线**（iCloud 已有匹配版，未触发 download） |
| 采集侧注入 | `./llm-radar-run.sh --help` | `[run] chromedriver: …/Application Support/llm-radar/chromedriver/chromedriver` |
| cron 最小环境 | `env -i PATH=/usr/bin:/bin … --print-path` | 正常输出路径（manager 用绝对路径，不依赖 `~/.local/bin` 在 PATH） |
| 两采集器解析 | 分别调 `_resolve_chromedriver` | 主采集 → 稳定路径；X 采集 → `(稳定路径, 'env:TWITTER_CHROMEDRIVER')`，**无版本不匹配告警** |
| 告警侧修复 | `llm-radar-report-watch.py` | 告警正文中 chromedriver 假根因消失（只剩真实原因） |
| 前置守卫·有回退路径 | 稳定路径覆盖为 154 后 `env -u CHROMEDRIVER ./llm-radar-run.sh --help` | `[run] chromedriver: …/script-miner/cache/chromedriver/chromedriver`（回退到兼容路径，**不**触发 ensure） |
| 前置守卫·全不可用 | 同上但 `CHROMEDRIVER_MANAGER=/nonexistent/mgr` | 打印 `[run] chromedriver 未就绪 ⇒ 尝试自动跟随（ensure）`，采集照常继续（不阻断） |

测试：`tests/test_chromedriver_bootstrap.py`（13 例：ready 判定 / usable_path / ensure noop·upgrade·download /
watch 静默·去重·恢复 / CLI 退出码）+ 既有套件 ⇒ 全量 **343 passed, 2 deselected**。

## 4. 运行时契约

- 状态文件：`cache/records/chromedriver-guard.json`（`ts / ok / action / sig / summary / detail`）。
- 退出码（供 cron 判失败）：`0` 就绪或已升级｜`1` 未就绪（失败已发消息）｜`2` manager 不可用。
- 通知纪律：同一 `sig` 不重复发；失败持续期间只发第一条；恢复正常发一条 `✅ 已恢复`。
- 手工排查：
  ```bash
  python3 scripts/chromedriver_bootstrap.py --check          # 当前判定（含 stable_compatible）
  python3 scripts/chromedriver_bootstrap.py --print-path     # 采集器会用的路径
  python3 scripts/chromedriver_bootstrap.py --ensure         # 立即跟随（幂等）
  chromedriver-manager check --json                          # 权威真源
  ```

## 5. 已知边界

1. **采集进行中 Chrome 升级**：本次覆盖的是「采集开始前」与「每小时兜底」；会话中途升级仍会失败一轮，
   下一轮自动恢复（不做「中途重试」以免污染半轮数据）。
2. **iCloud 无匹配版且网络不可用**：守卫会连发 1 条失败消息后静默（指纹去重），并在下一小时重试；
   机器长期离线时以「采集跳过/降级」表达，不额外告警。
3. **X 采集的 Selenium Manager 路径**：`TWITTER_CHROMEDRIVER` 已注入，但若手工直跑
   `python3 scripts/twitter-collector.py --attach`（绕过 wrapper）则走原扫描逻辑（可自行 export）。
4. **日志轮转未做**（P4 待办）：本次只把告警判据从日志改成 manager，`collector.log` 仍无切割。
