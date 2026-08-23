# llm-radar CLI 治理与全局注册 — re-review报告 v1.1

> 日期: 2026-08-23
> 文件: documents/solutions/llm-radar-cli-governance-design-v1.1-20260823.md
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.jaden.tech
> 待 push commit: 7bd8f26 (docs@design v1.1), a714a7c (docs@design v1.0), 552307e (docs@handoff)
> 上轮评审: documents/reviews/llm-radar-cli-governance-review-v1.0-20260823.md (70/B CONDITIONAL, 6 🟡 + 3 🟢)
> review维度: 合理性 / 严格性 / 安全性 + 治理合规
> review者: Security Reviewer (IRIS) / hermes-1.2.0

## 数据验证

| # | 验证项 | 方法 | 结果 |
|:-:|:-------|:-----|:-----|
| 1 | REA-11 文件名修正 | grep 'mcp-server' v1.1 文档 | ✅ 仅 L191 `llm-radar-mcp-server.py`, 无 `mcp-server.py` 裸引用残留 |
| 2 | RIG-1 二选一删除 | grep '二选一' | ✅ 0 命中; CRITICAL_HOURS 独立常量 L139 (`LLM_RADAR_CRITICAL_HOURS` env, 默认 48) |
| 3 | RIG-1 49h 近似残留 | grep 'STALE_HOURS\*7\|49h' | ✅ L143 仅为解释性说明 ("不采用 STALE_HOURS*7=49 的近似"), 非可选方案 |
| 4 | RIG-2 .env 实现路径 | read L182-185 | ✅ fork 项目内模板 + `set -a; source .env; set +a` 于 exec 前, 与 llm-radar-run.sh 模式一致 |
| 5 | RIG-3 install.py 模板耦合 | read script-miner/skills/cli-registry/scripts/install.py + templates/wrapper.sh.tmpl | ⚠️ 前提属实 (wrapper.sh.tmpl:77-78 硬编码 `~/CodeSpace/script-miner/cache/cli-registry/calls.log`), fork+移除方案明确; 但 **install.py 无 --template 标志** (L20 `TEMPLATE = SKILL_DIR/"templates/wrapper.sh.tmpl"` 硬编码, L90 直读; main() 仅支持 --dry-run/--force/uninstall, 其余参数静默忽略) → 新发现 RIG-10 |
| 6 | RIG-4 测试隔离方案 | read L194-200 + conftest.py + collector.py:43-45 | ✅ fixture 方案明确 (patch project_root 到 tmp + 预置 3 文件); ⚠️ 附注: DATA_DIR/SNAPSHOT_PATH 为模块常量 (collector.py:43-45), status 读取必须走 project_root 派生路径, 否则 fixture 静默失效 → O-4 |
| 7 | RIG-5 连续失败级别 | read L121,127-129 + python3 json.load data/metrics.json | ✅ 锁定全局 `consecutive_fails` (run 级); 实测全局=0, source_health.qbitai=37 — 与设计"单源 37 连败是常态"陈述一致 |
| 8 | RIG-6 timestamp 路径 | grep collector.py | ✅ L126 标注"项目根, 非 data/"; collector.py:375/1305 `self.project_root / 'timestamp.json'` 证实 |
| 9 | RIG-7 分叉检测语义 | read L131-132 | ✅ 注明基于本地 origin/main ref, 不主动 fetch, 记录过期语义 |
| 10 | RIG-9 文本输出 | read L145-149 | ✅ §4.5 定义单行摘要, 对齐 dt-status, 无 emoji 前缀 |
| 11 | RIG-3 环境可用性 | conda env list + py3.12 python import | ✅ 本 Mac conda py3.12 存在且含 openai/selenium/requests/bs4/prettytable — 设计示例 `env.conda: py3.12` 本机可用 (O-5: Linux 主机需 llm-radar env) |
| 12 | 页脚版本 | tail v1.1 文档 | ⚠️ L225 仍写 `*版本: 1.0*`, frontmatter 1.1 / 文件名 v1.1 — 修复轮未触及的残留 → O-2 |
| 13 | 示例数字占位符 | read L103 | ⚠️ 仍为 "288 (100/43/100/45/47)" 占位符 (实测 stats 100/50/100/55/61), 未标注 → O-3 (v1.0 RIG-8 残留) |
| 14 | 文档命名/frontmatter | head v1.1 文档 | ✅ kebab-case 无点无下划线, 文件名 v1.1 与 frontmatter version: 1.1 一致, 日期 20260823, type: design, profile: ops, 修订记录 L19-24 完整 |
| 15 | commit 格式 | git log 7bd8f26 | ✅ `docs@design: llm-radar CLI 治理设计 v1.1 — 评审修正 6 🟡 + 3 🟢 (CL-SEC11)` — type@scope 合规 |
| 16 | 验收标准 8 条 | read §8 | ✅ 全部可测 (help 一致性/七字段/四态/无 snapshot critical/--force 绕过/exit=0/无副作用/入 git/回归绿) |

