# timestamp.json 增强 + 质量门禁部分推送 设计方案

> 日期: 2026-07-13
> 状态: 待评审

---

## 需求

1. `质量门禁未通过` 日志改 `❌` emoji
2. `timestamp.json` 增加运行状态字段，质量门禁失败时只 commit+push timestamp.json

---

## timestamp.json 新 Schema

```json
{
  "generated_at": "2026-07-13T07:00:06.288592",
  "last_news_date": "2026-07-13",
  "last_run_at": "2026-07-13T07:00:06",
  "last_run_status": "success",
  "last_run_detail": "",
  "entity_count": 357,
  "period": "2026-07-06 ~ 2026-07-13",
  "version": "1.0"
}
```

质量门禁失败时示例：
```json
{
  "generated_at": "2026-07-13T07:00:06",
  "last_news_date": "2026-07-13",
  "last_run_at": "2026-07-13T07:00:06",
  "last_run_status": "failed",
  "last_run_detail": "空 URL: 8 条; key_people 缺失率 81%",
  "entity_count": 357,
  "period": "2026-07-06 ~ 2026-07-13",
  "version": "1.0"
}
```

## 推送策略

```
质量门禁通过 → snapshot.json + timestamp.json 都 commit+push    ← 现行为
质量门禁失败 → 不写 snapshot.json，只 commit+push timestamp.json
```

**原因**：
- 监控端通过 `timestamp.json` 的 `last_run_status` 判断管线状态
- 门禁失败时 snapshot 数据质量差，不落盘可避免下次 `git pull` 冲突

## 实现

### 流程变更

```
run():
  issues = _verify()            → 日志改 ❌，存到 self._quality_detail
  quality_ok = len(issues) == 0
  snapshot = merge_entities(quality_ok=quality_ok)
    if quality_ok:
      _save_snapshot()          ← 只在通过时写盘
    _write_timestamp(snapshot, quality_ok)   ← 始终写
    _auto_push(changelog, partial=not quality_ok)
      partial=True:  git add timestamp.json → commit → push
      partial=False: git add -A → commit → push
```

### 改动点

| 文件 | 方法 | 改动 |
|:---|:---|:---|
| `llm-radar-collector.py` | `run()` | log `❌`；存 `_quality_detail` |
| `llm-radar-collector.py` | `_write_timestamp()` | + `last_run_at`, `last_run_status`, `last_run_detail` |
| `llm-radar-collector.py` | `merge_entities()` | + `quality_ok` 参数，控制是否 save |
| `llm-radar-collector.py` | `_auto_push()` | + `partial` 参数 |
| `tests/test_timestamp.py` | 测试 | 更新 schema 断言 |

### 不做的

- ❌ 不改 `llm-radar-run.sh` — auto-push 逻辑在 collector 内部已足够

---

## 监控端使用

```bash
curl -s https://llm-radar.lab.jaden.tech/timestamp.json | python3 -c "
import sys,json
d=json.load(sys.stdin)
ok = d['last_run_status']=='success'
print(f'Status: {\"OK\" if ok else \"FAIL\"}  News: {d[\"last_news_date\"]}  Run: {d[\"last_run_at\"]}')
if not ok: print(f'Detail: {d[\"last_run_detail\"]}')
"
```
