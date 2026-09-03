# LLM Radar — review-log

> 作用: review运行日志。由 review profile 在审查后 append。
>
> 文件命名: 固定为 `review-log.md`，放项目根目录。
> 适用: 风格 B 文件（无版本号，持续 append），不可删除历史条目。

## 2026-08-10 — 治理规范审查 (5 commits)

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 5 个未 push commit — d0aee7f, 2652160, a0fcc67, b3ce8de, 7ab70b7
- **Tracking**: 无安全发现 (纯治理审查)
- **状态**: ⏳ CONDITIONAL PASS — 80/100 (B)
- **报告**: documents/reviews/llm-radar-governance-review-v1.0-20260810.md
- **实现 prompt**: ⬜ 无需生成 (非 PASS)

### 发现摘要

| # | Severity | Title | Status |
|---|----------|-------|--------|
| C-1 | 🟡 | b3ce8de `chore@project:` type 不在项目既定类型集 | Open |
| N-1 | 🟡 | features.md 前导 YAML 缺 type/version/date/author/tags | Open |
| N-2 | 🟡 | review-log.md 模板未定制 (本条为首个实际条目) | Fixed |
| A-1 | 🟡 | review-log 0 条目 vs .review-level.yaml 4 条目 gap | Open |

### 历史条目说明

.review-level.yaml 中有 4 条 review_history (2026-07-11 ~ 2026-07-13)，对应 LR-SEC-001 ~ LR-SEC-010。此 review-log.md 由 7ab70b7 初始化，历史条目未回填。详见 .review-level.yaml。

---

## 2026-08-10 — 治理规范审查 (2 commits)

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 2 个未 push commit — 0058fcb, 63de4b3
- **Tracking**: 无安全发现 (纯治理审查)
- **状态**: ✅ PASS — 100/100 (A)
- **报告**: documents/reviews/llm-radar-governance-review-v1.1-20260810.md
- **实现 prompt**: ✅ 已生成

### 发现摘要

无发现 — 2 个 commit 全部合规。data 管线刷新 + model 切换 fix。

### 实现 prompt

────────────────────────────────────────
  实现 prompt — review 待修正项 (v1.0)
────────────────────────────────────────

对 llm-radar 项目 ~/CodeSpace/llm-radar.jaden.tech 修正 v1.0 审查的 4 项待修正。

聚焦文件: v1.0 审查报告 (documents/reviews/llm-radar-governance-review-v1.0-20260810.md)

核心变更:
  1. b3ce8de `chore@project:` → `feat@project:` 或在 .review-level.yaml 添加 commit_types
  2. features.md 前导 YAML 补全 type/version/date/author/tags
  3. review-log.md 模板已定制（本条标记为 Fixed）
  4. review-log.md 回填 4 条历史条目或标注 "pre-template reviews"

实现文件:
  - features.md (补全前导 YAML)
  - .review-level.yaml (添加 commit_types enum 或修正 b3ce8de type)
  - review-log.md (回填历史条目)

参考:
  - 审查: documents/reviews/llm-radar-governance-review-v1.0-20260810.md
  - 审查: documents/reviews/llm-radar-governance-review-v1.1-20260810.md

产出:
  1. 按治理规范 commit规范提交
  2. 修正后通知 review profile 复查

---

## 2026-08-12 — git flow fix 设计评审 v1.1

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 设计文档 v1.1 + 2 个 commit — db8d792 (v1.0), 5254ea4 (v1.1)
- **Tracking**: REA-1, RIG-1, RIG-2, RIG-3
- **状态**: ✅ RESOLVED — 见 2026-08-12 re-review v1.2 (PASS 100/100)
- **报告**: documents/reviews/llm-radar-git-flow-fix-review-v1.0-20260812.md
- **实现 prompt**: ✅ 已生成 (v1.2 PASS)

### 发现摘要

| # | Severity | Title | Status |
|---|----------|-------|--------|
| REA-1 | 🟡 | D1 时序依赖 "本地优先→auto-push 收敛" 未显式标注 | ✅ Fixed (v1.2) |
| RIG-1 | 🟡 | checkout --theirs 对 untracked 文件未覆盖 | ✅ Fixed (v1.2) |
| RIG-2 | 🟡 | fetch 失败场景未覆盖 | ✅ Fixed (v1.2) |
| RIG-3 | 🟡 | 写盘函数调用时序未在文档中显式标注 | ✅ Fixed (v1.2) |

### 3D 评分

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 合理性 | 🟢 | 根因链完整, 方案对比充分, 确认项集成到位 |
| 严格性 | 🟡 | 3 个边界/时序遗漏 |
| 安全性 | 🟢 | subprocess list-form, force-with-lease, 0 注入面 |

---

## 2026-08-12 — git flow fix 设计复审 v1.2

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 设计文档 v1.2 + 1 个 commit — 117e382 (修复 v1.1 4 项 🟡)
- **Tracking**: REA-1/RIG-1/RIG-2/RIG-3 ✅ all fixed; O-1 🟢 (optional)
- **状态**: ✅ PASS — 100/100 (A)
- **报告**: documents/reviews/llm-radar-git-flow-fix-rereview-v1.2-20260812.md
- **实现 prompt**: ✅ 已生成

### 发现摘要

| # | Severity | Title | Status |
|---|----------|-------|--------|
| REA-1 | 🟡 | D1 时序标注 | ✅ Fixed — §D1 要点 + 底部调用顺序图 |
| RIG-1 | 🟡 | checkout --theirs untracked | ✅ Fixed — git ls-files 分叉 + os.remove |
| RIG-2 | 🟡 | fetch 失败 | ✅ Fixed — D1 步骤 1 新增 fetch 失败→warning |
| RIG-3 | 🟡 | 写盘时序 | ✅ Fixed — 底部 run() 调用顺序图 |
| O-1 | 🟢 | os.remove 原子性 | 建议实施时用 tempfile + rename |

---

## 2026-08-13 — git flow fix 实现审计 v1.0

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 实现 commit cb82792 + 实现报告 1464f80 + data 5e95ebd
- **Tracking**: 无安全发现; 2 🟢 (test_timestamp 日期 / handbook type enum)
- **状态**: ✅ PASS — 100/100 (A)
- **报告**: documents/reviews/llm-radar-git-flow-fix-impl-audit-v1.0-20260813.md
- **实现 prompt**: ⬜ 无需生成 (实现已完成)

### 发现摘要

| # | Severity | Title | Status |
|---|----------|-------|--------|
| D1 | ✅ | _sync_remote fetch+ff-only+分叉本地优先 | Verified |
| D2 | ✅ | _push_with_recovery rejected→rebase→force-lease→dead-letter | Verified |
| D3 | ✅ | _clean_conflict_file tracked/untracked 分叉 | Verified (test 覆盖) |
| D4 | ✅ | CRON_SCHEDULE Darwin 每小时 / Linux 7/14/21 | Verified |
| O-2 | 🟢 | test_timestamp.py 硬编码日期 (pre-existing) | Non-blocking |
| O-3 | 🟢 | handbook §2 type enum 缺 impl | Non-blocking |

### 测试

12/12 gitflow 单测 ✅; 全量 86 passed / 2 failed (pre-existing, 与本改动无关)

---

## 2026-08-13 — health probe 设计评审 v1.1

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 设计文档 v1.1 + 2 个 commit — 203c62a (v1.0), b6d7335 (v1.1)
- **Tracking**: REA-1, REA-2, RIG-1, RIG-2
- **状态**: ✅ RESOLVED — 见 2026-08-13 re-review v1.2 (PASS 100/100)
- **报告**: documents/reviews/llm-radar-health-probe-review-v1.0-20260813.md
- **实现 prompt**: ✅ 已生成 (v1.2 PASS)

### 发现摘要

| # | Severity | Title | Status |
|---|----------|-------|--------|
| REA-1 | 🟡 | B1 脚本路径 (~/.hermes) 与 C2 确认 (项目 scripts/) 矛盾 | ✅ Fixed (v1.2) |
| REA-2 | 🟡 | status==success 混入质量门禁语义 (待确认) | ✅ Fixed (v1.2) |
| RIG-1 | 🟡 | last_run_at 无时区后缀, 新鲜度计算歧义 | ✅ Fixed (v1.2) |
| RIG-2 | 🟡 | 探针 fetch 无 cache-busting, CDN 陈旧副本未覆盖 | ✅ Fixed (v1.2) |

### 数据验证要点

- 字段名 last_run_at/last_run_status/last_news_date 与 collector `_write_timestamp` schema 一致 ✅
- 线上实测 last_run_at=2026-07-13 (30 天陈旧), 探针需求真实存在
- last_run_at 为 `datetime.now().isoformat()` 无时区 — RIG-1 根因

---

## 2026-08-13 — health probe 设计复审 v1.2

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 设计文档 v1.2 + 1 个 commit — 81ddac2 (修复 v1.1 4 项 🟡)
- **Tracking**: REA-1/REA-2/RIG-1/RIG-2 ✅ all fixed; O-1/O-2 🟢 (optional)
- **状态**: ✅ PASS — 100/100 (A)
- **报告**: documents/reviews/llm-radar-health-probe-rereview-v1.2-20260813.md
- **实现 prompt**: ✅ 已生成

### 发现摘要

| # | Severity | Title | Status |
|---|----------|-------|--------|
| REA-1 | 🟡 | 脚本路径统一 scripts/ | ✅ Fixed — 0 残留 ~/.hermes |
| REA-2 | 🟡 | 告警语义分离 | ✅ Fixed — 新鲜度 exit1 / 质量 exit0 |
| RIG-1 | 🟡 | 时区契约 | ✅ Fixed — +08:00 显式声明 |
| RIG-2 | 🟡 | cache-busting | ✅ Fixed — ?t=<epoch> |
| O-1 | 🟢 | 三态 exit code 契约注释 | 实施时写入脚本注释 |
| O-2 | 🟢 | 时区假设固化 | 实施时脚本顶部注释 |

---

## 2026-08-15 — git flow fix v1.3 设计评审

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 设计文档 v1.3 + 1 个 commit — 3acce2b (补 D2 rebase 冲突后 force-with-lease 路径)
- **Tracking**: RIG-1
- **状态**: ✅ PASS — 95/100 (A)
- **报告**: documents/reviews/llm-radar-git-flow-fix-v1.3-review-v1.0-20260815.md
- **实现 prompt**: ✅ 已生成

### 发现摘要

| # | Severity | Title | Status |
|---|----------|-------|--------|
| RIG-1 | 🟡 | 数据覆盖语义低估 (并发覆盖对方新实体, 非仅旧数据) | Open (待文档澄清) |

### 3D 评分

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 合理性 | 🟢 | 根因代码级成立, force-with-lease 安全边界清晰 |
| 严格性 | 🟡 | 1 处数据覆盖语义低估 |
| 安全性 | 🟢 | --force-with-lease lease 保护, list-form, 0 注入面 |

### 根因验证

`_push_with_recovery()` else 分支 (collector.py:350-355) abort 后未尝试 force-with-lease, 直接 dead-letter — 与设计描述一致 ✅

---

## 2026-08-15 — git flow fix v1.3 re-review + 实现审计

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: RIG-1 修复 (a16e0d5) + 实现 (3d2c991) — force-with-lease path + 2 单测
- **Tracking**: RIG-1 ✅ fixed; A1/B1 ✅ 确认; 实现逐项 verified
- **状态**: ✅ PASS — 100/100 (A)
- **报告**: documents/reviews/llm-radar-git-flow-fix-v1.3-rereview-v1.1-20260815.md
- **实现 prompt**: ⬜ 无需生成 (实现已完成)

### 发现摘要

| # | Severity | Title | Status |
|---|----------|-------|--------|
| RIG-1 | 🟡 | 数据覆盖语义 | ✅ Fixed — 风险表改「临时丢失对方本轮新实体, 下轮重新合并」 |
| A | — | force-with-lease 用法 | ✅ A1 采用 |
| B | — | 测试覆盖 | ✅ B1 采用 |

### 实现验证

- else 分支 +7 行 force-with-lease 与设计逐项对应 ✅
- 14/14 单测通过 (12 原 + 2 新) ✅
- 无新安全发现 ✅

---

## 2026-08-23 — CLI 治理与全局注册设计 v1.0 (CL-SEC11)

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: documents/solutions/llm-radar-cli-governance-design-v1.0-20260823.md (commit a714a7c) — 设计评审 (合理性/严格性/安全性 + 治理合规)
- **Tracking**: REA-11, RIG-1~5 待修 (6 findings); GOV-1~6 合规
- **状态**: ⏳ CONDITIONAL PASS — 70/100 (B)
- **报告**: documents/reviews/llm-radar-cli-governance-review-v1.0-20260823.md
- **实现 prompt**: ⬜ 未生成 (非 PASS, 修复后重审)

