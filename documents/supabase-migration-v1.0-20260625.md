# LLM-Radar Supabase 迁移方案

> 从 JSON 文件 + Git 存储迁移到 Supabase (PostgreSQL)，消除数据更新时的 Git 操作，
> 同时保留版本历史。

---

## 1. 当前架构 vs 目标架构

```
当前（JSON + Git）:
  采集/写入 → snapshot.json → git commit+push → GitHub Pages → fetch JSON
                                                    │
                                              需 git 操作才能更新
                                              无实时能力

目标（Supabase）:
  采集/写入 → Supabase (PostgreSQL) → REST API / JS SDK → 前端
                                                    │
                                              即时可见
                                              无需 git
                                              支持实时订阅
```

### 保留的通道

Git 仍用于:
  - 代码版本控制（不包含数据）
  - .github/workflows 定时采集（可选备用）
  - 数据快照备份（git backup 脚本）

不再有:
  - auto-push 提交 snapshot.json
  - 数据变更触发 GitHub Pages 重建

---

## 2. 表结构设计

### 2.1 核心实体表 (5 张)

#### providers

```sql
CREATE TABLE providers (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    country         TEXT DEFAULT '',
    hot_score       INTEGER DEFAULT 0,
    hot_level       TEXT DEFAULT '平稳',
    last_event      TEXT DEFAULT '',
    last_event_date TEXT DEFAULT '',
    last_event_url  TEXT DEFAULT '',
    confidence      TEXT DEFAULT 'medium',
    flagship_models JSONB DEFAULT '[]',
    key_people      JSONB DEFAULT '[]',
    focus_areas     JSONB DEFAULT '[]',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_providers_hot ON providers (hot_score DESC);
CREATE INDEX idx_providers_country ON providers (country);
```

#### people

```sql
CREATE TABLE people (
    id                  TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    name_en             TEXT DEFAULT '',
    title               TEXT DEFAULT '',
    employer_id         TEXT DEFAULT '',
    influence_level     TEXT DEFAULT '活跃人物',
    hot_score           INTEGER DEFAULT 0,
    hot_level           TEXT DEFAULT '平稳',
    recent_activity     TEXT DEFAULT '',
    recent_activity_date TEXT DEFAULT '',
    recent_activity_url  TEXT DEFAULT '',
    confidence          TEXT DEFAULT 'medium',
    known_for           JSONB DEFAULT '[]',
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    updated_at          TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_people_hot ON people (hot_score DESC);
CREATE INDEX idx_people_employer ON people (employer_id);
```

#### tools

```sql
CREATE TABLE tools (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    category        TEXT DEFAULT '',
    website         TEXT DEFAULT '',
    github          TEXT DEFAULT '',
    description     TEXT DEFAULT '',
    pricing_model   TEXT DEFAULT '',
    maturity        TEXT DEFAULT '可用',
    hot_score       INTEGER DEFAULT 0,
    hot_level       TEXT DEFAULT '平稳',
    last_update     TEXT DEFAULT '',
    last_update_date TEXT DEFAULT '',
    last_update_url  TEXT DEFAULT '',
    confidence      TEXT DEFAULT 'medium',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_tools_hot ON tools (hot_score DESC);
CREATE INDEX idx_tools_category ON tools (category);
```

#### llms

```sql
CREATE TABLE llms (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    provider_id     TEXT DEFAULT '',
    family          TEXT DEFAULT '',
    type            TEXT DEFAULT '',
    open_weights    BOOLEAN DEFAULT FALSE,
    tier            TEXT DEFAULT '主力',
    status          TEXT DEFAULT '发布',
    hot_score       INTEGER DEFAULT 0,
    hot_level       TEXT DEFAULT '平稳',
    hot_reason      TEXT DEFAULT '',
    last_event      TEXT DEFAULT '',
    last_event_date TEXT DEFAULT '',
    last_event_url  TEXT DEFAULT '',
    confidence      TEXT DEFAULT 'medium',
    capabilities    JSONB DEFAULT '[]',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_llms_hot ON llms (hot_score DESC);
CREATE INDEX idx_llms_provider ON llms (provider_id);
```

