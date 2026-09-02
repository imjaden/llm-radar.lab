# LLM-RADAR-CL005 wrapper env 修复 — 补充审计报告 v1.0

> 日期: 2026-09-02
> 待审 commit: 07baf8f `fix@llm-radar: add conda_sh/brew_prefix to cli-registry (LLM-RADAR-CL005 wrapper env)` (ahead 1, 未 push)
> 前置: 423eac7 `audit@review: impl audit (LLM-RADAR-CL005)` — CL005 主闭环已 push
> review者: review/llm-radar-cl005-wrapper-env-fix-audit (hermes-1.2.0)
> review维度: 最小性 / 可复现性 / 安全 / 一致性 / 无遗漏 / 无回退 (6 维, 100-base)

## 结论摘要

补充修复正确、最小、已实测生效。`lr status` 在干净 env (cron 等价) 下解析到 py3.12 (3.12.13),
NotOpenSSLWarning 归零; 根因 (旧 wrapper CONDA_SH 空 → 回退 `/Caskroom/...` 缺 /opt/homebrew 前缀 →
conda 未激活 → python3 回落 3.9/LibreSSL) 已闭环。审计在点 5 (无遗漏) 范围内新发现 1 🔴 (预存,
gitignored, 非本 commit 引入, 未入 git/未泄漏) 已就地清除; 2 🟡 遗留 (非阻塞)。

**评分: 95 / 100 (A) → ✅ PASS。** 审计为 push 执行者, PASS 后 commit + push。

## 验收逐项 (审计要点 1-6)

| # | 审计要点 | 方法 (锚点/实测) | 结果 |
|:--|:--|:--|:--:|
| 1 | .cli-registry.yaml 最小且正确 (仅 2 行 env) | `git show 07baf8f` diff 仅 +2 行 `conda_sh`/`brew_prefix`; 两路径 `ls` 均存在 (`/opt/homebrew` + conda.sh) | ✅ |
| 2 | wrapper 可复现 (install.py / 模板占位符) | install.py L124-125 填充 `{{conda_sh}}`/`{{brew_prefix}}`; 手工复刻模板填充 vs 实际 wrapper diff 仅多 .env 4 行 | 🟡 (conda 可复现, .env 不可复现 → GOV-1) |
| 3 | .env 加载段必要且安全 (不打印 key) | wrapper L78-80 `set -a && source .env && set +a` 无 echo; collector L179 `os.environ.get('DEEPSEEK_API_KEY')` 不自载 .env → 必要 | ✅ |
| 4 | symlink 指向一致 | `~/.local/bin/{lr,llm-radar}` 均 → `cache/system-command/llm-radar-wrapper.sh` | ✅ |
| 5 | 无遗漏 (旧 lr-wrapper.sh 引用 / gitignored 产物影响面) | grep 无代码引用旧 lr-wrapper.sh; 发现 `cache/cli-registry/wrapper.sh.tmpl` 与 .env 同 sha256 (SEC-1) + orphan `lr-wrapper.sh` (HYG-1) | 🟡 |
| 6 | 不影响 CL005 已审计范围 | diff 仅 .cli-registry.yaml env 段, 无任何 CL005 代码/测试回退 | ✅ |

## 根因与实测

- 根因: 旧 `lr-wrapper.sh` L50-52 `CONDA_SH=""` → 回退 `/Caskroom/miniconda/...` (缺 /opt/homebrew 前缀)
  → conda.sh 不存在 → conda 未激活 → python3 回落 `/usr/bin/python3` 3.9.6 (LibreSSL 2.8.3)
  → urllib3 v2 NotOpenSSLWarning (collector L35 顶层 `import requests` → 任何子命令含 `status` 均触发)。
- 实测 1 (3.9 触发复现根因): `/usr/bin/python3 /tmp/llmradar_warn_check.py` → NotOpenSSLWarning (LibreSSL 2.8.3)。✅
- 实测 2 (py3.12 无告警): `/opt/homebrew/Caskroom/miniconda/base/envs/py3.12/bin/python3` 同脚本 → 无 warning。✅
- 实测 3 (修复后干净 env): `env -i PATH=... HOME=$HOME bash -c 'lr status'` → exit 0, py3.12 (3.12.13), `grep -c NotOpenSSLWarning` = 0。✅
- 实测 4 (交互 shell): `lr status` → exit 0, 0 warning。✅

