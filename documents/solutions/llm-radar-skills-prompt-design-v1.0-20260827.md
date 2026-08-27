---
title: llm-radar skills 供给站 + prompt 子命令设计
topic: llm-radar
type: design
version: 1.0
date: 2026-08-27
author: hermes-1.2.0
tags: [llm-radar, skills, prompt, cli, ai-interchange, twitter]
profile: ops
provider: deepseek
model: deepseek-v4-flash
---

# llm-radar skills 供给站 + prompt 子命令设计 v1.0

> 探讨确认 (2026-08-27): 决策 D1 1A / D2 1B / D3 1C / D4 2D / D5 1E / D6 1F 锁定。
> 对应闭环: LLM-RADAR-CL004。

## 修订记录

- v1.0 (2026-08-27) — 初版: 决策锁定 (A1 B1 C1 D1 E1 F1), 编号修正为 LLM-RADAR-CL004
  (CL001/CL002/CL003 已被 2026-08-27 当日闭环占用)。

---

## 1. 背景与目标

llm-radar 已具备 AI 采集能力 (scripts/twitter-collector.py, CDP attach 登录态) 与
项目内 skills 先例 (skills/github-workflow/SKILL.md), 但缺少面向 AI 的"使用说明"
供给通道 (ai-interchange 通道①: 项目 skills/ 目录 + CLI `prompt` 子命令, hs 实证)。
本闭环三件事:

1. 将 X 采集功能沉淀为项目 skill `skills/x-twitter-collector/SKILL.md` (D1 1A)。
2. 修复 `llm-radar prompt` 报错 (现状: main() 无 prompt 分支 → "❌ 未知命令: prompt")。
3. 参考 hs `prompt` 逻辑实现 `llm-radar prompt [<skill>]` (D3 1C 全量对齐)。

约束 (继承):

