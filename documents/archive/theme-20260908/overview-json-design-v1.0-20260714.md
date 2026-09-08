# 页面概览数据加速加载 设计方案

> 日期: 2026-07-14
> 状态: 待评审

---

## 问题

当前 `index.html` 和 `changelog.html` 首次加载时显示"加载中..."，等待 `data/snapshot.json`（~320KB）完全下载后才能看到任何内容。用户感知延迟明显，尤其在移动网络或 GitHub Pages CDN 回源时。

## 目标

- **0.5s 内**看到关键信息（数据刷新时间、各维度实体数量、最新热点标题）
- 骨架屏/占位符过渡，减少"白屏等待"体感
- 不增加网络请求总带宽，概览文件极致压缩（< 2KB）

---

## 方案：`overview.json` 轻量预览文件

### 数据结构

```json
{
  "v": 1,
  "t": "2026-07-13T16:34:24",
  "p": "2026-07-06 ~ 2026-07-13",
  "s": {"pr": 93, "pe": 81, "to": 99, "ll": 82, "ho": 100},
  "h": [
    {"d": "2026-07-13", "t": "苹果起诉OpenAI挖角窃密"},
    {"d": "2026-07-13", "t": "Anthropic季度利润破10亿美元"},
    {"d": "2026-07-13", "t": "DeepSeek和智谱被曝自研AI推理芯片"}
  ],
  "r": "failed",
  "rd": "空 URL: 8 条; key_people 缺失率 81%"
}
```

字段说明（单字母压缩体积）：

| 字段 | 含义 | 值示例 |
|:---|:---|:---|
| `v` | schema 版本 | 1 |
| `t` | 数据生成时间 (generated_at) | ISO datetime |
| `p` | 覆盖周期 (period) | "2026-07-06 ~ 2026-07-13" |
| `s` | 各维度实体数 (stats) | pr=providers, pe=people, to=tools, ll=llms, ho=hotspots |
| `h` | 最新热点（Top 3） | 仅标题和日期 |
| `r` | 最近运行状态 | "success" / "failed" |
| `rd` | 运行状态详情 | quality gate 失败原因或空 |

**体积**: ~300 bytes（vs snapshot.json 的 ~320KB，缩小 1000 倍）

### 生成时机

在 `merge_entities()` 中，与 `_write_timestamp()` 同时生成：

```python
def _write_overview(self, snapshot, quality_ok=True):
    """生成 overview.json 轻量预览文件"""
    stats = {}
    for dim, key in [('providers','pr'), ('people','pe'), ('tools','to'),
                      ('llms','ll'), ('hotspots','ho')]:
        stats[key] = len(snapshot.get(dim, []))

    hotspots = sorted(snapshot.get('hotspots', []),
                      key=lambda h: h.get('date', ''), reverse=True)[:3]

    overview = {
        'v': 1,
        't': snapshot.get('generated_at', ''),
        'p': snapshot.get('period', ''),
        's': stats,
        'h': [{'d': h.get('date', ''), 't': h.get('title', '')} for h in hotspots],
        'r': 'success' if quality_ok else 'failed',
        'rd': getattr(self, '_quality_detail', ''),
    }

    (self.project_root / 'overview.json').write_text(
        json.dumps(overview, ensure_ascii=False, separators=(',', ':')))
```

### 前端加载流程

```
┌──────────────────────────────────────────────┐
│  页面打开                                     │
│    ↓                                         │
│  立即 fetch overview.json (~0.3s)            │
│    ↓                                         │
│  渲染骨架: 更新时间和各 tab 数字               │
│    ↓                                         │
│  background: fetch snapshot.json (~3s)       │
│    ↓                                         │
│  完整渲染: 列表 + 表格                        │
│    ↓                                         │
│  替换骨架: 平滑过渡                           │
└──────────────────────────────────────────────┘
```

### index.html 改动

```javascript
// 现有: 单次 fetch snapshot.json → 渲染全部
// 改为: 两次 fetch → 先轻量再完整

var overviewReady = false;
var snapshotReady = false;

// 1. 立即加载概览
fetch('overview.json?t=' + Date.now())
  .then(r => r.json())
  .then(function(o) {
    overviewReady = true;
    // 显示数据刷新时间
    document.getElementById('update-time').textContent = o.t;
    // 更新各 tab 数字徽章
    updateTabCounts(o.s);  // pr:93, pe:81, to:99, ll:82, ho:100
    // 显示 Top 热点速览
    renderHotspotPreview(o.h);
    if (snapshotReady) hideSkeleton();
  });

// 2. 后台加载完整数据
fetch('data/snapshot.json?t=' + Date.now())
  .then(r => r.json())
  .then(function(d) {
    DATA = d;
    snapshotReady = true;
    renderAllTabs();
    if (overviewReady) hideSkeleton();
  });
```

### 视觉效果

加载中 → 概览就绪的过渡：

