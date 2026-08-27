---
title: X弹框按钮图标化与拷贝降级修复设计
topic: llm-radar
type: design
version: 1.0
date: 2026-08-27
author: hermes-1.2.0
tags: [llm-radar, x, frontend, clipboard, split-preview]
profile: ops
provider: deepseek
model: deepseek-v4-flash
---

# X弹框按钮图标化与拷贝降级修复设计 v1.0 (LLM-RADAR-CL003)

> 探讨确认(2026-08-27): A1 B2+B3 C1 D1 + 残余 1A 2A。
> 用户确认串: "A1 B2+B3 C1 D1" + "1A 2A"。
> 闭环: LLM-RADAR-CL003 (新式编号, 续 CL002)。

## 修订记录

- v1.0 (2026-08-27) — 初版: 按钮纯图标化 (用户手工微调提交) + 拷贝降级链修复。

---

## 1. 背景与目标

1. 用户手工微调: X 弹框按钮行 (index.html:305-307) 从 "🔗 打开原文 / 👤 作者主页 / 📋 拷贝"
   改为纯图标 "🔗 / 👤 / 📋" (工作区未提交, 需提交入库)。
2. 拷贝报错: `index.html:1143 Uncaught TypeError: Cannot read properties of undefined
   (reading 'writeText')` — navigator.clipboard 在非安全上下文 (http://IP 访问等) 为 undefined,
   直接 `.writeText` 抛 TypeError 且发生在 promise catch 之前 (CL001 OBS-2 仅覆盖 promise 失败,
   未覆盖 API 本身不可用)。

目标:

- 按钮图标化入库; 拷贝在任何上下文可用 (clipboard API → execCommand 降级)。
- 反馈语义清晰; 悬停可辨识 (纯图标无文字, 需 title)。

## 2. 决策记录

| # | 决策 | 内容 |
|:---|:---|:---|
| D1 | 拷贝降级 | A1: `navigator.clipboard?.writeText(text)` 防御; API 不可用或 promise 失败 → textarea + `document.execCommand('copy')` 兜底 |
| D2 | 反馈/复原 | B2: 成功 '已拷贝 ✓' 1500ms / 失败 '拷贝失败' 2000ms 复原; orig 从 '📋 拷贝' 改 '📋' (与纯图标一致) |
| D3 | 悬停提示 | B3: 三按钮加 title="打开原文" / "作者主页" / "拷贝推广内容" |
| D4 | 提交/测试 | C1: 手工微调 + 修复同一 commit; D1: test_html 新增断言 (clipboard 防御 + execCommand 降级存在) |
| D5 | execCommand 反馈 | 2A: 按返回值 true → '已拷贝 ✓' / false → '拷贝失败' |

## 3. 详细设计

### 3.1 HTML 按钮 (index.html:305-308, 用户微调 + title)

```html
<a class="sp-act" id="sp-act-link" href="#" target="_blank" rel="noopener noreferrer" title="打开原文">🔗</a>
<a class="sp-act" id="sp-act-profile" href="#" target="_blank" rel="noopener noreferrer" title="作者主页">👤</a>
<button class="sp-act" id="sp-act-copy" type="button" title="拷贝推广内容">📋</button>
```

### 3.2 copyTweet 降级链 (index.html:1132-1150 重构)

```js
function copyTextFallback(text) {           // execCommand 兜底 (非安全上下文可用)
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed'; ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  let ok = false;
  try { ok = document.execCommand('copy'); } catch(e) { ok = false; }
  document.body.removeChild(ta);
  return ok;
}

function copyTweet(f) {
  // ... 组装 lines (不变, C2 模板) ...
  const btn = document.getElementById('sp-act-copy');
  const orig = '📋';                          // 与纯图标初始态一致 (B2)
  const text = lines.join('\n');
  const done = () => { btn.textContent = '已拷贝 ✓'; setTimeout(() => { btn.textContent = orig; }, 1500); };
  const fail = () => { btn.textContent = '拷贝失败'; setTimeout(() => { btn.textContent = orig; }, 2000); };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done).catch(() => { copyTextFallback(text) ? done() : fail(); });
  } else {
    copyTextFallback(text) ? done() : fail();
  }
}
```

- SEC-1: lines 组装不变 (textContent/静态), textarea 是临时 DOM 节点, 无注入面。
- 复原 1500/2000ms 语义不变 (OBS-1 继承)。

### 3.3 测试 (tests/test_html.py)

- 新增断言 (TestPerfOptimize 同文件或新类):
  - copyTweet 含 clipboard 防御: `navigator.clipboard && navigator.clipboard.writeText` 存在 (或 `?.`)。
  - 含 execCommand 降级: `document.execCommand('copy')` 存在。
- 无其他测试影响 (无 '📋 拷贝' 文本断言依赖, 已 grep 确认)。

## 4. 测试影响

- 机制 2/3: `python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q` (预期 216+ passed)。
- 无数据/CI/collector 影响。

## 5. 观察项

- O-1: 纯图标按钮可访问性 — title 已补; 如需 aria-label 可后续加 (本次 title 足够)。
- O-2: execCommand 已废弃 (deprecated) 但非安全上下文唯一可用路径, 保持兜底定位。

## 6. 验证清单 (dev 阶段)

1. 机制 2/3 pytest 全绿 (含新断言)。
2. 本地 http://localhost:8080 手工: 拷贝成功 '已拷贝 ✓' 复原 '📋'; title 悬停可见。
3. 非安全上下文验证 (可选): `python3 -m http.server 8080 --bind 0.0.0.0` 用 http://<局域网IP>:8080 访问 → 拷贝走降级仍成功 (或不报 TypeError)。
4. CI 绿跑 (review push 后)。
