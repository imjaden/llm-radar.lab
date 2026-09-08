# Changelog.html 功能增强设计方案

> 日期: 2026-07-13
> 状态: 待评审

---

## 问题

当前 changelog 摘要列是原始 diff 字符串，可读性差：

```
hot_score: 80 → 70; hot_level: 爆热 → 高热; last_event: 向OpenAI提起诉讼...
```

用户无法快速判断"谁变了、为什么、影响多大"。

## 目标

- **changelog.html**：看实时动态 — 最近 48h 谁被提及、热度升降、关联实体
- **index.html (仪表盘)**：看整体情况 — 已有 tab 视图，无需改动

---

## 方案：前端增强 + 后端 changelog 字段扩展

### 1. 后端：changelog 增加 `name` 字段

在 `merge_entities()` 生成 changelog 时，附带实体名称和维度中文名。

```python
# 当前 changelog 条目
{"type": "update", "dimension": "providers", "id": "openai", "summary": "...",
 "date": "...", "time": "...", "url": "..."}

# 增加
{"type": "update", "dimension": "providers", "id": "openai",
 "name": "OpenAI",                    ← 新增：实体名称
 "dim_label": "厂商",                 ← 新增：维度中文名
 "summary": "...",
 "date": "...", "time": "...", "url": "..."}
```

### 2. 后端：summary 格式标准化

当前 summary 是 `_diff_fields()` 生成的原始 diff。改为结构化摘要：

```
"[苹果起诉窃取机密并挖走400人] 热度 95→90、等级 爆热→高热"
```

规则：
- 以 `[事件摘要]` 开头（来自 last_event / recent_activity）
- 后接关键变化：热度升降、等级变化、状态变更
- 事件来自于 new 的 summary 字段或 update 的 last_event 字段

```python
def _format_changelog_summary(self, item, old=None):
    """生成人类可读的 changelog 摘要"""
    event = item.get('last_event') or item.get('recent_activity') or item.get('last_update') or ''
    parts = [event] if event else []
    
    # 热度变化
    if old:
        old_score = old.get('hot_score', 0)
        new_score = item.get('hot_score', 0)
        if old_score != new_score:
            delta = new_score - old_score
            arrow = '↑' if delta > 0 else '↓'
            parts.append(f'热度 {arrow}{abs(delta)} ({old_score}→{new_score})')
    
    return '  |  '.join(parts) if parts else item.get('name', '')
```

### 3. 前端：changelog.html 新布局

```
┌──────────────────────────────────────────────────────────────┐
│ 📋 更新日志                      数据源: [36氪] [InfoQ] ...  │
│ 更新时间: 2026-07-13 16:34 · 最近 50 条                      │
├──────────────────────────────────────────────────────────────┤
│ 07-13 16:34  update  厂商  OpenAI                            │
│   苹果起诉窃取机密并挖走400人  |  热度 ↓5 (95→90)           │
│   关联: GPT-5.6, ChatGPT Work  ·  来源: 36氪 ↗              │
├──────────────────────────────────────────────────────────────┤
│ 07-13 16:34  update  厂商  Anthropic                         │
│   季度利润突破10亿美元  |  热度 ↓5 (90→85)                  │
│   关联: Claude Fable 5  ·  来源: 36氪 ↗                     │
├──────────────────────────────────────────────────────────────┤
│ 07-13 16:34  new     工具  Cursor                            │
│   300行代码写个Cursor，成为AI时代开发工具标杆                  │
│   来源: InfoQ ↗                                              │
└──────────────────────────────────────────────────────────────┘
```

变更：
- 维度列显示中文名（厂商/人物/工具/模型）
- 摘要列分两行：事件行（加粗）+ 元信息行（热度变化、关联实体、来源链接）
- 热度升降用 ↑↓ 箭头 + 数值

### 4. 前端：关联实体交叉引用

`llms` 变更时显示所属 `provider_id`：
```
模型  GPT-5.6  [new]
  旗舰模型，全面围剿Claude
  厂商: OpenAI  ·  来源: 36氪 ↗
```