### 发现摘要

| # | Severity | Title | Status |
|---|----------|-------|--------|
| REA-11 | 🟡 | §6 引用 mcp-server.py, 实际文件为 llm-radar-mcp-server.py | Open |
| RIG-1 | 🟡 | §4.4 48h 阈值"实施时二选一"未锁定 (STALE_HOURS*7=49h ≠ 48h 与 §4.2 表格矛盾) | Open |
| RIG-2 | 🟡 | wrapper .env 加载无实现路径 (install.py 模板不含 .env, collector 不读 .env) | Open |
| RIG-3 | 🟡 | cli-registry install.py 模板硬编码 script-miner calls.log 路径, 复用会写脏 | Open |
| RIG-4 | 🟡 | §6 测试隔离仅提示无方案 (temp_snapshot 不隔离 project_root, 08-15 污染源仍在) | Open |
| RIG-5 | 🟡 | §4.2 "连续失败 ≥3" 级别未明确 (全局 consecutive_fails vs source_health, qbitai=37 会永久 critical) | Open |

### 数据验证要点

- 现状评估全部属实: main() 1985-2101, 空入参 exit=1 (实测), help 平铺, 无 --json, 10 命令。
- checkpoint 协议与 dt-status 一致 (七字段/四态/icon emoji/message 无 emoji/shell action 用 cmd 字段)。
- STALE_HOURS=7 与 llm-radar-health.py:38 一致; _think force 绕过已内建 (1377-1379)。
- cli-registry 结构与 script-miner 先例一致, 但 wrapper.sh.tmpl 无 .env + script-miner 耦合。
- 无 🔴 安全发现: status 全只读, actions cmd 静态, help 拦截防误执行。

---

## 2026-08-23 — CLI 治理与全局注册设计 v1.1 re-review (CL-SEC11)

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: documents/solutions/llm-radar-cli-governance-design-v1.1-20260823.md (commit 7bd8f26) — 设计复审 (6 🟡 + 3 🟢 修复核验 + 新问题扫描)
- **Tracking**: REA-11, RIG-1~5, RIG-6/7/9 已修复 ✅; RIG-10 (新 🟡) 并入 impl prompt #5; O-2~O-5 🟢
- **状态**: ✅ PASS — 95/100 (A)
- **报告**: documents/reviews/llm-radar-cli-governance-rereview-v1.1-20260823.md
- **实现 prompt**: ✅ 已生成 (cache/review-prep/prompt-llm-radar-cli-governance-impl-20260823.md)

### 修复核验

| # | v1.0 问题 | v1.1 验证 |
|---|----------|---------|
| REA-11 | mcp-server.py 文件名 | ✅ L191 llm-radar-mcp-server.py, 无残留 |
| RIG-1 | 48h 二选一 | ✅ CRITICAL_HOURS=48 独立常量 (L139), 无二选一残留 |
| RIG-2 | .env 无实现路径 | ✅ fork 模板 + set -a source .env (L182-185) |
| RIG-3 | calls.log 模板耦合 | ⚠️ fork+移除 ✅; 但 install.py 无 --template → RIG-10 |
| RIG-4 | 测试隔离无方案 | ✅ fixture patch project_root + 预置 3 文件 (L194-200) |
| RIG-5 | 连续失败级别未明确 | ✅ 全局 run 级 consecutive_fails (L121,127-129) |
| RIG-6/7/9 | 🟢 三项 | ✅ 路径标注 / 不主动 fetch 语义 / §4.5 文本输出 |

### 新增发现

- 🟡 RIG-10: §5.2 "用 install.py --template 指向 fork 模板" — install.py 无此标志 (TEMPLATE 硬编码 install.py:20, main() 仅 --dry-run/--force/uninstall, 未知参数静默忽略 → 照字面执行会静默回用硬编码模板, calls.log 污染重现)。修法 ② 手工从 fork 模板生成 wrapper, 已并入 impl prompt 核心变更 #5。
- 🟢 RIG-8 残留: §4.1 示例数字仍为占位符未标注 (实测 stats 100/50/100/55/61)。
- 🟢 O-2: 页脚 L225 仍写 "版本: 1.0" (frontmatter 1.1)。
- 🟢 O-4: DATA_DIR/SNAPSHOT_PATH 为模块常量 (collector.py:43-45), status 读取须走 project_root 派生路径, fixture 防御性 patch data_dir/snapshot_path。
- 🟢 O-5: .cli-registry.yaml 示例 env.conda: py3.12 本 Mac 可用 (env 存在且含依赖); Linux 主机按 AGENTS.md 需改 conda `llm-radar` env。

### 数据验证要点

- 9 项修复逐项 grep/read 核验, 8.5/9 完全落地; 实测 conda py3.12 存在且含 openai/selenium/requests/bs4/prettytable。
- 验收标准 8 条可测; 命名 kebab-case / frontmatter v1.1 / commit 7bd8f26 docs@design 合规。

---

## 2026-08-23 — CLI 治理与全局注册实现审计 (CL-SEC11)

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 实施 commit 26219ba (feat@cli) 最终审计 — 实现 vs 设计 v1.1 一致性 + 测试质量 + 治理合规 + 安全性; 全量 pytest 复跑 120 passed
- **Tracking**: LR-SEC-011 (🟡) 1 项; LR-SEC-012/013/014 (🟢 确认项); O-1~O-5 🟢 观察
- **状态**: ✅ PASS — 95/100 (A)
- **报告**: documents/reviews/llm-radar-cli-governance-implementation-review-v1.0-20260823.md

### 审计结论

- 实现与设计 v1.1 一致性 C1~C11 全 ✅: 分组 help / 空入参 exit=0 / positional help 拦截 (实测 run help 0.24s 秒回) / status --json 七字段 / 四态评估 / 数据源全只读 / STALE_HOURS=7 + CRITICAL_HOURS=48 env 可配 (实测 override 生效) / .cli-registry.yaml 入 git / wrapper fork 模板去 calls.log + exec 前 .env (实测 wrapper L81-83)。
- 测试: tests/test_status.py 四态+边界+fixture 隔离 (patch project_root → tmp, 不触真实项目根), test_cli.py 拦截+空入参; 独立复跑 120 passed。
- 治理: commit type@scope 全合规, AGENTS.md 已更新, wrapper 生成物在 gitignored cache/。
- 安全: status 全只读 (rev-list 不 fetch, 测试断言), actions cmd 静态, user-level symlink 无提权面。

### 发现

| # | Severity | Title | Status |
|---|----------|-------|--------|
| LR-SEC-011 | 🟡 | `run --force help` 绕过 positional help 拦截 (help 非首位), 实测触发 run 流水线副作用 (git fetch + metrics 写入, 'help' 非合法源快速失败, 有界) | ✅ Closed (90b5aa5 全 args 扫描 + 2 测试, 实测拦截) |

### 数据验证要点

- 16 项全部实测/读取, 含 stdout 纯净性 (JSON 可 json.loads)、双命令 help/status 输出 diff 为空、敏感信息扫描 0 hits。
- pytest 写脏数据文件已 git checkout 还原; 唯一遗留 .hermes-project.yaml 修改为会话前既有, 不动。
- 待 push 实况: 仅 5830b5b + 26219ba 两个 ahead (prompt 所列 6 个中 4 个已在 origin/main)。

---

## 2026-08-23 — CLI 治理实现审计尾项复核 (CL-SEC11)

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 尾项复核 — 90b5aa5 fix@cli (LR-SEC-011), 59c8b92 docs@design (O-5); 独立实测 + pytest tests/test_cli.py 13 passed
- **Tracking**: LR-SEC-011 → Resolved; O-5 → Resolved; findings_open 0
- **状态**: ✅ PASS — 100/100 (A)
- **报告**: documents/reviews/llm-radar-cli-governance-recheck-v1.0-20260823.md

### 复核结论

- 90b5aa5: `any(a.upper()=='HELP' for a in args)` 全 args 扫描替换 `args[0]` 首位检查 (collector.py:2213-2220), 防 `run --force help` / `fetch qbitai help` 绕过; 拦截作用域仍限 fetch/run/commit/crontab 四子命令, 无扩大。
- 59c8b92: 设计 v1.1 §4.2 ok 行补 "严格小于; 恰 7h 判 ok, 实现 `> STALE_HOURS` 才 warning" — 与实现 collector.py:1845 (`age_hours > STALE_HOURS` → warning, `>` 非 `>=`) 一致, 恰 7h 保持 ok, 无 off-by-one。
- 实测: `run --force help` → stdout 仅"用法:" 一行, exit=0, 无采集副作用; `crontab --list` → exit=0 正常输出 cron 行。
- pytest tests/test_cli.py → 13 passed in 3.79s (原 11 + 新 2)。

### 发现

| # | Severity | Title | Status |
|---|----------|-------|--------|
| LR-SEC-011 | 🟡 | help 拦截仅检查 args[0], `run --force help` 可绕过 | ✅ Resolved (90b5aa5) |
| O-5 | 🟢 | 设计 §4.2 ok 行边界标注缺失 | ✅ Resolved (59c8b92) |

### 数据验证要点

- 全部独立实测: git show 两 commit diff / `run --force help` / `crontab --list` / 读 collector.py:1843-1846 边界逻辑 / pytest 13 passed。
- pytest 写脏数据文件为 test_timestamp 已知问题, 已还原, 非本次引入; .hermes-project.yaml 为会话前既有修改, 不动。

---

## 2026-08-23 — 收敛复核 + CL-SEC11 链批量审计 (13 commits, 9d88886→21b50c5)

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 双机分叉 rebase 收敛后的 13 个已 push commit — 收敛正确性 / CL-SEC11 8 步链完整性 / CLI 代码质量 / mcp-server 重构正确性 / commit 治理合规
- **Tracking**: LR-SEC-015/016 → ✅ Resolved (6b69de8/b55c8fb); LR-SEC-017 → 注记/Closed; findings_open 0
- **状态**: ✅ PASS — 90/100 (A); 尾项修复复核见 2026-08-23 recheck v1.1 (PASS 100/100)
- **报告**: documents/reviews/llm-radar-cli-governance-convergence-review-v1.0-20260823.md

### 结论摘要

- 收敛正确性 ✅: 13 commits 全为功能/文档/审计, 无本地旧数据 auto-push 混入; HEAD snapshot = 远端最新 21:02 (server=linux, 324 entities), isolation-test 0 hits; 148774b 被 skip 符合设计。
- CL-SEC11 链 ✅: 9d09745(设计)→3d38e18(修复)→b8ebbf2(复审)→f371d49(dev)→53608b4(核查)→3926f65(审计)→2f827ac+9897d6c(尾项)→77840ff(尾项复核) 全齐, 双轨记录完整。
- 代码质量 ✅: status 全只读四态评估, help 全 args 扫描拦截; pytest 32 (CLI) + 122 (全量非 selenium) passed。
- 重构 ⚠️: mcp-server → scripts/ 移动正确 (PROJECT_ROOT parent→parent.parent), 但遗漏 2 个消费者路径 → LR-SEC-015。

### 发现

| # | Severity | Title | Status |
|---|----------|-------|--------|
| LR-SEC-015 | 🟡 | mcp-server 重构遗漏: scripts/mcp_submit_update.py:13 + scripts/mcp-protocol-demo.py:44 仍指向项目根 | ✅ Resolved (6b69de8) |
| LR-SEC-016 | 🟡 | README.md:139 config 示例 + integ 文档 L230 路径未同步 scripts/ | ✅ Resolved (b55c8fb) |
| LR-SEC-017 | 🟢 | 审计记录 SHA 为 rebase 前 (90b5aa5/59c8b92/26219ba), 当前历史为 2f827ac/9897d6c/f371d49 | 注记/Closed (映射见 recheck v1.1) |

### 数据验证要点

- git rev-list origin/main...HEAD = 0/0; git log fec3c58..21b50c5 = 恰好 13。
- pytest tests/test_cli.py + tests/test_status.py = 32 passed; 全量非 selenium = 122 passed, 2 deselected。
- pytest 写脏数据文件已还原 (git checkout --), .hermes-project.yaml 为并发会话修改, 不动。

---

