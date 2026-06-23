# 搜索引擎搜索技巧 —— 以 Bing 为例

> 所有示例基于 Bing（Microsoft 必应），大部分操作符在 Google / DuckDuckGo 也通用。
> 聚焦**热点场景**：竞品调研、社媒监听、技术调研。

---

## 快速参考

| 你要做 | 搜索示例 |
|:---|:---|
| 搜某个站的内容 | `{keyword} site:{domain}` |
| 搜某类文件 | `{keyword} filetype:pdf` |
| 搜某个时间段 | `{keyword} after:2026-01-01` |
| 排除噪音词 | `{keyword} -{noise}` |
| 精确匹配短语 | `"{exact phrase}"` |
| 标题包含关键词 | `intitle:{keyword}` |
| URL 包含关键词 | `inurl:{keyword}` |
| 二选一 | `{term1} OR {term2}` |

---

## 1. Bing 操作符（一表全览）

Bing 默认是 AND 搜索。所有示例均可在 bing.com 直接测试。

| 操作符 | 作用 | 示例 |
|:---|:---|:---|
| `"精确短语"` | 强制字面匹配，禁用同义词 | `"agent loop"` |
| `+term` | **必须**包含该词 | `+AI +security` |
| `-term` | 排除该词 | `llm -openai` |
| `OR` 或 `|` | 二选一（**必须大写**） | `(openai OR anthropic) pricing` |
| `NOT` | 排除（等价 `-`，**必须大写**） | `AI NOT chatbot` |
| `&` | AND 缩写 | `AI & security` |
| `()` | 布尔分组 | `(seo OR ppc) case study` |
| `site:domain` | 站内搜索 | `site:arxiv.org "transformer"` |
| `-site:domain` | 排除域名 | `llm -site:medium.com` |
| `filetype:pdf` | 限定文件格式 | `"state of ai" filetype:pdf` |
| `after:YYYY-MM-DD` | 在此日期后 | `"large language model" after:2026-01-01` |
| `before:YYYY-MM-DD` | 在此日期前 | `before:2025-01-01` |
| `ip:IP` | 查看该 IP 上的网站 | `ip:8.8.8.8` |
| `loc:code` | 限定地区结果 | `loc:US` |
| `language:code` | 限定语言 | `language:zh` |
| `feed:` | 找 RSS 订阅源 | `feed:AI` |
| `hasfeed:` | 有 feed 链接的页面 | `hasfeed:llm` |

**运算符优先级（从高到低）**：
1. `()` → 2. `""` → 3. `NOT` `-` `+` → 4. `AND` `&` → 5. `OR` `|`

> ⚠️ `NOT` 和 `OR` **必须大写**，否则被当作停用词忽略。
> ⚠️ Bing 只处理前 10 个搜索词。

---

## 2. 实战组合（直接套用）

```text
# 站内精准搜索（最常见的用法）
"{keyword}" site:{target-domain}
示例: "agent loop" site:github.com

# 竞品内容盘点
site:competitor.com intitle:"guide" OR intitle:"tutorial"

# 挖掘 PDF / 文档型资产
site:competitor.com (filetype:pdf OR filetype:xlsx) -inurl:blog

# 排除聚合站/广告站
{keyword} -site:medium.com -site:reddit.com -site:quora.com

# 跨竞品对比
(site:comp1.com OR site:comp2.com) intitle:"{topic}" -site:mycompany.com

# 指定时间段的新内容
{keyword} after:{last-month}

# 投稿机会挖掘
"write for us" OR "guest post" intitle:"{topic}"

# 发现未链接的品牌提及
"Your Brand" -site:yourdomain.com

# 特定地区 + 语言的内容
site:competitor.com loc:CN language:zh
```

---

## 3. 跨引擎兼容速查

| 操作符 | Bing | Google | DuckDuckGo | 备注 |
|:---|:---:|:---:|:---:|:---|
| `""` 精确短语 | ✅ | ✅ | ✅ | 所有引擎通用 |
| `-` 排除 | ✅ | ✅ | ✅ | 最常用 |
| `OR` | ✅ | ✅ | ✅ | 必须大写 |
| `site:` | ✅ | ✅ | ✅ | Web 搜索标配 |
| `filetype:` | ✅ | ✅ | ✅ | 格式：pdf/doc/xls/ppt |
| `intitle:` | ⚠️ 部分 | ✅ | ✅ | Bing 有时不生效 |
| `inurl:` | ⚠️ 部分 | ✅ | ✅ | Bing 有时不生效 |
| `after:`/`before:` | ⚠️ 不可靠 | ✅ | ❌ | Bing 用 Tools 菜单更稳 |
| `+` 必须包含 | ✅ | ❌废弃 | ✅ | Google 已不支持 |
| `ip:` `loc:` `feed:` | ✅ | ❌ | ❌ | Bing 独有 |
| `*` 通配符 | ❌ | ✅ | ❌ | 仅 Google 支持 |

---

## 4. Bing Tips

- **搜索工具栏**：搜索结果页顶部有 `All / Images / Videos / Maps / News / ...` 标签，切换后自动带限定符
- **时间过滤**：点 Tools → 选 `Any time / Past 24h / Past week / Custom range`，比手动敲 `after:` 更可靠
- **区域切换**：搜索结果页右上角设置 → Country/Region，影响 `loc:` 和搜索结果排序
- **图片搜索**：支持 `layout:square` `layout:wide` `layout:tall` 和 `color:color` `color:bw` 等图片自身操作符
- **`filetype:` 不生效时**：尝试在 Tools → Filters → Type 下拉选文件类型
- **Bing 对中文搜索支持较好**：长句自然语言查询也能理解意图，多数场景不需要刻意拆成操作符

---

## 5. 搜索策略清单

- [ ] 明确意图：信息搜索 / 导航到站 / 对比调研
- [ ] 先宽后窄：从宽泛词开始，逐层 `-排除` `site:限定` 收窄
- [ ] 精确短语优先：`"` 禁用同义词模糊，提高命中精度
- [ ] 排除噪音：`-site:medium.com -site:reddit.com -site:linkedin.com`
- [ ] 时间限定：`after:` 或 Tools 菜单过滤过时内容
- [ ] 文件类型限定：`filetype:pdf` 找深度资料，`filetype:xlsx` 找数据
- [ ] 跨引擎验证：同一个查询在 Bing / Google / DDG 结果差异很大
- [ ] 保存常用模板为浏览器搜索快捷方式

---

## 📋 元信息

| 项目 | 内容 |
|:---|:---|
| 助手名称 | IRIS (byHermes) |
| 创建时间 | 2026-06-22 20:30:00 |
| 信息来源 | Microsoft Bing Support、Google Search Docs、DuckDuckGo Help Pages |