`people` 变更时显示 `employer_id`：
```
人物  Sam Altman  [update]
  主导GPT-5.6发布，澄清ChatGPT Work定位
  所属: OpenAI  ·  来源: 36氪 ↗
```

实现：前端通过 snapshot 数据反向查找（按 `provider_id`/`employer_id` 匹配）。

---

## 数据安全

### XSS 防护：三层防御

**层 1 — 后端净化 `_sanitize_text()`**

在生成 changelog summary 前，对所有 LLM 输出的自由文本做净化：

```python
import html

def _sanitize_text(text, max_len=200):
    """净化 LLM 输出：HTML 实体转义 + 截断 + 去控制字符"""
    if not text:
        return ''
    # 去掉 Unicode 控制字符 (0x00-0x1F, 0x7F-0x9F) 保留换行/制表符
    text = ''.join(ch for ch in text if ch == '\n' or ch == '\t' or ord(ch) >= 32)
    # HTML 实体转义（< > & " '）
    text = html.escape(text, quote=True)
    # 截断
    if len(text) > max_len:
        text = text[:max_len-3] + '...'
    return text
```

调用位置：
- `last_event` / `recent_activity` / `last_update` 文本
- `name` / `id` 字段（作为 HTML 属性值输出时）

**层 2 — 前端 textContent 渲染**

用户可控内容统一用 `textContent` 替代 `innerHTML`：

```javascript
// ❌ 当前: innerHTML 渲染 summary（XSS 风险）
td.innerHTML = '<span>' + summary + '</span>';

// ✅ 改为: 仅对可信结构（链接）用 innerHTML，文本用 textContent
var textSpan = document.createElement('span');
textSpan.className = 'summary-text';
textSpan.textContent = summary;  // 纯文本，禁止 HTML 解析
td.appendChild(textSpan);
```

例外：来源链接 `<a>` 标签是前端生成的固定结构（不包含用户输入），可以用 innerHTML。

**层 3 — URL Scheme 校验**

```javascript
function safeUrl(url) {
    if (!url) return null;
    // 仅允许 https:// scheme
    if (/^https:\/\/.+/.test(url)) return url;
    // data:, javascript:, file: 等全部拒绝
    return null;
}
```

渲染时：
```javascript
var href = safeUrl(item.url);
if (href) {
    var link = document.createElement('a');
    link.href = href;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.className = 'text-cobalt-400 hover:text-cobalt-300';
    link.textContent = '↗';
    td.appendChild(link);
}
```

### 向后兼容

旧 changelog 条目（无 `name` / `dim_label` 字段）的 fallback：

```javascript
// 前端 fallback
var name = item.name || item.id || '?';
var dimLabel = item.dim_label || item.dimension || '?';
```

```python
# 后端 fallback（_format_changelog_summary）
if not item.get('name') and not item.get('id'):
    return '(未知实体)'
event = _sanitize_text(item.get('last_event') or ...)
```

### 新实体 (new) 摘要格式

```
new 条目:
  事件文本  |  热度 85
  （无 old 参数，不显示升降箭头）

update 条目:
  事件文本  |  热度 ↑5 (80→85)
  （有 old 参数，显示箭头+变化量）
```

---

## 变更清单

| 文件 | 改动 |
|:---|:---|
| `llm-radar-collector.py` | changelog 条目加 `name`、`dim_label` |
| `llm-radar-collector.py` | `_sanitize_text()` + `_format_changelog_summary()` |
| `llm-radar-collector.py` | summary 存储时已转义（前端直接用 textContent） |
| `changelog.html` | 新布局：textContent 渲染 + safeUrl + 双行摘要 + ↑↓ 箭头 + 关联实体 |

---

## 不做的

- ❌ 不改 index.html 仪表盘 — 当前 tab 视图已满足"整体情况"
- ❌ 不改 snapshot.json schema — 仅 changelog 数组增加字段，向后兼容
- ❌ 不做增量渲染 — 依然渲染最近 50 条
- ❌ 不加 DOMPurify — 纯 textContent 方案已足够（无富文本需求）
