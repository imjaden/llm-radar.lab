# AI 热点摘要增强设计方案

> 日期: 2026-07-13
> 状态: 待评审

---

## 问题

当前 hotspots 的 summary 由 LLM 在 extract 阶段一次性生成，质量不稳定：
- 信息密度低（"XX 发布了 YY" 缺乏上下文）
- 有时直接复制原标题，缺乏提炼
- 无法利用原文全文（extract 阶段只有截断后的 12000 字符）

## 方案：两步式摘要

```
extract_entities():
  LLM 提取 → hotspots[{title, url, summary_brief, ...}]
                                    ↓
  _enhance_hotspots():              ← 新增
    对每条 hotspot:
      1. web_extract(url)           ← 取全文 markdown
      2. LLM summarize(全文, title)  ← 生成 80 字中文摘要
      3. 回填 hotspot.summary
```

## 接口

```python
def _enhance_hotspots(self, hotspots, max_count=5):
    """对 Top-N 热点从原文生成高质量摘要。

    - 跳过无 URL 或 URL 为空的热点
    - web_extract 失败 → 保留 LLM 原始摘要
    - LLM summarize 失败 → 保留原始摘要
    - 不增加热点数量，原地修改 summary 字段
    """
```

### Summarize Prompt

```
你是一个科技新闻编辑。基于以下文章全文，为目标标题生成一条 80 字以内的中文摘要。

要求：
- 包含：谁 + 做了什么 + 为什么重要
- 不要重复标题
- 不要出现"本文""据报道"等套话
- 一句话完成

标题：{title}
全文：{content[:3000]}
```

### 调用位置

在 `run()` 中，`extract_entities()` 之后、`merge_entities()` 之前：

```python
entities = self.extract_entities(fetch_results)
entities['hotspots'] = self._enhance_hotspots(entities.get('hotspots', []))
```

## 性能影响

| 阶段 | 调用 | 耗时估算 |
|:---|:---|:---|
| 现有 extract | 1 次 LLM | ~130s |
| web_extract × 5 | 5 次 HTTP | ~15s |
| LLM summarize × 5 | 5 次 API | ~25s |
| **总计增加** | | **~40s** |

## 降级策略

```
web_extract 失败        → 保留原始 summary
LLM 返回为空            → 保留原始 summary
热点数 > 5              → 只处理 Top-5（按 hot_score 排序）
热点无 URL              → 跳过
```

## 不做的

- ❌ 不修改 snapshot.json schema — summary 字段复用
- ❌ 不修改前端 — 摘要长度前端已自适应
- ❌ 不做增量更新 — 每次都重新生成全部热点摘要
- ❌ 不使用其他 LLM 提供商 — 复用现有 DeepSeek API

## 变更清单

| 文件 | 改动 |
|:---|:---|
| `llm-radar-collector.py` | 新增 `_enhance_hotspots()` 方法 |
| `llm-radar-collector.py` | `run()` 中 extract 后调用 |

---

## 监控端验证

timestamp.json 可查看最新热点摘要质量：
```bash
curl -s https://llm-radar.lab.jaden.tech/data/snapshot.json | \
  python3 -c "
import json,sys
d=json.load(sys.stdin)
for h in d.get('hotspots',[]):
    print(f\"{h.get('date','')} | {h.get('title','')}\")
    print(f\"  {h.get('summary','')}\n\")
"
```
