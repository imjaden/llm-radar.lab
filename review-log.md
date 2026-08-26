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
- **状态**: ⏳ CONDITIONAL PASS — 80/100 (B)
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
