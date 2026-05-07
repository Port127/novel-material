# 架构重构设计文档

> **注意：本文档为历史设计草案（2026-04-27）**
> 实际实现略有不同，详见 `scripts/core/schema.sql`。
> 主要差异：向量维数从 vector(1024) 改为 vector(4096)

## 日期
2026-04-27

## 背景

### 用户核心诉求

本项目定位为 **小说写作参考检索库**，服务于两个写作场景：

**场景一：前期规划阶段**
- 生成世界观 → 检索相似世界观参考
- 生成大纲/细纲 → 检索多条高匹配度大纲，糅合

**场景二：章节写作阶段**
- 写章纲 → 检索相似章纲参考
- 写人物 → 检索相似人物描写
- 写事件 → 检索相似事件参考

### 5 个具体检索场景

| # | 场景 | 查询示例 |
|---|------|----------|
| 1 | 大纲检索 | "找 3 本修仙小说的大纲，主角都是废柴逆袭" |
| 2 | 细纲检索 | "找悬疑类小说的中段推进模式" |
| 3 | 章纲检索 | "找 10 本小说第 1 章的开局写法" |
| 4 | 人物检索 | "找修仙类小说的导师型人物写法" |
| 5 | 事件检索 | "找雨中告别的写法" |

### 规模目标

- **1000 本小说** 起步
- 每本 ~500 章 → 总计 **50 万章**
- 章节标签、人物出场、事件描述 → **千万级记录**

---

## 当前系统问题

### 核心错位

| 当前系统 | 实际需求 |
|----------|---------|
| 围绕"事件拆分"构建 | 需要按大纲/细纲/章纲/人物/事件分别检索 |
| 事件边界不可控（"戏剧动作"是文学概念） | 需要低成本、可控的拆分单元 |
| 大纲/人物/世界观散落在各文件夹 | 需要全局聚合，跨书检索 |
| 单本事件拆分耗时几百批次 | 需要支持 1000 本规模化处理 |

### 事件拆分的根本问题

1. **边界定义模糊**：LLM 对"戏剧动作"理解偏差无法程序检验
2. **粒度不均**：同为"主线事件"，粒度差距可达 33 倍
3. **覆盖重叠**：同一段文本被多个事件覆盖，但没有层级关系定义
4. **投入产出比低**：1 本大书卡很久，但检索效果不理想

---

## 重构方案

### 一、处理流程简化

**当前流程：**
```
入库 → 清洗 → 大纲 → 世界观 → 人物 → 标签 → 事件拆分(几百批) → 索引 → 精调 → 统计
```

**新流程：**
```
入库 → 清洗 → 大纲 → 世界观 → 人物 → 标签 → 章级分析(自动) → 全局聚合索引
```

**核心变化：**
- 移除事件拆分（边界不可控，投入产出比低）
- 新增章级分析（每章生成摘要+出场人物+章节功能标签，自动化）

### 二、章级分析方案

以**章节**为最小分析单元，边界完全可控：

```yaml
# 每章分析产物
chapter: 1
title: "牢狱之灾"
summary: "许七安穿越入狱，面临流放命运..."  # 50-100字
word_count: 4500
characters_appear: [许七安, 狱卒, 采薇]
chapter_function: [开局困境, 悬念引入, 人物亮相]
tension_level: 4
pacing: 快
setting: [监牢]
key_plot_point: inciting_incident  # 可选：如果本章是关键节点
```

**优势：**
- 边界定义完全可控（章节标题是天然的）
- 处理成本低（可自动化）
- 检索效果好（能找到"开局第1章怎么写"、"高潮章怎么写"）
- 可规模化（1000 本轻松处理）

### 三、数据存储架构

#### 规模评估

| 数据实体 | 每本书 | 1000本 | 数据量级 |
|----------|--------|--------|---------|
| 章节 | ~500章 | 50万章 | 千万级 |
| 章节标签（每章5维） | ~25条 | 1250万条 | 千万级 |
| 人物 | ~50人 | 5万人 | 十万级 |
| 人物-章节出场 | ~200次 | 20万次 | 百万级 |
| 世界观设定 | ~30条 | 3万条 | 十万级 |
| 大纲结构（节拍级） | ~100条 | 10万条 | 十万级 |
| 全文摘要文本 | 500段 | 50万段 | ~50GB文本 |

