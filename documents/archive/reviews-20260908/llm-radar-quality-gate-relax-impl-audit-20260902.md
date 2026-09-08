# LLM-RADAR-CL005 质量门禁放宽与重试优化 — 实现审计报告 v1.0

> 日期: 2026-09-02 (审计执行日)
> 设计文档: documents/solutions/llm-radar-quality-gate-relax-design-v1.0-20260902.md (v1.1, ba76927)
> 设计复审: documents/reviews/llm-radar-quality-gate-relax-design-rereview-v1.1-20260902.md (PASS 95/A)
> 待审 commit: 1dc7ddf feat@llm-radar: quality gate relax + retry 5->3 (前置 docs 961d666/25bccaf/ba76927/0a9de44/e94c9f3)
> review者: review/llm-radar-quality-gate-relax-impl-audit (hermes-1.2.0)
> review维度: 一致性 / 测试 / 治理 / 安全 / 运维 (5 维 + 100-base, PASS 阈值 ≥85/A)

## 结论摘要

实现与设计 v1.1 完全一致。D2/D5/D6/D7 全部落地, 前置 4 🟡 (REA-1/RIG-1/RIG-2/RIG-3) + SEC-001
在代码层正确落实。审计新发现 3 🟡 文档漂移 (DOC-1~3, 非阻塞):

- **DOC-1 🟡**: `_verify` docstring L1424 仍称「热点数量」为阻断硬指标 (N4 清单项「顺带更新
  docstring L1422-1423」漏改) — 审计中修复。
- **DOC-2 🟡**: features.md 质量门禁「热点 ≥3 条」旧口径 — 审计中修复。
- **DOC-3 🟡**: AGENTS.md L82/L145 仍描述旧门禁 — protected 文件无写权限, 待用户改
  (仅文档, 不影响功能/安全)。

**评分: 95 / 100 (A) → ✅ PASS。** 代码与测试全对, 唯文档漂移 (2 已修 + 1 待用户) 属完整性缺口,
不阻塞 push。

## 验收逐项 (设计 v1.1 §3.1-3.3 + 复审验收清单)

| # | 验收项 | 方法 (源码锚点) | 结果 |
|:--|:--|:--|:--:|
| 1 | D2 重试 5→3 | L780 `for retry_i in range(1, 4)`; 日志 4 处: L781 `/3` / L785 `/3 LLM 调用失败` / L789 `/3 返回空内容` / L795 `已重试 3 次` | ✅ |
| 2 | D5 热点阻断→warning | L1454-1455 `if len(hotspots) < 3: warnings.append(...未阻断)` (不再 append issues) | ✅ |
| 3 | D5 实体 0 阻断 (4 维度排除热点) | L1449-1451 `entity_count = sum(len(entities.get(d,[])) for d in ['providers','people','tools','llms'])`; ==0 → issues | ✅ |
| 4 | D5 分层拦截 | run L1745 `if not entities: return False` (拦 None) + L1429 `if not entities: return ['实体提取为空']` (防御) 保留 | ✅ |
| 5 | D6 热点数 checks 第 5 项 | L1911 `{'label':'热点数',...}`; L1903 `'warning' if hotspot_count < 3 else 'info'` | ✅ |
| 6 | D6 不影响主 status | L1864-1869 status_str 5 因子 (快照缺失/新鲜度/连续失败/质量门禁/git分叉) 无热点数 | ✅ |
| 7 | D7 判定顺序 实体→热点 | L1449 实体检查先于 L1454 热点检查 | ✅ |
| 8 | D3 daily-checker 需求 prompt | cache/review-prep/cl005-daily-checker-handoff-prompt.md (09-02 11:15) 存在; 未跨项目改代码 | ✅ |
| 9 | N1 §6 冒烟门槛 | design v1.1 §6 项3 改「记录 LLM 阶段耗时 (预期 ~216s, <300s 承诺)」 (1dc7ddf 内含) | ✅ |
| 10 | 测试同步 | test_verify.py 4 用例 (新增) + test_status.py::test_ok_checks labels → 5 项 | ✅ |
| 11 | 全量回归 | `pytest -m "not selenium" --ignore=test_cli.py --ignore=test_selenium.py` → 223 passed, 2 deselected (独立复跑) | ✅ |
| 12 | 冒烟 lr status --json | 5 checks 含 '热点数' (81 条 info); status=warning 因 Git 6 ahead 非热点 | ✅ |

