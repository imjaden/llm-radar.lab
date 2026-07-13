# LLM Radar — Entity Emoji 映射表

> 版本: 1.0 | 日期: 2026-07-13 | 基于 data/snapshot.json 实际 ID
> 匹配策略: **id 精确匹配**（非 name）。id 是数据管道稳定主键，不受 LLM 改名影响。

---

## 维度默认 Emoji

| 维度 | Emoji | 中文 |
|:---|:---:|:---|
| providers | 🏢 | 厂商 |
| people | 👤 | 人物 |
| tools | 🔧 | 工具 |
| llms | 🧠 | 大模型 |
| hotspots | 🔥 | 热点 |

未匹配到专属 emoji 的实体 → 自动 fallback 到维度默认。

---

## 厂商 Emoji 映射（providers）

### 国际厂商

| id | Emoji |
|:---|:---:|
| openai | 🌀 |
| anthropic | 🧬 |
| google | 🔮 |
| google-deepmind | 🔮 |
| meta | ♾️ |
| microsoft | 🪟 |
| apple | 🍎 |
| amazon | 📦 |
| nvidia | 🎮 |
| tesla | ⚡ |
| spacex | 🚀 |
| spacex-xai | 🚀 |
| xai | 🚀 |
| mistral-ai | 🌬️ |
| groq | ⚙️ |
| jetbrains | ✈️ |
| gitlab | 🦊 |
| cloudflare | ☁️ |
| dropbox | 📁 |
| netflix | 🎬 |
| snowflake | ❄️ |
| vercel | ▲ |
| elastic | 🔍 |
| slack | 💬 |
| hubspot | 🎯 |
| neuronpedia | 🧠 |
| target | 🎯 |
| zed-industries | ⌨️ |
| dexmal | 🤖 |
| api7 | 🔌 |
| astral | ⭐ |
| inferma | 📊 |
| subquadratic | 🔢 |

### 国内厂商

| id | Emoji |
|:---|:---:|
| baidu | 🐾 |
| alibaba-cloud | 🛒 |
| tencent | 🐧 |
| tencent-hunyuan | 🐧 |
| bytedance | 🎵 |
| huawei | 🪷 |
| meituan | 🛵 |
| xiaomi | 📱 |
| kuaishou | 📹 |
| deepseek | 🐋 |
| zhipu-ai | 🏛️ |
| z-ai | 🏛️ |
| ant-group | 🐜 |
| ant-linbot | 🐜 |
| shengshu-tech | 🌱 |
| kunlun-wanwei | 🏔️ |
| moore-threads | 🧵 |
| mobvoi | 🚪 |
| netease-youdao | 📖 |
| lenovo | 💻 |
| lenovo-vehicle | 🚗 |
| kling-ai | 🎨 |
| volcengine | 🌋 |
| tiangong-ai | 🏔️ |
| xingfan-ai | ⭐ |
| guangxiang-tech | 💡 |
| youjia-innovation | 🚗 |
| jiutianzhanyi | 🛩️ |
| jiuzhang-yunji | ☁️ |
| yunshi-ai | ☁️ |
| bocloud | ☁️ |
| daxiao-robot | 🦾 |
| robo-science | 🦾 |
| wujie-robobrain | 🧠 |
| wujie-roborain | 🧠 |
| facemind | 🧠 |
| xiehou-fashion-tech | 👗 |
| haizhi | 📊 |
| qianfang-technology | 🚦 |
| internscience | 🔬 |
| dingtalk | 💬 |
| cursor | 🖱️ |
| chen-yongchao-startup | 🚀 |
| qinghua-chen-yongchao | 🚀 |
| beijing-decision-ai | 📈 |
| test-company | 🧪 |
| tp | 🏗️ |
| cl-test | 🧪 |
| isolation-test | 🔒 |
| hyper3d | 🎥 |
| hyper3d-developer | 🎥 |

### 学术/研究

| id | Emoji |
|:---|:---:|
| tsinghua-university | 🎓 |
| mit | 🏛️ |
| baai | 🧪 |
| bai-yuan | 🧪 |
| chinese-academy-of-sciences | 🔬 |
| hku | 🏫 |