#### 技术选型

**SQLite 当前能胜任的部分：**
- 按 material_id 查单本书
- 按章节号查单章
- 小规模数据检索

**SQLite 无法胜任的部分（千万级规模）：**
- 跨 1000 本按标签组合检索（需扫千万行）
- 全文摘要的模糊搜索（FTS5 不支持中文分词）
- 多条件 AND 检索（需要多表 JOIN）
- 人物关系图查询
- 并发检索（写锁互斥）

**检索需求本质：**
- 5 个检索场景中，2 个是结构化查询，3 个涉及语义相似度
- 需要向量搜索能力（"找类似写法"类查询）

#### 最终方案：PostgreSQL + pgvector

```
                    用户检索请求
                         |
                         v
              ┌─────────────────────┐
              │   检索路由层          │  分析查询意图
              └─────────────────────┘
                    |         |
          结构化查询         语义查询
                |              |
                v              v
        ┌───────────┐   ┌──────────────┐
        │PostgreSQL  │   │ pgvector     │
        │(结构化数据) │   │(摘要/描述)   │
        └───────────┘   └──────────────┘
              |              |
              └──────┬───────┘
                     |
                     v
              ┌──────────────┐
              │  融合排序层   │  综合结构化+语义结果
              └──────────────┘
```

**PostgreSQL 负责：**
- 小说元信息（genre、作者、字数等）
- 章节结构化数据（章号、标题、张力值、章节功能标签）
- 大纲结构（幕/序列/节拍树，JSONB 存储）
- 人物名册（原型、角色、心理特征）
- 世界观设定（势力、地理、物品）
- 所有标签维度的精确匹配

**pgvector 负责：**
- 章节摘要的语义搜索
- 事件/场景描述的语义匹配
- 人物描述的相似性检索
- "找类似写法"类查询

**为什么选 pgvector 而不是独立向量数据库：**
- 和结构化数据同一数据库，JOIN 方便
- 同一数据库内可做结构化+向量联合查询
- 千万级记录完全胜任
- 部署简单，不需要额外服务
- 未来到亿级再迁移到 Qdrant 也不迟

### 四、目录结构调整

```
data/
├── novels/                           # 每本小说独立
│   └── {material_id}/
│       ├── meta.yaml                 # 元数据
│       ├── source.txt                # 清洗后原文
│       ├── chapter_index.yaml        # 章节索引（章号+标题+行号）
│       ├── chapters.yaml             # [NEW] 章级分析
│       ├── outline/                  # 大纲（文件夹结构）
│       │   ├── _index.yaml
│       │   ├── structure.yaml
│       │   ├── hooks_network.yaml
│       │   └── ...
│       ├── worldbuilding/            # 世界观（文件夹结构）
│       ├── characters/               # 人物（文件夹结构）
│       └── tags.yaml                 # 小说级标签
│
├── material.db                       # SQLite（过渡期使用）
├── index.yaml                        # 素材路由表
└── tags.yaml                         # 标签字典
```

### 五、数据库 Schema 设计（PostgreSQL）

#### chapters 表

```sql
CREATE TABLE chapters (
    material_id TEXT NOT NULL,
    chapter INTEGER NOT NULL,
    title TEXT,
    summary TEXT,                        -- 50-100字内容摘要
    summary_embedding vector(1024),      -- pgvector 向量
    word_count INTEGER,
    tension_level INTEGER,               -- 1-5
    pacing TEXT,                         -- 快/慢/喘息/加速
    setting TEXT[],                      -- 场景类型数组
    key_plot_point TEXT,                 -- inciting_incident/midpoint/climax...
    chapter_functions TEXT[],            -- 章节功能标签数组
    characters_appear TEXT[],            -- 出场人物数组
    PRIMARY KEY (material_id, chapter),
    FOREIGN KEY (material_id) REFERENCES novels(material_id)
);
```

#### novels 表（增强）