## 发现项

| # | Severity | Title | 说明 | 处置 |
|:-:|:--------:|:------|:-----|:-----|
| SEC-1 | 🔴 | `cache/cli-registry/wrapper.sh.tmpl` 与 .env 字节相同 (含 live DEEPSEEK_API_KEY) | 预存 (mtime 08-24), gitignored 未入 git/未泄漏; 但 AGENTS.md L52 称其为「wrapper fork 模板」, 实为误 cp 的密钥副本 | ✅ 审计中删除 (cache/cli-registry/ 已空) |
| GOV-1 | 🟡 | wrapper .env 加载段为手工 patch, `install.py --force` 再生成即丢失 | hermes-manager 模板 `templates/wrapper.sh.tmpl` 无 .env 段; install.py 仅 6 处字符串替换; 复刻填充 diff 确认仅 .env 4 行为手工 | ⏳ 后续 (P2) |
| HYG-1 | 🟡 | orphan `cache/system-command/lr-wrapper.sh` (旧坏 wrapper, CONDA_SH 空) 仍存在 | 无 symlink 指向, gitignored, 死文件 | ⏳ 后续 (P3, 可删) |

## 维度评估

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 最小性 | 🟢 | diff 仅 2 行 env, 无越界改动 |
| 可复现性 | 🟡 | conda/brew 占位符经 install.py 可复现; .env 段不可复现 (GOV-1) |
| 安全 | 🟢 | .env 加载不打印 key; diff 无密钥; 清除 SEC-1 密钥副本 (未泄漏) |
| 一致性 | 🟢 | lr/llm-radar 同 wrapper; 与 daily-checker/hermes-manager 配置形态对齐 |
| 无遗漏 | 🟡 | orphan lr-wrapper.sh 未清 (HYG-1); SEC-1 已清 |
| 无回退 | 🟢 | CL005 范围零回退 |

## 评分明细

```
基准分: 100
  点1 最小性      ✅   0
  点2 可复现性    🟡  -3  (conda 可复现, .env 不可复现 → GOV-1)
  点3 安全        ✅   0   (不打印 key; SEC-1 为预存/非本 commit, 审计中已清)
  点4 一致性      ✅   0
  点5 无遗漏      🟡  -2  (orphan lr-wrapper.sh → HYG-1)
  点6 无回退      ✅   0
────────────────────────
得分: 95 → A → ✅ PASS
```

## 结论

**✅ PASS — 95/100 (A)。** 核心修复 (conda_sh/brew_prefix) 正确最小, 根因经 4 项实测闭环,
NotOpenSSLWarning 归零; 无 CL005 回退; push 无密钥泄漏 (SEC-1 为 gitignored 预存文件, 不入 commit)。
新发现 1 🔴 已在审计中就地清除; 2 🟡 遗留 (GOV-1/HYG-1) 不阻塞 push。

## 后续 (遗留, 不阻塞)

- GOV-1 (P2): 让 wrapper .env 加载段可复现。二选一: (a) hermes-manager install.py 支持项目级模板覆盖
  (读 `cache/cli-registry/wrapper.sh.tmpl`); (b) AGENTS.md 记录「install.py --force 后须手工补 .env 段」
  步骤。当前 wrapper 已含 .env 段, 功能不受影响; 仅在再生成时需注意。
- HYG-1 (P3): 删除 orphan `cache/system-command/lr-wrapper.sh`。
- AGENTS.md L52「wrapper fork 模板: cache/cli-registry/wrapper.sh.tmpl」现已失效 (文件已删且机制本未接入
  install.py), 建议随 GOV-1 一并修正 (protected 文件, 用户侧改)。

---

*报告: documents/reviews/llm-radar-cl005-wrapper-env-fix-audit-20260902.md | 结论: ✅ PASS 95/100 (A) | 点1/3/4/6 ✅ + 点2/5 🟡 + SEC-1 已清 | commit + push*
