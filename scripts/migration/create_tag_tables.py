#!/usr/bin/env python
"""创建标签相关数据库表。

创建的表：
- tags: 标签定义表（核心）
- genre_domain_map: 题材领域映射表
- new_tag_candidates: 新标签候选表
- new_genre_candidates: 新题材候选表
- free_tags_stats: 自由标签统计表
"""
import os
import sys
import psycopg2
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("错误: 请设置 DATABASE_URL 环境变量")
    sys.exit(1)


def create_tag_tables():
    """创建所有标签相关表。"""
    print("正在连接数据库...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True

    with conn.cursor() as cur:
        # 1. 标签定义表
        print("创建 tags 表...")
        cur.execute("""
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
            )
        """)

        # 索引
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tags_dimension ON tags(dimension)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tags_domain ON tags(domain)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_tags_synonym ON tags(synonym_of)")

        # 2. 题材领域映射表
        print("创建 genre_domain_map 表...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS genre_domain_map (
                genre_primary VARCHAR(50) PRIMARY KEY,
                domains JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        # 3. 新标签候选表
        print("创建 new_tag_candidates 表...")
        cur.execute("""
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
            )
        """)

        # 索引
        cur.execute("CREATE INDEX IF NOT EXISTS idx_candidates_status ON new_tag_candidates(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_candidates_count ON new_tag_candidates(occurrence_count DESC)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_candidates_dimension ON new_tag_candidates(dimension)")

        # 4. 新题材候选表
        print("创建 new_genre_candidates 表...")
        cur.execute("""
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
            )
        """)

        # 5. 自由标签统计表
        print("创建 free_tags_stats 表...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS free_tags_stats (
                dimension VARCHAR(50),
                tag VARCHAR(100),
                occurrence_count INTEGER DEFAULT 1,
                last_seen TIMESTAMP DEFAULT NOW(),
                UNIQUE(dimension, tag)
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_free_tags_count ON free_tags_stats(occurrence_count DESC)")

        # 6. 初始化 genre_domain_map 数据
        print("初始化 genre_domain_map 数据...")
        cur.execute("""
            INSERT INTO genre_domain_map (genre_primary, domains) VALUES
                ('玄幻', '{"element": ["common", "xuanhuan"], "setting": ["cultivation"]}'::jsonb),
                ('仙侠', '{"element": ["common", "xianxia"], "setting": ["cultivation"]}'::jsonb),
                ('都市', '{"element": ["common", "dushi"], "setting": ["modern"]}'::jsonb),
                ('科幻', '{"element": ["common", "kehuan"], "setting": ["kehuan"]}'::jsonb),
                ('奇幻', '{"element": ["common", "qihuan"], "setting": ["magic"]}'::jsonb),
                ('悬疑灵异', '{"element": ["common", "lingyi"], "setting": ["modern"]}'::jsonb),
                ('武侠', '{"element": ["common", "wuxia"], "setting": ["wuxia"]}'::jsonb),
                ('历史', '{"element": ["common", "history"], "setting": ["modern"]}'::jsonb),
                ('游戏', '{"element": ["common", "game"], "setting": ["modern"]}'::jsonb),
                ('军事', '{"element": ["common"], "setting": ["modern"]}'::jsonb),
                ('体育', '{"element": ["common"], "setting": ["modern"]}'::jsonb),
                ('轻小说', '{"element": ["common", "qihuan"], "setting": ["magic"]}'::jsonb),
                ('诸天无限', '{"element": ["common", "xuanhuan"], "setting": ["cultivation"]}'::jsonb),
                ('言情', '{"element": ["common"], "setting": ["modern"]}'::jsonb),
                ('浪漫青春', '{"element": ["common"], "setting": ["modern"]}'::jsonb),
                ('科幻空间', '{"element": ["common", "kehuan"], "setting": ["kehuan"]}'::jsonb),
                ('悬疑侦探女频', '{"element": ["common", "lingyi"], "setting": ["modern"]}'::jsonb),
                ('现实生活', '{"element": ["common"], "setting": ["modern"]}'::jsonb),
                ('现实', '{"element": ["common"], "setting": ["modern"]}'::jsonb),
                ('短篇', '{"element": ["common"], "setting": ["modern"]}'::jsonb),
                ('混合', '{"element": ["common"], "setting": ["modern"]}'::jsonb),
                ('其他', '{"element": ["common"], "setting": ["modern"]}'::jsonb)
            ON CONFLICT (genre_primary) DO UPDATE SET domains = EXCLUDED.domains, updated_at = NOW()
        """)

    conn.close()
    print("标签表创建完成!")
    print("已创建的表: tags, genre_domain_map, new_tag_candidates, new_genre_candidates, free_tags_stats")
    print("已初始化 22 个一级题材的领域映射")


if __name__ == "__main__":
    create_tag_tables()