# skills 供给站 + prompt 子命令 实现审计报告 (LLM-RADAR-CL004)

> 日期: 2026-08-27 (审计执行日)
> 项目路径: ~/CodeSpace/llm-radar.lab
> 设计文档: documents/solutions/llm-radar-skills-prompt-design-v1.0-20260827.md (commit 8f14683)
> 设计评审: documents/reviews/llm-radar-skills-prompt-review-v1.0-20260827.md (PASS 90/A, RIG-001/002 并入实现验收清单)
> 实现 commit: f0276ea feat@llm-radar: add x-twitter-collector skill and prompt subcommand (LLM-RADAR-CL004)
> 审计者: ops/llm-radar-skills-prompt-impl-audit (hermes-1.2.0)
> 审计方法: 1A 协议第 7 步独立核验 — 不采信 dev 自报, 全部证据来自 git diff / 源码读取 / 独立复跑 / hs 逐行对照 / 运行时实测
> 约束: 只读项目文件 (除报告与 review-log/.review-level 追加); 未 commit / 未 push

## 结论摘要

**✅ PASS — 95/100 (A)。** 评审「实现验收清单」5 项核心变更全部落地:

- **SKILL.md (验收 1)** ✅: frontmatter (name/description 首 57 字符自含 "Use when operating" 触发/category devops) + 正文 7 节与 scripts/twitter-collector.py 实况逐一核验一致; OBS-3 双 profile 概念表 (cache/twitter-profile vs ~/chrome-twitter-cdp:9222) 就位, "浓缩+深度指针"注明成立。
- **collector prompt (验收 2)** ✅: main() 分支在 help 之后、`LLMRadarCollector()` 实例化之前, sys.exit 于分支内; `_cmd_prompt` 行为矩阵 8 行与 hs cli.py:685-800 逐行对齐; SKILLS_DIR=PROJECT_ROOT/'skills' (L47); 参数解析三形态全覆盖; 运行时实测无 "DeepSeek API key" 日志。
- **RIG-001 (验收 3)** ✅: help【其他】组两行式落地 — `  prompt` + 10 空格描述行, 与同组 help/<cmd> help 行字节级同格式 (评审修正块字面亦为 10 空格, "11 空格"系评审笔误, 见 IMPL-OBS-1)。
- **测试 (验收 4)** ✅: test_cli.py 8 用例 (含 RIG-002 `test_cli_prompt_json_not_found`) 全部落地; 独立复跑 21 passed (13+8); 断言防假阳性整体成立 (精确集合/exit code/stderr-stdout 分流), 唯 no_key_log 断言串 scope 有盲点 → AUD-001 🟡 (非阻塞)。
- **AGENTS.md (验收 5)** ✅: 三处同步 (结构 L20 / Key Commands L33 / CLI 治理 L45), 与 OBS-4 要求逐行一致。

独立复跑: test_cli 21 passed (预期 21) + 全量 243 passed / 2 deselected (预期 243) — 与审计预期完全一致; 手工实测 6 项全过; 测试污染 3 文件精确还原 (git status 回到仅 3 件评审产物)。

1 🟡 (AUD-001, 测试硬化建议, 不阻塞) + 5 🟢 观察。

## 逐项验证表 (对照评审实现验收清单 5 项 + RIG-001/002)

