# llm-radar 双端分叉自动收敛 — 复审报告 v1.1-r2

> 日期: 2026-09-06
> 文件: documents/solutions/llm-radar-git-fork-converge-design-v1.1-r2-20260906.md
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.lab
> 复审对象: 5c1bf42 docs@llm-radar: git fork auto-converge design v1.1-r2 fix RIG-7~9 (CL006)
> 上轮结论: v1.1 CONDITIONAL PASS 85/100 — 3 新 🟡 (RIG-7/8/9)
> review维度: 合理性 / 严格性 / 安全性
> closed_loop: LLM-RADAR-CL006
> 本轮: 仅评审，不 push（PASS 后由 ops 执行 Phase 0 收敛并 push，随后另行调度实现审计）

```
┌─ DESIGN RE-REVIEW ─────────────────────────────────┐
│  Document: llm-radar-git-fork-converge-design-v1.1-r2 │
│  Version : v1.1-r2                                  │
│  Commit  : 5c1bf42                                  │
├─────────────────────────────────────────────────────┤
│  合理性   🟢 (根因/方案不变, 三轮已代码级确认)        │
│  严格性   🟢 (RIG-7/8/9 全修, 无新矛盾)             │
│  安全性   🟢 (v1.4 契约维持, 0 新攻击面)            │
│  结论     PASS — 100/100 (A)                        │
└─────────────────────────────────────────────────────┘
```

## 分叉实况复核 (2026-09-06)

- 本地 main = 5c1bf42 (HEAD)，远端 origin/main 落后于本地的另一链，merge-base = af48ced。
- `git rev-list --left-right --count origin/main...HEAD` = 3 / 7，即本地 ahead 7、远端 ahead 3。
- 与 v1.1 复审时 (5/3) 相比本地又增 2 个 commit（e90fb2d audit@review + 5c1bf42 本文档），符合「分叉只增不减、仅 Phase 0 收敛」的预期。设计 L91 已声明「执行前 fetch 以当时实况为准，不承诺固定 SHA」，RIG-3 修复对此类漂移免疫，本轮复核继续成立。

## Fix Verification（逐项核对）

| # | v1.1 问题 | v1.1-r2 修复 | 验证 |
|:-:|:----------|:-------------|:----:|
| RIG-7 | overview.json D1 规则遗漏 v/r/rd 三字段 + h top3 截断未声明 | D1 L115 补全 7 字段：v 任一侧(恒1) / t,p,r,rd 取较新侧 / s 合并后 snapshot 各维度 len 重算 / h 按 (date,hot_score) 降序 top3 重算(非并集) | ✅ 与 `_write_overview` L1358-1366 逐字段一致（v/t/p/s/h/r/rd 7 字段、s 键 pr/pe/to/ll/ho、h 按 (date,hot_score) 降序 [:3]） |
| RIG-8 | partial→converge 与 D2 脏工作区守护矛盾（dirty 拦截致兜底 no-op） | D3 L172 锁定：partial push 失败 → 先 `git checkout -- data/snapshot.json overview.json` 丢弃未提交质量失败数据 → 工作区 clean → `_converge_fork()`；dead-letter `changelog_count:0 / changelog_snapshot:[] / error:'partial...'` | ✅ 行号全属实：`_save_snapshot` L1164 / `_write_overview` L1168 / partial `git add timestamp.json` L399 / `_write_dead_letter` L332-347（changelog_count/snapshot 契约一致）；丢弃数据未 push、下轮重生成，无损（历史好数据在上一 commit） |
| RIG-9 | 多时间字段优先级未定（较新侧无定义，跨机不确定） | D1 L126 规则 2 锁定 `last_event_date` > `date` > `updated_at`（存在即用、不交叉比较；updated_at 仅无语义日期 fallback）+ 单测多时间字段冲突断言（L187） | ✅ 规则自洽、确定性成立；updated_at 降级为 fallback 解决了 v1.1 指出的「run 时间戳误导较新侧」问题 |