- 纯文档 + CLI 子命令, 不调 LLM, 不采集数据, 无网络副作用。
- prompt 子命令不实例化 LLMRadarCollector (避免 API key 日志噪音, 与 help/status 先例一致)。
- 新增 skill 是纯文档动作, CLI 自动扫描; 但必须同步 skills 精确集合断言测试 (ai-interchange 验收 #6)。

## 2. 决策记录

| # | 决策 | 内容 |
|:---|:---|:---|
| D1 | skill 命名 | 1A: `x-twitter-collector` (对应脚本名, 简洁) |
| D2 | skill 内容范围 | 1B: 项目专属运维速查; 通用 X 技术深坑指向 Hermes skill x-twitter-scraping, 不整篇复制 |
| D3 | prompt 功能范围 | 1C: 全量对齐 hs — 无参列表 / <name> 全文 / --brief / --json 信封 / 不存在报错+可用列表+exit 1 |
| D4 | urllib3 噪音 | 2D: 不动 (模块级 import requests 的 NotOpenSSLWarning 所有命令均有, 本次只修功能错误) |
| D5 | 测试策略 | 1E: test_cli.py 扩展 subprocess 黑盒用例 + skills 精确集合断言 (仿 hs test_prompt.py) |
| D6 | 流程与编号 | 1F: 设计文档 → draft LLM-RADAR-CL004 READY → dev → 用户核实 → review 审计 → push (仅 review) |

## 3. 详细设计

### 3.1 skills/ 目录与 x-twitter-collector skill (D1 1A / D2 1B)

- 位置: `skills/x-twitter-collector/SKILL.md`, 与已入库的 `skills/github-workflow/SKILL.md` 同构
  (YAML frontmatter: name/description/category/tags/triggers + 正文)。
- frontmatter 建议: category: devops; description 首 57 字符内自含触发条件
  ("Use when operating llm-radar X 热点采集器…")。
- 内容大纲 (B1 项目专属, 素材源: scripts/twitter-collector.py 头部 / x-hotspot-design-v1.3 §3-§4 /
  data/twitter-targets.yaml / AGENTS.md X 采集节 / Hermes skill x-twitter-scraping 提炼):

  1. CLI 签名与退出码: 默认 collect / --collect / --login / --dry-run / --attach;
     exit 0=成功(含部分成功) / 1=抓取失败或配置错误 / 2=登录态失效。
  2. 配置 `data/twitter-targets.yaml`: name/handle/url 必填, enabled 默认 true,
     max_tweets 默认 30; 增删人物后采集自动生效。
  3. 数据 schema `data/twitter.json`: targets[].tweets[] 字段
     (id/text/forward/posted_at(UTC Z)/url/views/replies/retweets/likes/images);
     retention "30/24h" 条数窗口规则。
  4. 登录态与 CDP: profile ~/chrome-twitter-cdp + 9222; --login 人工登录一次;
     cron 自动拉起; 登录墙检测 → exit 2 + 人工恢复提示。
  5. 入库与 push: 采集成功自带 commit+push `auto-push@llm-radar: update twitter (N changes)`;
     push 失败仅记 cron 日志, 下轮自动重试。
  6. cron `20 9,21 * * *` 错峰 (避开主采集整点 :00, 防双 Chrome 资源竞争)。
  7. 故障排查 (仅本采集器直接相关): 残留 Chrome/Singleton 锁清理、chromedriver pin
     (attach 卡死)、attach 后零页面恢复 (curl -X PUT 开新 tab)。
     通用 X 技术深坑 (虚拟列表 DOM 回收/动态滚动/自动化登录被拦截/降级) →
     指向 Hermes profile skill `x-twitter-scraping`, 不复制。

- 挂载机制: 无额外动作 — prompt 子命令自动扫描 skills/ 目录供给 (与 github-workflow 同构)。
- 分工边界: Hermes profile 层 x-twitter-scraping (通用技术) / llm-radar-ops (项目运维速查);
  项目 skills/ 层是本仓库 AI 对接供给 (通道①), 三处不重复。

### 3.2 prompt 子命令实现 (D3 1C, 对齐 hs cli.py:685-770)

- main() 分支位置: `command == 'prompt'` 放在 `help` 分支之后、
  `LLMRadarCollector()` 实例化之前 (与 help/status 先例一致, 无 API key 日志)。
- `_cmd_prompt()` 独立函数, 行为矩阵:

| 输入 | 输出 | exit |
|:---|:---|:---|
| 无参 | "可用 skills:" 列表 — name + description + references + 用法行 `llm-radar prompt <name>` | 0 |
| `<name>` | SKILL.md 全文 | 0 |
| `<name> --brief` | description + 章节标题 (章节: 扫描 `^#{2,3} ` 行) | 0 |
| `--json` (无参) | `{status: ok, error: "", data: [{name, description, references}]}` | 0 |
| `<name> --json` | `{status: ok, error: "", data: {name, content, references: {stem: text}}}` | 0 |
| `<不存在>` | stderr `❌ skill '<name>' 不存在` + stdout 可用列表 | 1 |
| `<不存在> --json` | `{status: error, data: null, error: "skill '<name>' 不存在"}` | 1 |
| skills/ 缺失或空 | `❌ skills/ 目录不存在` / `❌ 无可用 skill` (--json 信封对应) | 1 |

- 实现要点:
  - `SKILLS_DIR = PROJECT_ROOT / 'skills'` (脚本已有 PROJECT_ROOT 常量)。
  - 参数解析: `--json` / `--brief` 为 flag; 第一个非 `-` 开头参数 = skill_name。
  - description 提取: 逐行读 frontmatter 中 `description:` 行取第一个 (同 hs `_skill_desc`)。
  - references: 仅列出 `references/*.md` 文件名 (列表模式) / 全文 (详情 --json)。
  - 输出用 print, 与脚本现有风格一致; 不引入新依赖。

### 3.3 urllib3 NotOpenSSLWarning (D4 2D)

- 不处理。模块级 `import requests` (llm-radar-collector.py:35) 在 import 期触发
  urllib3 v2 + LibreSSL 警告, **所有命令均有** (含 help, 已实测复现)。
- prompt 分支提前于 collector 实例化已消除 "✅ DeepSeek API key" 日志;
  保留 import 期警告以与 help 行为一致 (一致性优先, 避免只对单命令做特殊抑制)。
- 若后续想全局清理, 另开闭环处理 (记观察 O-3)。

### 3.4 help 分组更新

- `print_grouped_help()` 的【其他】组补一行:
  `llm-radar prompt             列出可用技能 (AI 对接, llm-radar prompt <name> 输出全文)`
- 对齐 hm-style 分组帮助格式 (对齐列宽)。

## 4. 测试与验收 (D5 1E)

### 4.1 test_cli.py 扩展 (subprocess 黑盒, 与 test_cli_sources/test_cli_help 同风格)

1. `test_cli_prompt_list`: `prompt` → exit 0, stdout 含 `github-workflow` +
   `x-twitter-collector` + 用法行 `llm-radar prompt x-twitter-collector`。
2. `test_cli_prompt_detail`: `prompt x-twitter-collector` → exit 0,
   stdout 含 `# x-twitter-collector` + 关键章节 (如 "CLI 签名" 或 "登录态")。
3. `test_cli_prompt_brief`: `prompt x-twitter-collector --brief` → 含 description + `章节:`。
4. `test_cli_prompt_json_list`: `prompt --json` → exit 0, status ok,
   names 集合 = {github-workflow, x-twitter-collector} (精确断言, 防漂移)。
5. `test_cli_prompt_json_detail`: `prompt x-twitter-collector --json` →
   status ok + data.name + data.content 含正文。
6. `test_cli_prompt_not_found`: `prompt nope` → exit 1, stderr 含 "不存在",
   stdout 含可用列表。
7. `test_cli_prompt_no_key_log`: `prompt` → stdout/stderr 不含 "DeepSeek API key"
   (验证未实例化 collector, 防回归噪音)。

### 4.2 验收标准

1. `llm-radar prompt` 无参列出 skills 清单 (github-workflow + x-twitter-collector) exit 0。
2. `llm-radar prompt x-twitter-collector` 输出全文 exit 0, 无 API key 日志。
3. `llm-radar prompt nope` exit 1 + stderr 报错 + stdout 可用列表。
4. `--json` 信封实测: 正常路径 status ok / 错误路径 status error + exit≠0。
5. pytest 全量绿 (含 test_cli.py; CI `pytest tests/` 自动覆盖)。

验证命令:

```bash
python3 -m pytest tests/test_cli.py -q                     # 新增 prompt 用例
python3 -m pytest tests/ -m "not selenium" -q              # 全量 (CI 等价, 本地)
# 注意: 本地传统验证命令 --ignore=tests/test_cli.py, 本闭环新增用例后必须显式跑 test_cli.py
```

## 5. 观察项

- O-1: skills 精确集合断言 (test_cli.py EXPECTED_SKILLS 或等价) — 新增 skill 必改断言
  (ai-interchange 验收 #6 先例, 防漂移)。
- O-2: AGENTS.md 双处同步 — CLI 治理节补 `prompt` 命令 + 项目结构节补 skills/ 目录
  (防漂移 O-2 先例; dev 阶段实施)。
- O-3: urllib3 NotOpenSSLWarning 全局清理 (D4 2D 决定本次不动; 若用户后续要求全命令
  干净, 另开闭环, 模块级 filterwarnings 一行改动)。

## 6. 实施顺序 (dev)

1. 新建 `skills/x-twitter-collector/SKILL.md` (D2 1B 内容大纲)。
2. collector: `_cmd_prompt()` + main() `prompt` 分支 (help 之后) + help 分组补行。
3. test_cli.py 扩展 7 用例 + AGENTS.md 双处同步。
4. 验证: test_cli.py + 全量 pytest + 手工实测 4 条验收命令。

## 7. 风险与回退

| 风险 | 影响 | 缓解 |
|:---|:---|:---|
| skills/ 目录缺失/为空 | prompt 报错 | 报错 + exit 1 (与 hs 同构); 测试断言错误路径 |
| main() 分支位置错误 | API key 日志噪音回归 | 分支放 help 之后、实例化之前; test_cli_prompt_no_key_log 防回归 |
| --json 信封格式漂移 | AI 对接解析失败 | 测试断言 status/data/error 键 |
| 断言与 skill 集合漂移 | 新增 skill 后测试红 | O-1 集合断言, 加内容必改断言 |
| AGENTS.md 与实现漂移 | 文档误导 | O-2 双处同步 + review 审计检查 |

---

> 设计评审入口: documents/reviews/ (LLM-RADAR-CL004 闭环)。
