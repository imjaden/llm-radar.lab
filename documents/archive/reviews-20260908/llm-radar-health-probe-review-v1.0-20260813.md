# llm-radar health probe — review报告 v1.1

> 日期: 2026-08-13
> 文件: documents/solutions/llm-radar-health-probe-design-v1.1-20260813.md
> 项目路径: ~/CodeSpace/llm-radar.jaden.tech
> 待 push commit: 203c62a (v1.0), b6d7335 (v1.1)
> review维度: 合理性 / 严格性 / 安全性 + Commit 规范 / 命名规范

## 数据验证

| 验证项 | 方法 | 结果 |
|:-------|:-----|:-----|
| 未 push commit 数 | `git log origin/main..HEAD --oneline \| wc -l` | 2 |
| timestamp.json 字段名 | 读 `_write_timestamp()` (collector.py:1285-1292) | last_run_at / last_run_status / last_news_date 均存在 ✅ |
| 本地 timestamp.json | `python3 -c json.load` | last_run_at=2026-08-13T21:05 (新鲜), status=failed |
| 线上 timestamp.json | `web_extract llm-radar.lab.jaden.tech/timestamp.json` | last_run_at=**2026-07-13** (30 天陈旧!), status=failed |
| last_run_at 时区 | 读 `datetime.now().isoformat()` (collector.py:1288) | **无时区后缀** (naive datetime) |
| 设计字段引用 | 读 design doc B1 节 | last_run_at / last_run_status / last_news_date — 与 schema 一致 ✅ |

## 合理性评估

### 评分表

| # | 项 | 评估 |
|:-:|:---|:----:|
| 1 | 问题匹配 | ✅ 真实 gap (CLI 无 health 指令, cron health-daily 只查 hermes-manager 自身) |
| 2 | watchdog 模式选择 | ✅ no_agent=true 正确 — 确定性阈值检查无需 LLM, 零 token |
| 3 | 方案对比 | ✅ A(每小时)/B(每6h)/C(服务器后1h) 三方案对比, B 有理有据 |
| 4 | 频率-阈值自洽 | ✅ 6h 间隔 < 7h 阈值, 任何过期必然被至少一次探针捕获 |
| 5 | 术语表 | ✅ 5 术语定义清晰 |
| 6 | 脚本位置一致性 | ❌ REA-1: B1 节 (line 96) 写 `~/.hermes/profiles/ops/scripts/`，但 C2 确认 (line 172) 与实施范围 (line 176) 改为 `项目内 scripts/` — 自相矛盾未同步 |
| 7 | status 条件语义 | ⚠️ REA-2: `status != success → 告警` 把「采集链路新鲜度」与「质量门禁通过」混为一谈。当前本地/线上数据均为 status=failed 但 last_run_at 可能新鲜 — 会误报 |

**评级**: 🟡 (1 处自相矛盾 + 1 处语义待确认)

## 严格性评估

### 评分表

| # | 项 | 评估 |
|:-:|:---|:----:|
| 1 | 边界情况 | ✅ 网络失败/JSON 解析失败 → 告警 (而非静默); status!=success → 告警 |
| 2 | 验收标准可测 | ✅ 3 条标准 (手动 exit 0/1, cron list 可见, 无 git 副作用) |
| 3 | 风险评估 | ✅ 4 项风险有缓解 |
| 4 | last_run_at 时区 | 🟡 RIG-1: `datetime.now().isoformat()` 无时区后缀, 探针 `now - last_run_at` 有时区歧义 (服务器 vs 本机时区差 → 新鲜度偏移) |
| 5 | CDN 缓存陈旧副本 | 🟡 RIG-2: 探针直接 fetch timestamp.json 无 cache-busting (`?t=`)。线上实测 last_run_at=2026-07-13 (30 天陈旧), 风险表仅覆盖「部署延迟 <1h」未覆盖「缓存陈旧副本」 |
| 6 | 告警投递 | 🟢 RIG-3: deliver=local 告警不投递用户 (明确非目标, 但探针价值受限直到配置投递平台) |