```
┌──────────────────────────────────────────────┐
│  LLM Radar              更新于 16:34:24      │
│                                              │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐        │
│  │ 93 │ │ 81 │ │ 99 │ │ 82 │ │100 │        │
│  │厂商│ │人物│ │工具│ │模型│ │热点│        │
│  └────┘ └────┘ └────┘ └────┘ └────┘        │
│                                              │
│  🔥 苹果起诉OpenAI挖角窃密                   │
│  🔥 Anthropic季度利润破10亿美元              │
│  🔥 DeepSeek和智谱被曝自研AI推理芯片         │
│                                              │
│  ⏳ 正在加载完整数据...                       │
└──────────────────────────────────────────────┘
```

### 骨架屏

当 overview.json 就绪但 snapshot.json 仍在加载时，各 tab 内容区显示骨架占位：

```html
<div class="skeleton-table">
  <div class="skeleton-row h-4 w-full bg-gray-800 animate-pulse rounded mb-2"></div>
  <div class="skeleton-row h-4 w-3/4 bg-gray-800 animate-pulse rounded mb-2"></div>
  <div class="skeleton-row h-4 w-5/6 bg-gray-800 animate-pulse rounded"></div>
</div>
```

### changelog.html 改动

changelog 不需要完整加载体验——它本身就是"最近 50 条"的列表。但可以利用 overview.json 展示数据时效：

```
📋 更新日志
数据更新: 2026-07-13 16:34 · 状态: ❌ quality gate failed
热点: 苹果起诉OpenAI · Anthropic利润破10亿 · DeepSeek自研芯片
────────────────────────────────────────
[changelog 列表正常加载...]
```

---

## 数据安全与容错

### 渲染规范：沿用 textContent 标准

所有 overview.json 中的数据渲染统一使用 `textContent`，禁止 `innerHTML`。与 changelog-enhance-design 保持一致。

```javascript
function renderHotspotPreview(hotspots) {
    var container = document.getElementById('hotspot-preview');
    container.textContent = '';  // 清空
    hotspots.forEach(function(h) {
        var div = document.createElement('div');
        div.className = 'text-xs text-gray-300';
        div.textContent = '🔥 ' + h.t;  // textContent，非 innerHTML
        container.appendChild(div);
    });
}

function renderOverviewStats(stats) {
    // stats = {pr:93, pe:81, to:99, ll:82, ho:100}
    // pr=厂商 pe=人物 to=工具 ll=模型 ho=热点
    Object.keys(stats).forEach(function(key) {
        var el = document.getElementById('tab-count-' + key);
        if (el) el.textContent = stats[key];
    });
}
```

### 错误处理：双 fetch 退化逻辑

```javascript
var overviewReady = false;
var snapshotReady = false;

// 1. 概览加载（有 catch 退化）
fetch('overview.json?t=' + Date.now())
  .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
  .then(function(o) {
    overviewReady = true;
    renderOverviewStats(o.s);
    renderHotspotPreview(o.h);
    document.getElementById('update-time').textContent = o.t;
    if (snapshotReady) hideSkeleton();
  })
  .catch(function(e) {
    overviewReady = true;  // 标记完成，跳过概览
    console.warn('overview.json 加载失败:', e.message);
  });

// 2. 完整数据加载
fetch('data/snapshot.json?t=' + Date.now())
  .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
  .then(function(d) {
    DATA = d;
    snapshotReady = true;
    renderAllTabs();
    if (overviewReady) hideSkeleton();
  })
  .catch(function(e) {
    document.getElementById('error-msg').textContent = '❌ 数据加载失败，请稍后刷新';
    document.getElementById('error-msg').style.display = 'block';
  });
```

退化矩阵：

| overview.json | snapshot.json | 用户体验 |
|:---|:---|:---|
| ✅ 成功 | ✅ 成功 | 先概览→后完整（正常路径） |
| ❌ 失败 | ✅ 成功 | 跳过概览，直接完整渲染 |
| ✅ 成功 | ❌ 失败 | 看到概览数字+热点，底部显示"加载失败" |
| ❌ 失败 | ❌ 失败 | 显示"数据加载失败，请稍后刷新" |

### _quality_detail 安全性

`_quality_detail` 来自 `_verify()` 方法，值为固定模式字符串拼接（数字 + 中文固定文本），无 LLM 输出、无用户输入。即使意外渲染到 innerHTML 也安全。

---

## 变更清单

| 文件 | 改动 |
|:---|:---|
| `llm-radar-collector.py` | `_write_overview()` 方法 |
| `llm-radar-collector.py` | `merge_entities()` 中调用 |
| `index.html` | 两阶段加载: overview.json → snapshot.json |
| `index.html` | 骨架屏样式 + 过渡动画 |
| `changelog.html` | overview.json 摘要展示 |
| `tests/test_overview.py` | 测试用例 |

---

## 不做的

- ❌ 不使用 Service Worker 缓存 — GitHub Pages 已有 CDN
- ❌ 不做增量数据推送 (WebSocket/SSE) — 静态站点
- ❌ 不做离线模式 — 需要实时数据
- ❌ 不改 tab 内容的分页加载 — 一次全量渲染已够快
