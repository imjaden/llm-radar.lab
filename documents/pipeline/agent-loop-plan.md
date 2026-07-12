# Agent Loop 升级计划 — llm-radar

> 基于 **Think → Act → Observe → Verify** 闭环，改造当前线性采集管道。
> 目标：自修正、可观测、质量门禁。

---

## 1. 架构

### 当前（线性）

```
Fetch ──→ Extract ──→ Merge ──→ Push
```

### 目标（闭环）

```
                  ┌──────────────────────────────────┐
                  │  [Think] Collection Strategy     │
                  │  · Skip if interval < 6h?        │
                  │  · Degrade sources with 3 fails  │
                  │  · Prioritize last 48h events    │
                  └────────────┬─────────────────────┘
                               │
                               ▼
                  ┌──────────────────────────────────┐
                  │  [Act]   Fetch + Extract + Merge │
                  │  · 7 sources fetch (parallel)    │
                  │  · LLM extract (prompt rule 8)   │
                  │  · Incremental merge + dedup     │
                  └────────────┬─────────────────────┘
                               │
                               ▼
                  ┌───────────────────────────────────┐
                  │  [Observe] Metrics Recording      │
                  │  · sources: success/fail/timeout  │
                  │  · llm: parse fail, token usage   │
                  │  · data: avg freshness, dedup rate│
                  │  · push: success, skip reason     │
                  └────────────┬──────────────────────┘
                               │
                               ▼
                  ┌──────────────────────────────────┐
                  │  [Verify] Quality Gate           │
                  │  · Freshness > 7d? → degraded    │
                  │  · LLM parse fail? → retry once  │
                  │  · Hotspots < 3? → low conf      │
                  │  · Push fail? → retry → dead     │
                  └────────────┬─────────────────────┘
                               │
                    ┌──────────┴──────────┐
                    │                     │
                    ▼                     ▼
             ┌──────────────┐    ┌──────────────┐
             │ ✅ Pass      │    │ ❌ Fail       │
             │ push normal  │    │ record+skip  │
             └──────────────┘    └──────────────┘
```

---

## 2. 实现步骤

### 2.1 [Think] 采集策略决策

**位置**：`collector.run()` 开头，git pull 之后

```python
def _think(self):
    """采集策略决策"""
    # 1. 距上次采集间隔
    if self._interval_too_short():
        self._print_info('距上次采集不足 6h，跳过')
        return False
    # 2. 检查各数据源健康状态
    unhealthy = self._check_source_health()
    if unhealthy:
        self._print_warn(f'以下源健康状态不佳: {unhealthy}')
    # 3. 决定采集策略
    self._strategy = self._decide_strategy(unhealthy)
    return True
```

### 2.2 [Observe] 指标记录

**位置**：独立方法，各步骤结束时调用

```python
def _observe(self, stage, data):
    """记录运行指标到 data/metrics.json"""
    metrics_path = self.data_dir / 'metrics.json'
    # 加载 → 更新 → 保存
    # stages: fetch_done, extract_done, merge_done, push_done
    # data: source_name, duration, success, entity_count, avg_age, ...
```

**metrics.json 结构**：

```json
{
  "last_run": "2026-06-22T14:00:00",
  "run_count": 128,
  "sources": {
    "qbitai": {"total": 128, "success": 122, "fail": 6, "last_fail": "2026-06-20"},
    "github-trending": {"total": 128, "success": 108, "fail": 20, "last_fail": "2026-06-22"}
  },
  "llm": {
    "total_calls": 128,
    "parse_fail": 6,
    "avg_tokens": 4500,
    "avg_duration_s": 55
  },
  "data": {
    "avg_new_per_run": 8.5,
    "avg_update_per_run": 15.2,
    "avg_event_age_hours": 72,
    "dedup_ratio": 0.3
  },
  "push": {
    "total": 128,
    "success": 126,
    "skip_no_change": 1,
    "failed": 1
  }
}
```

### 2.3 [Verify] 质量门禁

**位置**：`_verify()` 方法，merge 后 push 前

```python
def _verify(self, changelog, entities):
    """质量门禁"""
    issues = []
    # 1. 事件新鲜度
    ages = self._calc_event_ages(entities)
    median_age = median(ages) if ages else 999
    if median_age > 168:  # 7天
        issues.append(f'事件中位数新鲜度 {median_age}h > 168h')
    # 2. 热点数量
    if len(entities.get('hotspots', [])) < 3:
        issues.append(f'热点仅 {len(entities["hotspots"])} 条')
    # 3. JSON 解析重试
    if self._parse_retry_count > 0:
        issues.append(f'JSON 解析重试 {self._parse_retry_count} 次')
    # 4. 去重比异常
    total_new = sum(1 for c in changelog if c['type'] == 'new')
    total_update = sum(1 for c in changelog if c['type'] == 'update')
    if total_new == 0 and total_update == 0:
        issues.append('无任何变更')
    return issues
```

**门禁决策**：

```python
issues = self._verify(changelog, entities)
if issues:
    self._print_warn(f'质量门禁未通过: {"; ".join(issues)}')
    self._skip_push = True
    # 记录原因，跳过 auto-push
else:
    self._skip_push = False
```

### 2.4 自修正

| 故障 | 响应 |
|:---|:---|
| 同一源连续 3 次超时 | `sources_health[src] = "deprecated"`，打印告警 |
| LLM 解析失败 | 重试 1 次，prompt 去掉 JSON schema 要求，只要求返回纯 JSON |
| Push 失败 | 重试 1 次，失败则记录到 dead letter |

---

## 3. 文件变更清单

| 文件 | 变更 |
|:---|:---|
| `llm-radar-collector.py` | 新增 `_think()`、`_observe()`、`_verify()` 方法；`run()` 集成闭环 |
| `data/metrics.json` | 新增，运行指标持久化 |
| `.gitignore` | 追加 `data/metrics.json`（可选，非必须） |
| `features.md` | 追加 agent-loop 功能条目 |

---

## 4. 增量实施（P0 → P2）

```
P0 [30 行]  _verify() 事件新鲜度 + LLM 重试
P1 [50 行]  _observe() metrics.json
P1 [15 行]  _think() 间隔判断
P2 [80 行]  自修正（源降级 + dead letter）
```

分支策略：`feat/agent-loop` → 逐 commit 实现 P0 → P1 → P2 → 合入 main。
