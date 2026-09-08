# llm-radar git flow fix — review报告 v1.1

> 日期: 2026-08-12
> 文件: documents/solutions/llm-radar-git-flow-fix-design-v1.1-20260812.md
> 项目路径: ~/CodeSpace/llm-radar.jaden.tech
> 待 push commit: db8d792 (v1.0), 5254ea4 (v1.1)
> review维度: 合理性 / 严格性 / 安全性 + Commit 规范 / 命名规范

## 数据验证

| 验证项 | 方法 | 结果 |
|:-------|:-----|:-----|
| 未 push commit 数 | `git log origin/main..HEAD --oneline \| wc -l` | 2 |
| 设计文档行数 | `wc -l` | 214 行 |
| design doc 版本 | 读取 frontmatter `version` | 1.1 |
| 代码 subprocess 模式 | `grep -n 'shell=True\|os\.system\|eval(' llm-radar-collector.py` | 0 处 (全部 list-form) |
| `_auto_push()` 当前实现 | `read_file llm-radar-collector.py:223-281` | 有 push 无 rebase 重试/force-with-lease — 与设计描述的现状一致 |
| `run()` 中 git pull | `read_file llm-radar-collector.py:1878-1880` | `git pull --rebase` — 与设计描述的根因一致 |
| `_write_snapshot/_write_timestamp/_write_overview` | `search_files` 确认存在 | 3 个函数均存在，无冲突标记检测 — 与设计一致 |
| 冲突标记检测逻辑 | `grep '<<<<<<< HEAD' llm-radar-collector.py` | 0 处 — 未实现（设计中 D3 待实施） |

## 合理性评估

### 评分表

| # | 项 | 评估 |
|:-:|:---|:----:|
| 1 | 根因分析完整性 | ✅ 四级根因链 (两机分叉 → pull-rebase 无兜底 → run 继续执行 → auto-push 无恢复), 附 2026-08-12 时间线还原 |
| 2 | 方案对比 | ✅ 4 方案 (A/B/C/D) 各有优缺点表, D 被选中并给出理由 |
| 3 | 与真实事件的对齐 | ✅ 直接对应 7/14 (27 天冻结) + 8/12 (68 实体丢失) 两次事故 |
| 4 | D1-D4 模块划分 | ✅ 4 个独立模块, 各自对应根因链的一环: 同步→推送收敛→文件防护→频率 |
| 5 | 非目标声明 | ✅ 明确 4 项不改变的范围 |
| 6 | 确认项集成 | ✅ A1 B1 C1 D2 已映射到最终实施范围 |
| 7 | 时序说明明确性 | ⚠️ REA-1: D1 说"本地优先, 交给 auto-push 收敛", 但 D1 skip 同步后本地数据尚未 commit — 隐含依赖 run 后续的 write→auto-push 流程。文档可显式标注 "D1 不 commit, D2 阶段 commit+push" |

**评级**: 🟢 (1 处澄清建议)

## 严格性评估

### 评分表

| # | 项 | 评估 |
|:-:|:---|:----:|
| 1 | 验收标准可测性 | ✅ 5 条标准全部可操作 (`--force` 验证、模拟分叉、冲突标记检测、rejected 场景、crontab 检查) |
| 2 | 错误状态覆盖 | ✅ 所有 git 失败 → warning, 不阻断 run; rebase 残留检测 §D1+§D2 |
| 3 | 性能影响 | ✅ 6h 防抖保证实际 API 调用频率不变; 每小时 cron 仅增加 cron 触发开销 |
| 4 | 风险评估 | ✅ 4 项风险各有缓解措施 |
| 5 | checkout --theirs 边界 | 🟡 RIG-1: `checkout --theirs` 仅在文件已 git-tracked 时有效。若目标文件为 untracked (首次创建或 gitignored), `checkout --theirs` 会失败。建议增加文件跟踪状态检查, untracked 时直接删除/重置 |
| 6 | fetch 失败场景 | 🟡 RIG-2: D1 流程只处理"分叉"和"快进", 未覆盖 `git fetch` 本身失败(网络中断/认证过期/远端不可达)。建议 fetch 超时 + 失败 warning, 继续 run |
| 7 | 写盘函数调用时序 | 🟡 RIG-3: D3 的三个 `_write_*` 与 D1 `_sync_remote()` 和 D2 `_auto_push()` 的调用顺序未在文档中明确。当前代码 run() 的顺序是: git pull → 采集 → 提取 → 写盘 → auto-push。设计应标注 "写盘在 _sync_remote 之后、_auto_push 之前" |