```sql
CREATE TABLE novels (
    material_id TEXT PRIMARY KEY,
    name TEXT,
    author TEXT,
    genre TEXT[],                        -- 类型标签数组
    word_count INTEGER,
    chapter_count INTEGER,
    status TEXT,
    premise TEXT,                        -- 一句话核心前提
    premise_embedding vector(1024),      -- pgvector 向量
    structure_type TEXT,                 -- 三幕式/英雄之旅/...
    act_count INTEGER,
    sequence_count INTEGER,
    theme TEXT[],
    tone TEXT[],
    hook_count INTEGER,
    subplot_count INTEGER,
    tags JSONB,                          -- 小说级标签
    built_at TEXT
);
```

#### outline_sequences 表

```sql
CREATE TABLE outline_sequences (
    id SERIAL PRIMARY KEY,
    material_id TEXT NOT NULL,
    act INTEGER,                         -- 所属幕
    sequence INTEGER,                    -- 序列号
    title TEXT,
    chapters_start INTEGER,
    chapters_end INTEGER,
    description TEXT,
    description_embedding vector(1024),
    FOREIGN KEY (material_id) REFERENCES novels(material_id)
);
```

#### outline_beats 表

```sql
CREATE TABLE outline_beats (
    id SERIAL PRIMARY KEY,
    material_id TEXT NOT NULL,
    act INTEGER,
    sequence INTEGER,
    beat INTEGER,                        -- 节拍号
    title TEXT,
    chapter INTEGER,
    description TEXT,
    description_embedding vector(1024),
    tension INTEGER,
    FOREIGN KEY (material_id) REFERENCES novels(material_id)
);
```

#### characters 表（增强）

```sql
CREATE TABLE characters (
    id SERIAL PRIMARY KEY,
    material_id TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT,                           -- protagonist/antagonist/supporting/minor
    archetype TEXT,
    moral_spectrum TEXT,
    arc_summary TEXT,
    arc_summary_embedding vector(1024),
    narrative_function TEXT,
    psychology JSONB,                    -- fatal_flaw/obsession/soft_spot/...
    first_appearance TEXT,
    last_appearance TEXT,
    appearance_count INTEGER DEFAULT 0,
    file_path TEXT,
    description TEXT,
    FOREIGN KEY (material_id) REFERENCES novels(material_id)
);
```

#### character_appearances 表

```sql
CREATE TABLE character_appearances (
    id SERIAL PRIMARY KEY,
    material_id TEXT NOT NULL,
    character_name TEXT NOT NULL,
    chapter INTEGER NOT NULL,
    significance TEXT,                   -- major/minor/cameo
    role_in_chapter TEXT,
    FOREIGN KEY (material_id) REFERENCES novels(material_id)
);
```

#### worldbuilding_entities 表

```sql
CREATE TABLE worldbuilding_entities (
    id SERIAL PRIMARY KEY,
    material_id TEXT NOT NULL,
    entity_type TEXT,                    -- faction/region/item/system/...
    name TEXT NOT NULL,
    description TEXT,
    description_embedding vector(1024),
    properties JSONB,                    -- 类型相关的属性
    first_appearance TEXT,
    importance TEXT,                     -- primary/secondary/minor
    FOREIGN KEY (material_id) REFERENCES novels(material_id)
);
```

#### 索引设计

```sql
-- 章节检索索引
CREATE INDEX idx_chapters_material ON chapters(material_id);
CREATE INDEX idx_chapters_functions ON chapters USING GIN(chapter_functions);
CREATE INDEX idx_chapters_characters ON chapters USING GIN(characters_appear);
CREATE INDEX idx_chapters_tension ON chapters(tension_level);
CREATE INDEX idx_chapters_key_plot ON chapters(key_plot_point);

-- 人物检索索引
CREATE INDEX idx_characters_material ON characters(material_id);
CREATE INDEX idx_characters_name ON characters(name);
CREATE INDEX idx_characters_archetype ON characters(archetype);
CREATE INDEX idx_characters_role ON characters(role);

-- 大纲检索索引
CREATE INDEX idx_sequences_material ON outline_sequences(material_id);
CREATE INDEX idx_beats_material ON outline_beats(material_id);

-- 向量搜索索引
CREATE INDEX idx_chapters_summary_vec ON chapters USING ivfflat (summary_embedding vector_cosine_ops);
CREATE INDEX idx_novels_premise_vec ON novels USING ivfflat (premise_embedding vector_cosine_ops);
CREATE INDEX idx_beats_desc_vec ON outline_beats USING ivfflat (description_embedding vector_cosine_ops);
CREATE INDEX idx_characters_arc_vec ON characters USING ivfflat (arc_summary_embedding vector_cosine_ops);
CREATE INDEX idx_wb_desc_vec ON worldbuilding_entities USING ivfflat (description_embedding vector_cosine_ops);

-- 全文搜索索引
CREATE INDEX idx_chapters_summary_fts ON chapters USING gin(to_tsvector('chinese', summary));
```

