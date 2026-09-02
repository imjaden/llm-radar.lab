---
title: "llm-radar 质量门禁放宽与重试优化设计"
topic: quality-gate-relax
type: design
version: "1.1"
date: "2026-09-02"
author: ops
tags: [llm-radar, quality-gate, retry, heal, daily-checker]
profile: ops
provider: deepseek
model: deepseek-v4-flash
---

# LLM-RADAR-CL005 — 质量门禁放宽与重试优化设计 v1.1

## 修订记录

| 版本 | 日期 | 修订人 | 说明 |
|:---|:---|:---|:---|
| v1.0 | 2026-09-02 | ops | 初版（探讨确认 3 轮决策全锁定） |
| v1.1 | 2026-09-02 | ops | 设计评审修正（COND 80/B → 复评）: REA-1 实体维度口径/位置, RIG-1 日志 4 处, RIG-2 status_str 因子枚举, RIG-3 耗时重ground + SEC-001 取舍声明 |

## 背景与根因

daily-checker 反复报「LLM Radar 数据更新: 未恢复（复验仍异常）」，线上数据停在
2026-09-01 22:42:08。三层根因（实测证据）：

1. **3 源长期降级** → 素材不足: qbitai（79 连败）/ github-trending（29）/ huggingface（63）
   因网络限制无法访问（服务器端已知；本地需 FLClash 但决策 1c 接受降级），每天只抓 3 个
   健康源（机器之心 / InfoQ / 36氪）。
2. **LLM 提取不稳定** → 超时: JSON 解析失败重试 5 次 × ~40s，LLM 阶段 324s，总耗时 358s
   > daily-checker heal 300s 预算（collector.log 09-02 08:40 run 实测）。
3. **热点 0 条** → 质量门禁失败 → 不 push: 素材少 → 提取不出热点（09-02 提取 53 实体但
   热点 0 条）→ auto-push 跳过 → 复验仍异常 → 死循环。

热点趋势（D 确认，最近 10 天每次 run 提取热点数）: 08-29~08-31 稳定 5/5；
09-01 降至 4/5；09-02 归零（门禁失败）。

## 决策记录

| 编号 | 决策 | 内容 |
|:---|:---|:---|
| D1 | 接受源降级（1c） | 不配置 FLClash；qbitai/github-trending/huggingface 永久缺失，固定抓 3 健康源 |
| D2 | 重试优化（2a） | JSON 解析失败重试 5→3 次，LLM 阶段压到 ~200s |
| D3 | daily-checker 配合（3a） | llm-radar 单独 per-checkpoint timeout = 600s（全局 300s 不动），需求 prompt 打印转交 |
| D4 | 存量恢复（4a） | B/C 落地后统一 lr run --force 恢复线上数据 |
| D5 | 质量门禁放宽（1b+2b） | 判定顺序实体→热点：实体 >0 → push（热点 0 也 push）；实体 0（全源失败）→ fail 不 push |
| D6 | 可见性（4a） | 热点 <3 仅作 checks 附加条目（warning 图标），不改变主 status |
| D7 | 判定细节（1a 2a 3a） | 热点<3 只作 checks 附加项；实体>0 才 push；先实体维度再热点维度 |

## §3 详细设计

### 3.1 JSON 解析失败重试 5→3（D2）

- 位置: `llm-radar-collector.py` `extract_entities`（L681 起; 重试块约 L776-796）
- 改动:
  - `for retry_i in range(1, 6)` → `range(1, 4)`（L779）
  - 日志计数 4 处同步: L780 `重试 {retry_i}/5` → `/3`; L788 `重试 {retry_i}/5 返回空内容` → `/3`;
    L784 `重试 {retry_i}/3 LLM 调用失败` 与 L794 `已重试 3 次` 当前已是 `/3`/`3 次`
    （既有漂移: 5 次重试下就已错标, 本次改动恰好使其变正确, 无需再改）
- 耗时估算（重ground）: 根因 #2 实测 324s / 6 次调用 ≈ 54s/次; D2 后 4 次调用（1 首次 + 3 重试）
  ≈ 216s, 总耗时 <300s（主目标达成）; 注意 "≤200s" 非承诺, D3（600s timeout）为硬兜底

### 3.2 质量门禁放宽（D5 D7）