**评级**: 🟡 (3 处遗漏/模糊)

## 安全事项

🟢 无安全发现。

| 检查项 | 结果 |
|:-------|:----:|
| subprocess 模式 | ✅ 全部 list-form (`subprocess.run(['git', ...])`) — 0 处 `shell=True`/`os.system()` |
| `--force-with-lease` | ✅ 正确使用 lease 保护, 仅当本地 rebase 成功后调用 |
| 冲突标记检测 | ✅ 内容字符串匹配 (`<<<<<<< HEAD`) — 无 eval/exec |
| 新增依赖 | ✅ 无 (纯 git CLI 操作) |
| 凭证暴露 | ✅ 无 |
| 输入注入 | ✅ git 参数均为硬编码字符串 |

## Commit 规范评估

| # | SHA | Subject | Type | Scope | 验证 |
|:-:|:-----|:--------|:-----|:------|:----:|
| 1 | db8d792 | `docs@design: llm-radar git flow fix — root cause + auto-heal sync/push design v1.0` | docs ✅ | design ✅ | ✅ |
| 2 | 5254ea4 | `docs@design: llm-radar git flow fix v1.1 — record confirmed A1 B1 C1 D2` | docs ✅ | design ✅ | ✅ |

项目既定类型集: {data, feat, fix, docs, auto-push}。2/2 ✅。

## 命名规范评估

| 检查项 | 文件 | 结果 |
|:-------|:-----|:----:|
| 设计文档 | `llm-radar-git-flow-fix-design-v1.1-20260812.md` | ✅ kebab-case, topic-type-version-date |
| 目录 | `documents/solutions/` | 🟢 合法子目录 (项目首次使用, 非违规) |
| Frontmatter 字段 | title/topic/type/version/date/author/tags | ✅ 7 字段完整 |
| v1.0 → v1.1 | git rename (db8d792→5254ea4) | ✅ 清晰追溯 |

## 评分

| 扣分项 | 严重度 | 扣分 |
|:-------|:------:|:----:|
| REA-1: D1 "本地优先" 时序依赖未显式标注 | 🟡 | -5 |
| RIG-1: checkout --theirs 对 untracked 文件未覆盖 | 🟡 | -5 |
| RIG-2: fetch 失败场景未覆盖 | 🟡 | -5 |
| RIG-3: 写盘函数调用时序未显式标注 | 🟡 | -5 |

**得分**: 100 - 20 = **80 / 100 → Rating: B**

| 🔴 | 🟡 | 🟢 |
|:--:|:--:|:--:|
| 0 | 4 | 2 |

## 结论

**CONDITIONAL PASS** — 设计方案架构正确, 根因分析扎实, 方案 D 全链路自愈逻辑完整。4 个 🟡 均为边界覆盖/文档澄清, 可在实施中一次性修正, 不阻塞开发启动。

### 修改意见 (按编号)

| 编号 | 问题 | 建议改法 |
|:---|:---|:---|
| REA-1 | D1 时序依赖未显式 | 在 D1 描述末尾加一句: "D1 仅同步,不 commit。本地数据在 run() 后续 write→auto-push 流程 commit+push。" |
| RIG-1 | checkout --theirs 对 untracked 无效 | D3 增加: "若文件不在 git 跟踪中(git ls-files --error-unmatch), 则直接删除/重置为空, 而非 checkout --theirs" |
| RIG-2 | fetch 失败未覆盖 | D1 流程第 4 步增加: "若 git fetch 失败(超时/网络), 记 warning, 跳过同步, 继续 run" |
| RIG-3 | 写盘时序未标注 | 在 "实施范围" 表格或 D3 末尾加一行: "调用顺序: _sync_remote → 采集 → 提取 → D3 写盘函数 → _auto_push" |

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | D1 时序依赖显式标注 "D1 不 commit, D2 负责" | 合理性 🟡 |
| □ | checkout --theirs 失败兜底 (untracked 文件) | 严格性 🟡 |
| □ | fetch 失败场景覆盖 (超时/网络中断 → warning → 继续) | 严格性 🟡 |
| □ | 写盘函数调用时序在文档中显式标注 | 严格性 🟡 |
