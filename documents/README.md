# llm-radar 文档中心

本目录是 llm-radar.lab 的**知识底座索引**：6 份主题手册为现行知识入口（机制/决策史/坑），
保留原位主题说明与手册并存，一次性过程文档（design/review/audit/verify 等）按归档口径
移入 `archive/{solutions,reviews,theme}-20260908/`。

## 主题手册（documents/handbooks/，编制 2026-09-08，现行知识底座）

| 手册 | 覆盖主题 | 素材桶（份数） | 说明 |
|---|---|---|---|
| [git-sync](handbooks/llm-radar-git-sync-handbook-v1.0-20260908.md) | 双机同步与 git 自愈：force 决策反转史、方案 D 全链自愈、语义并集收敛（CL006） | solutions+reviews（18） | 决策史索引，机制以 code 现行行号锚点为准 |
| [cli-governance](handbooks/llm-radar-cli-governance-handbook-v1.0-20260908.md) | CLI/工程治理：12 子命令面、CL-SEC11 决策、prompt 供给、runtime-files 布局 | solutions+reviews（13） | 含 LR-SEC-011~017 注册 |
| [collector-pipeline](handbooks/llm-radar-collector-pipeline-handbook-v1.0-20260908.md) | 采集与数据流双 pipeline：data-flow 骨架 + X 热点 v1.3 终态（CL-SEC19/20） | 主题子目录+solutions+reviews（10） | twitter-collector CLI/常量逐字实核 |
| [frontend](handbooks/llm-radar-frontend-handbook-v1.0-20260908.md) | 站点渲染/前端：emoji 约定 + CL001 弹框/CL002 加载/CL003 拷贝降级 | emoji-mapping+solutions+reviews（11） | index.html 现行行号锚点 |
| [ops](handbooks/llm-radar-ops-handbook-v1.0-20260908.md) | 部署/cron/探针：Linux 环境、CI、health 三态退出契约、hermes cron wrapper | 主题子目录+solutions+reviews（8） | O-1/O-2 编号出处 |
| [quality-loop](handbooks/llm-radar-quality-loop-handbook-v1.0-20260908.md) | 质量与流程：门禁演变链（CL005）、治理基线、开发流程闭环、requirements 规范 | solutions+reviews+loop（12） | 整合三份 agent-loop 文档 |

手册 frontmatter：`author=hermes-v0.20.6(2026.8.27) profile=dev type=summary date=2026-09-08`；
素材提炼（gitignored）：`cache/doc-consolidation/llm-radar-{domain}-extract.md` ×6。

## 保留原位（不归档，与手册并存）

- 主题说明（现行参考/骨架，手册 §参考文档 列明漂移点）：
  `emoji-mapping-v1.0-20260713.md`（根）、`pipeline/data-flow-v1.0-20260622.md`、
  `ops/linux-deployment-v1.0-20260701.md`、`ops/github-ci-issues-v1.0-20260704.md`、
  `mcp/mcp-protocol-design-v1.0-20260623.md`、`integ/hermes-integration-v1.0-20260624.md`
- 流程/交接件：`handoff/`（跨 profile 交接清单；.hermes-project.yaml 引用 ops 一份）
- 治理/工作流面（仓库根或独立体系，不在本目录）：`review-log.md`、`.review-level.yaml`、
  `AGENTS.md`（protected，DOC-1/DOC-3 待用户改）、`tasks/`、`requirements.md`（活跃输入）、
  仓库根 `features.md`
- 早期归档（2026-07-11 批）：`archive/` 根下 6 份（含 features.md，排除知识库同步）

## 归档口径（2026-09-08 docs@archive）

一次性过程文档 76 份 → `documents/archive/{solutions,reviews,theme}-20260908/`：

| 桶 | 计数 | 内容 |
|---|---|---|
| `archive/solutions-20260908/` | 14 | design 终版（impl-v1.0 按 Q3 迁 reviews 桶） |
| `archive/reviews-20260908/` | 50 | review/rereview/impl-audit/ops-verify/ops-check/audit（含迁入的 git-flow-fix-impl-v1.0） |
| `archive/theme-20260908/` | 12 | 主题子目录一次性批 + Q4/Q6/Q7 附注件 |

Q3 改名（同批 docs@sync）：reviews 桶 4 份 `llm-radar-fork-converge-*` → `llm-radar-git-fork-converge-*`；
`cl005-fork-merge-audit` → `cl005-git-fork-merge-audit`；`git-flow-fix-impl-v1.0` 由 solutions 迁 reviews 桶。
Q4：`loop/requirements-spec.md` → archive/theme-20260908/：剥 `N|` 行号前缀修复（内容 = quality-loop handbook §5.7）。
Q6/Q7：supabase-migration / hotspot-summarize（未落地）、search-tips / github-emoji-conventions（通用非项目特有）附注后归档。

**编号纪律**：正文引用决策编号（D1-D7 / RIG-1~9 / LR-SEC / OBS 等）须带来源报告/闭环
（如 CL005 评审报告），仅凭编号无法定位；族终审结论以各手册 §关键决策 为准。
