-- Novel Material V3 - PostgreSQL Schema
-- 数据库初始化脚本

-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;
-- 启用名称和标题模糊匹配
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ============================================================
-- novels 表：小说元信息
-- ============================================================
CREATE TABLE IF NOT EXISTS novels (
    material_id TEXT PRIMARY KEY,
    name TEXT,
    author TEXT,
    genre TEXT[],                        -- 类型标签数组
    word_count INTEGER,
    chapter_count INTEGER,
    status TEXT DEFAULT 'raw',           -- raw / clean / analyzed / indexed
    premise TEXT,                        -- 一句话核心前提
    premise_embedding vector(4096),      -- pgvector 向量
    structure_type TEXT,                 -- 三幕式/英雄之旅/...
    act_count INTEGER,
    sequence_count INTEGER,
    theme TEXT[],
    tone TEXT[],
    hook_count INTEGER,
    subplot_count INTEGER,
    tags JSONB,                          -- 小说级标签
    search_tokens TEXT NOT NULL DEFAULT '',
    search_document tsvector GENERATED ALWAYS AS
        (to_tsvector('simple', search_tokens)) STORED,
    built_at TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================
-- chapters 表：章级分析（核心）
-- ============================================================
CREATE TABLE IF NOT EXISTS chapters (
    material_id TEXT NOT NULL,
    chapter INTEGER NOT NULL,
    title TEXT,
    type TEXT DEFAULT 'normal',            -- normal/afterword/extra/author_note
    summary TEXT,                        -- 50-100字内容摘要
    summary_embedding vector(4096),      -- pgvector 向量
    word_count INTEGER,
    tension_level INTEGER,               -- 1-5
    pacing TEXT,                         -- 快/慢/喘息/加速
    setting TEXT[],                      -- 场景类型数组
    key_plot_point TEXT,                 -- 结构角色标记（代码推断）：inciting_incident/midpoint/climax/resolution 等
    key_event TEXT,                      -- 关键事件描述（LLM生成）：10-30字精炼情节描述
    -- 滑动窗口新增字段（阶段二）
    tension_change TEXT,                 -- 张力变化方向：上升/持平/下降
    emotion_transition TEXT,             -- 情感过渡描述（10-50字）
    plot_progress TEXT,                  -- 情节进度描述（20-100字）
    chapter_functions TEXT[],            -- 章节功能标签数组
    characters_appear TEXT[],            -- 出场人物数组
    -- 章节级标签（阶段四新增）
    emotional_tone TEXT[],               -- 情感基调数组
    scene_type TEXT[],                   -- 场景类型数组
    technique TEXT[],                    -- 叙事技巧数组
    hook_type TEXT,                      -- 章末钩子类型
    search_tokens TEXT NOT NULL DEFAULT '',
    search_document tsvector GENERATED ALWAYS AS
        (to_tsvector('simple', search_tokens)) STORED,
    PRIMARY KEY (material_id, chapter),
    FOREIGN KEY (material_id) REFERENCES novels(material_id) ON DELETE CASCADE
);

-- key_plot_point 合法值：inciting_incident / first_turning_point / midpoint / second_turning_point / climax / resolution
-- tension_change 合法值：上升 / 持平 / 下降

-- ============================================================
-- outline_sequences 表：大纲序列
-- ============================================================
CREATE TABLE IF NOT EXISTS outline_sequences (
    id SERIAL PRIMARY KEY,
    material_id TEXT NOT NULL,
    act INTEGER,                         -- 所属幕
    sequence INTEGER,                    -- 序列号
    title TEXT,
    chapters_start INTEGER,
    chapters_end INTEGER,
    description TEXT,
    search_tokens TEXT NOT NULL DEFAULT '',
    search_document tsvector GENERATED ALWAYS AS
        (to_tsvector('simple', search_tokens)) STORED,
    FOREIGN KEY (material_id) REFERENCES novels(material_id) ON DELETE CASCADE
);

-- ============================================================
-- outline_beats 表：大纲节拍
-- ============================================================
CREATE TABLE IF NOT EXISTS outline_beats (
    id SERIAL PRIMARY KEY,
    material_id TEXT NOT NULL,
    act INTEGER,
    sequence INTEGER,
    beat INTEGER,                        -- 节拍号
    title TEXT,
    chapter INTEGER,
    description TEXT,
    description_embedding vector(4096),
    tension INTEGER,
    search_tokens TEXT NOT NULL DEFAULT '',
    search_document tsvector GENERATED ALWAYS AS
        (to_tsvector('simple', search_tokens)) STORED,
    FOREIGN KEY (material_id) REFERENCES novels(material_id) ON DELETE CASCADE
);

-- ============================================================
-- characters 表：人物
-- ============================================================
CREATE TABLE IF NOT EXISTS characters (
    id SERIAL PRIMARY KEY,
    material_id TEXT NOT NULL,
    name TEXT NOT NULL,
    role TEXT,                           -- protagonist/antagonist/supporting/minor
    archetype TEXT,
    moral_spectrum TEXT,
    arc_summary TEXT,
    arc_summary_embedding vector(4096),
    narrative_function TEXT,
    psychology JSONB,                    -- fatal_flaw/obsession/soft_spot/...
    first_appearance TEXT,
    last_appearance TEXT,
    appearance_count INTEGER DEFAULT 0,
    file_path TEXT,
    description TEXT,
    search_tokens TEXT NOT NULL DEFAULT '',
    search_document tsvector GENERATED ALWAYS AS
        (to_tsvector('simple', search_tokens)) STORED,
    FOREIGN KEY (material_id) REFERENCES novels(material_id) ON DELETE CASCADE,
    UNIQUE(material_id, name)
);

-- ============================================================
-- character_appearances 表：人物出场记录
-- ============================================================
CREATE TABLE IF NOT EXISTS character_appearances (
    id SERIAL PRIMARY KEY,
    material_id TEXT NOT NULL,
    character_name TEXT NOT NULL,
    chapter INTEGER NOT NULL,
    significance TEXT,                   -- major/minor/cameo
    role_in_chapter TEXT,
    FOREIGN KEY (material_id) REFERENCES novels(material_id) ON DELETE CASCADE
);

-- ============================================================
-- worldbuilding_entities 表：世界观设定
-- ============================================================
CREATE TABLE IF NOT EXISTS worldbuilding_entities (
    id SERIAL PRIMARY KEY,
    material_id TEXT NOT NULL,
    entity_type TEXT,                    -- faction/region/item/system/...
    name TEXT NOT NULL,
    description TEXT,
    description_embedding vector(4096),
    properties JSONB,                    -- 类型相关的属性
    first_appearance TEXT,
    importance TEXT,                     -- primary/secondary/minor
    search_tokens TEXT NOT NULL DEFAULT '',
    search_document tsvector GENERATED ALWAYS AS
        (to_tsvector('simple', search_tokens)) STORED,
    FOREIGN KEY (material_id) REFERENCES novels(material_id) ON DELETE CASCADE,
    UNIQUE(material_id, entity_type, name)
);

-- ============================================================
-- 索引设计
-- ============================================================

-- 章节检索索引
CREATE INDEX IF NOT EXISTS idx_chapters_material ON chapters(material_id);
CREATE INDEX IF NOT EXISTS idx_chapters_functions ON chapters USING GIN(chapter_functions);
CREATE INDEX IF NOT EXISTS idx_chapters_characters ON chapters USING GIN(characters_appear);
CREATE INDEX IF NOT EXISTS idx_chapters_tension ON chapters(tension_level);
CREATE INDEX IF NOT EXISTS idx_chapters_key_plot ON chapters(key_plot_point);
-- 章节级标签索引（阶段四新增）
CREATE INDEX IF NOT EXISTS idx_chapters_emotional_tone ON chapters USING GIN(emotional_tone);
CREATE INDEX IF NOT EXISTS idx_chapters_scene_type ON chapters USING GIN(scene_type);
CREATE INDEX IF NOT EXISTS idx_chapters_technique ON chapters USING GIN(technique);
CREATE INDEX IF NOT EXISTS idx_chapters_hook_type ON chapters(hook_type);
CREATE INDEX IF NOT EXISTS idx_chapters_search_document ON chapters USING GIN(search_document);
CREATE INDEX IF NOT EXISTS idx_chapters_title_trgm ON chapters USING GIN(title gin_trgm_ops);

-- 小说检索索引
CREATE INDEX IF NOT EXISTS idx_novels_search_document ON novels USING GIN(search_document);
CREATE INDEX IF NOT EXISTS idx_novels_name_trgm ON novels USING GIN(name gin_trgm_ops);

-- 人物检索索引
CREATE INDEX IF NOT EXISTS idx_characters_material ON characters(material_id);
CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(name);
CREATE INDEX IF NOT EXISTS idx_characters_archetype ON characters(archetype);
CREATE INDEX IF NOT EXISTS idx_characters_role ON characters(role);
CREATE INDEX IF NOT EXISTS idx_characters_search_document ON characters USING GIN(search_document);
CREATE INDEX IF NOT EXISTS idx_characters_name_trgm ON characters USING GIN(name gin_trgm_ops);

-- 大纲检索索引
CREATE INDEX IF NOT EXISTS idx_sequences_material ON outline_sequences(material_id);
CREATE INDEX IF NOT EXISTS idx_beats_material ON outline_beats(material_id);
CREATE INDEX IF NOT EXISTS idx_outline_sequences_search_document ON outline_sequences USING GIN(search_document);
CREATE INDEX IF NOT EXISTS idx_outline_sequences_title_trgm ON outline_sequences USING GIN(title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_outline_beats_search_document ON outline_beats USING GIN(search_document);
CREATE INDEX IF NOT EXISTS idx_outline_beats_title_trgm ON outline_beats USING GIN(title gin_trgm_ops);

-- 世界观检索索引
CREATE INDEX IF NOT EXISTS idx_wb_material ON worldbuilding_entities(material_id);
CREATE INDEX IF NOT EXISTS idx_wb_type ON worldbuilding_entities(entity_type);
CREATE INDEX IF NOT EXISTS idx_worldbuilding_search_document ON worldbuilding_entities USING GIN(search_document);
CREATE INDEX IF NOT EXISTS idx_worldbuilding_name_trgm ON worldbuilding_entities USING GIN(name gin_trgm_ops);

-- 向量搜索索引
-- 注意: pgvector (IVFFLAT/HNSW) 不支持超过 2000 维的向量索引
-- 当前使用 vector(4096)，向量列为普通列，搜索时走全表扫描
-- CREATE INDEX idx_chapters_summary_vec ON chapters USING ivfflat (summary_embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX idx_novels_premise_vec ON novels USING ivfflat (premise_embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX idx_beats_desc_vec ON outline_beats USING ivfflat (description_embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX idx_characters_arc_vec ON characters USING ivfflat (arc_summary_embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX idx_wb_desc_vec ON worldbuilding_entities USING ivfflat (description_embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================================
-- 标签分级系统表
-- ============================================================

CREATE TABLE IF NOT EXISTS tags (
    id SERIAL PRIMARY KEY,
    dimension VARCHAR(50) NOT NULL,
    tag VARCHAR(100) NOT NULL,
    domain VARCHAR(50) NOT NULL,
    group_name VARCHAR(100),
    is_common BOOLEAN DEFAULT FALSE,
    synonym_of VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(dimension, tag)
);

CREATE INDEX IF NOT EXISTS idx_tags_dimension ON tags(dimension);
CREATE INDEX IF NOT EXISTS idx_tags_domain ON tags(domain);
CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag);
CREATE INDEX IF NOT EXISTS idx_tags_synonym ON tags(synonym_of);

CREATE TABLE IF NOT EXISTS genre_domain_map (
    genre_primary VARCHAR(50) PRIMARY KEY,
    domains JSONB NOT NULL,
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS new_tag_candidates (
    id SERIAL PRIMARY KEY,
    dimension VARCHAR(50) NOT NULL,
    tag VARCHAR(100) NOT NULL,
    suggested_domain VARCHAR(50),
    source_material VARCHAR(100),
    context_genre VARCHAR(50),
    occurrence_count INTEGER DEFAULT 1,
    status VARCHAR(20) DEFAULT 'pending',
    reviewed_at TIMESTAMP,
    reviewed_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(dimension, tag)
);

CREATE INDEX IF NOT EXISTS idx_candidates_status ON new_tag_candidates(status);
CREATE INDEX IF NOT EXISTS idx_candidates_count ON new_tag_candidates(occurrence_count DESC);
CREATE INDEX IF NOT EXISTS idx_candidates_dimension ON new_tag_candidates(dimension);

CREATE TABLE IF NOT EXISTS new_genre_candidates (
    id SERIAL PRIMARY KEY,
    genre VARCHAR(50) NOT NULL,
    description TEXT,
    source_material VARCHAR(100),
    occurrence_count INTEGER DEFAULT 1,
    status VARCHAR(20) DEFAULT 'pending',
    reviewed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(genre)
);

CREATE TABLE IF NOT EXISTS free_tags_stats (
    dimension VARCHAR(50),
    tag VARCHAR(100),
    occurrence_count INTEGER DEFAULT 1,
    last_seen TIMESTAMP DEFAULT NOW(),
    UNIQUE(dimension, tag)
);

CREATE INDEX IF NOT EXISTS idx_free_tags_count ON free_tags_stats(occurrence_count DESC);
