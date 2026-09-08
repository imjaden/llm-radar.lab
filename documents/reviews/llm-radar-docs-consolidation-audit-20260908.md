# llm-radar docs-consolidation 审计 (P5 推广 #2)

- **日期**: 2026-09-08
- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2
- **Scope**: 3 docs commits（本地 main，未 push）— c572028 / d5e2405 / a439553
- **Verdict**: ✅ PASS — 100/100 (A)
- **findings**: 0（OBS-1~2 🟢 记录）

## 背景

P5 推广 #2 llm-radar docs-consolidation：phase-1 盘点（Q1-Q8 按推荐）→ phase-2 六手册草稿
（documents/handbooks/ ×6, 836 行）→ phase-3 归档 76 份 + README 重建 + Q3-Q7 修复。
本审计只针对 3 个 docs commit；auto-push 数据 commit（fd68662/7e2c3b5）已上 origin，不在范围。

## 审计项核验

| # | 项 | 结果 |
|---|----|------|
| 1 | 手册内容与实现一致（抽样 STALE_HOURS / CRON_SCHEDULE / twitter parse_args / 站点渲染） | ✅ |
| 2 | 归档 76 份（reviews 50 / solutions 14 / theme 12），R100 保历史，原位文件未动，无误移 | ✅ |
| 3 | 引用零残留（0 dangling；tasks/al-rename.sh L90 豁免合理性复核通过） | ✅ |
| 4 | Q3/Q4/Q5 修复（改名落 reviews 桶 + git- 段统一 / requirements-spec 行号剥离 / README 树+链接 / YAML parse） | ✅ |
| 5 | 测试无回归（266 passed 2 skipped 0 failed），脏数据文件已还原 worktree 干净 | ✅ |
| 6 | git 卫生（3 commits 各只含目标，无 auto-push 混入，无 -A） | ✅ |
| 7 | 安全面（纯文档/路径变更，源码仅注释） | ✅ |
| 8 | AGENTS.md 未擅改（protected） | ✅ |

## 数据验证要点

- **手册常量逐字实核**：STALE_HOURS = `int(os.environ.get('LLM_RADAR_STALE_HOURS','12'))`
  （collector L70 / health.py L38，双文件读同一 env）；CRON_SCHEDULE = `'0 * * * *' if Darwin else
  '0 7,14,21 * * *'`（collector L2389）；twitter `parse_args` L849-871（默认 collect / --collect /
  --login / --dry-run / --attach，退出码 0/1/2，未知/多余参数 → USAGE + exit 1）。手册引用行号
  与源码逐条一致。
- **frontmatter 合规**：6 份手册统一 `author: hermes-v0.20.6(2026.8.27)` / `profile: dev` /
  `type: summary` / `date: 2026-09-08`。
- **站点渲染行号逐条命中**（index.html 1333 行）：TABS L336 / EMOJI_M L597 / DIM_EM L598 /
  entEmoji L599 / hl L479 / he L480 / copyTweet L1133 —— 全部精确。
- **归档**：d5e2405 76 条 R100 rename = reviews 50 + solutions 14 + theme 12，与 documents/README.md
  口径一致；git show 全部 0 行改动（纯 rename 保历史）。原位 4 件未动：pipeline/data-flow、
  ops/linux-deployment、ops/github-ci-issues、根 emoji-mapping。documents/{reviews,solutions,
  loop,verify} 已清空，无他人文件误移。
- **引用零残留**：76 basename × 非 archive/非豁免面 = 86 命中，全部为 archive 上下文（更新后
  引用），0 dangling。Q3 旧名（fork-converge / cl005-fork-merge）仅存于「原 X → Y」改名注记，
  非悬空引用。al-rename.sh L90 豁免合理：一次性迁移脚本 `[ -f ]` 守卫幂等，源文件已改名归档，
  改操作数会伪造历史。
- **Q3-Q7**：git-flow-fix-impl 由 solutions 迁 reviews 桶（d5e2405）；cl005-fork-merge → cl005-git-
  fork-merge + 4 份 fork-converge → git-fork-converge 同批 a439553 完成（git- 段统一一次 commit）。
  requirements-spec 行号 token 0 残留（`N|` 前缀剥离）。README 目录树 + 链接重建（0 broken link）。
  .review-level.yaml `yaml.safe_load` 通过（46 条 entry）。
- **测试**：conda py3.12 独立复跑 `266 passed, 2 skipped, 0 failed`（108.83s）。2 skipped =
  2 个 `@pytest.mark.selenium`（test_html.py L308/L360，selenium 未装，稳定基线）。脏数据文件
  snapshot.json / overview.json / timestamp.json 已 `git checkout --` 还原，worktree clean（ahead 3）。
- **安全面**：c572028/d5e2405 纯文档 + rename；a439553 源码仅 2 处注释类改动（scripts/twitter-
  collector.py docstring 路径 + data/twitter-targets.yaml 注释路径），无逻辑/数据值改动。
- **AGENTS.md**：git log fd68662..a439553 -- AGENTS.md 为空，未擅改（protected）。

## 观察项（🟢 记录，不扣分）

| # | 观察 | 裁定 |
|---|------|------|
| OBS-1 | 简报称「242 passed 2 deselected」，实测「266 passed 2 skipped」—— dev 自报滞后（与 runtime-files 审计「dev 自报 242，套件增长」同源）；「deselected」实为「skipped」（2 个 selenium 用例） | 🟢 记录，无回归 |
| OBS-2 | review-log.md 末两条「报告」路径仍指 documents/reviews/（未随 docs@sync 改 archive），与 .review-level.yaml 已改路径不对称 | 🟢 记录（review 侧 append-only 历史条目，豁免面内） |

## 结论

无阻塞项。手册内容与实现逐字一致，归档 76 份保历史且引用零残留，Q3-Q7 修复正确，测试无回归，
git 卫生与安全面干净，AGENTS.md 未擅改。**PASS — 100/100 (A)**，可 push。
