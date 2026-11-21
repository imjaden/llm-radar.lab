# 中国境内可用推理模型 · 性价比 Top 20（20261121）

> 口径：混合价 = （3×输入 + 输出）/ 4，单位 USD / 百万 token；性价比 = 能力分 ÷ 混合价。
> 只收 `reasoning=true` + `tool_call=true` + 上下文 ≥128k 的型号；境内 = 12 个厂商官方 / .cn 直连渠道。
> 快照：`models.dev/api.json` sha256 `9afe118c19c8b85d…`（6789801 B）、
> Artificial Analysis 榜单页 sha256 `0c30587683ae59bd…`（1451466 B）。
> 原始数据：`documents/reports/cn-reasoning-models-20261121.json`；生成脚本：`scripts/fetch-cn-reasoning-models.py`。

## 1. 结论（先看这五行）

- **性价比甜点**是三个 Flash：`MiMo-V2.6-Flash`（152.7）、`Qwen3.8 Flash`（151.0）、`GLM-5.3-Flash`（144.1）——能力分 27~29，混合价 0.18 上下，都是 1M 上下文。
- **能力/价格拐点**是 `DeepSeek V4.1 Flash 1017`（指数 32.6 / 混合 0.263）——再往上加价，指数提升明显变慢。
- **旗舰里最便宜**是 `Tencent Hy4`（34.6 / 1.251），旗舰里最强是 `Kimi K3.1 Pro`（46.5 / 4.000）。
- **开源可自托管**：`MiMo-V2.6-Flash`/`Pro`、`GLM-5.3-Flash`、`DeepSeek V4.1 Flash 1017`、`Qwen3.8 27B`、`Step 5 Preview`、`GLM-4.7-FlashX`。
- **极限低价**：`Qwen3.7 Flash`（混合 0.052，1M 上下文，未测评测）——适合分诊/格式化这类不走深推理的环节。

## 2. 榜单（20 条）

| # | 模型 | 境内渠道 | 能力分 | 输入 $ | 输出 $ | 混合价 | 分/价 | 上下文 |
|---|---|---|---|---|---|---|---|---|
|  1 | MiMo-V2.6-Flash | Xiaomi | 26.73 | $0.140 | $0.280 | $0.175 | 152.7 | 1048k 开源 |
|  2 | Qwen3.8 Flash | Alibaba (China) | 28.58 | $0.119 | $0.401 | $0.189 | 151.0 | 1000k |
|  3 | GLM-5.3-Flash | Volcengine Ark | 27.80 | $0.119 | $0.416 | $0.193 | 144.1 | 1000k 开源 |
|  4 | DeepSeek V4.1 Flash 1017 | DeepSeek | 32.59 | $0.150 | $0.600 | $0.263 | 124.2 | 1048k 开源 |
|  5 | MiniMax-M3.1-Flash **[在用]** | MiniMax (minimax.cn) | 29.06 | $0.149 | $0.598 | $0.262 | 111.1 | 1000k 开源 |
|  6 | MiMo-V2.6-Pro **[在用]** | Xiaomi | 29.89 | $0.435 | $0.870 | $0.544 | 55.0 | 1048k 开源 |
|  7 | MiniMax-M3 | MiniMax (minimax.cn) | 18.88 | $0.314 | $1.255 | $0.549 | 34.4 | 1000k 开源 |
|  8 | Hy4 | Tencent TokenHub | 34.56 | $0.834 | $2.501 | $1.251 | 27.6 | 1048k |
|  9 | Qwen3.8 27B | SiliconFlow (China) | 20.11 | $0.450 | $1.799 | $0.787 | 25.5 | 262k 开源 |
| 10 | Step 5 Preview | StepFun (China) | 28.53 | $1.046 | $2.989 | $1.532 | 18.6 | 1000k 开源 |
| 11 | GLM-5.3 | Alibaba (China) | 31.65 | $1.100 | $3.851 | $1.788 | 17.7 | 1000k 开源 |
| 12 | Qwen3.8 Max | Alibaba (China) | 42.89 | $1.777 | $5.332 | $2.666 | 16.1 | 1000k |
| 13 | Kimi K3.1 Pro **[在用]** | Moonshot AI (China) | 46.45 | $1.944 | $10.167 | $4.000 | 11.6 | 1048k 开源 |
| 14 | DeepSeek V4 Pro 0813 | Volcengine Ark | 23.06 | $1.336 | $4.008 | $2.004 | 11.5 | 1000k 开源 |
| 15 | Qwen3.5 397B-A17B | Alibaba (China) | 50.0* | $0.172 | $1.032 | $0.387 | 129.2 | 262k 开源 |
| 16 | Qwen3.7 Plus | Alibaba (China) | 55.1* | $0.276 | $1.101 | $0.482 | 114.2 | 1000k |
| 17 | Kimi K2.7 Code | Moonshot AI (China) | 57.7* | $0.971 | $4.034 | $1.737 | 33.2 | 262k 开源 |
| 18 | Qwen3.7 Flash | Alibaba (China) | 未测 | $0.030 | $0.118 | $0.052 | - | 1000k |
| 19 | Step 3.5 Flash | StepFun (China) | 未测 | $0.105 | $0.314 | $0.157 | - | 256k 开源 |
| 20 | GLM-4.7-FlashX | Zhipu AI | 未测 | $0.075 | $0.448 | $0.168 | - | 200k 开源 |