## 2026-08-23 — 收敛审计尾项复核 (LR-SEC-015/016/017, recheck v1.1)

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 收敛复核 (be7464d, PASS 90/A) 尾项修复复核 — 6b69de8 fix@cli (LR-SEC-015), b55c8fb docs@llm-radar (LR-SEC-016), LR-SEC-017 SHA 映射注记
- **Tracking**: LR-SEC-015 → ✅ Resolved; LR-SEC-016 → ✅ Resolved; LR-SEC-017 → 注记/Closed; findings_open 0
- **状态**: ✅ PASS — 100/100 (A)
- **报告**: documents/reviews/llm-radar-cli-governance-recheck-v1.1-20260823.md

### 复核结论

- **LR-SEC-015 ✅**: 两脚本路径补 `'scripts'` 段 — mcp_submit_update.py:13 `SERVER = str(_PROJECT_ROOT / 'scripts' / 'llm-radar-mcp-server.py')`, mcp-protocol-demo.py:44 同理 + L18 依赖注释同步。复算解析为项目根/scripts/llm-radar-mcp-server.py 且文件存在 (30KB); Popen (demo:191-192) 用 `str(MCP_SERVER)` 变量非裸文件名; py_compile 3 脚本 OK; scripts/ + tests/ 全量 grep 0 残留根路径引用。
- **LR-SEC-016 ✅**: 2 文件 5 处 — README.md:139 config 示例补 `scripts/`; integ 文档 L230/L239/L266/L304 共 4 处。残留裸引用仅 documents/archive/ (历史修复计划, 不改写) + documents/reviews/ (审计记录本身) + requirements-spec.md:38 文件名提及 (非路径消费者)。
- **LR-SEC-017 注记**: SHA 映射逐条验证 — 90b5aa5→2f827ac (fix@cli help 全 args 扫描), 59c8b92→9897d6c (docs@design O-5 边界标注), 26219ba→f371d49 (feat@cli 全局注册), 提交信息匹配无歧义。按 append-only 原则不改写历史条目, 仅注记。

### 发现

| # | Severity | Title | Status |
|---|----------|-------|--------|
| LR-SEC-015 | 🟡 | mcp-server 重构消费者断链 | ✅ Resolved (6b69de8) |
| LR-SEC-016 | 🟡 | 文档路径未同步 scripts/ | ✅ Resolved (b55c8fb) |
| LR-SEC-017 | 🟢 | 审计记录 SHA 为 rebase 前 | 注记/Closed |

### 数据验证要点

- git show 两 commit diff / Python 复算路径解析 / grep 残留扫描 / git log 对照 SHA 映射 / pytest tests/test_security.py + tests/test_gitflow.py = 19 passed (test_security 直接覆盖 mcp_server 路径 3 处)。
- 待 push 实况: git log origin/main..HEAD = 恰好 6b69de8 + b55c8fb 两个。
- pytest 写脏数据文件为 test_timestamp 已知问题, 已还原; .hermes-project.yaml 为会话前既有修改, 不动。

---

## 2026-08-23 — 目录改名旧路径清理审计 (4d7095b/ae05a70/1d8699c)

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 3 个未 push commit — 4d7095b fix@llm-radar (5 文件路径修正), ae05a70 docs@llm-radar (handoff/README/data-flow + 旧命名归档 rename), 1d8699c chore@project (.hermes-project.yaml 命名规范)
- **Tracking**: LR-SEC-018 (commit subject 语义) + LR-SEC-019 (handoff 文件名命名漂移), 均 🟢 注记; findings_open 0
- **状态**: ✅ PASS — 100/100 (A)
- **报告**: documents/reviews/llm-radar-path-refs-review-v1.0-20260823.md
- **实现 prompt**: ✅ 无需生成 (纯路径清理, 无新功能)

### 发现

| # | Severity | Title | Status |
|---|----------|-------|--------|
| LR-SEC-018 | 🟢 | 1d8699c subject "fix handoff doc pointer" 描述的动作不在 diff (指针自 530f875 即 lab-review); 实际变更 = 命名去 .lab 化 + updated_at | 注记 |
| LR-SEC-019 | 🟢 | session title (llm-radar-*) 与 handoff 文件名 (handoff-llm-radar.lab-*) 命名漂移, 无功能影响 | 注记 |

### 数据验证要点

