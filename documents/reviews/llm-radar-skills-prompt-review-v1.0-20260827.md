# skills 供给站 + prompt 子命令 设计 v1.0 — 评审报告

> 日期: 2026-08-27 (评审执行日)
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.lab
> 设计文档: documents/solutions/llm-radar-skills-prompt-design-v1.0-20260827.md (commit 8f14683)
> 决策: LLM-RADAR-CL004 — D1 1A / D2 1B / D3 1C / D4 2D / D5 1E / D6 1F
> 用户确认串: "A1 B1 C1 D1 E1 F1" (D4 标签歧义详见 OBS-2, 内容以复述批准"不动"为准)
> review者: ops/llm-radar-skills-prompt-review (hermes-1.2.0)
> review维度: 合理性 / 严格性 / 安全性 (3D + 100-base, 用户阈值 PASS ≥85/A)

## 结论摘要

设计 v1.0 与用户确认决策内容完全对应, 行为矩阵 8 行与 hs 实现逐项比对成立, 运行时验证
全部通过; 发现 2 项规格精度缺陷 (RIG-001/002, 机械级, 并入实现验收清单, 不阻塞 dev 启动):

- **§3.1 skill 定位 (A1/B1)** ✅: 命名 x-twitter-collector 对应脚本 scripts/twitter-collector.py
  (差 x- 前缀, 属 A1 用户确认命名, OBS-3 备注); 大纲 7 节与脚本头部实况 (CLI 签名/退出码
  0/1/2/retention 30/24h/配置 schema) 逐一核对一致; B1 边界成立 — 通用 X 技术深坑
  (虚拟列表 DOM 回收/动态滚动/自动化登录被拦截/降级) 全部指向 Hermes x-twitter-scraping 不复制,
  故障排查保留项为运维速查级浓缩, 与通用层重叠属可接受 (OBS-3 建议注明浓缩+指针策略)。
- **§3.2 prompt 行为矩阵 (C1)** ✅: 8 行 vs hs cli.py:685-800 逐项比对 — 列表/全文/--brief/
  --json 列表/--json 详情/不存在/不存在 --json/目录缺失全对齐; 参数解析规则 (flag + 首个非 -
  参数) 与 hs `next((a for a in args if not a.startswith('-')), None)` 一致, 覆盖
  `prompt --json` / `prompt <name> --json` / `prompt --brief <name>` 三形态;
  main() 分支位置 (help 之后、LLMRadarCollector() 实例化之前) 实测可行 — 构造器
  _load_api_key (L176-183) 的 key 日志 (L180/182) 不再触发, test 7 防回归成立。
- **§3.3 urllib3 不动 (D4)** ✅: 运行时实测 `help` 即出 NotOpenSSLWarning
  (python3.9 site-packages urllib3 v2 + LibreSSL 2.8.3), "所有命令均有"论证成立;
  与 help 行为一致性优先 + O-3 后置清理 = 当前最廉价一致方案 (模块级抑制即被拒的 D1;
  仅 prompt 抑制破坏一致性; PYTHONWARNINGS hacky)。
- **§3.4 help 分组** 🟡 RIG-001: 补行文案为单行内联 + 全称命令令牌, 与 print_grouped_help
  既有两行式 (命令行 / 缩进描述行) 格式不符, 按字面实现将产生列错位输出。
- **§4 测试 (E1)** ✅ 附 🟡 RIG-002: 7 用例覆盖 8 行矩阵的 6 行; 集合断言
  {github-workflow, x-twitter-collector} 防漂移成立 (skills/ 现状仅 github-workflow,
  基线正确); 本地显式跑 test_cli.py 已标注 (--ignore 坑); CI test.yml:14 不 ignore
  test_cli.py → 自动覆盖属实; 缺 `<不存在> --json` 自动化用例 (矩阵有行、hs 有用例)。
- **§5 观察项** ✅: O-1/O-2/O-3 合理; O-2 双处同步经 AGENTS.md 实测确认 (skills/prompt
  现 0 处提及) 确属必要, 可扩为三处 (Key Commands 节, OBS-4)。
- **决策对应 (7)** ✅: D1=1A/D2=1B/D3=1C/D4=2D(不动, 复述批准)/D5=1E/D6=1F; 编号
  LLM-RADAR-CL004 正确 (CL001/002/003 同日已占, review_history 实测)。

**评分: 90 / 100 (A) → ✅ PASS (≥85/A)。** 设计可进 dev。2 🟡 (机械级, 并入实现验收清单)
+ 5 🟢 观察项不阻塞。

## 逐项验证表 (7 项重点审查)

