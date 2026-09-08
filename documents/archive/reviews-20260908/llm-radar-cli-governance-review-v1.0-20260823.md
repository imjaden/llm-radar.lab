# llm-radar CLI 治理与全局注册 — review报告 v1.0

> 日期: 2026-08-23
> 文件: documents/solutions/llm-radar-cli-governance-design-v1.0-20260823.md
> 项目路径: /Users/jadenli/CodeSpace/llm-radar.jaden.tech
> 待 push commit: a714a7c (docs@design), 552307e (docs@handoff)
> review维度: 合理性 / 严格性 / 安全性 + 治理合规
> review者: Security Reviewer (IRIS) / hermes-1.2.0

## 数据验证

| # | 验证项 | 方法 | 结果 |
|:-:|:-------|:-----|:-----|
| 1 | main() 分发逻辑 | read_file 1985-2101 | ✅ 与设计"约 1985-2090 行"吻合; 空入参 exit=1 (1987-1990); 未知命令 exit=1 (2089-2090) |
| 2 | 子命令清单 | grep main 分支 | ✅ fetch/merge/run/selenium-check/sources/reset-health/crontab/commit/auto-push/help = 10 命令, 与设计一致 |
| 3 | 空入参 exit=1 | 实测 `python3 llm-radar-collector.py` | ✅ exit=1, 与设计 §3.2 声称一致 |
| 4 | help 平铺无分组 | read 2062-2086 | ✅ 无分组、无【】分类, 与设计一致 |
| 5 | 无 --json | grep main 分支 | ✅ 现状无任何 --json 处理 |
| 6 | timestamp.json 字段 | cat timestamp.json | ✅ 含 last_run_at/last_run_status/entity_count, 与设计 §4.3 一致; 但路径在**项目根** (collector.py:1305 `project_root / 'timestamp.json'`), 设计未标注路径 |
| 7 | metrics.json 连续失败 | python3 json.load | ⚠️ 两级并存: 全局 `consecutive_fails`(=0) 与 `source_health.<src>.consecutive_fails`(qbitai=37); 设计 §4.2"连续失败 ≥3"未明确级别 |
| 8 | snapshot.json 维度 | python3 json.load | ✅ stats.total_* = 100/50/100/55/61; 设计示例 "288 (100/43/100/45/47)" 为占位符 |
| 9 | STALE_HOURS | grep scripts/llm-radar-health.py | ✅ :38 `STALE_HOURS = int(os.environ.get('LLM_RADAR_STALE_HOURS', '7'))` 与设计 D5/§4.4 完全一致 |
| 10 | _think force | read 1375-1410 | ✅ force=True 直接返回, 绕过 6h 节流 (1377-1379), 与 D6 一致 |
| 11 | PROJECT_ROOT 推导 | read :43 | ✅ `Path(__file__).resolve().parent`, wrapper 全局调用兼容 |
| 12 | run help 现状误执行 | 实测 `run help` | ⚠️ 把 "help" 当 source 传入 fetch_all, 报 DEEPSEEK_API_KEY 错误但 exit=0 — positional help 拦截必要性证实 |
| 13 | checkpoint 协议 | daily-checker dt-status 协议文档 | ✅ 七字段/四态/icon emoji/message 无 emoji 一致; shell action 用 `cmd` 字段 (git-cloner-v1.0:92, toutiao-fm:52, web2md:83) 与设计 §4.1 一致 |
| 14 | cli-registry 先例 | script-miner/.cli-registry.yaml + install.py | ✅ 配置结构一致 (bin_dir/cache_dir/python/env/commands/alias_list); ⚠️ 但 install.py 模板 wrapper.sh.tmpl **不含 .env 加载**, 且硬编码 `~/CodeSpace/script-miner/cache/cli-registry/calls.log` 调用统计 |
| 15 | mcp-server 边界 | find 项目根 | ⚠️ 实际文件为 `llm-radar-mcp-server.py`, **不存在 mcp-server.py** — 设计 §6 引用名错误 |
| 16 | 测试隔离 | read tests/conftest.py + test_timestamp.py | ⚠️ temp_snapshot 只隔离 snapshot_path/data_dir, project_root 不变; test_timestamp.py:19/54/65/78/90 直接读写真实 `project_root/timestamp.json` — 已知污染源 (AGENTS.md 记载 08-15 事故), 设计仅 ⚠️ 一句未给方案 |
| 17 | 文档命名/frontmatter | head/文件名 | ✅ kebab-case 无点无下划线, v1.0 与 frontmatter version: 1.0 一致, 日期 20260823, type: design, profile: ops |
| 18 | commit 格式 | git log a714a7c | ✅ `docs@design: llm-radar CLI 治理与全局注册设计 v1.0 (CL-SEC11)` — type@scope 合规 |

## 合理性评估