| # | 验收项 | 预期 | 结果 | 证据 (独立验证) |
|:--|:-------|:-----|:----:|:----------------|
| 1 | SKILL.md — frontmatter | name: x-twitter-collector; description 首 57 字符自含触发 ("Use when operating…"); category: devops | ✅ | SKILL.md:2-4 — `name: x-twitter-collector` / `category: devops`; 首 57 字符 = `Use when operating llm-radar X 热点采集器 — CLI/配置/登录态/故障速查 (浓` (python len 实测, 触发自含) |
| 1 | SKILL.md — 正文 7 节 (1) CLI 签名/退出码 | 默认 collect / --collect / --login / --dry-run / --attach; exit 0/1/2 | ✅ | SKILL.md §CLI 签名与退出码 (L21-32) vs 脚本头部 L12-15 四参数逐一命中; exit 2 路径实测 = collector.py:724 (登录态失效) / :785 (登录墙, LOGIN_HINT L58); exit 1 路径 = 配置/抓取错误多处 (L660/691/696/713/738…) |
| 1 | SKILL.md — 正文 7 节 (2)(3) 配置 + schema | twitter-targets.yaml name/handle/url 必填, enabled/max_tweets 缺省容错 (max 30); twitter.json 30/24h schema | ✅ | SKILL.md §配置 (L36-40) / §schema (L42-59) vs 脚本 L48-50 `RETENTION = '30/24h'` (DEFAULT_MAX_TWEETS=30, RETENTION_HOURS=24) + data/twitter-targets.yaml 头部注释 (必填/缺省) + 10 账号实测 (grep handle: = 10) |
| 1 | SKILL.md — 正文 7 节 (4) 登录态与 CDP 双 profile 表 (OBS-3) | 区分脚本默认 profile vs 运维实际登录态 (~/chrome-twitter-cdp:9222) | ✅ | SKILL.md L65-68 概念表: `cache/twitter-profile/` (DEFAULT_PROFILE_DIR, TWITTER_PROFILE_DIR 可覆盖) vs `~/chrome-twitter-cdp` + CDP 9222 (cron --attach 复用; Chrome ≥151 禁止默认 profile 调试端口); 与脚本 L46 DEFAULT_PROFILE_DIR 一致; --login/--attach/登录墙 exit 2/pidfile 互斥 (L70-76) 均有脚本对应 |
| 1 | SKILL.md — 正文 7 节 (5)(6)(7) auto-push + cron + 故障排查 | 入库 auto-push 语义 / cron 20 9,21 错峰 / 故障浓缩+指向 x-twitter-scraping | ✅ | SKILL.md L78-83 auto-push (git add 限 data/twitter.json, push 失败下轮重试) / L85-92 cron 20 9,21 与 AGENTS.md X 采集节一致 / L94-106 故障排查 3 条浓缩 + 通用深坑指向 x-twitter-scraping (L16-17 "此处不复制" 注明); "浓缩+深度指针" OBS-3 要求成立 |
| 2 | collector — main() 分支位置 | prompt 分支在 help 之后、LLMRadarCollector() 实例化之前; sys.exit 于分支内 | ✅ | collector.py:2346-2349 — help 分支 2342-2344 之后、status/_silent_collector 2352 与实例化 2355 之前; `_cmd_prompt(args); sys.exit(0)` 于分支内; 未知命令 else 2425-2427 exit 1 不受影响 |
| 2 | collector — _cmd_prompt 行为矩阵 8 行全对齐 hs | 无参列表 / <name> 全文 / --brief / --json 列表 / --json 详情 / 不存在 stderr+列表+exit 1 / 不存在 --json 信封 / 目录缺失空报错 exit 1 | ✅ | collector.py:2207-2321 vs hs cli.py:685-800 逐行比对: json_mode/brief flag + `next((a for a in args if not a.startswith('-')), None)` 参数解析同构; 目录缺失 (2217-2223) / 空 (2241-2247) / 列表 (2250-2269) / 详情 (2271-2292) / brief (2294-2311) / 全文+refs 追加 (2313-2321) 全对齐; 仅 3 处适配: SKILLS_DIR 模块级常量 / 用法行前缀 llm-radar / brief 扫描 ^#{2,3} (设计 §3.2 明确采用, OBS-1 已知) |
| 2 | collector — 参数解析三形态 + SKILLS_DIR + 无 key 日志 | prompt --json / <name> --json / --brief <name> 三形态; SKILLS_DIR=PROJECT_ROOT/'skills'; prompt 路径无 "DeepSeek API key" | ✅ | SKILLS_DIR L47 `PROJECT_ROOT / 'skills'`; 三形态运行时实测 (--brief 前置 `llm-radar prompt --brief x-twitter-collector` 正常输出 description+章节); `prompt`/`prompt x-twitter-collector` stdout+stderr grep 'DeepSeek API key' = 0 命中 |
| 3 | RIG-001 — help 两行式 | 【其他】组 `  prompt` + 缩进描述行, 与既有行同格式 | ✅ | collector.py:2178-2179 = `  prompt` (2 空格) + `          列出可用技能（AI 对接，llm-radar prompt <name> 输出全文）` (10 空格); 与同组 2176-2177 help / 2180-2181 <cmd> help 字节级同格式 (python 逐行 indent 计数 2/10); 运行时 `llm-radar help` 实测输出一致 |
| 4 | test_cli.py 8 用例 (含 RIG-002) | 8 新用例: list/detail/brief/json_list/json_detail/not_found/json_not_found/no_key_log | ✅ | tests/test_cli.py:137-220 共 8 用例; RIG-002 `test_cli_prompt_json_not_found` (L206-213) 落地 — exit 1 + json.loads(stdout) + status error + data None + error 含 "不存在"; 独立复跑 21 passed (13 既有 + 8 新增; 评审验收清单预测 "20 (13+8−1)" 系算术笔误, 见 IMPL-OBS-2) |
| 4 | test_cli 断言防假阳性 | 精确集合 / exit code / stderr-stdout 分流 / no_key_log scope | ✅ (AUD-001 见发现项) | json_list 用 `names == EXPECTED_SKILLS` 精确集合相等 (L183, 多/缺 skill 均红); 8 用例全断言 returncode; not_found 分流断言 stderr 报错 + stdout 可用列表 (L201-203); no_key_log 断言 stdout+stderr 合并 (L220) — 但断言串仅覆盖成功路径日志 → AUD-001 |
| 5 | AGENTS.md 三处同步 (OBS-4) | 项目结构 skills/ + Key Commands prompt + CLI 治理 lr prompt | ✅ | AGENTS.md:20 (结构节 `skills/ — 项目 skills 供给站…`), :33 (Key Commands `python3 llm-radar-collector.py prompt [skill]`), :45 (CLI 治理 `lr prompt [skill] [--brief|--json]`) — 三处逐一命中, 与 OBS-4 要求一致 |