| # | 审查项 | 验证方法 | 结果 |
|:-:|:-------|:---------|:----:|
| 1 | §3.1 skill 定位 (A1/B1) | twitter-collector.py 头部 vs 大纲 7 节 + x-twitter-scraping 内容比对 | ✅ (OBS-3 备注) |
| 2 | §3.2 prompt 行为矩阵 | sed hs cli.py:685-800 逐行比对 + main() 2204-2302 分支位置 + 参数解析推演三形态 | ✅ (RIG-001/002 见发现项) |
| 3 | §3.3 urllib3 不动 (D4) | 运行时 `help` 2>&1 实测警告 + 一致性论证 + 替代方案枚举 | ✅ |
| 4 | §3.4 help 分组 | read print_grouped_help 2136-2179 既有格式 vs 补行文案 | 🟡 RIG-001 |
| 5 | §4 测试覆盖度 | test_cli.py 现状 (13 passed) + test.yml:14 CI 命令 + 集合断言基线 + hs test_prompt.py 对照 | 🟡 RIG-002 |
| 6 | §5 观察项 | AGENTS.md grep skills/prompt (0 有效命中) + O-1~O-3 逐条推演 | ✅ (OBS-4) |
| 7 | 决策对应 + 编号 | 探讨会话回溯 (确认串/选项表/复述批准) + review_history CL001-003 占用核验 | ✅ (OBS-2) |

## 数据验证

| # | 验证项 | 方法 | 结果 |
|:-:|:-------|:-----|:-----|
| 1 | 设计文件 + commit | git log --oneline -2 + git status | ✅ HEAD=8f14683 (design v1.0), worktree clean |
| 2 | hs 实现对照 | sed -n '680,800p' cli.py | ✅ _cmd_prompt 全逻辑: json_mode='--json' in args / brief / skill_name=next(非-参数); SKILLS_DIR; 目录缺失/空 双错误路径 exit 1; 不存在 stderr+可用列表+exit 1 / --json 信封; brief 扫 `^## `; 详情全文尾部追加 refs (`## {stem}` + 全文) |
| 3 | hs 测试对照 | read tests/test_prompt.py | ✅ 9 用例: TestSkillsDir 2 (目录扫描+frontmatter) + TestPromptCommand 7 含 test_not_found_json (错误信封) |
| 4 | urllib3 运行时 | `python3 llm-radar-collector.py help 2>&1 \| head` | ✅ NotOpenSSLWarning 实测出现 (urllib3 v2, LibreSSL 2.8.3) — "所有命令均有"成立 |
| 5 | prompt 现状复现 | `python3 llm-radar-collector.py prompt` | ✅ 构造器噪音 (❌ DEEPSEEK_API_KEY 未配置) + `❌ 未知命令: prompt` + real_exit=1 — 设计修复前提属实 |
| 6 | main() 分支位置 | read 2204-2302 | ✅ help 分支 2222-2224 (不实例化) / status 2227-2228 (_silent_collector) / 实例化 2230 / else 2300-2302 exit 1; prompt 插入 help 后、实例化前可行; _load_api_key L176-183 日志 L180/182 不再触发 |
| 7 | CI 自动覆盖 | read .github/workflows/test.yml:14 | ✅ `pytest tests/ -m "not selenium" --ignore=tests/test_selenium.py` — 未 ignore test_cli.py → CI 自动覆盖; 设计 §4.2 "CI pytest tests/ 自动覆盖" 属实 |
| 8 | skills/ 集合基线 | ls skills/ | ✅ 仅 github-workflow (SKILL.md, 无 references/) — 断言 {github-workflow, x-twitter-collector} 基线成立 |
| 9 | test_cli 基线 | pytest tests/test_cli.py -q | ✅ 13 passed (设计扩展 7 用例 → 20) |
| 10 | AGENTS.md 提及面 | grep 'skills\|prompt' AGENTS.md | ✅ 0 有效命中 (仅 llm-news-prompt.md 文件名 + "Retry prompt" 措辞) — O-2 双处同步确需; Key Commands 节为第三处 (OBS-4) |
| 11 | twitter-collector 实况 | sed 头部 1-60 | ✅ CLI 签名 (默认 collect/--collect/--login/--dry-run/--attach)、退出码 0/1/2、retention 30/24h 与大纲一致; DEFAULT_PROFILE_DIR=cache/twitter-profile + TWITTER_PROFILE_DIR 覆盖 vs 大纲 ~/chrome-twitter-cdp (OBS-3) |
| 12 | 确认串回溯 | session_search 探讨会话 (20260827_205047_35d6ad) | ✅ 选项表: D1=全局抑制 / D2=不动(倾向) / D3=不做; 用户字面 "A1 B1 C1 D1 E1 F1"; 复述明确"不动（D2）" + 用户「开始」批准 → 设计 D4=2D 内容正确, 字面 "D1" 为标签歧义 (OBS-2) |
| 13 | 编号占用 | .review-level.yaml 2026-08-27 条目 | ✅ CL001 (x-preview) / CL002 (perf-optimize) / CL003 (copy-fix) 已占 → CL004 正确; draft 已绑定 (探讨会话 hm loop list 实测识别) |

