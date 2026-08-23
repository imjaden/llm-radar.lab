# llm-radar 目录改名旧路径清理 — review报告 v1.0

> 日期: 2026-08-23
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.lab
> 审计对象: 3 个未 push commit (4d7095b / ae05a70 / 1d8699c, git log origin/main..HEAD)
> review维度: 实现一致性 / commit 规范 / 测试质量 / 边界合规
> 审核人: Security Reviewer (IRIS)

## 数据验证

| 验证项 | 方法 | 结果 |
|:-------|:-----|:-----|
| 待 push commit 实况 | `git log origin/main..HEAD` | ✅ 恰好 3 个: 4d7095b fix@llm-radar / ae05a70 docs@llm-radar / 1d8699c chore@project, 与 prompt 一致 |
| 活跃层旧路径残留扫描 | `grep -rn "llm-radar\.jaden\.tech"` (排除 documents/reviews/、archive/、mcp/、ops/、integ/、loop/、cache/、audit-log.md、review-log.md、logs/、data/*.log、*.pyc) | ✅ 0 文本命中; 仅剩 gitignored 运行时产物 (__pycache__/*.pyc 陈旧字节码, data/collector.log + data/mcp-server.log 历史运行日志, logs/) — 非源码残留 |
| 变体路径扫描 | `grep -rn "llm-radar[\.-]jaden"` 同排除集 (.py/.sh/.yaml/.html/.md/.js) | ✅ 0 命中 |
| 源码层测试引用 | `grep -rn "jaden\.tech" tests/` | ✅ tests/*.py 源码 0 命中 (仅 tests/__pycache__/*.pyc 陈旧字节码, gitignored 自动再生成) |
| 域名一致性 | `cat CNAME` + 活跃层 grep "jaden.tech" | ✅ CNAME = `llm-radar.lab.jaden.tech`; README/llm-radar-prompt.md/scripts/llm-radar-health.py:41/AGENTS.md 全部使用 `.lab.jaden.tech` 现域名 (注: prompt 背景称"站点域名 llm-radar.jaden.tech 不变"已过时, 实际域名随改名迁至 .lab, 代码侧一致无矛盾) |
| 聚合常量一致性 | `grep -n "project" tasks/agents-teamwork.yaml` + tasks/al-scanner.py:93 | ✅ 两处均 `llm-radar` |
| index.html 复制命令 | 4d7095b diff L788 | ✅ `cd ~/CodeSpace/llm-radar.lab && python3 llm-radar-collector.py run`, 与现目录一致 |
| handoff.doc 指针 | `.hermes-project.yaml` + `ls documents/handoff/` | ✅ `documents/handoff/handoff-llm-radar.lab-review.md` 存在 (4719B), 无悬空指针 |
| 全量回归 (非 selenium) | `pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q` | ✅ 109 passed, 2 deselected, 0 failed |
| 测试污染还原 | `git checkout -- data/snapshot.json overview.json timestamp.json` + `git status` | ✅ 工作区 clean |
| 旧命名归档 | `git ls-files \| grep jaden.tech` | ✅ 仅 documents/archive/handoff-llm-radar.jaden.tech-review.md (rename 100% similarity, 归档预期) |
| .hermes-project.yaml 历史 | `git log --oneline -- .hermes-project.yaml` + git show b3ce8de/530f875 | ✅ b3ce8de 建文件 (无 handoff), 530f875 加 handoff 段 (doc 从一开始即 lab-review), 1d8699c 仅改名规范 + updated_at |

## 一、实现一致性评估 (✅ PASS)

- ✅ 4d7095b (5 文件 5 行): index.html:788 复制命令 cd 路径、llm-radar-run.sh:15 Mac 路径注释、tasks/al-init.py:25 `PROJECT = Path(REAL_HOME)/"CodeSpace/llm-radar.lab"`、tasks/al-scanner.py:93 + tasks/agents-teamwork.yaml:3 聚合常量 — 四处改动均正确落地, 无过度修改 (改动面精确到单行, 无连带重构)。
- ✅ al-scanner.py 聚合常量 (`"project": "llm-radar"`) 与 agents-teamwork.yaml (`project: llm-radar`) 一致; index.html 复制命令与现目录 llm-radar.lab 一致; llm-radar-run.sh Linux 路径 /home/admin/codespace/llm-radar.lab 本已正确, 未动。
- ✅ ae05a70: README.md:139 MCP config 示例、handoff dev/ops/review 三件正文关键路径、data-flow L92/L268 手动执行 cd 与环境表 — 全部同步 .lab; 旧命名 handoff-llm-radar.jaden.tech-review.md 纯 rename (similarity 100%) 至 documents/archive/, 归属 docs commit 合理。
- ✅ 1d8699c: project 字段与 session titles 统一为 `llm-radar` (去 .lab 后缀), updated_at 刷新至 2026-08-23; handoff.doc 指针本就指向 lab-review, 未再改动。
- 🟢 LR-SEC-019 — 命名漂移 (record-only)
  session titles 已规范为 `llm-radar-{ops,dev,review}` (无 .lab), 但 handoff 文件名保留 `handoff-llm-radar.lab-{dev,ops,review}.md` (含 .lab)。两者语义一致 (.lab 是新目录名非旧残留), 无功能影响; handoff.doc 显式配置, 无断链。可选后续统一, 不阻塞。

## 二、commit 规范评估 (✅ PASS)

- ✅ 3/3 符合 `type@scope: subject`: fix@llm-radar / docs@llm-radar / chore@project; type 集合 (fix/docs/chore) 均在项目既定约定内 (历史使用 audit@/docs@/chore@/fix@ 同族)。
- ✅ 分组合理: 代码+配置功能性路径修正 → fix@llm-radar; 文档同步+归档 rename → docs@llm-radar; 项目级 .hermes-project.yaml 注册文件 → chore@project。rename 落入 docs commit (归档文档), 合理。
- ✅ subject 简洁 (≤60 字符), commit body 与 subject 一致 (除下述 LR-SEC-018)。
- 🟢 LR-SEC-018 — 1d8699c subject 与 diff 不符 (record-only)
  subject "fix handoff doc pointer to lab-review" 描述的动作在 diff 中不存在 — handoff.doc 自 530f875 (2026-08-15) 起即指向 lab-review, 该 commit 实际变更是 project/session 命名去 .lab 化 + updated_at 刷新。prompt 中"由不存在的 handoff-llm-radar-review.md 修正"的描述亦与 git 历史不符 (该指针从未存在于 git 历史)。无功能影响 (指针当前正确且指向存在文件), 仅 commit 记录语义不准; 建议后续写作如 "chore@project: normalize project/session naming to llm-radar"。

## 三、测试质量评估 (✅ PASS)

- ✅ `pytest tests/ -m "not selenium" --ignore=tests/test_cli.py --ignore=tests/test_selenium.py -q` = **109 passed, 2 deselected, 0 failed** (0.51s)。
- ✅ tests/*.py 源码 0 处 jaden.tech 引用 (test_html 扫 index.html 渲染面, test_selenium 虽 deselected 但其 fixture 无旧路径依赖)。
- ✅ 已知副作用已还原: data/snapshot.json / overview.json / timestamp.json `git checkout --` 后 `git status` clean。

## 四、边界合规评估 (✅ PASS)

- ✅ 历史记录层保留旧路径属预期, 未误报: documents/reviews/* (8 个历史审计报告)、audit-log.md (LR-SEC-005/010 条目)、review-log.md (历史 Style B 条目)、documents/archive/handoff-llm-radar.jaden.tech-review.md (归档交接件)、documents/mcp/mcp-protocol-design、documents/ops/github-ci-issues、documents/integ/hermes-integration、documents/loop/agent-loop-design、cache/review-prep/prompt-*.md (含本审计 prompt) — 均保留旧命名, 按 append-only/归档原则不改写。
- ✅ gitignored 运行时产物中的旧路径 (__pycache__/*.pyc、data/collector.log、data/mcp-server.log、logs/) 为历史运行痕迹或陈旧字节码, 非代码缺陷, 自动再生成。
- ✅ .git/index 匹配源于归档文件路径含 jaden.tech (被跟踪文件名), 非内容残留。

## 安全事项

无 🔴。本批 commit 仅路径字符串与文档同步, 无凭证暴露、无注入面、无权限变更; index.html 剪贴板命令为用户点击触发的静态字符串 (非 innerHTML 注入), README MCP 示例中的 `LLM_RADAR_MCP_KEY: "llm-radar-mcp-2026"` 为既有示例占位值 (非新增泄露)。

## 评分

| 级别 | 数量 | 扣分 |
|:----:|:----:|:----:|
| 🔴 HIGH | 0 | 0 |
| 🟡 MEDIUM | 0 | 0 |
| 🟢 LOW | 2 (LR-SEC-018, 019) | 0 |

得分: 100 / 100 → Rating: A

## 结论

**PASS (100/A)** — 3 个 commit 完成目录改名后旧路径清理: 活跃层 (源码/配置/文档, 排除历史与归档层) `llm-radar.jaden.tech` 零残留, 变体拼写零残留, 聚合常量与复制命令相互一致, 无遗漏无过度; commit type@scope 格式 3/3 合规、分组合理; 全量非 selenium 测试 109 passed 0 failed; 边界层旧路径保留符合 append-only 原则。2 个 🟢 观察 (commit subject 语义、handoff 文件名命名漂移) 均不阻塞。

**待处理 (可选, 非阻塞)**: LR-SEC-018/019 见待确认清单, 由用户决定是否顺手统一。

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | LR-SEC-018: 1d8699c subject 描述的动作不在 diff (指针早已正确); 可接受现状或后续写注释澄清 | 治理 🟢 |
| □ | LR-SEC-019: handoff 文件名 (含 .lab) 与 session title (无 .lab) 命名漂移; 可接受现状或后续统一重命名 | 命名 🟢 |