## 发现项

| # | Severity | Title | 说明 | 处置 |
|:-:|:--------:|:------|:-----|:-----|
| DOC-1 | 🟡 | `_verify` docstring 仍称「热点数量」为阻断硬指标 | L1424「仍阻断的硬指标: 新鲜度、热点数量」— 热点已非阻断; 设计复审 N4 清单项「顺带更新 docstring L1422-1423」漏改 | ✅ 审计中修复 (改「新鲜度、实体数(4 维度全 0)」+ 增 CL005 注) |
| DOC-2 | 🟡 | features.md 质量门禁旧口径 | L57「热点数量: 新提取热点 ≥3 条」— 与 CL005 实体>0 新门禁矛盾 | ✅ 审计中修复 (改「实体数 >0」+「热点 <3 仅 warning」) |
| DOC-3 | 🟡 | AGENTS.md 仍描述旧门禁 | L82「热点 ≥ 3 条」+ L145「Hotspot count ... ≥ 3 ... fails」— 设计/实现均未列 AGENTS.md 更新 | ⏳ 待用户改 (protected 文件无写权限; 仅文档, 不阻塞) |

## 维度评估 (5 维)

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 一致性 | 🟢 | D2/D5/D6/D7 与设计 §3.1-3.3 逐项对应; 4 实体维度排除热点 / 分层拦截 / status_str 5 因子均与设计一致 |
| 测试 | 🟢 | 4 新用例覆盖「热点0实体ok / 热点1 warning / 4维度全0阻断 / 热点≥3无警告」+ status 5 labels; 全量 223 独立复跑全绿 |
| 治理 | 🟡 | commit subject 全英文 `feat@llm-radar: quality gate relax + retry 5->3` 合规; 唯 3 处文档漂移未随代码同步 (DOC-1~3) |
| 安全 | 🟢 | 无新依赖/注入面/敏感数据; 仅循环上界 + 日志串 + 内存求和 + checks 计数; 无认证边界/数据流变更 |
| 运维 | 🟢 | D3 需求 prompt 已落盘转交; D4 存量恢复延后至 push 后 `lr run --force` (ops check 已记) |

## 评分明细

```
基准分: 100
  代码实现 (D2/D5/D6/D7)      ✅ 不计分
  测试覆盖 (4+1 用例)          ✅ 不计分
  DOC-1 🟡 -2  docstring 漂移 (N4 清单项漏改) — 审计中修复
  DOC-2 🟡 -1  features.md 旧口径 — 审计中修复
  DOC-3 🟡 -2  AGENTS.md 旧门禁 — protected 待用户改
────────────────────────
得分: 95 → A → ✅ PASS
```

## 结论

**✅ PASS — 95/100 (A)。** 核心实现 (retry 5→3 + 质量门禁放宽 + status checks 第 5 项)
与设计 v1.1 完全一致, 前置 4 🟡 阻塞项在代码层全部闭环; 测试覆盖意图充分且独立复跑全绿。
新发现仅 3 🟡 文档漂移 (非阻塞, 2 已随审计修复, 1 处 AGENTS.md 因 protected 待用户改),
不改变功能/安全/运维正确性。审计为闭环 push 执行者, 本次 PASS 后 commit + push。

## 后续 (遗留, 不阻塞)

- DOC-3 (P2): AGENTS.md L82 + L145 同步 CL005 门禁口径 (用户侧改, protected 文件):
  L82 → 「质量门禁：事件中位数新鲜度 < 7 天，实体 > 0（热点 <3 仅 warning）」;
  L145 → 删除「≥ 3 fails」改「<3 warning only, not a gate failure」。
- D4 存量恢复 (P1): push 后 `lr run --force` 恢复线上数据, 验证 `dk check llm-radar` 转 ok。
- O-1 计时验证 (P2): run 记录 LLM 阶段耗时 (预期 ~216s, <300s 承诺), 在 D4 执行时顺带验证。

---

*报告: documents/reviews/llm-radar-quality-gate-relax-impl-audit-20260902.md | 结论: ✅ PASS 95/100 (A) | D2/D5/D6/D7 ✅ + DOC-1/2 审计中修复 + DOC-3 🟡 待用户 | commit + push*