| # | 项 | 结果 |
|:-:|:---|:-----|
| REA-1 | 现状评估逐项准确 (入口形态/空入参 exit=1/help 平铺/无 --json/10 命令) | ✅ |
| REA-2 | 分组结构覆盖全部 10 现有命令 + status 新增, 无遗漏 | ✅ |
| REA-3 | `lr status --json` 七字段 (id/label/status/icon/message/checks/actions) 与 checkpoint 协议一致 | ✅ |
| REA-4 | 四态 ok/warning/critical/info 判定可执行, 数据源全只读 | ✅ |
| REA-5 | STALE_HOURS 对齐 health probe (llm-radar-health.py:38) | ✅ |
| REA-6 | D1-D7 决策与探讨确认一致, force 绕过 _think 已内建 | ✅ |
| REA-7 | .cli-registry.yaml 结构与 script-miner 先例一致 (alias_list 有 toutiao-fm/diary/draft 先例) | ✅ |
| REA-8 | `lr run --force` 一键修复 (方案 B) 与 D3 一致, 无过度设计 | ✅ |
| REA-9 | 空入参 exit=0 / positional help 拦截符合 hm-style 治理约定 (对齐 pc magnet 教训) | ✅ |
| REA-10 | 上游先行、下游 daily-checkin 不做的边界划分合理 | ✅ |
| REA-11 | 🟡 §6 引用 `mcp-server.py`, 实际文件是 `llm-radar-mcp-server.py` (项目根) | 边界表述合理但文件名错 |
| REA-12 | 🟢 【数据管理】分组仅 status 一个命令, 分组略薄; 可接受 (为后续扩展留位) | OBS |

## 严格性评估

| # | 项 | 结果 |
|:-:|:---|:-----|
| RIG-1 | 🟡 §4.4 "48h 阈值 = STALE_HOURS * 7 近似(或独立 CRITICAL_HOURS = 48, 实施时二选一)" 未锁定 | STALE_HOURS*7=49h ≠ 48h, 与 §4.2 表格 ">48h → critical" 矛盾; 若选乘法, 48-49h 区间状态闪变。应直接锁定独立常量 CRITICAL_HOURS=48, 删去"二选一"表述 |
| RIG-2 | 🟡 §5.2 "wrapper 需处理 .env 加载(参考 run.sh set -a 模式)" 无实现路径 | 现有 install.py wrapper.sh.tmpl 只加载 Homebrew/Conda/rbenv/Bun, **无 .env 逻辑**; collector 本身不读 .env (collector.py:173 只读 os.environ)。直接跑 install.py 生成的 wrapper, `lr run` 在非交互环境报 DEEPSEEK_API_KEY 未配置。需 fork 模板或 wrapper 加 source .env |
| RIG-3 | 🟡 §5.2 "用 cli-registry install.py 生成 wrapper" 未预判模板耦合 | wrapper.sh.tmpl 硬编码 `mkdir -p ~/CodeSpace/script-miner/cache/cli-registry; echo ... >> calls.log` (script-miner 专用统计), llm-radar 复用会写脏 script-miner 目录。需改模板或注明 fork |
| RIG-4 | 🟡 §6 ⚠️ "测试须隔离(temp_snapshot 需连 project_root 一起隔离)" 只提示无方案 | 现状 temp_snapshot fixture 只隔离 snapshot_path/data_dir, project_root 不变 (conftest.py); test_timestamp.py 直接写真实 project_root/timestamp.json (5 处) — 08-15 污染源仍在。status 命令跨读 project_root/timestamp.json + data/metrics.json + data/snapshot.json, 新测试 fixture 需 patch `collector.project_root` 到 tmp 并连读 3 文件; 设计应给出 fixture 方案 |
| RIG-5 | 🟡 §4.2 "连续失败 ≥3 → critical" 级别未明确 | metrics.json 两级: 全局 consecutive_fails(=0) vs source_health.<src>.consecutive_fails(qbitai=37)。若按 source_health 任一源, 当前状态将**永久 critical** (qbitai 已 37 连败, 被 fetch_all 自动跳过), status 面板失去区分度。应明确: 全局 run 级 (推荐, 与 _think 的 consec_fails 语义一致) |
| RIG-6 | 🟢 §4.3 未标注 timestamp.json 路径 | 实际在项目根 (collector.py:1305), 不在 data/。字段名全对, 实施者读代码可发现; 建议标注 |
| RIG-7 | 🟢 分叉检测基于本地 origin/main 快照, 未注明不主动 fetch | 本地 ref 过期时 ahead/behind 不准; "全部只读"约束下可接受, 建议注明语义 |
| RIG-8 | 🟢 §4.1 示例数字为占位符 (288 / 100/43/100/45/47) | 实际 stats 100/50/100/55/61, entity_count=305; 示例无碍但建议标注占位 |
| RIG-9 | 🟢 `lr status` 无 --json 时输出未定义 | 对齐 dt-status 先例: 无 --json 保持文本输出; 设计应补一句 (仅 [--json] 可选标志未定义 fallback) |

