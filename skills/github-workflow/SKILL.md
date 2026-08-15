---
name: github-workflow
description: llm-radar GitHub Actions CI 工作流与前端/后端变更验证 — 修复假阳性测试教训后的验证规范
category: ci
tags: [github-actions, ci, pytest, html, css, verification]
triggers:
  - 修改 index.html / changelog.html / tests/test_html.py 后需验证
  - 修改 llm-radar-collector.py 或 git-flow 相关代码后需验证
  - CI 报 test_html 或 test_timestamp 失败
  - 需要理解项目测试结构与验证命令
---

# GitHub Workflow (llm-radar CI)

llm-radar 的 CI 与本地验证规范。沉淀自 2026-08-15 两次 CI 失败教训(假阳性测试 + 验证不完整)。

## CI 工作流

- `.github/workflows/test.yml`: push 到 main / feat-* 分支、PR 到 main 时触发
- 命令: `python3 -m pytest tests/ -v --tb=short`(全量, 不排除 selenium)
- 环境: macos-latest, Python 3.11, `pip install pytest openai requests beautifulsoup4 selenium webdriver-manager prettytable`
- 密钥: `DEEPSEEK_API_KEY` 通过 GitHub Secrets 注入

## 验证命令(本地必须覆盖 CI 非 selenium 部分)

### 前端文件改动 (index.html / changelog.html / tests/test_html.py)

```bash
python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q
```

- 必须跑 pytest, 不能只靠浏览器 Selenium 渲染验证(它标记 @pytest.mark.selenium, CI 可能 skip)
- Selenium 渲染验证是补充: 用 headless Chrome + 本地 http.server, 检查 SEVERE/ERROR console 日志 + getComputedStyle 字号

### 后端/collector 改动

```bash
python3 -m pytest tests/test_gitflow.py -q   # 14 用例
python3 -m pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q  # 全量
```

### 测试残留清理

全量测试会写脏 `timestamp.json` / `overview.json` / `data/snapshot.json`(test_timestamp 用真实 project_root):
```bash
git checkout -- timestamp.json overview.json data/snapshot.json
```

## 2026-08-15 事故复盘(假阳性测试)

### 事故链

1. test_html.py 的 JS 语法检查正则扫**整个文件**找"含连字符的裸 key+冒号", 本意是防 emoji map 的 `google-deepmind` 不带引号
2. 当时 index.html/changelog.html 的 CSS 恰是 `'font-size':0.7rem`(带引号的**错误写法**)——恰好满足正则断言(要求 key 前非引号 → 跳过)
3. 测试绿灯 = 假阳性: CSS 实际是坏的, 测试保护的是"不存在的保证"
4. 修复 CSS 去引号(正确做法) → 测试立刻失败, 因为正则把 CSS 属性/伪类当 JS key

### 三层根因

| 层 | 根因 | 修复 |
|:---|:-----|:-----|
| 测试断言 | 想保护 JS 对象字面量, 却扫整个文件, 误伤 CSS | 只扫 `<script>` 块, 排除 `<style>` 块 |
| 假阳性绿灯 | 断言依赖被检查对象的巧合形态 | 测试通过 ≠ 行为正确; 改动实现时必须同步审视测试 |
| 验证不完整 | 修 index.html 后只做浏览器验证, 没跑 pytest 全量 | 前端改动必跑 pytest 非 selenium 全量 |

### 防复发规则

1. **测试断言必须精确匹配意图**: CSS 属性不带引号是合法写法, 不属于 JS key 检查范围
2. **前端改动 = 必跑 pytest**: 浏览器验证是补充, 不能替代
3. **本地验证集合覆盖 CI**: CI 跑全量, 本地至少跑同一集合去掉 selenium/cli
4. **假阳性检测**: 当断言依赖"被检查对象的某个巧合形态"时, 警惕测试在保护不存在的保证

## HTML 结构要点(CI 测试相关)

- index.html: `<style>` 块 23-142 行, `<script>` 块 11-22 与 258-888 行
- changelog.html: `<style>` 块 17-26 行, `<script>` 块 11-16 与 42-250 行
- CSS 属性**不得用引号包裹**(`'font-size':0.7rem` 是无效 CSS, 浏览器丢弃声明)
- 伪类选择器不得写成 `.'filter-chip':hover`(应为 `.filter-chip:hover`)
- emoji map key 含连字符/点号必须带引号(`'google-deepmind':`, `'gpt-5-6':`)——这是 JS 对象字面量, 与 CSS 相反

## 验证脚本模式(ad-hoc)

- 项目无正式测试套件, CI 用 pytest; 额外验证用 `hermes-verify-` 前缀临时脚本(tempfile 路径), 跑完清理
- 组合验证: 静态断言(grep/regex)+ Selenium 真实渲染(计算样式)
- 真实渲染用本地 http.server + 随机端口(避免端口冲突), headless Chrome