---

## 人物 Emoji 映射（people）

| id | Emoji |
|:---|:---:|
| sam-altman | 👔 |
| greg-brockman | 💻 |
| elon-musk | 🚀 |
| demis-hassabis | 🧩 |
| dario-amodei | 🧬 |
| daniela-amodei | 🧬 |
| dario | 🧬 |
| li-feifei | 👁️ |
| andrew-ng | 🤖 |
| ma-huateng | 🐧 |
| leijun | 📱 |
| liyanhong | 🐾 |
| jia-yangqing | 📦 |
| xiaochuan | 🔍 |
| zhou-hongyi | 🛡️ |
| luo-yonghao | 🔨 |
| huang-renxun | 🎮 |
| mark-zuckerberg | ♾️ |
| marc-benioff | ☁️ |
| liang-wenfeng | 🐋 |
| liangrubo | 🎵 |
| kaifulee | 💰 |
| kaiming-he | 🔬 |
| yann-lecun | 🔬 |
| yoshua-bengio | 🔬 |
| terence-tao | 📐 |
| john-jumper | 🔬 |
| noam-shazeer | 🧠 |
| arthur-mensch | 🌬️ |
| aidan-gomez | 🏗️ |
| linus-torvalds | 🐧 |
| andrew-yang | 🗳️ |
| mira-murati | 🌀 |
| clement-delangue | 🦊 |
| clem-delangue | 🦊 |
| jeff-bezos | 📦 |
| andy-jassy | ☁️ |
| sundar-pichai | 🔮 |
| meredith-whittaker | 🛡️ |
| matthew-prince | ☁️ |
| chen-yongchao | 🚀 |
| yan-junjie | 🌬️ |
| yangzhilin | 🏛️ |
| hu-yanbin | 🎵 |
| zhu-guangquan | 🎙️ |
| wengli | 🛡️ |
| gaojiyang | 🧠 |
| gu-yuxian | 🎮 |
| tiffany-luck | 💰 |
| thariq-shihipar | 💻 |
| hunter-bown | 🔧 |
| ralph-loop | 🔁 |
| uv-founder | 📦 |
| claude-code-father | 🧬 |
| google-ai-studio-head | 🔮 |
| met-cto | ♾️ |
| huggingface-ceo | 🤗 |
| li-auto-founder | 🚗 |
| qingfeng | 🎙️ |
| yu-kai | 🚗 |
| jinbo-xu | 🔬 |
| lihaisong | 💻 |
| zhoujingren | 🛒 |
| zhou-feng | 📖 |
| shang-mingdong | 🛡️ |
| yitao-duan | 🚗 |
| peng-yuxin | 🎓 |
| xing-bo | 🏗️ |
| mu-yao | 🦾 |
| tao-dacheng | 🤖 |
| chen-baoquan | 🎓 |
| chen-maobo | 💰 |
| zhang-tao | 💻 |
| wenming | 🔧 |
| tpe | 👤 |
| tang-jie | 🏛️ |
| jiangdaxin | 🧠 |
| ke-xiao | 🔬 |
| lin-junyang | 🐋 |
| lucas-ropek | 🌐 |
| caohaoyu | 💻 |

---

## 工具 Emoji 映射（tools）

按类别 + 专属映射，未列出工具 fallback 到类别默认。

### AI 编程/IDE (⌨️)

| id | Emoji |
|:---|:---:|
| cursor | 🖱️ |
| claude-code | 🧬 |
| chatgpt-work | 🌀 |
| agents-cli | 🤖 |
| code-fable-5 | 🧬 |
| fable-5 | 🧬 |
| claude-fable-5 | 🧬 |
| claude-science | 🧬 |
| codestral | 🌬️ |
| colab-cli | 🔮 |
| loopcoder-v2 | 🔁 |
| office-cli | 🪟 |
| vercel-labs-skills | ▲ |
| lmworkflow | ⚙️ |
| sonnet-5 | 🧬 |

### 模型推理/服务 (🚀)

