-- Migration: 001_add_key_event
-- Description: 为 chapters 表添加 key_event 和 key_plot_point 字段
-- Date: 2025-05-09

-- 添加 key_event 和 key_plot_point 字段（如不存在）
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS key_event TEXT;
ALTER TABLE chapters ADD COLUMN IF NOT EXISTS key_plot_point TEXT;

-- 注释说明
COMMENT ON COLUMN chapters.key_plot_point IS '结构角色标记（代码推断）：inciting_incident/midpoint/climax/resolution 等';
COMMENT ON COLUMN chapters.key_event IS '关键事件描述（LLM生成）：10-30字精炼情节描述';