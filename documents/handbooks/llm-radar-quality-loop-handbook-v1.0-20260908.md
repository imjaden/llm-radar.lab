---
author: hermes-v0.20.6(2026.8.27)
profile: dev
type: summary
date: 2026-09-08
---

# llm-radar quality-loop handbook v1.0（质量与流程）

> documents-consolidation phase-2 草稿（只写文件，未 commit）。素材全文（gitignored）：
> `cache/doc-consolidation/llm-radar-quality-loop-extract.md`。
> 本手册同时**整合三份 agent-loop 流程文档**（Q4：loop/agent-loop-design-v1.0 + loop/requirements-spec.md + pipeline/agent-loop-plan.md；原件已于 2026-09-08 归档 → documents/archive/theme-20260908/）。
> 代码行号核实基准：2026-09-08 工作区（CL006 后，门禁行号较 CL005 实现审计时点又漂移）。

## 〇、概念映射（必须先读）

「agent-loop」一词在仓内**双义**：

1. **跨 profile 开发流程闭环**（agent-loop-design v1.0 + requirements-spec）——需求→开发→评审 cron 接力 + 任务状态机，即下文 §五「开发流程 agent-loop」。
2. **数据管道自修正闭环**（agent-loop-plan）——采集器 Think→Act→Observe→Verify 蓝图，即 §六。其门禁口径「热点<3 → fail」是 **CL005 放宽前的旧版**（时间线：plan 早期 → CL005 2026-09-02 放宽）——引用勿混。

另：**requirements 规范**（原 requirements-spec.md，内容见 §5.7，原件已归档 → documents/archive/theme-20260908/）是面向**人类编写者**的需求清单规范（agent-loop 的输入格式），非开发流程本身。

## 一、定位

本手册覆盖质量与工程流程：**质量门禁与重试优化**（CL005 quality-gate-relax）、**治理基线**（commit/命名/审计基础设施）、**清理类审查**（w6-cleanup / path-refs）、以及被整合的 **agent-loop 三份流程文档**。

素材：12 份 = quality-gate-relax 5 + governance 2 + cleanup 2 + agent-loop 3。

## 二、功能概述

