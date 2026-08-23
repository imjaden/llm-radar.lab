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