| id | Emoji |
|:---|:---:|
| vllm | ⚡ |
| gpt-5-6 | 🌀 |
| gpt-5-5 | 🌀 |
| gpt-5.5-cyber | 🌀 |
| gpt-live | 🔴 |
| grok-4-20 | ⚙️ |
| grok-skills | ⚙️ |
| responses-api | 🔌 |
| gemini-3-x | 🔮 |
| google-liter-lm | 🔮 |
| openclaw | 🦾 |
| opendm | 🎮 |
| openrl | 🎮 |
| core-ai-framework | 🧠 |

### Agent 框架 (🤖)

| id | Emoji |
|:---|:---:|
| agentspace | 🤖 |
| agents-a1 | 🤖 |
| gelab-zero-4b-preview-sico-evolution | 🤖 |
| genevolve | 🧬 |
| memgui-agent | 🧠 |
| areal-2 | 🧪 |
| loop-engineering | 🔁 |
| aitoearn | 💰 |

### 视频/3D 生成 (🎥)

| id | Emoji |
|:---|:---:|
| hyper3d-tool | 🎥 |
| vidu-s1 | 🎥 |
| liveworld | 🎥 |
| flash-world-model | ⚡ |
| fast-leworldmodel | ⚡ |
| mobile-forge | 📱 |
| hyper3d | 🎥 |

### 音频/语音 (🎵)

| id | Emoji |
|:---|:---:|
| fun-asr-realtime | 🎵 |
| vibevoice-realtime | 🎵 |
| viitorvoice-nar | 🎵 |
| eseilane | 🎵 |
| caveman | 🎵 |

### 机器人/具身 (🦾)

| id | Emoji |
|:---|:---:|
| lingbot-vla-2 | 🦾 |
| lingbot-video | 🎥 |
| lingbot-vision | 👁️ |
| lingbot-depth-2-0 | 📏 |
| visics-tool | 🦾 |
| surgmotion | 🏥 |
| afford-vla | 🦾 |
| icrdrag | 🦾 |
| wyrd-ecs-core | 🦾 |

### 安全/评测 (🛡️)

| id | Emoji |
|:---|:---:|
| frontieror | 🛡️ |
| trustedari | 🛡️ |
| toxprune | 🧹 |
| coda-bench | 📊 |
| trm-thinking-reward-model | 🧠 |
| scpe | 📏 |

### 数据/搜索 (📊)

| id | Emoji |
|:---|:---:|
| atlas-agent-memory | 📊 |
| r3-embedding | 🔗 |
| slack-coco | 📊 |
| nvdock | 🎮 |
| adajepa | 🧠 |
| nova | ⭐ |
| dropbox-nova | 📁 |

### 包管理/工具链 (📦)

| id | Emoji |
|:---|:---:|
| uv | 📦 |
| bun | 🍞 |
| ds4-rs-metal | 🐋 |
| mandol | 🛠️ |
| taro | 🛠️ |

### 其他指定工具

| id | Emoji |
|:---|:---:|
| chrome-devtools-mcp | 🔍 |
| astryx | ⭐ |
| eve | 🌙 |
| comattack | ⚔️ |
| deeptutor | 🎓 |
| delta | 🔺 |
| gas-town | ⛽ |
| ticnote | 📝 |
| jetspec | ⚡ |
| limssr | 🔬 |
| mellum2 | 🛠️ |
| cwip-1.0 | 📦 |
| d-opsd | 🎮 |
| xpolicylab | 🧪 |
| minimax-m-series | 🌬️ |
| tt | 🔧 |
| wecom | 💬 |
| wechat-xiaowei | 💬 |
| feishu-ai-table | 📊 |
| ai-mediakit-cli | 🎬 |
| cubesandbox | 📦 |
| cube-sandbox | 📦 |
| jalapeno | 🌶️ |
| jialapenyo-chip | 🌶️ |

---

## 大模型 Emoji 映射（llms）

按系列/厂商分组。id 中包含系列前缀的共用同一个 emoji。