## 维度评估 (3D)

| 维度 | 评级 | 说明 |
|:-----|:----:|:-----|
| 合理性 | 🟢 | 三件事 (skill 沉淀/prompt 修复/全量对齐 hs) 与确认串内容逐项对应; 行为矩阵 8 行实测对齐; 分支位置消除噪音论证闭环; B1 边界分工清晰 (通用→Hermes, 项目→速查) |
| 严格性 | 🟡 | 2 项规格精度缺陷: help 补行格式 (RIG-001) + 错误信封缺自动化用例 (RIG-002); brief 扫描范围 ^#{2,3} 为 hs ^## 超集且未含 references 行 (OBS-1, 当前两 skill 无 references 影响为 0) |
| 安全性 | 🟢 | 纯文档 + 只读子命令, 无新依赖/无网络副作用/无注入面; no_key_log 测试防回归; --json 信封测试断言 status/data/error 键 |

## 发现项

### RIG-001 🟡 — §3.4 help 补行格式与既有分组格式不符 (机械级, 并入实现验收清单)

- **问题**: 设计 §3.4 补行文案为单行内联 `llm-radar prompt             列出可用技能
  (AI 对接, llm-radar prompt <name> 输出全文)`; 但 print_grouped_help (2136-2179) 全部行均为
  两行式 — 命令行 (`  <cmd>`) + 描述行 (11 空格缩进), 且命令令牌用短名 (run/fetch/status…)。
  全称令牌 "llm-radar prompt" 破坏列宽对齐与既有观感, 与"对齐 hm-style 分组帮助 (对齐列宽)"
  的声明自相矛盾。
- **修正 (dev 落地)**: 按既有两行式:
  ```
    prompt
            列出可用技能（AI 对接，llm-radar prompt <name> 输出全文）
  ```

### RIG-002 🟡 — 行为矩阵含 `<不存在> --json` 但 7 用例缺自动化覆盖 (机械级, 并入实现验收清单)

- **问题**: 行为矩阵第 7 行定义 `<不存在> --json` → `{status: error, data: null, error:
  "skill '<name>' 不存在"}` + exit 1; §7 风险表要求"--json 信封格式漂移 → 测试断言
  status/data/error 键"; hs test_prompt.py 有 test_not_found_json 先例; 但 §4.1 用例列表
  仅 7 条, 无错误信封路径用例 — 该路径回归 (如 error 键缺失) CI 抓不到。
- **修正 (dev 落地)**: 补第 8 用例 `test_cli_prompt_json_not_found`: `prompt nope --json` →
  exit 1 + json.loads(stdout) → status==error + data is None + error 含 "不存在"。

### 观察项 (🟢, 不扣分)

| # | Severity | 事项 | 说明 |
|:-:|----------|------|------|
| OBS-1 | 🟢 | brief 扫描范围 ^#{2,3} 为 hs (^##) 超集, 且 hs brief 含 references 文件名行设计未提 | "全量对齐 hs" (D3) 字面上有小偏差; 若 ^#{2,3} 属有意扩展建议设计加注; 当前两 skill 无 references/ 目录, 影响为 0 |
| OBS-2 | 🟢 | D4 标签追溯: 确认串字面 "D1" vs 原选项 D1=全局抑制 | 探讨复述明确"不动（D2）"+ 用户「开始」批准, 设计记 2D 与批准内容一致; 建议修订记录加注"确认串 D1 系标签笔误, 以复述批准内容不动/2D 为准"消除未来歧义 |
| OBS-3 | 🟢 | §3.1 故障排查保留项与 Hermes x-twitter-scraping 有内容重叠; 脚本默认 profile 与大纲表述需调和 | Singleton 锁清理/chromedriver pin/零页面恢复在 x-twitter-scraping 均有详版 — 项目 skill 保留属运维速查浓缩, 编写时注明"浓缩+深度指针"; 脚本 DEFAULT_PROFILE_DIR=cache/twitter-profile + TWITTER_PROFILE_DIR vs 运维实际 ~/chrome-twitter-cdp (attach), skill 需写明两者关系防误导 |
| OBS-4 | 🟢 | O-2 双处同步可扩为三处 | AGENTS.md Key Commands 节亦缺 prompt 命令行, 建议一并补 `python3 llm-radar-collector.py prompt [skill]` |
| OBS-5 | 🟢 | §4.2 验证命令未含测试污染还原步骤 | 全量 pytest 会写脏 timestamp.json/overview.json/data/snapshot.json (AGENTS.md 既有规则), dev 跑完需 `git checkout --` 精确还原 3 文件 |