## 新增发现

无 🟡/🔴。发现 1 项 🟢 观察（非阻塞，0 扣分）：

### 🟢 O-4 — twitter-targets.yaml 在 D1「数据白名单」表内但标注「非本设计合并对象」

D1 表（L110-118）标题「数据白名单（自动收敛仅处理这些 tracked 生成文件…）」共列 5 行，其中 `data/twitter-targets.yaml` 行（L118）的合并规则为「非本设计合并对象（配置变更走人工，极少双写）」；而背景 L59 写「前者（twitter.json）纳入收敛白名单」（隐含 twitter-targets.yaml 不在白名单）。三者措辞存在轻微张力：表头「仅处理这些」vs 其中一行「非处理对象」。

- 意图明确（config 冲突 → 人工 abort，不自动解决），无安全/确定性影响；D2 步骤 4「含白名单外文件 → abort 人工」的语义仍可正确落地（twitter-targets.yaml 应视为白名单外）。
- 建议（实施时一行澄清即可）：将 twitter-targets.yaml 移出「数据白名单」表，或在 L118 标注「白名单外 — 冲突 abort 人工」，避免实现者误将 5 行全当可自动合并对象。

## 安全事项

🟢 与 v1.4 安全契约一致性维持（复评要点 2）：

- 全程无 force push（D2 L157）；D3 L171 删 rebase 成功后 `--force-with-lease` 改普通 push，与 v1.0 SEC-1 结论一致。
- 白名单外冲突 abort 人工（D2 L158）、异常不抛不阻断采集（L160）、finally 清理残留态（L159），延续 v1.4 边界。
- 0 注入面：`_converge_fork` 走 `_git_run` list-form、固定 merge 消息、JSON 读写无代码执行（v1.0 SEC-3 结论不变）。
- 确定性成立（复评要点 2）：并集按 id、字段级合并空值填补 → 时间优先级（RIG-9 已锁定）→ JSON 字典序 tie-break（数字转字符串 + Unicode 码点），不依赖执行机 / merge 方向，跨机收敛结果一致且幂等可交换。

RIG-7/8/9 均非安全缺陷，O-4 为文档清晰度，无新攻击面、无凭据暴露、无提权面。

## 评分

v1.1 扣分项（RIG-7/8/9 共 -15）已全部修复 → base 归 100。本轮仅新增 🟢 O-4（0 扣分）。

| 发现 | 严重度 | 扣分 |
|:-----|:------:|:----:|
| RIG-7 overview 7 字段 + h 截断 | 🟡 | 已修 |
| RIG-8 partial→converge 矛盾 | 🟡 | 已修 |
| RIG-9 时间字段优先级 | 🟡 | 已修 |
| O-4 twitter-targets.yaml 表放置张力 | 🟢 | 0 |
| 合计 | | **0** |

得分: **100 / 100** → PASS (A)。

## 结论

**PASS (100/100)**

v1.1 的 3 个新 🟡 (RIG-7/8/9) 已逐项修复且逐行与源码实证一致：overview 7 字段规则与 `_write_overview` L1358-1366 完全吻合；partial→converge 通过「先 checkout 丢弃未提交生成文件再收敛」解除与 D2 脏守护的矛盾，行号（L1164/L1168/L399/L332-347）全部属实；时间字段优先级 `last_event_date > date > updated_at` 锁定且补单测断言。安全契约与 v1.4 一致性维持，确定性（跨机 tie-break）成立，无新攻击面。

唯一残余为 🟢 O-4（twitter-targets.yaml 白名单表放置的文档清晰度张力），非阻塞、0 扣分，建议实施时一行澄清。

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | O-4：实施时澄清 twitter-targets.yaml 为「白名单外 — 冲突 abort 人工」（一行标注即可，非阻塞） | 严格性 🟢 |

（本清单仅 O-4 一项，且为可选澄清；不影响 PASS 结论与 Phase 0 收敛启动。）