| 系列 | id 前缀/列表 | Emoji |
|:---|:---|:---:|
| GPT | gpt-5-5, gpt-5.5-cyber, gpt-5-5-pro, gpt-5-6, gpt-5.4, gpt5.4, gpt-live, chatgpt-work | 🌀 |
| Claude | claude, claude-sonnet-5, claude-fable-5, claude-mythos-5, fable-5-model, mythos-5, sonnet-5 | 🧬 |
| Gemini | gemini-3-1-ultra, gemini-omni-flash, gemma-4 | 🔮 |
| Grok | grok | ⚙️ |
| DeepSeek | deepseek, deepseek-v4-flash, deepseek-apple | 🐋 |
| 千问/Qwen | qwen3, qwen3-4b, qwen3-vl-8b, qianwen | 🛒 |
| GLM/智谱 | glm, glm-5-2 | 🏛️ |
| 混元 | hunyuan-hy3, hy3 | 🐧 |
| 豆包 Seed | seed-2-1, seed-2.1 | 🎵 |
| 可灵 | kling | 🎨 |
| 天工 | tiangong | 🏔️ |
| 灵波 | lingbot-world-model-2-0, lingbot-world-model-2.0, ant-lingbo-world-model-2-0, lingbot-video, lingbot-va-2-0, lingbot-vla-2-0, lingbot-depth-2-0 | 🐜 |
| MiniMax | minimax-m1 | 🌬️ |
| Vidu | vidu-s1 | 🎥 |
| 美团 | meituan-trillion-llm, meituan-zero-nvidia-trillion-model, longcat-2.0 | 🛵 |

### 其他独立模型

| id | Emoji |
|:---|:---:|
| alphafold | 🔬 |
| abot-earth05 | 🌍 |
| dm0-5 | 🔮 |
| happyhorse-1-1 | 🐴 |
| hyper3d-model | 🎥 |
| leanstral-1-5 | 🌬️ |
| mellum2 | 🛠️ |
| nano-banana-2-lite | 🍌 |
| nvdock | 🎮 |
| nvidia-audex-2b | 🎮 |
| nvidia-cwip-1-0 | 🎮 |
| nemotron-labs-twotower | 🎮 |
| robobrain-orca | 🐋 |
| wujie-robobrain-orca | 🧠 |
| tabfm | 📊 |
| tl | 🔧 |
| adajepa | 🧠 |
| agents-a1 | 🤖 |
| gelab-zero-4b-preview | 🤖 |
| fun-asr-realtime | 🎵 |
| vibevoice-realtime | 🎵 |
| surgmotion | 🏥 |
| visics | 🦾 |
| visics-model | 🦾 |
| physical-foundation-model | 💡 |
| he-kaiming-258m | 🔬 |
| he-kaiming-image-gen | 🔬 |
| tsinghua-spatial-model | 🎓 |
| general-cerebellum | 🦾 |
| galaxy-general-humanoid-brain | 🦾 |
| streaming-av-model | 🎵 |
| xiehou-2.0 | 👗 |
| xiehou-fashion-2-0 | 👗 |
| zhiqing | 🧠 |
| cwip-1-0 | 📦 |

---

## 热度等级 Emoji

| hot_level | Emoji |
|:---|:---:|
| 爆热 | 🔥 |
| 高热 | 🟠 |
| 温热 | 🟡 |
| 平稳 | 🟢 |
| 冷淡 | ⚪ |

---

## 前端实现（JS 常量）

