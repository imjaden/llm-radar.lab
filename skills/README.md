# skills/

本目录是 `lr prompt` 的**技能供给源**（collector 侧 `SKILLS_DIR = PROJECT_ROOT/skills`），随仓分发、随版本走。
它**不是** Hermes profile 的受管技能树（那套在用户 home 下的 hermes 目录与 hermes-manager 仓内）。

## 目录体系

本仓只有一层：skills/&lt;name&gt;/SKILL.md。
跨仓的「务实三层」（通用 skills / 治理 skills-governance / 启用 skills-active）**不在本仓落地** ——
本仓只需要「能被 `lr prompt` 列出 + 读全文」这一层，治理与启用由 hermes-manager 侧负责，
因此本仓不建 skills-governance/、skills-active/ 目录（`hm check readme` 对这两个路径显示「本仓不适用，跳过」）。

| 技能 | 用途 |
|:--|:--|
| [github-workflow](github-workflow/SKILL.md) | git 操作范式：批量提交改写、rebase 收敛、无 force 自愈流程 |
| [x-twitter-collector](x-twitter-collector/SKILL.md) | X 热点采集：CDP 复用登录态、风控处理、登录态持久化排障 |

## 新增技能（skills-extension 约定）

- 一个技能 = 一个目录 + 一份 SKILL.md：目录名小写连字符，frontmatter 的 `description` 写**触发条件**，正文写「怎么做 + 坑」。
- 遵循 skills-extension 约定：**引用不复写** —— 外部真源只给路径，不把正文抄进本仓（避免两处漂移）。
- 自检：`lr prompt` 应列出新技能；`lr prompt <name> --brief` 应返回摘要而非报错。
- 本目录变更后跑 `hm check readme .`（本文件亦受同一套 README 联动检查）。