## 安全事项

🟢 SEC-1 — status 数据源全只读 (timestamp.json/metrics.json/snapshot.json + git rev-list), 不触发采集副作用; 与 §4.3 声明一致。

🟢 SEC-2 — positional help 拦截 (args[0].upper()=='HELP' → exit=0) 防误执行: 实测 `run help` 现状把 "help" 当源采集、静默 exit=0, 拦截消除该行为; 对齐 pc magnet 事故教训。

🟢 SEC-3 — actions[].cmd 为静态字符串 (`lr run --force` / `lr auto-push`), 无用户输入注入面; 下游 daily-checker heal 以 `subprocess.run(action["cmd"], shell=True)` 执行 (heal-design:140), 静态 cmd 安全。

🟢 SEC-4 — 全局注册为 user-level symlink (~/.local/bin), 无提权面。

🟢 SEC-5 — wrapper .env 加载仅本地 CLI 场景, DEEPSEEK_API_KEY 不进 stdout; 与 console 规范 (不打印 token) 无冲突。

🟢 SEC-6 — 空入参 exit=1→0 变更影响面核查: llm-radar-run.sh 无参默认 `exec ... run` (不触空入参分支), crontab 走 run.sh, 无脚本依赖 exit=1; 变更安全。

## 治理合规

| # | 项 | 结果 |
|:-:|:---|:-----|
| GOV-1 | 文件名 `llm-radar-cli-governance-design-v1.0-20260823.md`: kebab-case、无点无下划线、v1.0、8 位日期 | ✅ |
| GOV-2 | frontmatter: type: design / version: 1.0 (与文件名一致) / date / author / tags / profile: ops | ✅ |
| GOV-3 | commit a714a7c `docs@design: ...` — type@scope 格式, design 文档用 docs@design scope 符合项目先例 | ✅ |
| GOV-4 | 决策表 D1-D7 完整, 探讨确认 "6+1" 引用可追溯 | ✅ |
| GOV-5 | 变更清单覆盖 collector/.cli-registry.yaml/测试/AGENTS.md 四类文件 | ✅ |
| GOV-6 | 验收标准 8 条可测, 与设计章节对应 | ✅ |

## 评分

| 级别 | 数量 | 扣分 |
|:-----|:-----|:-----|
| 🔴 HIGH | 0 | 0 |
| 🟡 MEDIUM | 6 (REA-11, RIG-1, RIG-2, RIG-3, RIG-4, RIG-5) | -30 |
| 🟢 LOW | 8 (REA-12, RIG-6~9, SEC-1~6) | 0 (记录) |

得分: **70 / 100 → B**

## 结论

**CONDITIONAL PASS (70/B)** — 无 🔴 阻断项, 架构与协议设计正确; 6 个 🟡 修正项集中在实施细节 (wrapper 环境/模板耦合/测试隔离/阈值锁定/语义明确), 不阻塞架构本身, 但按 standing rule 需修改后重审。

**需修改后重审** — 修复 prompt 发给 ops (设计文档 frontmatter `profile: ops`)。

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | REA-11: §6 "mcp-server.py" 改为实际文件名 `llm-radar-mcp-server.py` | 合理性 🟡 |
| □ | RIG-1: §4.4 锁定独立常量 CRITICAL_HOURS=48, 删除 "实施时二选一" 表述 | 严格性 🟡 |
| □ | RIG-2: 明确 wrapper .env 加载实现路径 (fork wrapper.sh.tmpl 加 source .env, 或 collector 内加 dotenv 加载) | 严格性 🟡 |
| □ | RIG-3: 明确 cli-registry install.py 模板的 script-miner 耦合处理 (改 calls.log 路径/移除统计) | 严格性 🟡 |
| □ | RIG-4: §6 补充测试隔离方案 (status fixture patch collector.project_root 到 tmp, 连读 3 文件) | 严格性 🟡 |
| □ | RIG-5: §4.2 明确 "连续失败 ≥3" 为全局 consecutive_fails (run 级), 非 source_health 任一源 | 严格性 🟡 |
| □ | RIG-6: §4.3 标注 timestamp.json 路径 (项目根) | 严格性 🟢 |
| □ | RIG-7: 注明分叉检测基于本地 origin/main ref, 不主动 fetch | 严格性 🟢 |
| □ | RIG-9: 补 `lr status` 无 --json 时文本输出定义 | 严格性 🟢 |

---

*报告: documents/reviews/llm-radar-cli-governance-review-v1.0-20260823.md | 追踪: REA-11 / RIG-1~5 / GOV-1~6 | 结论: CONDITIONAL PASS 70/B*
