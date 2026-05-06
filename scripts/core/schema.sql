-- Novel Material V2 - PostgreSQL Schema
-- 数据库初始化脚本

-- 启用 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

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
    summary TEXT,                        -- 50-100字内容摘要
    summary_embedding vector(4096),      -- pgvector 向量
    word_count INTEGER,
    tension_level INTEGER,               -- 1-5
    pacing TEXT,                         -- 快/慢/喘息/加速
    setting TEXT[],                      -- 场景类型数组
    key_plot_point TEXT,                 -- inciting_incident/midpoint/climax...
    chapter_functions TEXT[],            -- 章节功能标签数组
    characters_appear TEXT[],            -- 出场人物数组
    PRIMARY KEY (material_id, chapter),
    FOREIGN KEY (material_id) REFERENCES novels(material_id) ON DELETE CASCADE
);

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
    FOREIGN KEY (material_id) REFERENCES novels(material_id) ON DELETE CASCADE,
    UNIQUE(material_id, entity_type, name)
);

-- ============================================================
-- 索引设计
-- ============================================================

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

-- 世界观检索索引
CREATE INDEX idx_wb_material ON worldbuilding_entities(material_id);
CREATE INDEX idx_wb_type ON worldbuilding_entities(entity_type);

-- 向量搜索索引
-- 注意: pgvector (IVFFLAT/HNSW) 不支持超过 2000 维的向量索引
-- 当前使用 vector(4096)，向量列为普通列，搜索时走全表扫描
-- CREATE INDEX idx_chapters_summary_vec ON chapters USING ivfflat (summary_embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX idx_novels_premise_vec ON novels USING ivfflat (premise_embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX idx_beats_desc_vec ON outline_beats USING ivfflat (description_embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX idx_characters_arc_vec ON characters USING ivfflat (arc_summary_embedding vector_cosine_ops) WITH (lists = 100);
-- CREATE INDEX idx_wb_desc_vec ON worldbuilding_entities USING ivfflat (description_embedding vector_cosine_ops) WITH (lists = 100);