- 活跃层 grep `llm-radar.jaden.tech` + 变体 `llm-radar[\.-]jaden` (排除 reviews/archive/mcp/ops/integ/loop/cache/audit-log/review-log/logs/data-*.log/pyc) = 0 文本命中; tests/*.py 源码 0 命中; 仅 gitignored 运行时产物 (pyc/collector.log/mcp-server.log) 含旧路径, 非源码残留。
- al-scanner.py:93 与 agents-teamwork.yaml:3 聚合常量一致 (`llm-radar`); index.html:788 复制命令 cd 路径 = llm-radar.lab 与现目录一致。
- CNAME = llm-radar.lab.jaden.tech, 活跃层域名引用全部为现域名 (prompt 背景"域名不变"已过时, 代码侧无矛盾)。
- pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py = 109 passed, 2 deselected, 0 failed; 测试污染 (snapshot/overview/timestamp) 已 git checkout 还原, 工作区 clean。
- git log origin/main..HEAD 复核 = 恰好 3 commit, 与 prompt 一致。




---

## 2026-08-25 — X热点采集与分栏详情设计评审 (CL-SEC19)

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 设计 v1.0 (29045ed docs@design) — 采集器 (scripts/twitter-collector.py) / 数据 schema (data/twitter.json) / 前端 X热点 tab + 分栏详情 / crontab 并列 / 测试验收; 决策 Q1-Q11 + D1-D6 锁定
- **Tracking**: SEC-1 🔴, REA-1/REA-2, RIG-1/RIG-2 待修 (设计 v1.0, CL-SEC19); findings_open 5
- **状态**: ⏳ CONDITIONAL PASS — 70/100 (B)
- **报告**: documents/reviews/x-hotspot-review-v1.0-20260825.md
- **实现 prompt**: 未生成 (🔴 SEC-1 阻塞, ops 修后 bump v1.1 重审)

### 结论摘要

架构方向正确、决策闭环完整、采集方案可行 (36h 窗口 × 2/day cadence 匹配, 单轮失败被次轮覆盖; Selenium 登录态方案标准可行; 选择器多级 fallback 充分)。阻塞项为 🔴 SEC-1: 推文文本 (攻击者直接可控数据类) 经 innerHTML 直插渲染, 设计未指定输出编码, 现有 index.html 亦无 escape helper → stored XSS。另 4 🟡: REA-1 入库链路未闭环 (twitter-collector 无 commit/push, 仅靠主采集 git add -A 顺带, 质量门禁失败时 Pages 无限期陈旧); REA-2 cadence 前提与实况不符 (实测主采集每小时, 设计称每日 2 次) + 同刻并发 (双 Chrome + git add 竞争); RIG-1 部分成功语义与 last_error 持久化矛盾; RIG-2 CLI 签名未定义 (--login/--collect/默认模式矛盾)。

### 发现

| # | Severity | Title | Status |
|---|----------|-------|--------|
| SEC-1 | 🔴 | X热点渲染路径未指定输出编码 (推文 innerHTML → stored XSS); 现有前端无 escape helper | 待修 v1.1 |
| REA-1 | 🟡 | twitter.json 入库链路未闭环 ("同 snapshot.json 机制"不成立) | 待修 v1.1 |
| REA-2 | 🟡 | cadence 前提与实况不符 (主采集实测 hourly) + 同刻 :00 并发 | 待修 v1.1 |
| RIG-1 | 🟡 | 部分成功语义 + last_error 持久化矛盾 | 待修 v1.1 |
| RIG-2 | 🟡 | CLI 签名未定义 (--login/--collect/默认模式) | 待修 v1.1 |

### 数据验证要点

- 全部独立验证: git log 29045ed / crontab -l (主采集 hourly `0 * * * *`) / collector.py:2048 CRON_SCHEDULE + 371-429 auto-push (git add -A, partial 仅 timestamp.json) / index.html grep escape helper = 0 命中 (renderHotspotPanel L732-737 innerHTML 直插) / .gitignore (cache/ + data/*.log 覆盖) / scripts/ 5 个独立脚本先例 / country filter Han 检测 L296-298 / 36h×12h cadence 覆盖计算。
- 未修改任何项目文件 (只读审查); 报告 + review-log + .review-level.yaml 三件产物待 ops 统一处理 commit (本评审不 push)。

---

## 2026-08-26 — X热点设计复审 v1.1 (CL-SEC19)

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 设计 v1.1 (7238949 docs@design) — 复审 v1.0 的 5 修正项 (SEC-1/REA-1/REA-2/RIG-1/RIG-2) + 3 观察项 (O-1/O-4/O-6) 修复核验 + 新问题扫描
- **Tracking**: SEC-1/REA-1/REA-2/RIG-1/RIG-2 ✅ all fixed; O-1/O-4/O-6 ✅; O-7/O-10 顺带解决; X-REV-1~3 🟢 观察; v1.0 余项 O-2/3/5/8/9/11/12/13 挂账 (不阻塞); findings_open 0
- **状态**: ✅ PASS — 100/100 (A)
- **报告**: documents/reviews/x-hotspot-rereview-v1.1-20260826.md
- **实现 prompt**: ✅ 已生成 (cache/review-prep/prompt-x-hotspot-impl-20260826.md)

### 修复核验

| # | v1.0 问题 | v1.1 验证 |
|:--|:----------|:---------|
| SEC-1 | 🔴 XSS 输出编码 | ✅ §5.2 esc() 字符集 `& < > " ' \` `; §5.3 URL 白名单+noopener+图片二次校验; §5.4 src https 前缀 |
| REA-1 | 🟡 入库链路未闭环 | ✅ §4/§6 采集器自带 commit+push (auto-push@llm-radar: update twitter), push 失败记 last_error 不轰炸 |
| REA-2 | 🟡 cadence 实况+同刻并发 | ✅ Q6/§3.6 独立选择非"同 cadence", 主采集实测每小时已注明; cron `20 9,21` 错峰 |
| RIG-1 | 🟡 部分成功语义 | ✅ §3.5 四场景表 (全成功/部分成功/全失败/登录失效) 无矛盾, last_error 写盘条件显式 |
| RIG-2 | 🟡 CLI 签名 | ✅ §3.2 默认 collect / --collect / --login / --dry-run + 退出码 0/1/2 + 未知参数 exit 1 |
| O-1 | 时区混用 | ✅ 全 Z, grep +08:00 = 0 |
| O-4 | 缺退出码用例 | ✅ §7.1 exit-2 登录墙/挑战/全失败/部分成功用例 |
| O-6 | country filter 语义 | ✅ X tab 国家 chips 隐藏/置灰, 仅源 chips 生效 |

### 新增发现 (🟢, 不阻塞)

- X-REV-1: §3.6 "9:21 与 21:21" 表述残留 vs cron `20 9,21` (09:20/21:20) — 建议改 "9:20 与 21:20"。
- X-REV-2: push 失败 last_error 写入时机未定义 (写盘后 push 失败) + git add 范围未限定 — 实现时限定 data/twitter.json。
- X-REV-3: AGENTS.md 依赖清单未声明 PyYAML (环境已装, 无运行缺口)。

### 数据验证要点

- git show --stat 7238949: 设计 rename + 126 行实改 (修复声明均有正文支撑, 非仅追加); e4c22cb docs@review 记录两件套。
- 全部 8 项修复逐条读设计文档核验; grep +08:00 = 0; grep yaml → 仅 tasks/al-scanner.py 在用 PyYAML; .gitignore 覆盖 cache/ + data/*.log, twitter.json 不入 ignore。
- 复审执行日期 2026-08-26 (prompt 中 20260825 为设计文档日期, 报告文件名按实际执行日命名)。
- 未 commit / 未 push (1A 约束, commit 由 ops 处理); 本评审仅新增报告 + review-log + .review-level.yaml 三件 + cache/review-prep/ 实现 prompt。

---

## 2026-08-26 — X热点实现审计 v1.0 (CL-SEC19 闭环)

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 实现 commit 04b7866→23e3401 (11 CL-SEC19 + 2 auto-push 交错) — 采集器/前端/测试/AGENTS.md/cron 包装脚本 vs 设计 v1.1 一致性 + 测试质量 + 治理合规 + 安全性 + 运维闭环
- **Tracking**: 无 🔴🟡; IMPL-OBS-1~3 🟢 注记; 注记项 Q5(5A→--attach)/Chrome151/D1A/D4 已确认
- **状态**: ✅ PASS — 100/100 (A)
- **报告**: documents/reviews/x-hotspot-impl-audit-v1.0-20260826.md
- **实现 prompt**: ⬜ 无需生成 (实现已完成, 闭环)

### 审计结论

- 一致性 ✅: CLI 签名 (默认/--collect/--login/--dry-run + --attach 注记) / 退出码四场景 / schema UTC Z / esc() 转义 + 既有渲染点回填 / 分栏 + 抽屉 / chips / crontab 全落地。
- 测试 ✅: test_twitter_collector.py (配置/36h 容差/去重截断/DOM/写盘/退出码映射/O-12) + test_html.py TestXHotspotFrontend (11 断言); 复跑 184 passed。
- 治理 ✅: commit type@scope 合规; AGENTS.md 补 PyYAML (X-REV-3); §3.6 改 9:20/21:20 (X-REV-1); console 前缀/CSS 无引号。
- 安全 ✅: esc() 全字段 + textContent + URL/https 白名单 + CSP img-src; 无敏感入库 (git ls-files 0 命中); profile 登录态 gitignored; subprocess list-form。
- 运维 ✅: cron 包装 D1A 自动拉起; ProfileLock 互斥 (O-5); 原子写盘 + 去重幂等; git add 限定 twitter.json (X-REV-2); D4 attach 友好提示。

### 发现 (🟢, 不扣分)

| # | Severity | Title | Status |
|---|----------|-------|--------|
| IMPL-OBS-1 | 🟢 | prompt 所列 commit SHA 与仓库不符 (subjects 1:1 匹配, rebase 前记录残留, 同 LR-SEC-017 类) | 注记 |
| IMPL-OBS-2 | 🟢 | 指标字段 num() 直通未 esc() (int 类型保证, 非攻击者可控; 文本已全 esc) | 注记 |
| IMPL-OBS-3 | 🟢 | 图片 src 前端仅 https:// 前缀校验 (CSP img-src 为权威白名单, 三层闭合无风险) | 注记 |

### 数据验证要点

- git rev-parse HEAD origin/main = 6219fe1 双端一致, status clean; 实现 commit 全部已推送 (prompt "origin 0/0" 属实)。
- pytest 184 passed 复跑; 测试污染 (snapshot/overview/timestamp) 已 git checkout 还原。
- --attach 引入点 git log -S = 275918d (混入"首屏先抓再滚动" fix commit, 注记确认可接受)。
- 遗留注记项: O-9 (健康度入 metrics.json, 后续迭代), O-13 (主采集 cron 指向核对, ops 侧)。

---

## 2026-08-26 — X热点设计 v1.2 评审 (CL-SEC20)

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 设计 v1.2 (82d8d1a docs@design) — CL-SEC20 增强 5 项 (配置迁移 data/ 账号 1→10 / forward 字段 / 条数窗口 30+24h / 全站搜索 Cmd+F / 采集时长 5-8min); 继承 v1.1 机制核验
- **Tracking**: REA-1, RIG-1/RIG-2, SEC-1 (🟡 待修, findings_open 4); O-1~O-5 🟢 观察
- **状态**: ✅ RESOLVED — 见 2026-08-26 re-review v1.3 (PASS 100/100)
- **报告**: documents/reviews/x-hotspot-review-v1.2-20260826.md
- **实现 prompt**: ⬜ 未生成 (非 PASS, 待 ops 修 4 🟡 bump v1.3 重审)

### 发现摘要

| # | Severity | 维度 | Title | Status |
|:-:|:--------:|:----:|-------|--------|
| REA-1 | 🟡 | 合理性 | D1 条数窗口回填语义 §3.4 ("取最近 30") vs §7.1 ("补足到 30") 矛盾 | 待修 |
| RIG-1 | 🟡 | 严格性 | window_hours→retention 影响未完整枚举 (3 处测试断言 break + "写盘不变" 错误) | 待修 |
| RIG-2 | 🟡 | 严格性 | §3.6 "跳过本轮" vs "提前终止本轮" 风控语义矛盾 | 待修 |
| SEC-1 | 🟡 | 安全性 | 搜索 "高亮" innerHTML 注入面 + 查询词转义未约束 | 待修 |
| O-1~O-5 | 🟢 | — | forward esc 专项断言 / 作者 fallback 粒度 / ctrlKey / max_tweets 语义 / steipete 移除 | 观察 |

### 3D 评分

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 合理性 | 🟡 | 决策闭环完整、继承一致; D1 回填语义自相矛盾 (REA-1) |
| 严格性 | 🟡 | schema→测试影响遗漏 (RIG-1); 风控语义矛盾 (RIG-2); 30/24h 边界用例缺失 |
| 安全性 | 🟡 | "全字段 esc()" 覆盖 forward (O-1); 搜索高亮新注入面未约束 (SEC-1) |
| 继承一致性 | 🟢 | CLI/登录态/反爬/分栏/抽屉/crontab 无破坏 |

### 数据验证要点

- grep index.html `window_hours`/`retention` = 0 命中 → §4 "前端无需读" 成立; grep `doSearch`/`header-search` = 0 命中 → 搜索为净新增 (仅 searchIcon Bing 图标)。
- read tests/test_twitter_collector.py: 3 处 `assert ...['window_hours'] == 36` (L317/340/513) + TestWindowFilter 整类 36h 用例 + max_tweets 默认 20 断言多处, §7.1 未提及 → RIG-1。
- grep collector.py `WINDOW_HOURS` = 5 处 (within_window/filter_window/build_document/fetch_target/truncate_tweets), "废弃 36h" 缺函数级改造映射 → RIG-1。
- read 设计 §3.6 ("跳过本轮" vs "提前终止本轮") + §8 ("挑战跳过") 三处并存 → RIG-2。
- read index.html L468-471 esc() 存在并已用于 searchIcon title; read .gitignore 无 data/*.yaml 忽略 → §3.1 "入库" 成立。
- 未 commit / 未 push (1A 约束, commit 由 ops 处理); 本评审仅新增报告 + review-log + .review-level.yaml 三件。

---

## 2026-08-26 — X热点设计 v1.3 复审 (CL-SEC20 闭环)

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 设计 v1.3 (b9b025d docs@design) — 复审 v1.2 的 4 🟡 (REA-1/RIG-1/RIG-2/SEC-1) + O-1 🟢 修复核验 + 新问题扫描
- **Tracking**: REA-1/RIG-2/SEC-1 ✅ 全修; RIG-1 ✅ 主修 (残余 🟢 并入 impl prompt); O-1 ✅; 残余 🟢 O-2~O-5 + D3 名单基数; findings_open 0
- **状态**: ✅ PASS — 100/100 (A)
- **报告**: documents/reviews/x-hotspot-rereview-v1.3-20260826.md
- **实现 prompt**: ✅ 已生成

### 修复核验

| # | v1.2 问题 | v1.3 验证 |
|:--|:----------|:---------|
| REA-1 | 🟡 条数窗口回填语义矛盾 | ✅ §3.4 步骤5 三规则 (a/b/c) + 边界 (=30/=24h 整点); §7.1 用例同步 |
| RIG-1 | 🟡 schema 影响未完整枚举 | ✅ §4 retention + 3 处测试断言影响 + "写盘不变"更正; ⚠️ 残余: 函数映射 + 方法级命名 + max_tweets 20→30 断言 (→ impl prompt) |
| RIG-2 | 🟡 风控语义矛盾 | ✅ §3.6 单账号跳过 / 连续≥2 提前终止(已抓写盘) / 全未抓成 exit1 |
| SEC-1 | 🟡 搜索高亮注入面 | ✅ §5.2 结构化 DOM (span+textContent) 禁 innerHTML + 双转义; §7.2 `<script>` 用例 |
| O-1 | 🟢 forward XSS 断言 | ✅ §7.2 `<img onerror>` → 纯文本断言 |

### 残余观察 (🟢, 并入 impl prompt, 不阻塞)

- RIG-1 残余: 函数级改造映射缺失 (within_window/filter_window/truncate_tweets/build_document/fetch_target 5 函数); 断言未命名到方法级 (test_build_document_keys L316-317 / test_write_document_roundtrip L340 / test_all_disabled_writes_empty L513) + TestWindowFilter 36h 用例 + max_tweets 默认 20→30 断言 (test_max_tweets_default / test_max_tweets_zero_falls_back)。
- O-4 残余: "补足至 30" 硬编码 vs "N=max_tweets" 未显式等价 ("30" 应写作 max_tweets 默认 30)。
- O-2/O-3/O-5 残余: forward 作者 fallback 粒度 / ctrlKey 跨平台 / steipete 归档说明。
- 新 🟢: §2.2 D3 "新增 3 账号" vs §3.1 10 账号清单基数未说明。

### 数据验证要点

- read 设计 §3.4/§7.1 三规则+边界一致; §3.6 三态自洽; §5.2/§7.2 编码约束+注入用例齐。
- read tests/test_twitter_collector.py: 3 处 `assert ...['window_hours'] == 36` (L317/340/513) 确认存在; grep index.html retention/window_hours = 0 → §4 "前端不读" 成立。
- read collector.py: WINDOW_HOURS=36 5 处引用 + build_document `window_hours` 键 + cmd_collect ChallengeError 现为"跳过本轮" continue (无提前终止) — v1.3 设计描述的是待实现语义, 非现状矛盾。
- git show --stat b9b025d: design v1.2→v1.3 rename + 263 insertions, 修复声明有正文支撑。
- 未 commit / 未 push (1A 约束)。


---

## 2026-08-26 — X热点实现审计 v1.1 (CL-SEC20 闭环)

- **review者**: review/llm-radar.lab-review (hermes-1.2.0)
- **范围**: 实现 commit (2c11397→2899b06, 9 个) — CL-SEC20 5 增强 (配置迁移 data/ + 10 账号 / forward / 30-24h 条数窗口 / 全站搜索 + Cmd+F / 动态滚动) vs 设计 v1.3 一致性 + 测试质量 + 治理合规 + 安全性 + 运维闭环; CL-SEC19 收尾项 (9ff4536/dee96c2) 并入
- **Tracking**: 无 🔴🟡; IMPL-OBS-1~4 🟢 注记; 注记项 D1 1A 条数偏差/依赖约束/push 时机 已确认; findings_open 0
- **状态**: ✅ PASS — 100/100 (A)
- **报告**: documents/reviews/x-hotspot-impl-audit-v1.1-20260826.md
- **实现 prompt**: ⬜ 无需生成 (实现已完成, 闭环)

### 审计结论

- 一致性 ✅: 配置迁移 (data/twitter-targets.yaml + 根路径移除) / 10 账号 / forward "by @作者: 原文" / 条数窗口三规则 (apply_retention a/b/c + 边界 =30/=24h 整点 + per-account override) / 风控三态 (challenge_streak 单/连续 2/非连续) / retention schema (window_hours→retention, 0 残留 36h) / 全站搜索 + Cmd+F/Ctrl+F + 高亮结构化 DOM (禁 innerHTML) / forward 渲染 (esc + textContent) 全落地。
- 复审残余 🟢 落地: RIG-1 函数改造 (apply_retention/retention 键) ✅ / O-2 forward 作者 fallback (unknown) ✅ / O-3 ctrlKey ✅ / O-4 max_tweets 参数化 ✅; O-5 (steipete 归档) + D3 名单基数 未显式落地 (IMPL-OBS-3, 非阻塞)。
- 测试 ✅: test_twitter_collector.py (770 行, 条数窗口三规则+边界/forward 7 用例/风控三态/schema retention) + test_html.py TestSearchFeature (11 断言); 复跑 211 passed (184→211, CL-SEC20 新增)。
- 治理 ✅: commit type@scope 全合规; AGENTS.md 同步 (b11812f); console 前缀/CSS 无引号。
- 安全 ✅: esc() 全字段 + textContent + https 白名单 + CSP; 高亮禁 innerHTML; forward XSS 专项断言; 无敏感入库 (0 命中); git add 限定 data/twitter.json; subprocess list-form。
- 运维 ✅: cron 包装 D1A 自动拉起; attach 友好提示; ProfileLock 互斥; 原子写盘 + 去重幂等; 动态滚动 200513e (84→109 提升)。

### 发现 (🟢, 不扣分)

| # | Severity | Title | Status |
|---|----------|-------|--------|
| IMPL-OBS-1 | 🟢 | 审计 prompt 所列 commit SHA 与仓库不符 (subjects 1:1 匹配, rebase 前记录残留, 同 LR-SEC-017 类) | 注记 |
| IMPL-OBS-2 | 🟢 | 指标字段 num() 直通未 esc() (int 类型保证, 非攻击者可控; 文本已全 esc, 同 v1.0) | 注记 |
| IMPL-OBS-3 | 🟢 | 复审残余 O-5 (steipete 归档说明) + D3 名单基数 doc clarity 未显式落地 | 注记 |
| IMPL-OBS-4 | 🟢 | searchIcon 注释/代码不符 (encodeURIComponent 未调用), pre-existing 8907a76, 不在 CL-SEC20 diff | 注记 |

### 数据验证要点

- git rev-parse HEAD origin/main = 2899b06 双端一致, status clean, 0 未推送; 实现 commit 全部已推送。
- read data/twitter-targets.yaml (10 目标) + data/twitter.json (retention '30/24h' + 4 顶层键 + forward 格式正确, 7-14 条/账号)。
- grep 36h 残留: collector/tests/index.html `window_hours`/`WINDOW_HOURS`/`==36`/`filter_window`/`truncate_tweets` = 0 功能残留。
- pytest 211 passed 复跑; 测试污染 (snapshot/overview/timestamp) 待 git checkout 还原。
- 注记项 1 (D1 1A 条数偏差): 实测 30 条不可达 (X 对 CDP attach 降级无限滚动), 用户决策 B 接受 "24h 内全保留 + 首屏可达"; 动态滚动已尽力。
- 未 commit / 未 push (1A 约束, commit 由 ops 处理; push 已由 auto-push 完成)。

---

## 2026-08-27 — X热点弹框体验+CI修复 设计 v1.1 评审 (LLM-RADAR-CL001)

- **review者**: ops/llm-radar-x-preview-review (hermes-1.2.0)
- **范围**: 设计 v1.1 (adf9b2a docs@llm-radar) — 弹框居中720px / 三图标按钮行 / 完整拷贝素材 / sp-title 序号+sp-meta 完整时间 / CI pyyaml 补依赖+排除浏览器测试
- **Tracking**: D1~D5 与两轮确认串 (A1 B1 C2 D1 E1 + A1 B1 C1 D1) 完全对应, 无遗漏无越界; 7 项重点审查 6 ✅ + RIG-1 🟡 (版本命名, Bucket A 机械修复, 随 dev commit 落地); OBS-1~4 🟢; findings_open 0
- **状态**: ✅ PASS — 95/100 (A)
- **报告**: documents/reviews/llm-radar-x-preview-review-v1.0-20260827.md
- **实现 prompt**: ✅ 已生成

### 数据验证要点

- read index.html:69/:172/:86-87/:316 + JS 1080-1108: 基线 transform translate(-50%,-50%) 与 <1200px 分支 transform:none 成对; .sp-link 替换面完整。
- 实测 data/twitter.json: 10 targets url 全 https://, handle/name 无 null; 109 tweets 无空 text/url/posted_at。
- read test.yml:13-14: pip 列表确缺 pyyaml; 命令无排除 → §3.5 根因链逐环成立 (twitter-collector.py:37-40/:83-84 + test_twitter_collector.py:763)。
- grep tests/test_twitter_collector.py: 无 requests/webdriver/Chrome 调用 (全 FakeDriver + fixture HTML), CI 保留执行合理。
- 版本一致性: frontmatter/文件名 v1.0 vs 内容 v1.1 → RIG-1 (dev 随 commit 落地)。
- 未 commit / 未 push (1A 约束)。

---

## 2026-08-27 — X热点弹框体验+CI修复 实现审计 (LLM-RADAR-CL001)

- **review者**: ops/llm-radar-x-preview-impl-audit (hermes-1.2.0)
- **范围**: 实现 eea7482 (feat@llm-radar) — 对照评审报告「实现验收清单」7 项 + 验证清单 5 项, 独立核验
- **Tracking**: 7 项验收全 ✅ (基线 CSS / transform:none / .sp-actions 三按钮零 sp-link 残留 / 序号+三按钮逻辑 / fmtFull+copyTweet / test.yml pyyaml+排除 / RIG-1 rename+frontmatter); RIG-1 ✅ 已落地; OBS-1 ✅ 已在实现闭环 (失败 2s 复原); IMPL-OBS-1~3 🟢; findings_open 0
- **状态**: ✅ PASS — 100/100 (A)
- **报告**: documents/reviews/llm-radar-x-preview-impl-audit-v1.0-20260827.md
- **实现 prompt**: ⬜ 不适用 (实现审计)

### 数据验证要点

- git 证据: eea7482 --stat (test.yml 4 +- / 评审报告 +143 / design rename 4 +- / index.html 66 ++--); d930df7 (.review-level +9 / review-log +20); status clean, 3 未推送。
- 独立复跑: 主套件 211 passed (2 deselected) + twitter 专项 82 passed + test_cli 13 passed = 306 项, 全部与预期一致; 测试污染 (timestamp/overview/data/snapshot) 已精确 `git checkout --` 还原, 工作区 clean。
- SEC-1 专项: copyTweet lines.join 纯文本无 HTML; sp-act href 仅 /^https:\/\// 白名单 + 非 https removeAttribute; innerHTML 仅静态标签 + esc(src); 表格行 esc() 全字段。
- 设计 §3.3 vs copyTweet 模板逐行比对一致; §3.4 序号 sameIdx 子集与 spNav 同子集逻辑天然一致。
- 已知事项 (不视为缺陷): 评审报告文件被 dev 纳入 eea7482 (归属轻微混入, 内容正确); review-log/.review-level 由 ops 恢复后 commit d930df7。
- 未 commit / 未 push (1A 约束)。

---

## 2026-08-27 — 页面加载优化 设计 v1.0 评审 (LLM-RADAR-CL002)

- **review者**: ops/llm-radar-perf-optimize-review (hermes-1.2.0)
- **范围**: 设计 v1.0 (138f62d docs@llm-radar) — 4 项优化决策 (A1 Tailwind 预编译 / B1 条件缓存 / C1 snapshot compact / D1 渲染缓存) + 编号 1A=CL002 逐项核验
- **Tracking**: RIG-1~4 🟡 待修 (findings_open 4); O-1~4 🟢 观察; 修复后 bump v1.1 重审
- **状态**: ⏳ CONDITIONAL PASS — 80/100 (B)
- **报告**: documents/reviews/llm-radar-perf-optimize-review-v1.0-20260827.md
- **实现 prompt**: ⬜ 未生成 (非 PASS, 待 ops 修 4 🟡 bump v1.1 重审)

### 发现摘要

| # | Severity | Title | Status |
|---|----------|-------|--------|
| RIG-1 | 🟡 | B1 `?t=` 枚举不全: 设计列 3 处, 实际 5 处 (漏 index.html:1282 init 首屏加载 + changelog.html:157/:166); D2 "去掉全部" 未落实 | 待修 v1.1 |
| RIG-2 | 🟡 | D4 缓存失效遗漏 filter/sort 交互: 过滤/排序内嵌 renderer (renderLLMs:696 等 6 处), setFilter/toggleSource/toggleSort 命中缓存 → 面板陈旧 + 计数不一致 | 待修 v1.1 |
| RIG-3 | 🟡 | C1 写盘点误判: :1353 是 _archive_snapshot 写 data/history/{week}.json (周归档), 非 snapshot.json (仅 1279); 与 D3 "history 保持 pretty" 矛盾 | 待修 v1.1 |
| RIG-4 | 🟡 | §4 测试影响遗漏: test_html.py:147 硬断言 `?t=` 模式, B1 落地必挂 | 待修 v1.1 |

### 3D 评分

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 合理性 | 🟡 | 决策闭环完整、9 项确认完全映射; A1/CSP 方向正确; B1 枚举与"去掉全部"矛盾 (RIG-1) |
| 严格性 | 🟡 | D4 失效条件 (RIG-2); C1 写盘点 (RIG-3); 测试影响 (RIG-4) |
| 安全性 | 🟢 | 去 CDN 收窄第三方 JS 面; 缓存复用既有 renderer 输出, 无新注入路径 |

### 数据验证要点

- 独立盘点: grep `?t=` → index 4 处 (452/1027/1235/1282) + changelog 2 处 (157/166); grep json.dump 10 处逐点归属 (1279=_save_snapshot, 1353=_archive_snapshot→history, 其余 keep-pretty 列表正确)。
- read renderers 6 处确认 filterMode/sourceFilter/sortState 内嵌; doSearch→applySearchFilter 每次重跑, 搜索无陈旧 (设计该声明成立)。
- grep tests/ `?t=` 唯一命中 test_html.py:147; 缩进断言 0 命中 (设计 §4 "预期无" 正确)。
- 环境: node v26.0.0/npx 11.16.0 可用; static/ 已有 favicon 先例; .gitignore 覆盖 cache/ + *.log, static/tailwind.css 可入库; snapshot 316K/twitter 69K 与设计一致。
- 未 commit / 未 push (1A 约束); 本评审仅新增报告 + review-log + .review-level.yaml 三件。

---

## 2026-08-27 — 页面加载优化 设计 v1.1 复审 (LLM-RADAR-CL002)

- **review者**: ops/llm-radar-perf-optimize-rereview (hermes-1.2.0)
- **范围**: 设计 v1.1 (4c98e52 docs@llm-radar) — 复审 v1.0 的 4 🟡 (RIG-1~4) + 2 观察 (O-1/O-4) 修复核验 + 新问题扫描
- **Tracking**: RIG-1~4 ✅ 全修; O-1/O-4 ✅ 落地; N1 🟡 (§6 冒烟 grep .text-cobalt-500 类不存在, 并入 impl 验收清单); N2/N3 🟢; findings_open 0
- **状态**: ✅ PASS — 95/100 (A)
- **报告**: documents/reviews/llm-radar-perf-optimize-rereview-v1.1-20260827.md
- **实现 prompt**: ✅ 已生成 (见报告「实现验收清单」)

### 修复核验

| # | v1.0 问题 | v1.1 验证 |
|:--|:----------|:---------|
| RIG-1 | ?t= 枚举不全 | ✅ §3.2 枚举 6 位置 (index 452/1027/1235/1282 + changelog 157/166) = grep 全量 100% 一致; 页面级重定向 (index 337-345 / changelog 12-15) 标注不动; "共 5 处" 应为 6 (N2 🟢) |
| RIG-2 | 缓存失效漏 filter/sort | ✅ §3.4 复合 key (tab\|filterMode\|sourceFilter\|JSON.stringify(sortState[tab])) 覆盖 renderer 内嵌全部状态 (renderLLMs:696 等 6 处); 数据刷新置空; 计数每轮重算; 搜索独立于缓存 |
| RIG-3 | 写盘点误判 history | ✅ §1+§3.3 只列 1279 _save_snapshot; :1353 history 保持 pretty; keep-pretty 列表逐点 grep 归属一致 |
| RIG-4 | 测试断言漏 ?t= | ✅ §4 列出 test_html.py:147; 断言同步方案 (无 ?t= + {cache:'no-cache'} + console.warn 保留) 意图一致 |
| O-1 | changelog 重定向补注 | ✅ §3.2 补 changelog.html:12-15 标注不动 |
| O-4 | 边缘缓存窗口 | ✅ §3.2 注记 GH Pages ~10min 窗口 + 自动刷新自愈 |

### 新增发现

| # | Severity | Title | Status |
|:-:|:--------:|-------|--------|
| N1 | 🟡 | §6 冒烟 grep `.text-cobalt-500` 必挂 — 页面 0 使用 (仅 cobalt-300/400), JIT 只生成 content 扫描类 → 产物必不含; 改 `.text-cobalt-400` 或删 | 并入 impl 验收清单 #1 |
| N2 | 🟢 | "共 5 处 ?t=" 数字应为 6 (4 index + 2 changelog); 上轮 RIG-1 "实际 5 处" 亦应为 6 | 注记 |
| N3 | 🟢 | §6 "(O-3)"/"(O-2 阶段注记)" 引用上轮观察项编号, 与 §5 重排后 O-1~O-4 冲突 | 注记 |

### 数据验证要点

- 独立盘点: grep `?t=` → index 4 (452/1027/1235/1282) + changelog 2 (157/166) = 6 处, 与 §3.2 枚举逐一相等; 页面重定向 index 337-345 / changelog 12-15 实际读取确认与数据 fetch 可区分。
- grep json.dump 10 处: 1279=_save_snapshot→snapshot.json (SNAPSHOT_PATH L44), 1353=_archive_snapshot→history, 327/674/1312/1372/1700/2041 keep-pretty, 1343 overview compact — 与 §3.3 列表一致。
- read renderTab:738-749 (renderers 含 xhotspots; 计数 743-749 尾部无条件执行), renderLLMs:696, setFilter/toggleSource/toggleSort/doSearch 调用面 — §3.4 复合 key + 搜索独立声明成立。
- grep index/changelog cobalt 类: `text-cobalt-300`×4 + `text-cobalt-400`×6, `text-cobalt-500` = 0 → N1; tailwind.config 内联 (index.html:12-21) 定义 cobalt 400/500 + accent 400/500, 与 §3.1 提取范围一致。
- read tests/test_html.py:144-148: :147 硬断言 `'data/twitter.json?t=' + Date.now()` 属实, §4 修法精确。
- git: 4c98e52 design v1.1 修正 commit 为 HEAD (rename + 55+/30-), 与修正声明相符; 上轮三件产物 (报告/review-log/.review-level) 仍工作区未 commit, 本次追加不冲突。
- 未 commit / 未 push (1A 约束); 本复审仅新增报告 + review-log 追加 + .review-level.yaml 追加。

---

## 2026-08-27 — 页面加载优化 实现审计 (LLM-RADAR-CL002)

- **review者**: ops/llm-radar-perf-optimize-impl-audit (hermes-1.2.0)
- **范围**: 实现 commit 8f008e7 (feat@llm-radar: 页面加载优化 A1+B1+C1+D1) — 复审报告实现验收清单 5 项 + N1~N3 修正落地核验
- **Tracking**: 验收 1-7 ✅ 全落地; N1~N3 ✅ 设计文档修正已提交; IMPL-OBS-1~6 🟢 观察; findings_open 0
- **状态**: ✅ PASS — 100/100 (A)
- **报告**: documents/reviews/llm-radar-perf-optimize-impl-audit-v1.0-20260827.md

### 验收核验

| # | 验收项 | 结果 | 证据 |
|:--|:-------|:----:|:-----|
| 1 | D1 样式预编译 (config/产物<30KB/CDN→link/CSP/内联style/关键类) | ✅ | tailwind.config.js cobalt/accent; static/tailwind.css 14,061B 入库; 双文件 :10 link; CSP script-src 移除 cdn; 内联 <style> 保留; .text-cobalt-400 + .max-w-\[1400px\] 命中, .text-cobalt-500 0 命中 (N1 预期) |
| 2 | D2 条件缓存 (6 处 ?t= 删 + 页面重定向保留 + 10min 保留) | ✅ | grep ?t= 双文件 = 0; 6 处 fetch {cache:'no-cache'} 逐一读取 (index 445/1023/1233/1280 + changelog 157/166); 页面重定向 index 324-333 / changelog 11-16 完整; setInterval 10min (index:435) |
| 3 | D3 snapshot compact (1279 唯一改) | ✅ | grep json.dump 9 处: 1279 indent=None; 327/674/1312/1353/1372/1700/2041 全 indent=2; 1343 overview 本就 compact; 1917 print |
| 4 | D4 渲染缓存 (复合 key + 刷新置空 + 计数/搜索每轮) | ✅ | index:344-345 RENDER_CACHE/clearRenderCache; :735 复合 key (tab\|filterMode\|sourceFilter\|sortState); :446/:1027/:1031 三处置空; :739-746 计数/搜索每轮执行 |
| 5 | 测试同步 (:147 断言 + TestPerfOptimize 4 用例) | ✅ | test_html.py:144-149 无 ?t= + no-cache + console.warn; TestPerfOptimize 4 用例独立复跑 4 passed |
| 6 | AGENTS.md 构建命令 (O-2) | ✅ | AGENTS.md 107-124「样式构建」节: npx tailwindcss@3.4.17 命令 + 新增类重构建规则 |
| 7 | N1/N2/N3 设计文档修正 | ✅ | 8f008e7 内设计文档: 枚举改 6 处 (N2); §6 冒烟改 .text-cobalt-400 并注明 cobalt-500 勿作目标 (N1); 观察项编号引用改文字 (N3) |

### 数据验证要点

- 独立复跑全量: `python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q` → **215 passed, 2 deselected** (与预期 215 一致); TestPerfOptimize → **4 passed**。
- 冒烟: `grep cdn.tailwindcss.com index.html changelog.html` = 0; `ls -lh static/tailwind.css` = 14K (14,061B < 30KB); `grep -c text-cobalt-400` / `max-w-\[1400px\]` = 各 1; `.text-cobalt-500` = 0 (N1 修正后预期)。
- D3 体积收益实测: 当前 snapshot.json 315.5KB (323,086B) 内存重序列化 compact → 251.7KB (257,740B), **-20.2%**, 与设计估算 (~250K/-20%) 一致; round-trip 正常; 实际写盘待 collector 下次 run 生效。
- 条件缓存计数: `{cache:'no-cache'}` index 4 + changelog 2 = 6 处, 与设计枚举 100% 一致。
- 全仓残留扫描: cdn 仅文档/测试断言/历史归档/review-prep 提示; tests/ 内 ?t= 全为"不应存在"断言; 无其他数据 fetch ?t=。
- 测试污染精确还原: timestamp.json / overview.json / data/snapshot.json git checkout 指定 3 文件, 哈希与基线逐字节一致, git status clean。
- IMPL-OBS 🟢: (1) loadTwitterData 失败路径也清缓存 (正向增强); (2) 产物 13.7KB 余量充足, 自定义色类全生成; (3) refreshData 失败不清缓存 (与设计一致, catch 静默为既有行为); (4) ?t= 断言与页面重定向 p.set('t') 无冲突; (5) TestPerfOptimize 计数断言精确; (6) RENDER_CACHE 内存面有界。
- 未 commit / 未 push (1A 约束); 本审计仅新增报告 + review-log 追加 + .review-level.yaml 追加。

---

## 2026-08-27 — 拷贝降级修复+按钮图标化 设计 v1.0 评审 (LLM-RADAR-CL003)

- **review者**: ops/llm-radar-copy-fix-review (hermes-1.2.0)
- **范围**: 设计 v1.0 (75826f2 docs@llm-radar) — 按钮纯图标化 (用户手工微调, 工作区 M index.html) + copyTweet 拷贝降级链 (clipboard 防御 → execCommand 兜底, 返回值反馈) + 测试
- **Tracking**: RIG-001 🟡 (test_html 断言规格防假阳性) 并入实现验收清单; O-1~O-4 🟢 观察; findings_open 0
- **状态**: ✅ PASS — 95/100 (A)
- **报告**: documents/reviews/llm-radar-copy-fix-review-v1.0-20260827.md
- **实现 prompt**: ✅ 已生成 (设计 PASS, 可进 dev)

### 发现摘要

| # | Severity | Title | Status |
|---|----------|-------|--------|
| RIG-001 | 🟡 | §3.3 测试断言规格防假阳性不足: 裸子串 `navigator.clipboard.writeText` 会被 index.html:1208 ago.onclick 既有裸调用满足 (修复前即绿, 零保护); D1 表 `?.` 与 §3.2 `&&` 双形式需正则兼容; 须 scope 到 copyTweet 函数体 | 并入实现验收清单 |

### 3D 评分

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 合理性 | 🟢 | 决策 D1-D5 与确认串 (A1 B2+B3 C1 D1 + 残余 1A 2A) 完全对应; 图标化+title 补偿、降级链、反馈语义方向正确; 改动面最小 |
| 严格性 | 🟡 | 降级链三分支 (API 缺失/promise 失败/返回值反馈) 完整; §3.3 断言规格有假阳性风险 (RIG-001) |
| 安全性 | 🟢 | textarea 临时节点 + value/textContent 赋值, 无 innerHTML → 无注入面 (SEC-1 声明成立) |

### 数据验证要点

- grep tests/ + changelog.html: 📋/拷贝/copyTweet/sp-act 断言 0 命中 (仅 changelog.html:31 无关 h1) → 设计"无 '📋 拷贝' 文本断言依赖"声明属实。
- 现状: index.html:1143 裸 `navigator.clipboard.writeText` — TypeError 发生在 promise catch 前, 与设计 bug 描述完全一致; :1208 ago.onclick 同款裸调用但仅 localhost (secure context) 触发, 不受影响 (O-1)。
- `document.execCommand('copy')` 与 `navigator.clipboard && navigator.clipboard.writeText` 当前 index.html 均 0 命中 → 新断言 RED-前成立; 裸 `navigator.clipboard.writeText` 2 处 (1143/1208) → 全文件子串断言假阳性 (RIG-001)。
- 测试基线: `pytest tests/test_html.py -m "not selenium"` = 27 passed / 2 deselected; 全量非 selenium/cli = 215 → +1 = 216, 与设计 §4 "预期 216+" 一致。
- git: HEAD=75826f2 (design v1.0); 工作区仅 index.html (按钮图标化 3+/3-); 分支 14 ahead/3 behind 为既有分叉, 与本评审无关。
- 未 commit / 未 push (1A 约束); 本评审仅新增报告 + review-log 追加 + .review-level.yaml 追加。

## 2026-08-27 — 拷贝降级修复+按钮图标化 实现审计 (LLM-RADAR-CL003)

- **review者**: ops/llm-radar-copy-fix-impl-audit (hermes-1.2.0)
- **范围**: 实现 commit 0013b84 (feat@llm-radar: X弹框按钮图标化+拷贝降级修复) — 设计 D1-D5 + 评审验收清单 3 项核心变更 + RIG-001 断言规格落地核验
- **Tracking**: 验收 1-8 ✅ 全落地; RIG-001 ✅ 断言规格落实 (区域截取+正则双形式+禁裸子串); IMPL-OBS-1~6 🟢 观察; findings_open 0
- **状态**: ✅ PASS — 100/100 (A)
- **报告**: documents/reviews/llm-radar-copy-fix-impl-audit-v1.0-20260827.md

### 验收核验

| # | 验收项 | 结果 | 证据 |
|:--|:-------|:----:|:-----|
| 1 | D1 降级链 — clipboard 防御 (&& / ?.) | ✅ | index:1149 `if (navigator.clipboard && navigator.clipboard.writeText)` — undefined 短路不再抛 TypeError (根因修复) |
| 2 | D1 降级链 — promise catch → fallback | ✅ | index:1150 `.catch(() => feedback(copyTextFallback(text)))` |
| 3 | D1 降级链 — API 不可用分支 | ✅ | index:1151-1153 else → `feedback(copyTextFallback(text))`; 三分支完整 |
| 4 | D1 copyTextFallback (textarea + execCommand boolean + finally 移除; SEC-1) | ✅ | index:1157-1172: value/setAttribute 赋值 0 innerHTML; try { select; return execCommand('copy') } catch false; finally removeChild |
| 5 | D2 B2 — orig='📋' + 1500/2000ms 复原; 无残留 | ✅ | index:1143 orig='📋'; :1145-1148 feedback(ok) 1500/2000ms; grep '📋 拷贝' index.html = 0 |
| 6 | D3 B3 — 三按钮 title + 纯图标保留 | ✅ | index:306-308 title 打开原文/作者主页/拷贝推广内容; 🔗/👤/📋 无文字 (用户微调已入库未还原) |
| 7 | D4 D1 测试 — TestCopyTweetFallback 4 用例 (RIG-001) | ✅ | test_html.py:159-200: _copy_region 截取至 spNav 前含 copyTextFallback; 防御断言正则 `navigator\.clipboard(?:\?\.|\s*&&)\s*navigator\.clipboard\.writeText`; execCommand 断言; orig 正+负断言; 三 title; 无全文件裸 writeText 子串 |
| 8 | 改动面最小化 | ✅ | git show --stat = index.html + tests/test_html.py 2 文件 (78+/12-); 数据/CI/collector 0 改动 |

### 数据验证要点

- 独立复跑全量: `python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q` → **219 passed, 2 deselected** (与预期 219 一致); TestCopyTweetFallback → **4 passed**。
- 断言真实性推演: 防御正则要求 clipboard 与 writeText 间有 `&&`/`?.`, ago.onclick (:1230) 裸 writeText 无法满足 → 测试真实防护 (RIG-001 假绿风险排除); execCommand('copy') 仅存在于 copyTextFallback → 区域截取含 fallback 由该用例独立证明。
- clipboard 调用面: 仅 2 处 — :1149-1150 (copyTweet 已防御) + :1230 (ago.onclick, localhost 专用 secure context, 设计范围外, 评审 O-1 已知)。
- '📋 拷贝' 残留: index.html 0 命中; tests/ 2 命中均为负断言本身 (docstring + `not in region`)。
- 用户微调保留: 0013b84 diff 按钮行 = 纯图标 + title 共存, 与设计 §3.1 逐字一致。
- IMPL-OBS 🟢: (1) fallback 用 top:-9999px+readonly 替代设计 opacity:0 — 功能等价更稳; (2) feedback() 合并 done/fail 闭包 — 语义一致更精简; (3) 评审 O-3 (iOS setSelectionRange) 未补 — 非验收项; (4) ago.onclick 裸 writeText 未动 — 范围外; (5) 区域截取边界依赖函数位置, assert message 已注明; (6) orig 负断言锁定 B2 核心。
- 测试污染精确还原: timestamp.json / overview.json / data/snapshot.json git checkout 指定 3 文件, 哈希与基线逐字节一致, git status clean。
- 未 commit / 未 push (1A 约束); 本审计仅新增报告 + review-log 追加 + .review-level.yaml 追加。

---

## 2026-08-27 — skills 供给站+prompt 子命令 设计 v1.0 评审 (LLM-RADAR-CL004)

- **review者**: ops/llm-radar-skills-prompt-review (hermes-1.2.0)
- **范围**: 设计 v1.0 (8f14683 docs@llm-radar) — x-twitter-collector skill 沉淀 + `llm-radar prompt` 子命令 (全量对齐 hs cli.py:685-800) + test_cli 扩展 + AGENTS.md 双处同步
- **Tracking**: RIG-001 🟡 (help 补行格式非两行式) + RIG-002 🟡 (行为矩阵含 `<不存在> --json` 但 7 用例缺自动化) 并入实现验收清单; OBS-1~5 🟢 观察; findings_open 0
- **状态**: ✅ PASS — 90/100 (A)
- **报告**: documents/reviews/llm-radar-skills-prompt-review-v1.0-20260827.md
- **实现 prompt**: ✅ 已生成 (设计 PASS, 可进 dev)

### 发现摘要

| # | Severity | Title | Status |
|:-:|:--------:|-------|--------|
| RIG-001 | 🟡 | §3.4 help 补行为单行内联+全称令牌, 与 print_grouped_help 两行式/短名格式不符 | 并入实现验收清单 (两行式 `prompt` + 缩进描述行) |
| RIG-002 | 🟡 | 行为矩阵含 `<不存在> --json` 错误信封但 7 用例无自动化 (hs 有 test_not_found_json) | 并入实现验收清单 (补第 8 用例) |

### 3D 评分

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 合理性 | 🟢 | 三件事与确认串内容逐项对应; 行为矩阵 8 行实测对齐 hs; main() 分支位置消除 key 日志论证闭环; B1 边界分工清晰 |
| 严格性 | 🟡 | 2 项规格精度缺陷 (help 格式 / 错误信封测试); brief ^#{2,3} 为 hs ^## 超集 (OBS-1) |
| 安全性 | 🟢 | 纯文档+只读子命令, 无新依赖/无注入面; no_key_log 防回归 |

### 数据验证要点

- 运行时实测: `help` 出 NotOpenSSLWarning (python3.9 urllib3 + LibreSSL) → D4 "所有命令均有"成立; `prompt` 现状 = 构造器噪音 + `❌ 未知命令: prompt` + exit 1 → 设计修复前提属实。
- main() 2204-2302: help 分支 2222-2224 不实例化 / status 2227-2228 / 实例化 2230 / else 2300-2302 → prompt 插入点可行, key 日志 (L180/182) 不再触发。
- hs 对照: cli.py:685-800 _cmd_prompt 全逻辑逐行比对 (8 行矩阵全对齐, brief 扫 `^## `, 详情追加 refs); test_prompt.py 9 用例含 test_not_found_json。
- CI: test.yml:14 未 ignore test_cli.py → 自动覆盖属实; 本地传统命令 --ignore=tests/test_cli.py 已由设计显式标注必须另跑。
- skills/ 现状 = {github-workflow} (无 references/) → 精确集合断言基线成立; test_cli.py 基线 13 passed (扩展后 20)。
- AGENTS.md grep skills/prompt = 0 有效命中 → O-2 双处同步确需; Key Commands 节为第三处 (OBS-4)。
- 确认串回溯 (探讨会话 20260827_205047_35d6ad): D 组选项 D1=全局抑制/D2=不动; 复述批准"不动（D2）"+「开始」→ 设计 D4=2D 内容正确, 字面 "D1" 为标签歧义 (OBS-2)。
- 编号: review_history 实测 CL001 (x-preview) / CL002 (perf-optimize) / CL003 (copy-fix) 2026-08-27 已占 → CL004 正确。
- 未 commit / 未 push (1A 约束); 本评审仅新增报告 + review-log 追加 + .review-level.yaml 追加。

---

## 2026-08-27 — skills 供给站+prompt 子命令 实现审计 (LLM-RADAR-CL004)

- **review者**: ops/llm-radar-skills-prompt-impl-audit (hermes-1.2.0)
- **范围**: 实现 commit f0276ea (feat@llm-radar: add x-twitter-collector skill and prompt subcommand) — 设计 D1-D6 + 评审实现验收清单 5 项 + RIG-001/002 落地核验
- **Tracking**: 验收 1-5 ✅ 全落地; RIG-001 ✅ 两行式落地 (2+10 空格与既有行一致); RIG-002 ✅ 第 8 用例落地; AUD-001 🟡 (no_key_log 断言 scope 盲点, 非阻塞); IMPL-OBS-1~5 🟢 观察; findings_open 1
- **状态**: ✅ PASS — 95/100 (A)
- **报告**: documents/reviews/llm-radar-skills-prompt-impl-audit-v1.0-20260827.md

### 验收核验

| # | 验收项 | 结果 | 证据 |
|:--|:-------|:----:|:-----|
| 1 | SKILL.md frontmatter + 正文 7 节 | ✅ | name/description 首 57 字符自含 "Use when operating" 触发/category devops; 7 节 (CLI 签名退出码 0/1/2 / targets 配置 / schema 30/24h / 双 profile 概念表 (OBS-3) / auto-push / cron 20 9,21 / 故障浓缩→x-twitter-scraping) 与 twitter-collector.py 实况逐一核验一致 |
| 2 | collector prompt 分支 + 行为矩阵 8 行 | ✅ | main():2346-2349 help 后/实例化前/sys.exit 于分支内; _cmd_prompt 2207-2321 vs hs cli.py:685-800 逐行对齐; SKILLS_DIR L47; 参数三形态实测; 无 key 日志 grep 0 |
| 3 | RIG-001 help 两行式 | ✅ | L2178-2179 `  prompt` + 10 空格描述行, 与同组 help/<cmd> help 行字节级同格式 (评审修正块字面亦 10 空格, "11"系评审笔误) |
| 4 | test_cli 8 用例 + RIG-002 | ✅ | L137-220 8 用例; json_not_found (L206-213) status error + data None + exit 1; 独立复跑 21 passed; 防假阳性: 精确集合相等/exit code/分流断言 — no_key_log scope 盲点 → AUD-001 |
| 5 | AGENTS.md 三处同步 | ✅ | :20 (结构节 skills/) / :33 (Key Commands prompt) / :45 (CLI 治理 lr prompt) 逐一命中 |

### 数据验证要点

- 独立复跑: `python3 -m pytest tests/test_cli.py -q` → **21 passed** (13 既有 + 8 新增; 评审验收清单预测 "20 (13+8−1)" 系算术笔误); `python3 -m pytest tests/ -m "not selenium" -q` → **243 passed, 2 deselected** — 与审计预期完全一致。
- 手工实测 6 项全过: prompt 列表 exit 0 / prompt x-twitter-collector 全文无 key 日志 / prompt nope exit 1 (stderr 报错 + stdout 可用列表) / prompt --json 信封 (status ok, names 精确 = 双 skill) / prompt nope --json 错误信封 (status error/data null, exit 1) / help【其他】组两行式。
- NotOpenSSLWarning 实测出现于 prompt stderr (urllib3 v2 + LibreSSL) — D4 已知 ("所有命令均有"), 与 help 一致, 非缺陷。
- AUD-001: no_key_log 断言串 "DeepSeek API key" 仅匹配构造器成功路径日志 (L181); 失败路径 "DEEPSEEK_API_KEY 未配置" (L183, 全大写+下划线) 不含该串 — 本地无 key 环境假绿风险, CI (secrets key) 守卫有效; 断言串出自评审验收清单原文, 建议后续 test 硬化 (双串或时间戳前缀断言)。
- 测试污染精确还原: timestamp.json / overview.json / data/snapshot.json git checkout 指定 3 文件, git status 回到仅 3 件评审产物 (与审计前一致)。
- 未 commit / 未 push (1A 约束); 本审计仅新增报告 + review-log 追加 + .review-level.yaml 追加。

---

## 2026-09-02 — 质量门禁放宽与重试优化设计 评审 (LLM-RADAR-CL005)

- **review者**: review/llm-radar-quality-gate-relax-design (hermes-1.2.0)
- **范围**: 设计文档 llm-radar-quality-gate-relax-design-v1.0-20260902.md (961d666) — D1~D7 决策 + §3 详细设计 + §4 测试影响 + §5 观察项
- **Tracking**: REA-1 🟡 (实体0判定 5维度 vs 4实体维度口径 + 拦截位置误述) / RIG-1 🟡 (重试日志 4 处只列 1 处) / RIG-2 🟡 (status_str 因子误述, "实体数"非因子) / RIG-3 🟡 (~40s/次 vs 实测 324s/6≈54s, O-1 "≤200s" 余量不足) / O-1~O-6 ℹ️; findings_open 4
- **状态**: ⏳ CONDITIONAL PASS — 80/100 (B)
- **报告**: documents/reviews/llm-radar-quality-gate-relax-design-review-v1.0-20260902.md
- **实现 prompt**: ⬜ 无需生成 (非 PASS)

### 发现摘要

| # | Severity | Title | Status |
|---|----------|-------|--------|
| REA-1 | 🟡 | 实体0判定维度口径 (5维度 vs 4实体维度) + 拦截位置误述 (run L1739 vs _verify L1428) | 待修 |
| RIG-1 | 🟡 | 重试日志 4 处计数只列 1 处 (L788 漏; L784/L794 既有漂移) | 待修 |
| RIG-2 | 🟡 | status_str 因子枚举误述 ("实体数"非因子, 漏 quality_status/git_status) | 待修 |
| RIG-3 | 🟡 | 耗时估算 ~40s/次 vs 实测 54s/次, O-1 "≤200s" 余量不足 | 待修 |
| O-1~O-6 | ℹ️ | 跨项目锚点/用例落点/热点数读存量/实体数冗余/空changelog/方法名typo | 观察 |

### 数据验证要点

- 源码锚点全命中: _verify L1419-1463 (热点阻断 L1447-1449) / checks L1894-1899 / status_str L1857-1863 / merge_entities quality_ok 链路 L951→1141→1155→1283 / _auto_push partial L372-399。
- 漂移: 方法名 `_extract_entities` → 实际 `extract_entities` (L681); status_str 因子实为 5 项 (快照缺失/新鲜度/连续失败/质量门禁status/git分叉), 无 "实体数"。
- 重试块 4 处计数: L780 `/5` / L784 `/3` / L788 `/5` / L794 `3 次` — 设计只列 L780, L788 漏改。
- 测试影响: test_ok_checks labels 断言需加 '热点数' (L96); test_warning_quality_failed (L165) 语义不变; test_timestamp.py 不调 _verify 不变; tests/ 无 _verify 直接单测 (新增 2 用例为首批)。
- 未 commit / 未 push (任务显式约束); 本评审仅新增报告 + review-log 追加 + .review-level.yaml 追加 (3 件产物, 不碰 WIP 的 .hermes-project.yaml / data/snapshot.json / overview.json)。

---

## 2026-09-02 — 质量门禁放宽与重试优化设计 复审 (LLM-RADAR-CL005 v1.1)

- **review者**: review/llm-radar-quality-gate-relax-design-rereview (hermes-1.2.0)
- **范围**: 设计文档 v1.1 (ba76927) — 上轮 4 🟡 (REA-1/RIG-1/RIG-2/RIG-3) + SEC-001 逐项回归
- **Tracking**: REA-1 ✅ / RIG-1 ✅ / RIG-2 ✅ / RIG-3 ✅ / SEC-001 ✅; N1 🟡 (§6 冒烟 ≤200s 未同步, 并入 impl); N2~N4 ℹ️; findings_open 0
- **状态**: ✅ PASS — 95/100 (A)
- **报告**: documents/reviews/llm-radar-quality-gate-relax-design-rereview-v1.1-20260902.md
- **实现 prompt**: ✅ 已生成 (报告末「实现验收清单」段, 含 N1 修正)

### 发现摘要

| # | Severity | Title | Status |
|---|----------|-------|--------|
| REA-1 | ✅ | 实体0判定 4 实体维度 (排除 hotspots) + 分层拦截 (L1739 拦 None / _verify 新检查拦空 dict / L1428 防御) | 已修 |
| RIG-1 | ✅ | 重试日志 4 处计数全列 (L780/L788 →/3; L784/L794 既有漂移) + L779 循环 | 已修 |
| RIG-2 | ✅ | status_str 5 因子枚举 (快照/新鲜度/连续失败/质量门禁status/git分叉) | 已修 |
| RIG-3 | ✅ | 耗时重ground 216s (324/6=54, 4×54), O-1 不承诺 ≤200s | 已修 |
| SEC-001 | ✅ | §3.3 + §5 O-1b 取舍显式声明 | 已修 |
| N1 | 🟡 | §6 冒烟「计时 LLM 阶段 ≤200s」与 216s 矛盾 (RIG-3 放宽未同步 §6) | 并入 impl |
| N2~N4 | ℹ️ | 背景 ~40s 旧值 / D2 ~200s 略乐观 / L776-L778 注释+_verify docstring 同步未列 | 观察 |

### 数据验证要点

- 源码锚点复核: L1739 `if not entities: return False` / L1428 `return ['实体提取为空']` / L1433 4 维度循环 / L1857-1863 5 因子 / L1896 实体数 status='info' / 重试块 L779-794。
- RIG-1 grep 全量: collector 重试块硬编码计数恰 L780/L784/L788/L794 四处 + L779 循环, 无遗漏; tests/ 无 retry 计数断言。
- RIG-3 算术: 324/6=54s/次; 4 次调用×54=216s; 6 次=1 首次 + range(1,6) 5 重试, 自洽。
- N1: §6 项 3「计时 LLM 阶段 ≤200s」与 §3.1/§5「≤200s 非承诺/非目标」自相矛盾, 照单必挂。
- commit 报告 + review-log + .review-level.yaml (3 件产物), 不 push; 不碰 WIP (.hermes-project.yaml / data/snapshot.json / overview.json)。

---

## 2026-09-02 — 质量门禁放宽与重试优化 实现审计 (LLM-RADAR-CL005)

- **review者**: review/llm-radar-quality-gate-relax-impl-audit (hermes-1.2.0)
- **范围**: feat commit 1dc7ddf (retry 5→3 + 质量门禁放宽 + status checks 第5项) + tests + design v1.1 §6 N1 修正
- **Tracking**: D2/D5/D6/D7 ✅ 全落地; DOC-1/2/3 🟡 文档漂移 (docstring/features.md 审计中修复, AGENTS.md 待用户改); findings_open 1
- **状态**: ✅ PASS — 95/100 (A)
- **报告**: documents/reviews/llm-radar-quality-gate-relax-impl-audit-20260902.md
- **实现 prompt**: ⬜ 无需生成 (实现已完成, PASS 后 push)

### 发现摘要

| # | Severity | Title | Status |
|---|----------|-------|--------|
| DOC-1 | 🟡 | _verify docstring 仍称「热点数量」为阻断硬指标 (N4 清单项漏改) | 审计中修复 |
| DOC-2 | 🟡 | features.md 质量门禁「热点 ≥3 条」旧口径 | 审计中修复 |
| DOC-3 | 🟡 | AGENTS.md L82/L145 仍描述旧门禁 (protected 文件无写权限) | 待用户改 |

### 数据验证要点

- 独立复跑: `pytest -m "not selenium" --ignore=test_cli.py --ignore=test_selenium.py` → 223 passed, 2 deselected; test_verify.py 4 用例 + test_status.py::test_ok_checks 5 labels 全绿。
- 源码锚点: L780 range(1,4) + L781/785/789/795 四处 /3 计数; L1449-1451 实体 4 维度 ==0 阻断; L1454-1455 热点 <3 warning; L1429 防御; run L1745 拦 None; L1911 checks 第5项; L1864-1869 status_str 5 因子无热点。
- 联动面核验: merge_entities quality_ok=False 时空实体 dict merge 为 no-op (不 wipe 存量) + _auto_push partial 仅推 timestamp.json; 前端 index.html 空热点态 (L570) 已兜底, 无破坏。
- 冒烟: `lr status --json` 5 checks 含「热点数」(81 条 info); 主 status=warning 因 Git 6 ahead 非热点。
- D3 需求 prompt 已落盘 cache/review-prep/cl005-daily-checker-handoff-prompt.md。
- 测试污染还原: timestamp.json / overview.json / data/snapshot.json git checkout 还原; .hermes-project.yaml WIP 不碰。

---

## 2026-09-02 — wrapper env 修复 补充审计 (LLM-RADAR-CL005)

- **review者**: review/llm-radar-cl005-wrapper-env-fix-audit (hermes-1.2.0)
- **范围**: 补充修复 commit 07baf8f (conda_sh/brew_prefix → wrapper env, 修 NotOpenSSLWarning)
- **Tracking**: SEC-1 🔴 (预存密钥副本, 审计中删除); GOV-1 🟡 (.env 段不可复现); HYG-1 🟡 (orphan lr-wrapper.sh); findings_open 2
- **状态**: ✅ PASS — 95/100 (A)
- **报告**: documents/reviews/llm-radar-cl005-wrapper-env-fix-audit-20260902.md
- **实现 prompt**: ⬜ 无需生成 (修复已完成, PASS 后 push)

### 发现摘要

| # | Severity | Title | Status |
|---|----------|-------|--------|
| SEC-1 | 🔴 | cache/cli-registry/wrapper.sh.tmpl 与 .env 字节相同 (live key, 误 cp) | 审计中删除 |
| GOV-1 | 🟡 | wrapper .env 段为手工 patch, install.py --force 再生成丢失 | 后续 P2 |
| HYG-1 | 🟡 | orphan cache/system-command/lr-wrapper.sh (旧坏 wrapper) | 后续 P3 |

### 数据验证要点

- 根因实测: /usr/bin/python3 3.9.6 (LibreSSL 2.8.3) import requests → NotOpenSSLWarning; py3.12 3.12.13 → 无。旧 lr-wrapper.sh CONDA_SH 空 → /Caskroom/... 缺 /opt/homebrew 前缀 → conda 未激活。
- 修复实测: env -i 干净 env lr status → py3.12 3.12.13, grep -c NotOpenSSLWarning = 0; 交互 shell 同 0。
- diff 最小性: git show 07baf8f = 仅 .cli-registry.yaml +2 行 (conda_sh/brew_prefix); 两路径 ls 存在。
- 可复现性: install.py L124-125 填充 {{conda_sh}}/{{brew_prefix}} 占位符; 复刻模板填充 diff 仅 .env 4 行手工 (GOV-1)。
- symlink: ~/.local/bin/{lr,llm-radar} → cache/system-command/llm-radar-wrapper.sh (同一 wrapper)。
- SEC-1: cache/cli-registry/wrapper.sh.tmpl 与 .env 同 sha256 (26d9944a...); git check-ignore + git ls-files cache/ 空 → 未入 git/未泄漏; 审计中删除。

---

## 2026-09-02 — 分叉修复 merge 审计 (LLM-RADAR-CL005)

- **review者**: review/llm-radar-cl005-fork-merge-audit (hermes-1.2.0)
- **范围**: merge commit 3633cf4 (merge origin/main into local CL005 chain, 修复 Git 分叉 16 ahead/3 behind)
- **Tracking**: SEC-1 🟢 (服务器数据 commit 无代码回退); findings_open 0
- **状态**: ✅ PASS — 98/100 (A)
- **报告**: documents/reviews/llm-radar-cl005-fork-merge-audit-20260902.md
- **实现 prompt**: ⬜ 无需生成 (merge 已完成, PASS 后 push)

### 审计结论

- Merge 双方保留 ✅: Parent1=4362e84 (CL005 tip) + Parent2=ad62fa8 (server 21:02); CL005 代码链 10 commits + 服务器 3 数据 commits 全保留。
- 冲突解决 ✅: 数据文件 (snapshot/overview/timestamp) 取 origin/main 版 (21:02:05 > 18:42:04, 数据新鲜度优先); 非数据文件零冲突。
- 代码完整性 ✅: retry 5→3 (L780) / conda_sh (L7) / test_verify.py / features.md 全部 CL005 版存活; 服务器 3 commit 均纯数据 (timestamp/snapshot/overview), 无代码/test.yml 变更。
- 工作区 ✅: 17 ahead / 0 behind / clean; 17 = 16 CL005 + 1 merge。

### 发现

| # | Severity | Title | Status |
|---|----------|-------|--------|
| SEC-1 | 🟢 | 服务器数据 commit 无代码文件变更，无回退风险 | 已验证 |

### 数据验证要点

- `git show 3633cf4` 确认双 parent (4362e84 + ad62fa8)。
- `git diff 4362e84..3633cf4` = 仅 3 数据文件 (snapshot/overview/timestamp), 代码零变更。
- `git diff ad62fa8..3633cf4 -- data/snapshot.json overview.json timestamp.json` = 空 (merge = origin/main 版)。
- `git diff ad62fa8..3633cf4 -- llm-radar-collector.py tests/ .cli-registry.yaml features.md` = CL005 代码变更存在 (retry 5→3 / conda_sh / test_verify.py / features.md 实体数检查)。
- 服务器 3 commit (685a3e2/ac3cc0f/ad62fa8) 逐个 `git show --stat` = 纯数据文件, 0 代码变更。
- timestamp.json 当前值: generated_at=2026-09-02T21:02:05.317946, server=linux, hostname=iZ2ze0mvn4qle5b5jp7ndlZ。

---

## 2026-09-03 — Push 防覆盖修复审计 (v1.4)

- **review者**: Security Reviewer (review profile)
- **范围**: commit 074ac1b `fix@llm-radar: disable force-with-lease on rebase conflict (CL005 fork prevention v1.4)`
- **Tracking**: (无发现); findings_open 0
- **状态**: ✅ PASS — 100/100 (A)
- **报告**: documents/reviews/llm-radar-push-anti-overwrite-audit-20260903.md
- **实现 prompt**: ⬜ 无需生成 (修复已完成, PASS 后 push)

### 审计结论

- else 分支修改 ✅: rebase 冲突 → 禁 force-with-lease → dead-letter + 提示人工 merge (L356-366)
- rebase 成功路径 ✅: r2 force-with-lease 保留 (L348-355), 该路径 push 内容含远端, force 安全
- 测试更新 ✅: 3 用例覆盖新行为 (冲突禁 force + dead-letter 断言), 旧 v1.3 用例正确移除
- _sync_remote / 正常 push ✅: 不受影响 (独立路径)
- 无遗漏 ✅: finally abort 清理保留, dead-letter 字段语义正确

### 数据验证

- 全量测试: `pytest -m "not selenium" --ignore=test_cli.py --ignore=test_selenium.py` → 222 passed
- diff 最小性: 2 files changed, 22 insertions(+), 41 deletions(-)

实现 prompt: ✅ 已生成

---

## 2026-09-03 — STALE_HOURS 7→12 调整审计

- **review者**: Security Reviewer (review profile)
- **范围**: commit 2ff9b51 `fix@llm-radar: STALE_HOURS 7->12 for cross-night gap (2026-09-03)`
- **Tracking**: 🟡 SEC-280 (docstring L28 minor); findings_open 0 blockers
- **状态**: ✅ PASS — 98/100 (A)
- **报告**: documents/reviews/llm-radar-stale-hours-audit-20260903.md
- **实现 prompt**: ⬜ 无需生成 (常量调整, 无实现任务)

### 审计结论

- 双文件默认值同步 ✅: collector.py L53 + health.py L38 均为 `'12'`
- 注释一致 ✅: collector L50-52 + health L37 注释已更新为 12h
- docstring minor 🟡: health.py L28 docstring 仍写 "默认 7" (不影响运行时)
- tests ✅: 222 passed, mod.STALE_HOURS 自动跟随
- env 覆盖 ✅: LLM_RADAR_STALE_HOURS 环境变量机制完好
- AGENTS.md L50 🟡: 仍写 STALE_HOURS=7 (protected 拦截, 待用户改)
- 服务器 🟡: df9ef61 需后续 pull 同步

### 数据验证

- 全量测试: `pytest -m "not selenium" --ignore=test_cli.py --ignore=test_selenium.py` → 222 passed
- diff 最小性: 2 files changed, 6 insertions(+), 4 deletions(-)
- env 覆盖实测: `LLM_RADAR_STALE_HOURS=5` → 正确返回 5

实现 prompt: ⬜ 无需生成