---

## 检索场景实现

### 场景 1：大纲检索

```
用户输入："找 3 本修仙小说的大纲，主角都是废柴逆袭"

处理流程：
1. 解析意图：genre=修仙, trope=废柴逆袭
2. 在 novels 表中 WHERE genre @> ARRAY['修仙']
3. 在 premise_embedding 中向量搜索"废柴逆袭"语义
4. 返回 top 3 的大纲结构树（从 outline_sequences + outline_beats JOIN）
```

### 场景 2：细纲检索

```
用户输入："找悬疑类小说的中段推进模式"

处理流程：
1. 解析意图：genre=悬疑, stage=中段推进
2. 在 novels 表中过滤 genre
3. 在 outline_sequences 中搜索 act=2 且 description 匹配"推进模式"语义
4. 返回序列级结构对比
```

### 场景 3：章纲检索

```
用户输入："找 10 本小说第 1 章的开局写法"

处理流程：
1. 解析意图：chapter=1, function=开局
2. 在 chapters 表中 WHERE chapter=1 AND chapter_functions @> ARRAY['开局困境']
3. 在 summary_embedding 中向量搜索"开局写法"语义
4. 返回 top 10 的章节摘要+结构信息
```

### 场景 4：人物检索

```
用户输入："找修仙类小说的导师型人物写法"

处理流程：
1. 解析意图：genre=修仙, archetype=导师
2. JOIN novels + characters WHERE archetype='导师'
3. 在 arc_summary_embedding 中搜索"导师型写法"语义
4. 返回人物小传+关键出场章节
```

### 场景 5：事件检索

```
用户输入："找雨中告别的写法"

处理流程：
1. 解析意图：语义匹配"雨中告别"
2. 在 chapters 表的 summary_embedding 中搜索
3. 可选标签过滤：setting @> ARRAY['室外'], emotion='悲伤'
4. 返回匹配的章节摘要+完整章节信息
```

---

## 迁移路径

| 阶段 | 目标 | 数据规模 | 技术方案 | 预计耗时 |
|------|------|---------|---------|---------|
| **P0** | 验证章级数据结构 | 3本三体 | SQLite 新增章级表 | 1-2天 |
| **P1** | 迁移到 PostgreSQL | 50本 | PostgreSQL + pgvector | 3-5天 |
| **P2** | 规模化验证 | 500本 | 索引优化 + 批量处理 | 1-2周 |
| **P3** | 千本以上 | 1000+本 | 评估 pgvector → Qdrant | 按需 |

---

## 写入成本估算

| 环节 | 每章成本 | 1000本(50万章)成本 | 说明 |
|------|---------|-------------------|------|
| 章节切分 | ~0.01秒 | ~5000秒 | 纯脚本，机械操作 |
| 章级分析（LLM） | ~2秒 | ~166小时 | 可分批并行，10并发 ~17小时 |
| Embedding | ~0.1秒 | ~8小时 | 本地模型或API |
| 数据库写入 | ~0.01秒 | ~5000秒 | 批量插入 |

---

## 核心原则

1. **检索参考而非学习材料**：标注数据用于检索，不是训练 Agent
2. **Agent 主要靠自身能力**：标注数据提供参考样例，Agent 自行理解并糅合
3. **可控性优先**：用章节（天然边界）替代事件（模糊边界）
4. **渐进式迁移**：先用 SQLite 验证结构，再逐步升级基础设施
5. **混合检索**：结构化查询（精确过滤）+ 向量搜索（语义匹配）