## Fix Verification (逐项核对)

| # | v1.0 问题 | v1.1 修复 | 验证 |
|:-:|:----------|:----------|:----:|
| REA-11 | 🟡 §6 引用 mcp-server.py | L191 改为 llm-radar-mcp-server.py | ✅ |
| RIG-1 | 🟡 48h 二选一未锁定 (49≠48) | L139 锁定 CRITICAL_HOURS=48 独立常量 | ✅ |
| RIG-2 | 🟡 wrapper .env 无实现路径 | L182-185 fork 模板 + set -a source .env | ✅ |
| RIG-3 | 🟡 install.py 模板硬编码 calls.log | L172-176 fork 模板 + 移除/改写统计段 | ⚠️ fork 本身 ✅, 但 "install.py --template" 机制不存在 → RIG-10 |
| RIG-4 | 🟡 测试隔离只提示无方案 | L194-200 fixture patch project_root + 预置 3 文件 | ✅ (附 O-4 路径注意) |
| RIG-5 | 🟡 连续失败 ≥3 级别未明确 | L121,127-129 锁定全局 run 级 consecutive_fails | ✅ |
| RIG-6 | 🟢 timestamp.json 路径未标注 | L126 标注项目根 | ✅ |
| RIG-7 | 🟢 分叉检测未注明不 fetch | L131-132 注明本地 ref 语义 | ✅ |
| RIG-9 | 🟢 无 --json 输出未定义 | L145-149 §4.5 文本输出 | ✅ |

6 🟡 + 3 🟢 修复 8.5/9 逐项落地; RIG-3 核心意图 (fork + 隔离 calls.log) 达成, 但交付机制引用不存在标志。

## 合理性评估

| # | 项 | 结果 |
|:-:|:---|:-----|
| REA-1 | v1.1 无架构性改动, D1-D7 决策保持 | ✅ |
| REA-2 | §4.5 文本输出对齐 dt-status 先例, 与 --json 双轨清晰 | ✅ |
| REA-3 | fork 模板方案 (RIG-2/RIG-3) 保持项目自治, 不依赖 script-miner 目录 | ✅ |

## 严格性评估

| # | 项 | 结果 |
|:-:|:---|:-----|
| RIG-10 | 🟡 §5.2 "用 install.py --template 指向 fork 模板" — **install.py 无此标志** (TEMPLATE 硬编码 install.py:20, main() 仅 --dry-run/--force/uninstall, 未知参数静默忽略) | 照字面执行会静默用回硬编码模板 → calls.log 污染重现, 修复失效且无报错。修法: ① 扩展 install.py 增加 `--template <path>`; ② 或放弃 install.py, 手工从 fork 模板生成 wrapper (sed 填充 {{name}}/{{target_script}}/{{python}}/{{conda_env}} + chmod 755 + ln -sf), 自包含于项目内。推荐 ②, 零跨项目改动 |
| O-4 | 🟢 RIG-4 fixture 依赖 status 读取路径写法 | DATA_DIR/SNAPSHOT_PATH 是模块常量 (collector.py:43-45), patch 仅 project_root 时, 若 status 读 self.data_dir/self.snapshot_path 仍命中真实数据。建议: status 读取统一走 `self.project_root` 派生路径, 且 fixture 防御性同步 patch data_dir/snapshot_path |

