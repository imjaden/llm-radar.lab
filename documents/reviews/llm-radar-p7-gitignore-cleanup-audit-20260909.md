# llm-radar P7 gitignore 清理 + integ 指针审计

- **日期**: 2026-09-09
- **Reviewer**: Security Reviewer (review profile)
- **Level**: L2
- **Scope**: 1 commit — d113aee chore@cleanup（本地 main，未 push）
- **Verdict**: ✅ PASS — 100/100 (A)
- **findings**: 0（runtime-files 审计 OBS-1 ✅ 关闭）

## 背景

承接 cli-runtime-files 运行时迁移审计（2026-09-08）OBS-1「gitignore 过期条目」：data/ 运行时
文件迁至 cache/ 后，.gitignore 仍残留 4 条 data/ 过期忽略。dev commit d113aee 清理这 4 条，
并修正 integ 文档 2 处 MCP 协议设计文档旧指针（缺 `mcp/` 路径段）。本审计逐项验证清理正确性。

## 审计项核验

| # | 项 | 结果 |
|---|----|------|
| 1 | 移除 4 条 data/ 过期行正确；保留 data/history\|archive\|metrics\|dead-letter 有据 | ✅ |
| 2 | cache/ 整目录忽略存在（无需重复）；check-ignore 抽查 cache 文件 ignored + 保留 data 规则命中 | ✅ |
| 3 | integ 指针：documents/mcp/mcp-protocol-design-v1.0-20260623.md 存在；旧指针零残留 | ✅ |
| 4 | 工作树 clean；commit 仅 2 文件，无 -A 混入 | ✅ |
| 5 | review-log/.review-level 登记 + push origin main（ls-remote 核验） | ✅ |

## 数据验证要点

- **移除 4 条逐条实证（均过期）**：
  - `data/fetch-cache.json` → 全仓 grep 0 引用（运行时已迁 cache/）
  - `data/*.log` → 被更广 `*.log`（.gitignore L35）覆盖；代码日志写 cache/logs/，非 data/
  - `data/*.pid` → 0 data/ pid 写入；mcp-server 写 cache/pids/、twitter 写 cache/twitter-profile/.collector.lock
  - `data/collector.log` → 被 `*.log` 覆盖；全仓 0 引用
- **保留 4 条逐行实证（均有活跃写入，llm-radar-collector.py）**：
  - `data/history/` ← L1676 `history_dir = self.data_dir / 'history'`（_archive_snapshot 周快照）
  - `data/archive/` ← L1686 `archive_dir = self.data_dir / 'archive'`（_archive_items 过期实体归档）
  - `data/metrics.json` ← L964 / L1714 / L1957 / L2363
  - `data/dead-letter.json` ← L346 `dead_path = self.data_dir / 'dead-letter.json'`
- **git check-ignore 实证**：cache/、cache/logs、cache/pids、cache/foo.json 全 ignored；
  data/history/、data/history/x.json、data/archive/、data/archive/y.json、data/metrics.json、
  data/dead-letter.json 全命中保留规则；`check-ignore -v` 确认 data/collector.log、data/foo.log
  由 L35 `*.log` 宽规则覆盖（移除 data/ 专属行无回归）。
- **integ 指针**：`documents/mcp/mcp-protocol-design-v1.0-20260623.md` 存在（6980 bytes）；
  `grep 'documents/mcp-protocol-design-'`（旧形，缺 `mcp/` 段）零命中；新指针 3 处（README L157、
  integ L269/L306）一致。
- **git 卫生**：`git show d113aee --stat` 仅 .gitignore（-4 行）+ integ 文档（2 改 2 增）；
  worktree clean（`nothing to commit`）。

## 结论

无阻塞项。4 条 data/ 过期忽略行移除正确（2 条被 `*.log` 宽规则覆盖、2 条运行时已迁 cache/ 零引用），
保留 4 条均有活跃写入，cache/ 整目录忽略兜底充分；integ 指针改对且旧指针零残留；git 卫生干净。
**PASS — 100/100 (A)**，可 push。runtime-files 审计 OBS-1「gitignore 过期条目」✅ 本 commit 关闭。