`*` = 自建合成分（AA 未出官方指数时，用 hle-diamond / gpqa-diamond / terminalbench-4.0 / scicode /
frontiercode-2.0 / tau2-bench / long-context-reasoning / aa-briefcase / gdpval 九项百分位均值；与官方指数相关性 r≈0.45，
**不可与官方指数直接横比**）。`未测` = AA 没有任何评测数据，仅按价格档位入榜占位。

## 3. 在用标注（`llm-manager balance --json` 的 6 个付费渠道）

| 渠道 key | 在用模型 ID | 在本榜的位置 | 建议 |
|---|---|---|---|
| `deepseek` | `deepseek-v4-flash`（DeepSeek V4 Flash） | 未入榜（AA 未测该版本） | 同门 `DeepSeek V4.1 Flash 1017` 排 **#4**，混合价仅高 0.01，换代即得指数 32.6 |
| `kimi` | `kimi-k3.1-pro` | **#13**（46.45 / 4.000） | 旗舰档保留；日常跑量切 `Kimi K2.7 Code`（#17，1.737）更省 |
| `doubao` | `doubao-seed-2-0-pro-260215`（Seed 2.0 Pro） | 未入榜（AA 无该型号指数） | 同厂 `Seed 2.0 Code`（合成分 57.8）可作编码向替代；`Seed 2.0 Mini` 混合价 0.096 |
| `mimo` | `mimo-v2.6-pro` | **#6**（29.89 / 0.544） | 已在主力档；同门 `MiMo-V2.6-Flash` 排 **#1**，同上下文、价格 1/3 |
| `minimax` | `MiniMax-M3.1-Flash` | **#5**（29.06 / 0.262） | 性价比与 #4 基本并列，可作 DeepSeek 的热备 |
| `bigmodel` | `glm-5.2`（GLM-5.2） | 未入榜（GLM 最新为 5.3） | `GLM-5.3-Flash` 排 **#3**（144.1），`GLM-5.3` 排 **#11**（旗舰档） |

> 六个渠道里已有三个（Kimi / MiMo / MiniMax）直接落在 Top 20 内；未入榜的三个不是「差」，而是
> **AA 没有测到那个具体版本**，或**厂商已迭代到更新的小版本**。

## 4. 复核方法（任何人都能重跑）

```bash
cd ~/CodeSpace/llm-radar.lab
python3 scripts/fetch-cn-reasoning-models.py \
  --in-use "Kimi K3.1 Pro,MiMo-V2.6-Pro,MiniMax-M3.1-Flash,DeepSeek V4 Flash,Seed 2.0 Pro,GLM-5.2"
# 输出：documents/reports/cn-reasoning-models-<date>.json / .html
shasum -a 256 校验脚本打印的两个快照 sha256 是否与本文头部一致（快照会漂，数值就会变）
```

