# 部署收尾审计（conda_sh 对齐 + cron 实况注记）— 报告 v1.0

- **日期**: 2026-09-09
- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2
- **范围**: 2 commits — 843feb1 `fix@llm-radar: align conda_sh to Linux path` + c678e70 `docs@llm-radar: record actual remote cron schedule`
- **Verdict**: ✅ PASS — 100/100 (A)
- **findings_total**: 0 / **findings_open**: 0

## 结论

远端部署闭环收尾两笔本地小改：`.cli-registry.yaml` 将 conda_sh 对齐到 Linux 实况路径，
linux-deployment 文档补记远端 cron 实况差异留档。五条审计项全部通过，无安全发现，可推送。

## 审计项核验

| # | 审计项 | 结果 |
|---|--------|------|
| 1 | 843feb1 diff 仅 .cli-registry.yaml 1+/1-（conda_sh → /root/miniconda3）；env.conda=llm-radar 保持；无 -A | ✅ |
| 2 | c678e70 diff 仅 linux-deployment doc +4 行（第 6 节，第 5 节后 footer 前）；内容与源码实况一致 | ✅ |
| 3 | 影响面注记（记录不阻塞）：Mac wrapper 内嵌 conda 路径，运行时不读 .cli-registry.yaml → 不受影响 | ✅ |
| 4 | 工作树 clean；ahead 仅 2 commits（无 auto-converge 插入） | ✅ |
| 5 | 登记 review-log/.review-level + push origin main（ls-remote 核验） | ✅ |

## 逐项实证

### 1. 843feb1 — conda_sh 对齐

- `git show 843feb1 --stat`: ` .cli-registry.yaml | 2 +-`，1 file changed, 1 insertion(+), 1 deletion(-)。
- diff 仅 1 行：`conda_sh: /opt/homebrew/Caskroom/miniconda/base/etc/profile.d/conda.sh` → `conda_sh: /root/miniconda3/etc/profile.d/conda.sh`。
- `env.conda: llm-radar` 在 diff 上方，未改动（此前 f5579e3 已对齐）。无 -A 混入。

### 2. c678e70 — cron 实况注记

- `git show c678e70 --stat`: ` documents/ops/linux-deployment-v1.0-20260701.md | 4 ++++`，1 file changed, 4 insertions(+)，纯新增。
- 新增第 6 节位于第 5 节（L139 `## 6.` 之后第 5 节内容结束）与 footer（L144 `*版本: 1.0 | 创建: 2026-07-01*`）之间，结构正确。
- 注记「代码 CRON_SCHEDULE Linux 默认 0 7,14,21（collector L2389）」实证：`llm-radar-collector.py` L2389 = `CRON_SCHEDULE = '0 * * * *' if platform.system() == 'Darwin' else '0 7,14,21 * * *'` → 非 Darwin 默认 `0 7,14,21`，行号与值均准确。
- 注记「重定向 cache/logs/llm-radar-collector/collector.log」实证：`COLLECTOR_LOG` L63 = `CACHE_DIR / 'logs' / 'llm-radar-collector' / 'collector.log'`，即 `cache/logs/llm-radar-collector/collector.log`，与文档 L130 `tail -f` 引用同一路径，准确。
- 调度行为零改动：本 commit 为纯文档，不改 `CRON_SCHEDULE`/`crontab` 逻辑。

### 3. 影响面注记（OBS-1，记录不阻塞）

- `.cli-registry.yaml` 现为机器特定值（`conda: llm-radar` / `conda_sh: /root/miniconda3/...`）已入共享 origin。
- Mac 侧 `~/.local/bin/{lr,llm-radar}` 均为 symlink → `cache/system-command/llm-radar-wrapper.sh`（实测 `ls -la` 双软链一致）。
- wrapper `load_environment` 硬编码 Mac conda 路径：`CONDA_SH="/opt/homebrew/Caskroom/miniconda/base/etc/profile.d/conda.sh"` + `conda activate py3.12`，运行时不读 `.cli-registry.yaml` → Mac `lr` 当前不受本改动影响。
- `install.py` 仓库内不存在（find 空），为外部 cli-registry 工具组件；若未来 Mac 用该外部工具重生成 wrapper 且读 `.cli-registry.yaml`，会产出 Linux 路径 → 需以本地配置覆盖后再生成（非本批范围）。

### 4. 工作树 / ahead

- `git status`: nothing to commit, working tree clean。
- `git ls-remote origin main` = `306f0c1`（843feb1 的父）；`git rev-parse HEAD` = `c678e70` → ahead 2 / behind 0，无 auto-converge 插入。

### 5. 交付

- review-log.md 追加 PASS 条目；.review-level.yaml 追加 review_history 条目。
- push origin main 后 `git ls-remote` 核验。

## 结论

PASS — 100/100 (A)。配置对齐与文档留档均与源码实况一致，调度行为零改动，仅 1 条 🟢 影响面注记，可推送。