#### hotspots

```sql
CREATE TABLE hotspots (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    summary     TEXT DEFAULT '',
    date        TEXT DEFAULT '',
    source      TEXT DEFAULT '',
    url         TEXT DEFAULT '',
    hot_score   INTEGER DEFAULT 0,
    hot_level   TEXT DEFAULT '温热',
    confidence  TEXT DEFAULT 'medium',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_hotspots_date ON hotspots (date DESC);
CREATE INDEX idx_hotspots_hot ON hotspots (hot_score DESC);
```

### 2.2 关系表 (Junction Table)

替代当前 JSON 数组 related_providers, related_people, related_llms:

```sql
CREATE TABLE entity_relations (
    id          BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    relation    TEXT DEFAULT 'related',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(source_type, source_id, target_type, target_id, relation)
);
CREATE INDEX idx_er_source ON entity_relations (source_type, source_id);
CREATE INDEX idx_er_target ON entity_relations (target_type, target_id);
```

### 2.3 快照表（替代 git commit 的版本管理）

```sql
CREATE TABLE snapshots (
    id          BIGSERIAL PRIMARY KEY,
    data        JSONB NOT NULL,
    stats       JSONB NOT NULL,
    created_by  TEXT DEFAULT 'agent-loop',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_snapshots_time ON snapshots (created_at DESC);
```

---

## 3. Upsert 逻辑（替换当前 merge_entities）

```python
def supabase_upsert(table, records, relations=None):
    """批量 upsert，替换 merge_entities()"""
    for record in records:
        record['updated_at'] = datetime.now().isoformat()
        # 提取关系
        rels = {}
        for k in ['related_providers', 'related_people', 'related_llms', 'related_tools']:
            if k in record:
                rels[k.replace('related_', '')] = record.pop(k)
        # upsert 主表
        supabase.table(table).upsert(record, on_conflict='id').execute()
        # 同步关系
        for target_type, target_ids in rels.items():
            supabase.table('entity_relations').delete() \
                .eq('source_type', table).eq('source_id', record['id']) \
                .eq('target_type', target_type).execute()
            for tid in target_ids:
                supabase.table('entity_relations').upsert({
                    'source_type': table, 'source_id': record['id'],
                    'target_type': target_type, 'target_id': tid,
                }, on_conflict='source_type,source_id,target_type,target_id,relation').execute()
```

## 4. 迁移步骤

| Phase | 内容 | 时间 |
|:---|:---|:---:|
| 1 | 创建 Supabase 项目 + 建表 | 1 天 |
| 2 | 从 snapshot.json 导入数据到 Supabase | 1 天 |
| 3 | 改造 collector.py + MCP Server 写入 Supabase | 2 天 |
| 4 | 改造前端 index.html 从 Supabase 读取 | 2 天 |
| 5 | 切换 + 观察 | 0.5 天 |

## 5. 环境变量

```
# .env 新增
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJ...   # 服务端
SUPABASE_ANON_KEY=eyJ...      # 客户端

# .env 可移除
GITHUB_TOKEN（不再需要 auto-push）
```

## 6. 成本

| 项目 | Supabase Free | 当前数据量 |
|:---|:---:|:---:|
| 数据库 | 500 MB | ~50 KB |
| 月行数 | 100 万行 | ~600 行/月 |
| API 请求 | 免费 | 足够 |

Free Plan 足够。Pro ($25/月) 提供自动备份和 8GB 存储。

## 7. 风险与回退

| 风险 | 缓解 |
|:---|:---|
| Supabase 不可用 | 保留 snapshot.json 降级写入 |
| 数据不一致 | 迁移后逐行对比 |
| 前端改造问题 | 保留 index-static.html 备用 |

回退: 切回 fetch(snapshot.json), 恢复 auto-push。


*版本: 1.0 | 更新: 2026-06-25*