## 数据验证 (独立复跑)

| 验证项 | 命令 | 结果 |
|:-------|:-----|:-----|
| 实现 commit 存在且 HEAD | `git log --oneline -3` + `git show --stat f0276ea` | ✅ f0276ea 为 HEAD (ahead 2 = 8f14683 design + f0276ea impl), 4 文件 323+ (AGENTS 3 / collector 125 / SKILL.md 109 / test_cli 86); git status 审计前仅 3 件评审产物 (review-log.md/.review-level.yaml 修改 + 设计评审 untracked) |
| test_cli 定向 | `python3 -m pytest tests/test_cli.py -q` | ✅ **21 passed** in 6.26s (与审计预期 21 一致) |
| 全量测试 | `python3 -m pytest tests/ -m "not selenium" -q` | ✅ **243 passed, 2 deselected**, 3 warnings (与审计预期 243 一致); NotOpenSSLWarning 实测出现 (urllib3 v2 + LibreSSL 2.8.3) — D4 "所有命令均有" 前提成立 |
| 测试污染还原 | `git checkout -- timestamp.json overview.json data/snapshot.json` | ✅ git status 回到仅 3 件评审产物 (M .review-level.yaml / M review-log.md / ?? 设计评审报告), 与审计前一致 |
| hs 对照 | read hs cli.py:685-800 | ✅ _cmd_prompt 逐行比对: SKILLS_DIR 定位 (llm-radar 用模块常量等价)/8 行矩阵/参数解析/brief 扫 `^## ` 差异 (OBS-1) 全记录 |
| 手工 1 — 列表 | `llm-radar prompt` | ✅ exit 0; "可用 skills:" + 双 skill + description + 用法行 `llm-radar prompt <name>`; stderr 仅 urllib3 警告 |
| 手工 2 — 全文无 key 日志 | `llm-radar prompt x-twitter-collector` | ✅ exit 0; SKILL.md 全文; stdout+stderr grep 'DeepSeek API key' = 0 (stderr 仅 urllib3 警告, D4 已知) |
| 手工 3 — 不存在 | `llm-radar prompt nope` | ✅ exit 1; stderr `❌ skill 'nope' 不存在`; stdout `可用: github-workflow, x-twitter-collector` |
| 手工 4 — --json 信封 | `llm-radar prompt --json` | ✅ json.loads 成功: status=ok / error='' / names 精确 = [github-workflow, x-twitter-collector] / description 全非空 |
| 手工 5 — 错误信封 | `llm-radar prompt nope --json` | ✅ exit 1; status=error / data=null / error="skill 'nope' 不存在" |
| 手工 6 — help 两行式 | `llm-radar help` 【其他】组 | ✅ `  prompt` + 10 空格描述行, 与 help/<cmd> help 行同格式 (repr 字节级确认) |
| SKILL.md 实况核验 | grep/read scripts/twitter-collector.py + data/twitter-targets.yaml | ✅ CLI 签名 (L12-15) / DEFAULT_PROFILE_DIR (L46) / RETENTION 30/24h (L48-50) / 退出码 2 路径 (L724/785) / 登录墙检测 (L553-591) / targets 10 账号 — 7 节全部与实况一致 |

## 发现项

### AUD-001 🟡 — test_cli_prompt_no_key_log 断言 scope 盲点 (非阻塞)

