# 日志增强 + 健康检查端点 设计方案

> 日期: 2026-07-13
> 状态: 待评审

---

## 需求

| # | 需求 | 目的 |
|:--|:---|:---|
| 1 | `run` 所有日志加时间戳前缀 `2026-07-12 22:35:04` | 可追踪每次采集的精确时间 |
| 2 | 生成 `timestamp.json` 到项目根目录 | 外部通过 HTTP 检查管线是否存活 |

**(crontab 日志命名需求已移除，保持原有 `collector.log`)**

---

## 设计

### 1. 日志时间戳前缀

**改动**: `LLMRadarCollector` 的 4 个 print 方法统一加前缀。

```python
def _ts(self):
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

def _print_ok(self, msg):
    print(f'{self._ts()} ✅ {msg}')

def _print_err(self, msg):
    print(f'{self._ts()} ❌ {msg}')

def _print_info(self, msg):
    print(f'{self._ts()} ℹ️  {msg}')

def _print_warn(self, msg):
    print(f'{self._ts()} ⚠️  {msg}')
```

**影响**: 全部 CLI 输出（run / fetch / merge / sources / crontab / help）。测试 fixture 中已 monkey-patch 为 no-op，不受影响。

**风险**: 0，纯粹格式化改动。

---

### 2. timestamp.json 健康检查端点

**用途**: 外部监控 `https://llm-radar.lab.jaden.tech/timestamp.json` 判断管线是否存活。

**数据结构**:

```json
{
  "generated_at": "2026-07-13T07:14:06.288592",
  "last_news_date": "2026-07-13",
  "entity_count": 355,
  "period": "2026-07-06 ~ 2026-07-13",
  "version": "1.0"
}
```

字段说明:
- `generated_at`: 本次 run 完成时间（ISO 格式）
- `last_news_date`: 所有实体中最新的 `last_event_date`（实际最新资讯时间）
- `entity_count`: providers + people + tools + llms（不含 hotspots）
- `period`: 覆盖周期
- `version`: schema 版本

**生成位置**: `merge_entities()` 中，保存 snapshot.json 之后。

```python
def _write_timestamp(self, snapshot):
    """生成 timestamp.json 健康检查端点"""
    all_ents = []
    for dim in ['providers', 'people', 'tools', 'llms']:
        all_ents.extend(snapshot.get(dim, []))

    last_date = ''
    for item in all_ents:
        for dk in ['last_event_date', 'recent_activity_date', 'last_update_date']:
            d = item.get(dk, '')
            if d and d > last_date:
                last_date = d

    ts_data = {
        'generated_at': snapshot.get('generated_at', ''),
        'last_news_date': last_date,
        'entity_count': len(all_ents),
        'period': snapshot.get('period', ''),
        'version': '1.0',
    }

    ts_path = self.project_root / 'timestamp.json'
    ts_path.write_text(json.dumps(ts_data, ensure_ascii=False, indent=2))
```

**路由**: 项目根目录 `/timestamp.json` → GitHub Pages 自动提供 `https://llm-radar.lab.jaden.tech/timestamp.json`。

**验证方式**:
```bash
curl -s https://llm-radar.lab.jaden.tech/timestamp.json | python3 -m json.tool
```

**风险**: 
- timestamp.json 需要被 git 追踪（不被 .gitignore 忽略），随 auto-push 一起推送到 GitHub Pages
- 如果质量门禁未通过（跳过 auto-push），timestamp.json 不会更新到线上 → 监控会发现数据过期

---

## 变更清单

| 文件 | 改动 | 行数 |
|:---|:---|:---:|
| `llm-radar-collector.py` | `_ts()` + 4 个 print 方法加前缀 | ~8 |
| `llm-radar-collector.py` | `_write_timestamp()` 新方法 | ~20 |
| `llm-radar-collector.py` | `merge_entities()` 中调用 `_write_timestamp()` | +1 |
| `tests/test_timestamp.py` | 3 个测试用例 | ~60 |

---

## 不做的

- ❌ 不在 `.gitignore` 中添加 timestamp.json — 它必须被 git 追踪才能 push 到 GitHub Pages
- ❌ 不对 crontab 已存在的旧条目做迁移（用户需手动 `crontab --add` 重新添加）