- **质量门禁现状（2026-09-08 code 实核）**：`_verify()`（L1746）——4 实体维度（providers/people/tools/llms）全 0 → issue「实体提取为空（4 维度全 0）」（L1776-1778）；**热点 <3 仅 warning 不阻断**（L1781-1782「热点仅 N 条（未阻断）」）；事件中位新鲜度 >168h（7 天）→ issue；空 URL>5/截断>0/裸域名>2 → warning。`run()` L1745 `if not entities: return False` 拦 None（全源失败主拦截），L1757 防御保留。
- **重试现状**：LLM JSON 解析失败重试 **3 次**（extract_entities L1007，`range(1, 4)` L1106；CL005 由 5→3，耗时 324s→~216s < 300s）。
- **status checks**（L2137）：5 项 = 数据日期/实体数/质量门禁/Git 同步/**热点数**（L2238，<3 → warning 否则 info）；主 status_str 由 5 因子决定（not snapshot/新鲜度/连续失败≥3/quality_status/git_status），**不受 checks 项影响**（断 daily-checker heal 死循环）。
- **治理基线**：commit 格式 `type@scope: subject`，项目既定类型集 **{data, feat, fix, docs, auto-push}**（governance 2026-08-10 实测归纳；requirements-spec 早期表 {add, fixed, optimized, refactor, docs, test, chore} 为旧版 [待核，以 .review-level.yaml commit_types 为现行权威]）；审计基础设施 = `.review-level.yaml`（项目根）+ `review-log.md`（根聚合，Style B 固定名）；评审报告档案 = `documents/archive/reviews-20260908/`；2026-09-07 起根 `audit-log.md` 移除，per-task `tasks/<task>/audit-log.md` 保留。

## 三、机制与指令说明（质量门禁演变链）

1. **plan 蓝图（2026-06）**：`_verify` 4 检查=事件中位新鲜度>168h / 热点<3 / LLM 重试留痕 / 无任何变更 → issues → `_skip_push=True`。其中「热点<3 → fail」「重试留痕 → issue」两条后被 CL005 废除/放宽——本蓝图是现行门禁的早期对照。
2. **方案 D 降级（2026-08-10）**：URL 门禁（空>5/截断>0/裸域>2）由阻断降为 warning（记 `_quality_warnings`），门禁只留新鲜度 + 热点≥3。
3. **CL005 放宽（2026-09-02，当前态）**：见 §二。判定顺序改「先实体维度后热点维度」：实体>0 → quality_ok → auto-push 完整推送；实体 0 → fail 不 push。已知取舍 **SEC-001**：实体>0 无下限（单条新鲜垃圾实体可过门禁；3 健康源稳定产出 ~50 实体风险低，新鲜度优先质量为代价，显式声明）。精确语义（O-5）：实为「实体>0 **且 changelog 非空**→push」（全过期/无变更仍 skip，auto-push L402-408 类逻辑）。
4. **重试 5→3 耗时账**：实测 324s / 6 次调用 ≈ 54s/次 → 4 次 ≈ 216s，总耗时 <300s 为承诺（「≤200s」非承诺，N1 修正）；daily-checker 侧 per-checkpoint timeout=600s（全局 300s 不动）为硬兜底（D3，跨项目仅打印需求 prompt 由用户转交，落 cache/review-prep/cl005-daily-checker-handoff-prompt.md）。

## 四、用法示例

```bash
# 恢复/触发（D4 存量恢复）
lr run --force                       # 门禁通过（实体>0）→ push → 线上恢复；验证 dk check llm-radar 转 ok

# 状态观测（5 checks 含热点数）
lr status --json

# 测试（CL005 后基线；test_verify.py 为首批直接单测）
python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q   # 223+ passed
python3 -m pytest tests/test_verify.py -q          # 4 用例：热点0实体ok / 热点1 warning / 4维度全0阻断 / 热点≥3无警告

git checkout -- timestamp.json overview.json data/snapshot.json   # 跑完还原污染
```

## 五、开发流程 agent-loop（整合 agent-loop-design v1.0；跨 profile 协作闭环）

> 文档尾注自称版本 1.2（2026-07-11）而文件名 v1.0 [待核]；正文多处旧项目名 llm-radar.jaden.tech（rename 前保留层）。落地脚本已被治理审查交叉引用（非纸上设计）：`tasks/al-scanner.py` / `al-init.py` / `al-dev.sh` / `al-review.sh` + prompt。

### 5.1 定位与解决的问题

基于文件 + cron 接力的全自动编排，零外部依赖：解决 profile 隔离（dev/review/research 各开 TUI 手动传信息）、评审遗漏（cron 自动检测）、失败追踪（3 次失败自动升级人工）、进度不可视（状态机 + Markdown 报告）。

### 5.2 参与者角色

| 角色 | profile/session | 职责 |
|---|---|---|
| Requirement | research / news-radar | 编写/完善 `requirements.md` |
| Developer | dev | 读 requirements.md → 实现 → 测试 → commit → 写 features.md |
| Reviewer | review / news-radar-review | 读 demand.md + features.md → 评审 → 写 per-task audit-log.md |

### 5.3 cron job 编排（方案 B：多个独立 job 轮询）

| job | profile | 模式 | 频率 | 脚本 |
|---|---|---|---|---|
| scanner | ops | no_agent=True 纯 Python | 每 5 分钟 | tasks/al-scanner.py（状态判断/文件操作/git push） |
| developer-executor | dev | agent + script context | 每 10 分钟 | tasks/al-dev.sh |
| reviewer-executor | review | agent | 每 10 分钟 | tasks/al-review.sh |
| escalation-reminder | ops | no_agent=True | 每 6 小时 | 内置于 al-scanner.py |

各 job 经 flock 拿文件锁 `tasks/.agent-loop.lock`，拿不到跳过本轮（scanner 用 Python 非 Shell——支持 flock/yaml/sha256）。注册示例（原文）：`cronjob action=create name="llm-radar scanner" schedule="every 5 min" profile=ops script=tasks/al-scanner.py no_agent=true`（developer/reviewer 同构 10 min）。

### 5.4 核心文件与状态机

- 文件：`requirements.md`（项目根迭代需求）/ `tasks/active-task`（symlink → 当前活跃 task）/ `tasks/<dir>/task-manifest.yaml`（状态机）/ `demand.md`（需求快照锁定范围）/ `features.md`（developer 交付清单）/ `audit-log.md`（reviewer 报告，**per-task**；根聚合在 review-log.md）/ `tasks/agents-teamwork.yaml`（聚合进度）。
- manifest 字段：task_id（`al-YYYYMMDD-NNN`）/ title / state / retry_count（仅 review 步增加）/ max_retries: 3 / escalated / source + **source_hash**（sha256 去重）/ history（8 步）。
- 状态流：`created`（人工编辑 requirements.md）→ `demand`（人工确认锁定）→ `assigned`（scanner）→ `in_progress`（dev-executor）→ `review`（dev 写完 features.md）→ `passed`/`failed`（reviewer-executor；failed retry<3 → assigned、≥3 → escalated）→ `passed`+scanner git push → `closed`。流转约束：created→demand 与 escalated→assigned/demand 必须**人工**。

### 5.5 失败与异常处理

- 超时表：scanner 4 分钟（间隔 5min 跳过本轮）/ dev-reviewer-executor 9 分钟（间隔 10min；下轮发现 state 仍 in_progress 跳过不重复执行）；job 自身 signal.alarm(840) 14 分钟缓冲。
- 锁异常：锁 >15 分钟视为异常（STALE_THRESHOLD=900），scanner 每轮 `lock_is_stale()` 回收——in_progress 回退 assigned（打印「dev-executor 可能异常中断，已回退 state 为 assigned」）。
- Escalated 超 24h（ESCALATED_NOTICE_THRESHOLD=86400）→ 🚨 提醒（操作：设 state=assigned + retry_count=0）。
- **方案 C（已确认）**：失败不改 demand.md/requirements.md，失败详情记入 audit-log.md，developer 回归阅读修复。

### 5.6 人机速查

创建/更新需求 = 编辑 requirements.md；初始化 `python3 tasks/al-init.py "<标题>"`（`--demand` 直接就绪）；确认需求完成 = state=demand；查进度 `cat tasks/agents-teamwork.yaml`；人工介入 = 改 state + 重置 retry_count；3 次失败明细 `cat tasks/al-<id>/{demand.md,features.md,audit-log.md}`。

### 5.7 requirements 规范要点（整合原 requirements-spec.md → 已归档 documents/archive/theme-20260908/；N| 行号污染已于 2026-09-08 修复，本目即其现行载体）

- **定位**：结构化需求清单（非技术设计/非聊天记录），每条独立可验收；3 条以上批量、多文件改动 → 写入 requirements.md（1-2 条简单需求可对话）。
- **模板**：`# 迭代需求: <标题>` → `## 涉及文件` → `## Bug 修复`（场景/期望/实际）→ `## 功能新增`（场景/行为/验收）→ `## 强调` 4 条（每条独立 commit / 实现后跑 tests / commit 不 push（review 通过后自动 push）/ 验收不过 AI 修后重验）。
- **5 原则**：每条可独立测试（B 依赖 A 分两轮）/ 引用现有 documents/ 术语（不自创名词）/ 场景优先方案次之（**70% 场景 + 30% 行为期望**）/ 验收标准可观测（❌「代码逻辑正确」→ ✅「运行测试全部通过」）/ 区分 Bug 与 Feature（处理 Bug 不做增强，反之亦然）。
- **5 反模式**：需求外溢（「顺便改一下」）/ 只写行为不写场景 / 验收标准模糊（「性能更好」）/ 一个需求塞多个改动 / 不更新 documents/（变化标注「## 同步更新」）。
- **AI 协作流程**：写完 →「requirements.md 已更新，执行」→ AI 逐条**复述理解 + 验收方案** → 用户确认/修正 → 实现 → 测试 → commit（不 push）→ features.md 打印「实现功能清单 + 验证结果」表 → 用户验收。
- **默认约束**：验证须实测（不能「代码看起来没问题」）；验证通过后打印结果表；验证用例必做（测试不通过不得 commit）；Commit 但不 Push（commit type 表见 §二 治理基线——早期表与现行集不一致 [待核]）。

## 六、数据管道 agent-loop 蓝图（整合 pipeline/agent-loop-plan.md → 已归档 documents/archive/theme-20260908/；历史早期设计）

- 目标：Think → Act → Observe → Verify 闭环改造线性管道（Fetch→Extract→Merge→Push），自修正、可观测、质量门禁。
- [Think] 采集策略（间隔<6h skip / 3 fails 源降级 / 48h 事件优先）→ [Act] Fetch+Extract+Merge（7 源 parallel / LLM prompt rule 8 / 增量 merge+dedup）→ [Observe] `_observe()` 写 metrics.json（sources/llm/data/push 四类指标）→ [Verify] 门禁（见 §三-1 旧口径）→ Pass push / Fail 记录跳过。
- 增量实施 P0-P2（30+50+15+80 行）与 `feat/agent-loop` 分支策略；现已被 CL005 部分替代/落地：`_think`（现 L1708）、metrics.json、源降级、dead-letter 均为现行实现同源。「3 fails 源降级」设想对应实际 qbitai 79 连败/github-trending 29/huggingface 63 状态。

## 七、关键决策（原文编号）

### 族 A quality-gate-relax（LLM-RADAR-CL005, 2026-09-02）

- 根因三层（实测）：3 源长期降级素材不足（每天 3 健康源）/ LLM 提取超时（5 次重试 ×54s，总 358s > daily-checker 300s 预算）/ 热点 0 条 → 门禁失败不 push → 死循环（09-02 提取 53 实体热点 0）。
- 决策 **D1-D7**（探讨 3 轮 + 设计评审修正）：**D1**（1c）接受源降级不配 FlClash / **D2**（2a）重试 5→3 压到 ~200s / **D3**（3a）daily-checker per-checkpoint 600s 兜底 / **D4**（4a）落地后 `lr run --force` 存量恢复 / **D5**（1b+2b）门禁放宽：判定实体→热点，实体>0 → push（热点 0 也 push），实体 0 → fail / **D6**（4a）热点<3 仅 checks 附加 warning 不改变主 status / **D7**（1a 2a 3a）判定细节：先实体维度再热点维度。
- 评审链：review 80/B CONDITIONAL（**REA-1** 4 实体维度口径与分层拦截位置误述 / **RIG-1** 重试日志 4 处只列 1 处 / **RIG-2** status_str 因子枚举不准 / **RIG-3** ~40s/次 与实测 54s/次不符；**SEC-001** 取舍建议显式声明；O-1~6 含 O-5 精确语义、O-3 热点数读存量 [待核]）→ rereview 95/A PASS（4 🟡 全闭合 + **N1** §6 冒烟「≤200s」未同步放宽→改「<300s」/记录 ~216s + N2-N4 ℹ️）→ impl-audit **95/100 (A) PASS**（验收 12 项逐项 ✅；新 3 🟡 文档漂移 **DOC-1** _verify docstring 仍旧口径（审计中修）/ **DOC-2** features.md L57 旧口径（审计中修）/ **DOC-3** AGENTS.md L82/L145 protected 待用户改）+ ops-check（独立复跑 1-6 全过；计时验证推迟至 review push 后——防 auto-push 带上未审计 commit）。
- 遗留：DOC-3（P2 用户侧）/ D4 存量恢复（P1）/ O-1 计时验证（P2）。

### 族 B 治理 generic（2026-08-10）

- v1.0 CONDITIONAL PASS 80/B（审 5 commit，4 🟡：b3ce8de `chore@project` 不在类型集、features.md 前导 YAML 缺字段 N-1、review-log 仍模板 N-2、review-log 0 条目 vs .review-level.yaml 4 条审计轨迹 gap）→ v1.1 PASS 100/A（0058fcb data / 63de4b3 fix 默认模型 v4-flash→deepseek-chat 全合规）。**B 族终审 100/100 (A)**。
- 治理基线见 §二；commit_types 可在 .review-level.yaml 扩展。

### 族 C 清理类

- **w6-cleanup-rereview**（2026-09-07，PASS 100/100 findings_open 0）：**F1** 🔴 al-scanner.py `handle_passed()` 写已删根 audit-log.md（open(...,"a") 静默重建）→ 修 5f63370 改 `tasks/al-scanner.py:203-204` root_log=review-log.md；**F2** 🟡 design 文档 4 处 audit-log.md 引用 → 修 af38d47；**L23** 🟢 裁定 requirements.md 为活跃工作流输入（al-init.py:27/al-scanner.py:161 主动读取）「维持原文正确」非缺陷；L201 per-task audit-log 保留正确。
- **path-refs-review**（2026-08-23，PASS 100/A）：目录改名 jaden.tech→.lab 活跃层旧路径零残留；**LR-SEC-018/019** 🟢 record-only（subject 与 diff 不符 / handoff 命名漂移）。documents/loop/ 属保留旧名层（agent-loop-design 在排除/保留集）。

## 八、已知坑

1. **「agent-loop」双义**：开发流程闭环 vs 数据管道闭环；引用必须指明（本文 §〇）。
2. **requirements 规范行号污染（已修复）**：原 documents/loop/requirements-spec.md（→ 已归档 documents/archive/theme-20260908/）297 物理行全带 `N|` 前缀（嵌号==物理行号，自洽）；2026-09-08 phase-3 剥前缀修复（修复后内容即本手册 §5.7）。
3. **commit type 集三处不一致 [待核]**：requirements-spec 早期表 vs governance 既定集 {data,feat,fix,docs,auto-push}——以 .review-level.yaml commit_types 为现行权威。
4. **门禁行号随实现漂移**：CL005 设计时点（L779/1419-1463）、实现审计时点（L780/1449-1454）、CL006 后现时点（L1106/1746-1782/2238）三套——引用注明时点。
5. **「实体>0 即 push」勿简写**：实际含 changelog 非空条件（全过期/无变更仍 skip）。
6. **热点数 check 读 snapshot 存量**非本次 run 提取数（O-3 遗留，语义未显式敲定 [待核]）。
7. **DOC-3 AGENTS.md 门禁表述仍旧口径**（protected 文件，用户侧改 P2）；改前引用以本手册 §二为准。
8. **w6 根审计日志已废弃**：新审计追记根 review-log.md；per-task tasks/<id>/audit-log.md 仍活跃——写入位置别弄反。
9. **agent-loop 落地脚本是活的治理对象**：al-scanner.py/al-init.py/al-dev.sh/al-review.sh 已被清理/路径审查引用；改 requirements.md 触发 scanner 流转属正常，勿误当 WIP。
10. **CL005 计时验证跨项目**：daily-checker per-checkpoint 600s 为外部配置（D3 prompt 转交），本仓不改。

## 九、参考文档

| 源文件（原位 documents/…） | 角色 | 处置 |
|---|---|---|
| solutions/llm-radar-quality-gate-relax-design-v1.0-20260902.md | CL005 design | 已归档 → archive/solutions-20260908/ |
| reviews/llm-radar-quality-gate-relax-design-review-v1.0-20260902.md | CL005 评审 | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-quality-gate-relax-design-rereview-v1.1-20260902.md | CL005 复审 | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-quality-gate-relax-impl-audit-20260902.md | CL005 审计（族终审） | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-quality-gate-relax-ops-check-20260902.md | CL005 ops 核查 | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-governance-review-v1.0-20260810.md | 治理审查 v1.0 | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-governance-review-v1.1-20260810.md | 治理审查 v1.1（族终审） | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-w6-cleanup-rereview-v1.0-20260907.md | 清理复审（终审） | 已归档 → archive/reviews-20260908/ |
| reviews/llm-radar-path-refs-review-v1.0-20260823.md | 路径清理审查 | 已归档 → archive/reviews-20260908/ |
| loop/agent-loop-design-v1.0-20260711.md | agent-loop 开发流程设计（Q4 整合入 §五） | 已归档 → archive/theme-20260908/ |
| loop/requirements-spec.md | 需求编写规范（Q4：N| 污染已修复，内容即 §5.7） | 已归档 → archive/theme-20260908/ |
| pipeline/agent-loop-plan.md | 数据管道闭环蓝图（Q4 整合入 §六） | 已归档 → archive/theme-20260908/ |

相关现行保留项（不归档）：`review-log.md` + `.review-level.yaml`（项目根，审计基础设施）、`tasks/`（agent-loop 落地脚本/状态，现行工作流）、`requirements.md`（活跃工作流输入，不存在则 al-init.py 建空占位）、AGENTS.md（protected；DOC-3 待用户改）、`cache/doc-consolidation/llm-radar-quality-loop-extract.md`（gitignored 提炼产物）。三份 loop 原件已于 2026-09-08 随 docs@archive 归档（documents/archive/theme-20260908/），本手册 §五/§5.7/§六 即其现行载体（档案注：agent-loop-design 文件名 v1.0 尾注 1.2 [待核]；requirements-spec N| 污染已修复，内容即 §5.7）。