判据链：`models.dev` 给价格/上下文/能力开关 → `AA 榜单` 给能力分 → 脚本按 `(3in+out)/4` 算混合价 →
按 `能力/混合价` 排序 → 只保留 `reasoning + tool_call + ctx≥128k` 且能在境内渠道买到报价的型号。

## 5. 数据边界（别把它当排行榜公告）

1. **榜 A（14 条）才有官方指数**；榜 B 是自建合成分，榜 C 无评测。三者不可直接横比。
2. **未纳入**：文心 ERNIE 5.5（models.dev 无百度 provider，取不到价）、豆包 Seed 2.1 Pro、Qwen3.8 2.4T A95B（境内无报价条目）。
3. **缓存价未进公式**：DeepSeek 缓存读 $0.003/1M、部分厂商 0.01 级，真实账单常比混合价低 30%~60%。
4. **包月 / Token Plan 未纳入**：`alibaba-token-plan-cn`、`tencent-token-plan`、`xiaomi-token-plan-cn`、`stepfun-step-plan` 等折算后更便宜。
5. AA 指数是综合智能分，不等于 opencode 里的实际工具体验；上下文、结构化输出、effort 档位都会影响表现。

## 6. opencode 接入片段

见 `documents/reports/opencode-cn-top20.json`：12 个境内 provider + 本榜 20 个模型 id，模型名里带 `[在用]` 的即当前付费渠道。
提供商元数据（api / npm / env 变量名）直接来自 models.dev catalog，opencode 会自动读取，片段里只需要 `options.apiKey` 与 `models` 白名单。

## 7. 附录 · 为什么本仓「大模型」页签按「中国」筛选只剩 7 条

**现象**：筛选后只剩 `混元Hy4`、`混元 Hy4 flash`、`混元Hy4 flash`、`驭物 Lion-ER-35B-A3B`、
`子曰4-R2T2`、`文心5.5 Flash`、`MiniMax开源生图模型`。

**根因**（`index.html:359 isCN()`）：筛选器不看厂商国别，而是「名字里有没有汉字」——

```js
function isCN(entity) {
  if (entity.country === '中国') return true;
  const name = (entity.name||'') + (entity.name_en||'') + (entity.id||'');
  return /\p{Script=Han}/u.test(name);
}
```

而 `data/snapshot.json` 的 `llms[]` 条目**没有 `country` 字段**（country 只存在于 `providers[]`），
于是判断全部落到「汉字正则」上：62 个模型实体里恰好 **7 个**中文名命中，**21 个中国厂商的英文名型号被误判为海外**，
包括 `Qwen4-Max`（阿里，热度 78）、`Kimi K3.1 Pro`（月之暗面，74）、`CloudRobo-WM1.2`（华为云，80）、
`ERNIE-5.5-Flash-Base`（百度，66）、`SenseNova U1 Pro`（商汤，72）、`Seedream 5.5`（字节，48）。

**为什么你常用/推荐的模型不在里面**：两条独立的门槛——
1. **实体来源是新闻**：这张表是「近窗口新闻里提到过的模型」，不是模型货架。`deepseek-v4-flash`、
   `doubao-seed-2-0-pro`、`mimo-v2.6-pro`、`glm-5.2` 这些具体版本没被抽成实体，自然不出现；
2. **即便出现也会被误筛**：英文名的中国模型全部被判成「海外」，包括已上榜的 `Kimi K3.1 Pro`。

**修法（两行内可验证，供你决策，我未改）**：把 `llms` 渲染前 join 一次 provider 国别，`isCN` 优先读
`entity.country || provider.country`，汉字正则只作兜底；另加 `混元Hy4 flash` / `混元 Hy4 flash` 这类
「空格差异重复实体」的归并（当前 62 条里有 1 组重复）。

> 该缺陷属于 llm-radar 前端数据口径（`index.html` + `data/snapshot.json`），与本报告的模型榜单是两套数据源，互不影响。
