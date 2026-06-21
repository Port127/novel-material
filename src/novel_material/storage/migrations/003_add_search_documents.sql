-- Migration: 003_add_search_documents
-- Description: 为检索实体增加可重建的中文词法文档与索引
-- Date: 2026-06-21

CREATE EXTENSION IF NOT EXISTS pg_trgm;

ALTER TABLE novels ADD COLUMN IF NOT EXISTS search_tokens TEXT NOT NULL DEFAULT '';
ALTER TABLE novels ADD COLUMN IF NOT EXISTS search_document tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', search_tokens)) STORED;
CREATE INDEX IF NOT EXISTS idx_novels_search_document
    ON novels USING GIN(search_document);
CREATE INDEX IF NOT EXISTS idx_novels_name_trgm
    ON novels USING GIN(name gin_trgm_ops);

ALTER TABLE chapters ADD COLUMN IF NOT EXISTS search_tokens TEXT NOT NULL DEFAULT '';
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS search_document tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', search_tokens)) STORED;
CREATE INDEX IF NOT EXISTS idx_chapters_search_document
    ON chapters USING GIN(search_document);
CREATE INDEX IF NOT EXISTS idx_chapters_title_trgm
    ON chapters USING GIN(title gin_trgm_ops);

ALTER TABLE characters ADD COLUMN IF NOT EXISTS search_tokens TEXT NOT NULL DEFAULT '';
ALTER TABLE characters ADD COLUMN IF NOT EXISTS search_document tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', search_tokens)) STORED;
CREATE INDEX IF NOT EXISTS idx_characters_search_document
    ON characters USING GIN(search_document);
CREATE INDEX IF NOT EXISTS idx_characters_name_trgm
    ON characters USING GIN(name gin_trgm_ops);

ALTER TABLE worldbuilding_entities ADD COLUMN IF NOT EXISTS search_tokens TEXT NOT NULL DEFAULT '';
ALTER TABLE worldbuilding_entities ADD COLUMN IF NOT EXISTS search_document tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', search_tokens)) STORED;
CREATE INDEX IF NOT EXISTS idx_worldbuilding_search_document
    ON worldbuilding_entities USING GIN(search_document);
CREATE INDEX IF NOT EXISTS idx_worldbuilding_name_trgm
    ON worldbuilding_entities USING GIN(name gin_trgm_ops);

ALTER TABLE outline_sequences ADD COLUMN IF NOT EXISTS search_tokens TEXT NOT NULL DEFAULT '';
ALTER TABLE outline_sequences ADD COLUMN IF NOT EXISTS search_document tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', search_tokens)) STORED;
CREATE INDEX IF NOT EXISTS idx_outline_sequences_search_document
    ON outline_sequences USING GIN(search_document);
CREATE INDEX IF NOT EXISTS idx_outline_sequences_title_trgm
    ON outline_sequences USING GIN(title gin_trgm_ops);

ALTER TABLE outline_beats ADD COLUMN IF NOT EXISTS search_tokens TEXT NOT NULL DEFAULT '';
ALTER TABLE outline_beats ADD COLUMN IF NOT EXISTS search_document tsvector
    GENERATED ALWAYS AS (to_tsvector('simple', search_tokens)) STORED;
CREATE INDEX IF NOT EXISTS idx_outline_beats_search_document
    ON outline_beats USING GIN(search_document);
CREATE INDEX IF NOT EXISTS idx_outline_beats_title_trgm
    ON outline_beats USING GIN(title gin_trgm_ops);
