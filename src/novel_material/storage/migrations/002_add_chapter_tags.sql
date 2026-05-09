-- Migration: 002_add_chapter_tags
-- Description: 为 chapters 表添加章节级标签字段（阶段四）
-- Date: 2026-05-09

-- 添加4列
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS emotional_tone TEXT[];
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS scene_type TEXT[];
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS technique TEXT[];
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS hook_type TEXT;

-- 添加 GIN 索引（支持数组检索）
CREATE INDEX IF NOT EXISTS idx_chapters_emotional_tone ON chapters USING GIN(emotional_tone);
CREATE INDEX IF NOT EXISTS idx_chapters_scene_type ON chapters USING GIN(scene_type);
CREATE INDEX IF NOT EXISTS idx_chapters_technique ON chapters USING GIN(technique);
CREATE INDEX IF NOT EXISTS idx_chapters_hook_type ON chapters(hook_type);

-- 注释说明
COMMENT ON COLUMN chapters.emotional_tone IS '情感基调标签数组';
COMMENT ON COLUMN chapters.scene_type IS '场景类型标签数组';
COMMENT ON COLUMN chapters.technique IS '叙事技巧标签数组';
COMMENT ON COLUMN chapters.hook_type IS '章末钩子类型';