- **问题**: `test_cli_prompt_no_key_log` 断言串 `"DeepSeek API key" not in (r.stdout + r.stderr)` 仅匹配构造器**成功路径**日志 (`DeepSeek API key 已从环境变量加载`, collector.py:181); **失败路径**日志为 `❌ DEEPSEEK_API_KEY 未配置，请在 .env 文件或环境变量中设置` (L183, 全大写+下划线), 不含该断言串。
- **影响**: 本地环境 DEEPSEEK_API_KEY unset (测试 subprocess 直接 `python3 llm-radar-collector.py`, 不载 .env; wrapper 才载 .env) — 若回归 (prompt 分支移到实例化之后), 输出会是 "❌ DEEPSEEK_API_KEY 未配置" + 列表, 断言不触发 → **测试假绿**; CI (test.yml:17 `DEEPSEEK_API_KEY: ${{ secrets.DEEPSEEK_API_KEY }}`) 下成功路径日志会被抓到 → **CI 守卫有效**。断言串来自设计评审验收清单原文 ("stdout+stderr 无 'DeepSeek API key'"), dev 照规格实施 — 缺陷在设计规格的断言选择, 本次审计独立核验发现 (审计项 #4 no_key_log scope)。
- **修复建议** (后续 test 硬化, 不阻塞本 PASS): 断言同时排除 `"DeepSeek API key"` 与 `"DEEPSEEK_API_KEY"` 两串, 或断言 stdout 无时间戳前缀日志行 (`\d{4}-\d{2}-\d{2}` 前缀), 使本地/CI 双环境均能捕获实例化回归。

### 观察项 (🟢, 不计分)

| # | Severity | Title | 说明 |
|:-:|----------|-------|------|
| IMPL-OBS-1 | 🟢 | RIG-001 "11 空格" 系评审笔误 | 评审修正块字面 (review doc L94-95) = 代码栅栏 2 空格 + `  prompt` + **10 空格**描述行; 实现 L2178-2179 = 2+10, 与修正块字面及文件既有行 (L2177/2181 均 10 空格) 三重一致 — 实现正确, 无漂移 |
| IMPL-OBS-2 | 🟢 | 评审验收清单预测 test_cli "20 passed (13+8−1)" 系算术笔误 | 实际 21 = 13 既有 + 8 新增 (无删减), 与审计预期 21 一致; 设计评审的 "−1" 无来源, 不影响验收 |
| IMPL-OBS-3 | 🟢 | urllib3 NotOpenSSLWarning 在 prompt stderr 出现 | D4 已知 ("所有命令均有", 与 help 一致, 一致性优先); 手工实测确认; 非缺陷 |
| IMPL-OBS-4 | 🟢 | github-workflow description 无 "Use when" 前缀 | 既有 skill, 非 CL004 范围 (57 字符触发要求仅针对 x-twitter-collector); 集合断言已覆盖其存在性 |
| IMPL-OBS-5 | 🟢 | brief 扫描 ^#{2,3} 为 hs ^## 超集 | 评审 OBS-1 已知; 设计 §3.2 明确采用 (章节含 ##/### 两级), 输出更全, 无影响 |

## 维度评估 (3D)

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 合理性 | 🟢 | 5 项验收与评审清单逐字一致; 3 处适配 (SKILLS_DIR 模块常量/用法行前缀/brief 范围) 均有设计依据; SKILL.md 7 节与脚本实况逐一核验无虚构 |
| 严格性 | 🟡 | AUD-001 no_key_log 断言 scope 盲点 (本地无 key 环境假绿风险, CI 有效); 其余边界 (目录缺失/空/不存在/双信封/三形态) 全有代码路径 + 测试 + 手工三重覆盖 |
| 安全性 | 🟢 | 纯文档 + 只读子命令, 0 注入面; --json 信封 status/data/error 键全断言; 无 API key 泄漏 (实测 grep 0); 分支位置消除构造期日志 |

## 评分明细

```
基准分: 100
  验收 1-5    ✅ 全部落地 (不计分)
  RIG-001     ✅ 两行式落地 (2+10 空格, 与既有行一致)
  RIG-002     ✅ 第 8 用例落地 (test_cli_prompt_json_not_found)
  AUD-001     🟡 -5  no_key_log 断言串只匹配成功路径日志 (本地无 key 环境假绿风险, CI 有效)
  IMPL-OBS-1~5 🟢 观察 (不计分)
────────────────────────
得分: 95 → A → ✅ PASS
```

## 结论

**✅ PASS — 95/100 (A)。** 实现 commit f0276ea 与设计 D1-D6 + 评审「实现验收清单」
5 项核心变更逐一吻合; RIG-001/RIG-002 两项评审 🟡 在实现中按要求落地; 独立复跑
test_cli 21 passed + 全量 243 passed / 2 deselected 与审计预期完全一致; 手工实测
6 项全过 (无 key 日志 / exit 1 / 双信封 / 两行式); SKILL.md 7 节与脚本实况逐一核验
无虚构。1 项 🟡 (AUD-001, no_key_log 断言 scope 盲点) 不阻塞 — 实现本身正确, CI
守卫有效, 修复建议 (断言双串或时间戳前缀) 记入报告供后续 test 硬化闭环参考。

实现 PASS, 可交由 review profile 按 1A 协议收尾 (push 等 review 阶段执行)。

---

*报告: documents/reviews/llm-radar-skills-prompt-impl-audit-v1.0-20260827.md | 结论: ✅ PASS 95/100 (A) | 验收 5 项全 ✅ + RIG-001/002 ✅ | AUD-001 🟡 (非阻塞) + IMPL-OBS-1~5 🟢 | 未 commit / 未 push (1A 约束)*