- 位置: `_verify()`（L1419-1463）
- 改动:
  1. 热点数量检查从阻断项（`issues`）移除 → 改为 warning（记入 `self._quality_warnings`）:
     `if len(hotspots) < 3: warnings.append(f'热点仅 {len(hotspots)} 条（未阻断）')`
  2. 实体 0（全源失败）仍阻断，分两层（位置澄清）:
     - run() L1739 `if not entities: return False` — 拦截 LLM 返回 None（全源失败主拦截）
     - `_verify` 新增检查拦截 "LLM 返回全空数组的 dict"（truthy dict 会绕过 L1739）:
       `sum(len(entities.get(d, [])) for d in ['providers','people','tools','llms']) == 0`
       → issues（**4 实体维度, 排除 hotspots**; 避免"仅 3 热点 + 0 实体"误判通过）
     - `_verify` 开头 `if not entities: return ['实体提取为空']`（L1428）保留（防御直接调用）
- 效果: 实体 >0 时 `quality_ok=True` → auto-push 完整推送；热点不足仅留痕

### 3.3 热点 <3 checks 附加 warning（D6）

- 位置: `status()` checks 构建（约 L1894-1899）
- 改动: checks 增加第 5 项 `{'label': '热点数', 'value': '<n> 条', 'status': 'warning' if n<3 else 'info'}`
- 注意: 主 status（status_str）由 5 项决定 — `not snapshot`（快照缺失）/ `freshness`（last_run_at 年龄）/
  `consec_fails>=3` / `quality_status`（timestamp.json 的 last_run_status）/ `git_status`（ahead/behind）,
  **不受 checks 项（含新增"热点数"）影响** — 断掉 daily-checker heal trigger（[warning, critical]）死循环。
  （"实体数"同样不是 status_str 因子, 仅影响 checks 显示, status 恒为 'info'。）
- 已知取舍（SEC-001）: 实体>0 阈值无下限, 单条新鲜垃圾实体可过门禁; 当前 3 健康源稳定产出 ~50 实体,
  实际风险低, 以新鲜度优先、质量为代价（显式声明）
- 同步测试: `tests/test_status.py::test_ok_checks` 断言 labels 列表需加 '热点数'

### 3.4 daily-checker 配合（D3, 跨项目转交）

- daily-checker 侧需求: config.yaml checkpoints 段 llm-radar 条目增加
  per-checkpoint timeout（600s），heal 执行 action cmd 的 subprocess timeout 使用
  该项而非全局 300s 固定值（当前 daily-checker.py:68 HEAL_TOTAL_TIMEOUT=300 全局限定）
- 本仓库只打印需求描述 prompt 供用户转交，不跨项目改动

### 3.5 存量恢复（D4）

- 实施 + daily-checker 落地后: `lr run --force` → 门禁通过（实体>0）→ push → 线上恢复
- 验证: `dk check llm-radar` 转 ok

## §4 测试影响

| 文件 | 用例 | 影响 |
|:---|:---|:---|
| tests/test_status.py | test_ok_checks | checks labels 断言需加 '热点数' |
| tests/test_status.py | test_warning_quality_failed | 语义不变（timestamp failed → warning） |
| tests/test_timestamp.py | test_status_success_when_no_issues | 不变（实体>0 通过） |
| tests/test_validate.py | 全部 | 不变（URL/完整性仍 warning 不阻断） |
| tests/test_extract.py | 全部 | 不变（JSON 解析 3 级 fallback 未动） |

新增测试:
- `test_verify_hotspots_zero_but_entities_ok`（热点 0 实体>0 → issues 空）
- `test_verify_all_empty_fails`（全空实体 → issues 非空）
- `test_status_hotspot_warning_check`（热点 <3 → checks 有 '热点数' warning 且主 status 不变）

## §5 观察项

- O-1: 实施后 LLM 阶段耗时 ~216s（重试 3 次上限, 按 54s/次 ground）; 总耗时 <300s 为承诺,
  "≤200s" 非目标; D3（600s timeout）为硬兜底
- O-1b: 已知取舍 — 实体>0 阈值无下限, 单条新鲜垃圾实体可过门禁（SEC-001, 当前风险低）
- O-2: 每次 run 仍 push（实体>0），数据新鲜度恢复，无未恢复通知
- O-3: daily-checker 侧 timeout 600s 落地后，heal 不再误报超时
- O-4: 热点 0 条时 checks 有 warning 留痕（可见性保留）

## §6 dev 验证清单

1. `python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q` 全绿
2. 新增 3 用例断言通过
3. 冒烟: `lr status --json` checks 含 '热点数'；`lr run --force` 计时 LLM 阶段 ≤200s
4. `git checkout --` 还原测试写脏的 timestamp.json / overview.json / data/snapshot.json
5. daily-checker 需求 prompt 落盘 cache/review-prep/ 打印给用户