```javascript
// 维度默认 + 实体专属映射
const EMOJI_MAP = {
  providers: {
    openai:'🌀', anthropic:'🧬', google:'🔮', 'google-deepmind':'🔮',
    meta:'♾️', microsoft:'🪟', apple:'🍎', amazon:'📦', nvidia:'🎮',
    tesla:'⚡', spacex:'🚀', 'spacex-xai':'🚀', xai:'🚀',
    'mistral-ai':'🌬️', groq:'⚙️', jetbrains:'✈️', gitlab:'🦊',
    cloudflare:'☁️', dropbox:'📁', netflix:'🎬', snowflake:'❄️',
    vercel:'▲', elastic:'🔍', slack:'💬', hubspot:'🎯',
    baidu:'🐾', 'alibaba-cloud':'🛒', tencent:'🐧', 'tencent-hunyuan':'🐧',
    bytedance:'🎵', huawei:'🪷', meituan:'🛵', xiaomi:'📱',
    kuaishou:'📹', deepseek:'🐋', 'zhipu-ai':'🏛️', 'z-ai':'🏛️',
    'ant-group':'🐜', 'ant-linbot':'🐜', 'shengshu-tech':'🌱',
    'kunlun-wanwei':'🏔️', 'moore-threads':'🧵', mobvoi:'🚪',
    'netease-youdao':'📖', lenovo:'💻', 'kling-ai':'🎨',
    volcengine:'🌋', 'tiangong-ai':'🏔️', 'guangxiang-tech':'💡',
    'robo-science':'🦾', 'wujie-robobrain':'🧠', 'wujie-roborain':'🧠',
    'xiehou-fashion-tech':'👗', haizhi:'📊', dingtalk:'💬',
    cursor:'🖱️', 'chen-yongchao-startup':'🚀',
    tsinghua-university:'🎓', mit:'🏛️', baai:'🧪', 'bai-yuan':'🧪',
    'chinese-academy-of-sciences':'🔬', hku:'🏫',
  },
  people: {
    'sam-altman':'👔', 'greg-brockman':'💻', 'elon-musk':'🚀',
    'demis-hassabis':'🧩', 'dario-amodei':'🧬', 'daniela-amodei':'🧬', dario:'🧬',
    'li-feifei':'👁️', 'andrew-ng':'🤖', 'ma-huateng':'🐧', leijun:'📱',
    liyanhong:'🐾', 'jia-yangqing':'📦', xiaochuan:'🔍', 'zhou-hongyi':'🛡️',
    'luo-yonghao':'🔨', 'huang-renxun':'🎮', 'mark-zuckerberg':'♾️',
    'liang-wenfeng':'🐋', liangrubo:'🎵', kaifulee:'💰', 'kaiming-he':'🔬',
    'yann-lecun':'🔬', 'yoshua-bengio':'🔬', 'terence-tao':'📐',
    'mira-murati':'🌀', 'clement-delangue':'🦊', 'chen-yongchao':'🚀',
    'yan-junjie':'🌬️', yangzhilin:'🏛️', 'ralph-loop':'🔁',
    'claude-code-father':'🧬',
  },
  tools: {
    cursor:'🖱️', 'claude-code':'🧬', 'chatgpt-work':'🌀', 'agents-cli':'🤖',
    'claude-fable-5':'🧬', 'fable-5':'🧬', 'claude-science':'🧬',
    vllm:'⚡', 'gpt-5-6':'🌀', 'gpt-5-5':'🌀', 'gpt-live':'🔴',
    'grok-4-20':'⚙️', 'grok-skills':'⚙️', 'gemini-3-x':'🔮',
    agentspace:'🤖', 'agents-a1':'🤖',
    'hyper3d-tool':'🎥', 'vidu-s1':'🎥', liveworld:'🎥',
    'fun-asr-realtime':'🎵', 'vibevoice-realtime':'🎵',
    'lingbot-vla-2':'🦾', 'lingbot-video':'🎥', 'visics-tool':'🦾',
    frontieror:'🛡️', trustedari:'🛡️',
    'atlas-agent-memory':'📊', 'r3-embedding':'🔗', nvdock:'🎮',
    uv:'📦', bun:'🍞', 'ds4-rs-metal':'🐋',
    'chrome-devtools-mcp':'🔍', ticnote:'📝', jalapeno:'🌶️',
    'code-fable-5':'🧬', sonnet-5:'🧬',
  },
  llms: {
    'gpt-5-6':'🌀', 'gpt-5-5':'🌀', 'gpt-5.5-cyber':'🌀', 'gpt-5-5-pro':'🌀',
    'gpt-5.4':'🌀', gpt5.4:'🌀', 'gpt-live':'🌀', 'chatgpt-work':'🌀',
    claude:'🧬', 'claude-sonnet-5':'🧬', 'claude-fable-5':'🧬',
    'claude-mythos-5':'🧬', 'fable-5-model':'🧬', 'mythos-5':'🧬', 'sonnet-5':'🧬',
    'gemini-3-1-ultra':'🔮', 'gemini-omni-flash':'🔮', 'gemma-4':'🔮',
    grok:'⚙️',
    deepseek:'🐋', 'deepseek-v4-flash':'🐋', 'deepseek-apple':'🐋',
    qwen3:'🛒', 'qwen3-4b':'🛒', 'qwen3-vl-8b':'🛒', qianwen:'🛒',
    glm:'🏛️', 'glm-5-2':'🏛️',
    'hunyuan-hy3':'🐧', hy3:'🐧',
    'seed-2-1':'🎵', 'seed-2.1':'🎵',
    kling:'🎨', tiangong:'🏔️',
    'lingbot-world-model-2-0':'🐜', 'lingbot-world-model-2.0':'🐜',
    'ant-lingbo-world-model-2-0':'🐜', 'lingbot-va-2-0':'🐜',
    'lingbot-video':'🐜', 'lingbot-depth-2-0':'🐜',
    'minimax-m1':'🌬️', 'vidu-s1':'🎥',
    'meituan-trillion-llm':'🛵', 'meituan-zero-nvidia-trillion-model':'🛵',
    'longcat-2.0':'🛵',
    alphafold:'🔬', 'hyper3d-model':'🎥', nvdock:'🎮',
    'visics-model':'🦾', 'physical-foundation-model':'💡',
  },
};

// 维度默认
const DIM_EMOJI = {
  providers:'🏢', people:'👤', tools:'🔧', llms:'🧠', hotspots:'🔥',
};

// 维度中文名
const DIM_LABELS = {
  providers:'厂商', people:'人物', tools:'工具', llms:'大模型', hotspots:'热点',
};

// 查找函数
function entityEmoji(dimension, id) {
    const map = EMOJI_MAP[dimension];
    if (map && map[id]) return map[id];
    // LLM 系列前缀匹配（gpt-*, claude-*, gemini-*, etc.）
    if (dimension === 'llms' && map) {
        for (const prefix of ['gpt-','claude-','gemini-','grok','deepseek','qwen','glm-','hunyuan','seed-','lingbot-','meituan-']) {
            if (id && id.startsWith(prefix)) {
                // 查找第一个匹配前缀的 entry
                for (const [k,v] of Object.entries(map)) {
                    if (k.startsWith(prefix)) return v;
                }
            }
        }
    }
    return DIM_EMOJI[dimension] || '❓';
}
```