## 安全事项

🟢 SEC-1 — 修复未改变 status 全只读约束 (timestamp/metrics/snapshot + git rev-list), 无新副作用面。

🟢 SEC-2 — fork 模板移除 script-miner calls.log 统计段, 消除跨项目目录写脏 (RIG-3 核心意图), 无权限面变化。

🟢 SEC-3 — RIG-10 修法 ② 手工生成 wrapper 不引入 shell 注入面 (占位符均为项目内静态值)。

## 治理合规

| # | 项 | 结果 |
|:-:|:---|:-----|
| GOV-1 | 文件名 v1.1 + frontmatter version: 1.1 + 修订记录 L19-24 三方一致 | ✅ |
| GOV-2 | commit 7bd8f26 `docs@design:` 格式合规, 主题含修复范围 | ✅ |
| GOV-3 | 验收标准 8 条与章节对应, 全部可测 | ✅ |
| GOV-4 | O-2 页脚 "版本: 1.0" 与 frontmatter 1.1 不一致 (页脚非权威字段, 仅观感) | 🟢 |

## 评分

v1.0 扣分项已全部修复 (6 🟡 → 0) → 基数回到 100, 仅计新增项:

| 级别 | 数量 | 扣分 |
|:-----|:-----|:-----|
| 🔴 HIGH | 0 | 0 |
| 🟡 MEDIUM | 1 (RIG-10) | -5 |
| 🟢 LOW | 5 (RIG-8 残留, O-2, O-3, O-4, O-5) | 0 (记录) |

得分: **95 / 100 → A**

## 结论

**PASS (95/A)** — 上轮 6 🟡 + 3 🟢 修复逐项核实, 8.5/9 完全落地, RIG-3 核心意图达成。1 个新 🟡 (RIG-10: install.py --template 不存在) 为非阻塞实施细节, 已作为核心变更 #5 修法并入实现 prompt, dev 实施时按推荐修法 ② (手工从 fork 模板生成 wrapper) 执行即可。可进入 dev 实施。

**实现 prompt 已生成**: cache/review-prep/prompt-llm-radar-cli-governance-impl-20260823.md

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | RIG-10: §5.2 "install.py --template" 不存在 — 实施时按修法 ② 手工生成 wrapper, 或扩展 install.py 加 --template (推荐 ②, 已并入 impl prompt #5) | 严格性 🟡 |
| □ | RIG-8: §4.1 示例数字仍为占位符 (288/100/43/100/45/47), 建议标注 "示例占位" | 严格性 🟢 |
| □ | O-2: 页脚 L225 "版本: 1.0" 改为 1.1 (frontmatter 已是 1.1) | 治理 🟢 |
| □ | O-4: status 读取统一走 self.project_root 派生路径; fixture 防御性同步 patch data_dir/snapshot_path | 严格性 🟢 |
| □ | O-5: .cli-registry.yaml 示例 env.conda 为 py3.12 (本 Mac 可用); Linux 主机按 AGENTS.md 需改 conda `llm-radar` env, 建议示例加注 | 合理性 🟢 |

---

*报告: documents/reviews/llm-radar-cli-governance-rereview-v1.1-20260823.md | 上轮: documents/reviews/llm-radar-cli-governance-review-v1.0-20260823.md | 结论: PASS 95/A | 实现 prompt: ✅ 已生成 (cache/review-prep/prompt-llm-radar-cli-governance-impl-20260823.md)*