## 评分

| 级别 | 数量 | 扣分 |
|:-----|:-----|:-----|
| 🔴 HIGH | 0 | 0 |
| 🟡 MEDIUM | 2 (RIG-001, RIG-002) | -10 |
| 🟢 LOW (观察) | 5 (OBS-1~5) | 0 |

**得分: 100 − 10 = 90 / 100 → A → PASS (≥85/A)**

## 结论

**✅ PASS (90/100, A) — 设计 v1.0 可进 dev。** 无 🔴, 2 🟡 (机械级, 并入实现验收清单),
5 🟢 观察。RIG-001/RIG-002 随 dev 实施一并修正即可, 不阻塞实现启动。

## 实现验收清单 (dev 侧, PASS 后执行)

**核心变更:**

1. 新建 `skills/x-twitter-collector/SKILL.md` (D2 1B 大纲 7 节): YAML frontmatter
   (name: x-twitter-collector, description 首 57 字符自含触发, category: devops);
   正文 CLI 签名/退出码 0/1/2、twitter-targets.yaml 配置、twitter.json schema (30/24h)、
   登录态与 CDP (~/chrome-twitter-cdp:9222, --login/--attach)、入库 auto-push 语义、
   cron 20 9,21 错峰、故障排查 (浓缩 + 指向 x-twitter-scraping, OBS-3)。
2. collector main() 加 `prompt` 分支 (help 分支之后、`LLMRadarCollector()` 实例化之前,
   sys.exit 于分支内) + `_cmd_prompt(args)` 独立函数 (行为矩阵 8 行全对齐 hs,
   SKILLS_DIR = PROJECT_ROOT/'skills', `--json`/`--brief` flag + 首个非 `-` 参数 = skill_name)。
3. **RIG-001**: print_grouped_help 【其他】组按两行式补 `prompt` 行
   (`  prompt` + 11 空格缩进描述行 `列出可用技能（AI 对接，llm-radar prompt <name> 输出全文）`)。
4. test_cli.py 扩展 8 用例 (7 + **RIG-002** `test_cli_prompt_json_not_found`):
   列表含双 skill + 用法行 / 全文含 `# x-twitter-collector` + 关键章节 / --brief 含
   description + `章节:` / `prompt --json` 精确集合 {github-workflow, x-twitter-collector} /
   `prompt <name> --json` data.name+content / `prompt nope` exit 1 + stderr 不存在 +
   stdout 可用列表 / `prompt nope --json` status error 信封 / no_key_log
   (stdout+stderr 无 "DeepSeek API key")。
5. AGENTS.md 三处同步 (OBS-4): CLI 治理节补 `prompt` 命令 + 项目结构节补 skills/ 目录
   + Key Commands 节补 `python3 llm-radar-collector.py prompt [skill]`。

**验证清单 (dev 提交前):**

1. `python3 -m pytest tests/test_cli.py -q` → 20 passed (13 + 8 − 1 无删减)。
2. `python3 -m pytest tests/ -m "not selenium" -q` 全量绿; **跑完 `git checkout --`
   timestamp.json overview.json data/snapshot.json** 还原 (OBS-5)。
3. 手工实测: `llm-radar prompt` 列表 / `llm-radar prompt x-twitter-collector` 全文无 key 日志 /
   `llm-radar prompt nope` exit 1 / `llm-radar prompt --json` 信封 / `help` 输出【其他】组
   `prompt` 行两行式对齐 (RIG-001)。
4. 验收 4 条命令全部 exit 码与输出符合行为矩阵 (含 `<不存在> --json` 信封)。
5. 提交规范: `type@scope: subject` 全英文小写; skill 与实现同一 feat commit 或分两个。

---

*报告: documents/reviews/llm-radar-skills-prompt-review-v1.0-20260827.md | 结论: ✅ PASS 90/100 (A) | RIG-001/002 🟡 (并入实现验收清单) + OBS-1~5 🟢 | 未 commit / 未 push (1A 约束)*