**评级**: 🟡 (2 处技术遗漏 + 1 处观察)

## 安全事项

🟢 无安全发现。

| 检查项 | 结果 |
|:-------|:----:|
| 网络请求 | ✅ HTTPS + timeout 15s |
| 脚本类型 | ✅ 纯 Python, 无 subprocess / shell |
| 凭证 | ✅ 无 (public endpoint, 无 auth) |
| exit code 契约 | ✅ 0 静默 / 1 告警 — 正确 watchdog 语义 |
| SSRF | ✅ URL 硬编码自有域名 |

## Commit 规范评估

| # | SHA | Subject | 验证 |
|:-:|:-----|:--------|:----:|
| 1 | 203c62a | `docs@design: llm-radar health probe watchdog — cron modes + freshness check design v1.0` | ✅ docs@design |
| 2 | b6d7335 | `docs@design: llm-radar health probe v1.1 — record confirmed A1 B1 C2` | ✅ docs@design |

2/2 ✅。

## 命名规范评估

| 检查项 | 文件 | 结果 |
|:-------|:-----|:----:|
| 设计文档 | `llm-radar-health-probe-design-v1.1-20260813.md` | ✅ kebab-case, topic-type-version-date |
| Frontmatter | title/topic/type/version/date/author/tags | ✅ 7 字段完整, type=design |

## 评分

| 扣分项 | 严重度 | 扣分 |
|:-------|:------:|:----:|
| REA-1: B1 节脚本路径与 C2 确认矛盾 (未同步) | 🟡 | -5 |
| REA-2: status==success 与新鲜度语义混淆 (待确认) | 🟡 | -5 |
| RIG-1: last_run_at 无时区后缀, 新鲜度计算有歧义 | 🟡 | -5 |
| RIG-2: 探针 fetch 无 cache-busting, CDN 陈旧副本未覆盖 | 🟡 | -5 |

**得分**: 100 - 20 = **80 / 100 → Rating: B**

| 🔴 | 🟡 | 🟢 |
|:--:|:--:|:--:|
| 0 | 4 | 2 |

## 结论

**CONDITIONAL PASS** — watchdog 模式正确、字段名核对无误、频率-阈值自洽。4 个 🟡 待修正，其中 REA-1 (自相矛盾) 与 RIG-1 (时区) 必须在实施前解决。

### 修改意见 (按编号)

| 编号 | 问题 | 建议改法 |
|:---|:---|:---|
| REA-1 | B1 line 96 与 C2 line 172/176 脚本路径矛盾 | 统一为「项目内 scripts/llm-radar-health.py」，删除 B1 节过时的 `~/.hermes/profiles/ops/scripts/` 描述 |
| REA-2 | status==success 把质量门禁与新鲜度混为一谈 | 明确告警语义：要么仅查新鲜度 (last_run_at ≤7h)，要么显式区分「新鲜度告警」vs「质量告警」两种输出。当前线上 status=failed 但可能新鲜，会误报 |
| RIG-1 | last_run_at 无时区 | 探针解析时用 `datetime.fromisoformat` + 明确时区契约 (建议采集器改 `datetime.now(timezone.utc).isoformat()`，探针按 UTC 解析)，或文档显式声明「last_run_at 为服务器本地时区」 |
| RIG-2 | 探针 fetch 无 cache-busting | 探针请求加 `?t=<epoch>` 参数绕过 CDN 缓存，避免读到陈旧副本导致误报 stale |

## 待确认清单

| □ | 项 | 类别 |
|:-:|:---|:-----|
| □ | B1 节脚本路径统一为项目内 scripts/ (与 C2 一致) | 合理性 🟡 |
| □ | 告警语义：仅新鲜度 or 新鲜度+质量分离 | 合理性 🟡 |
| □ | last_run_at 时区契约明确 (UTC 或服务器本地) | 严格性 🟡 |
| □ | 探针 fetch 加 cache-busting (?t=) | 严格性 🟡 |