---

## 维护约定

### 变更流程

- **新增实体**: 首次入库后 24h 内，在此文档添加 id→emoji 映射，同步更新 JS 常量
- **废弃实体**: 从映射表删除并标注删除日期（不删除 JS 常量中的条目以保持向后兼容）
- **更名实体**: id 不变则无需操作；id 变更则删除旧条目，添加新条目

### 覆盖度检查

每季度运行一次，检查 snapshot.json 中所有实体是否都有映射：

```bash
python3 -c "
import json
from pathlib import Path
data = json.loads(open('data/snapshot.json').read())
# 提取文档中已映射的 id（从 JS 常量或手动维护的集合）
mapped = {
    'providers': {'openai','anthropic','google',...},
    'people': {'sam-altman','greg-brockman',...},
    'tools': {'cursor','claude-code',...},
    'llms': {'gpt-5-6','claude',...},
}
for dim in ['providers','people','tools','llms']:
    ids = {i['id'] for i in data.get(dim,[])}
    missing = ids - mapped.get(dim, set())
    if missing:
        print(f'{dim} 缺失映射 ({len(missing)}):')
        for mid in sorted(missing):
            name = next((i['name'] for i in data[dim] if i['id']==mid), '?')
            print(f'  {mid:30s} {name}')
"
```

### 版本记录

| 版本 | 日期 | 变更 |
|:---|:---|:---|
| 1.0 | 2026-07-13 | 初始版本，覆盖 93 providers + 81 people + 99 tools + 82 llms |
