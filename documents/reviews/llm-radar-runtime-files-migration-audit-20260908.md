# LLM Radar — cli-runtime-files data/ 运行时迁移审计报告

- **日期**: 2026-09-08
- **reviewer**: Security Reviewer (review profile)
- **Level**: L2
- **范围**: 3 commit — f9928eb feat@collector (runtime files → cache/) / 7e7e41d docs@sync (README + skill cron) / 7006ee2 docs@sync (AGENTS.md)
- **承接**: cli-runtime-files 规范 v1.0 (HM-DESIGN-SEC-265) 落地第 2 项 P4 W2
- **Verdict**: ✅ PASS — 100/100 (A)

## 审计结论

无阻塞项。源码路径迁移仅改路径段 + docstring，采集逻辑/数据格式零改动；现行引用零残留；运行时文件已就位 cache/ 且 data/ 无残留；测试全绿；git 卫生正常（本地 ahead 仅 7006ee2，且只含 AGENTS.md）。

## 审计项逐项核验

### 1. 源码迁移正确 — ✅

| 位置 | 旧路径 | 新路径 |
|:-----|:-------|:-------|
| collector L62 `FETCH_CACHE_PATH` | `data/fetch-cache.json` | `cache/llm-radar-collector/fetch-cache.json` |
| collector L63 `COLLECTOR_LOG`（新增） | `data/collector.log` | `cache/logs/llm-radar-collector/collector.log` |
| collector L2387 `CRON_CMD` | `>> data/collector.log` | `>> {COLLECTOR_LOG}` |
| collector L2465 `crontab_status` | `data/collector.log` | `COLLECTOR_LOG` |
| mcp-server L416-417 PID/LOG | `data/mcp-server.{pid,log}` | `cache/pids/llm-radar-mcp-server.pid` + `cache/logs/llm-radar-mcp-server/mcp-server.log` |

- fetch 写盘 mkdir：L999 `self.fetch_cache_path.parent.mkdir(parents=True)` 自建 `cache/llm-radar-collector/`。
- 数据写盘 mkdir 保留：L1604 `self.data_dir.mkdir(parents=True)` — snapshot 仍写 data/，正确区分「真实数据」与「运行时产物」。
- `crontab_add` L2397 `COLLECTOR_LOG.parent.mkdir(parents=True)` — 安装 cron 时自建日志目录。
- mcp-server L418-419 `CACHE_PIDS_DIR/CACHE_LOGS_DIR.mkdir(parents=True)`；snapshot 保持 data/（L56-58 / L234-235）。
- diff 仅路径段 + docstring，零采集逻辑/数据格式改动。

### 2. 现行引用零残留 — ✅

- `grep -rn 'data/\(collector\|twitter\|mcp-server\)\.log\|data/fetch-cache' --include='*.py' --include='*.sh'` → **0 命中**。
- AGENTS.md L15/L58 ✅、README.md L89-98 ✅、skills/x-twitter-collector/SKILL.md L88 cron ✅ 均已同步到 cache/ 路径。
- `.gitignore` L20 `cache/` 覆盖全部新运行时路径（`git check-ignore` 确认 3 文件被忽略）。
- 🟢 OBS-1：`.gitignore` 过期条目（L2 `data/fetch-cache.json` / L5 `data/*.log` / L6 `data/*.pid` / L10 `data/collector.log`）未清理 — 无害（cache/ 已覆盖），建议后续 cleanup。

### 3. 运行时文件存在性 — ✅

| 路径 | 状态 |
|:-----|:----:|
| `cache/logs/llm-radar-collector/collector.log` | ✅ |
| `cache/logs/twitter-collector/twitter.log` | ✅ |
| `cache/logs/llm-radar-mcp-server/mcp-server.log` | ✅ |
| `cache/llm-radar-collector/fetch-cache.json` | ✅ |
| `cache/pids/` | 空（mcp-server 未运行，pid 为生命周期文件，非阻塞） |
| `data/` 下 `.log` / `.pid` / `fetch-cache` | **0** ✅ |

### 4. 测试 — ✅

- conda py3.12：`pytest --ignore=tests/test_selenium.py` → **263 passed + 2 skipped，0 failed**（234s）。
- 2 skipped = `test_html TestSeleniumPageLoad`（selenium 未装于 py3.12 env，`pytest.skip` 自跳过）。
- 高于 dev 自报 242（测试套件已增长），结论一致全绿。

### 5. git 卫生 — ✅

- `ls-remote` ground truth：origin/main = `6903089`；local HEAD = `7006ee2`（ahead 1 / behind 0）。
- `7006ee2` 只含 AGENTS.md（3 行改动）。
- auto-converge 3 笔（`a22c0aa` auto-push → `a7f7ccb` merge → `6903089` auto-push）正确插入 `7e7e41d` 之上；f9928eb/7e7e41d 为 ancestor，已在 origin。
- 工作区 clean（pytest 写脏数据文件已 `git checkout --` 还原）。

### 6. 外部协调 — 🟢 已声明（非阻塞）

- daily-checker：`checkpoints/10-llm-radar.sh` 用 `lr status --json`（读 snapshot/git 状态，不 tail collector.log）— 迁移不影响 heal 判定。
- 🟢 OBS-2：远端 59.110.66.1 需重部署 — `documents/ops/linux-deployment-v1.0-20260701.md:130` 仍 `tail -f data/collector.log`（历史 ops 文档，按任务范围不追改）；远端 cron + log-tail 需同步到 cache/ 新路径。

## 发现

| # | Severity | Title | Status |
|---|:--------:|-------|:------:|
| OBS-1 | 🟢 | `.gitignore` 过期条目（`data/fetch-cache.json` / `data/collector.log` / `data/*.log` / `data/*.pid`）未清理 | 注记（cache/ 已覆盖） |
| OBS-2 | 🟢 | 远端 59.110.66.1 需重部署（`tail -f data/collector.log` 旧路径） | 外部协调已声明 |

## 评分

Base 100；🟢 记录 only（×0）→ **100/100 (A) → PASS**
