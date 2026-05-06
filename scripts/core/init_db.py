#!/usr/bin/env python
"""初始化 PostgreSQL 数据库，创建所有表和索引。

包含：
1. novels/chapters/outline/characters/worldbuilding 表（schema.sql）
2. 标签分级系统表（create_tag_tables.py）
"""
import psycopg2
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("错误: 请设置 DATABASE_URL 环境变量或配置 .env 文件")
    exit(1)

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql")


def init_db():
    print("正在连接数据库...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True

    # 1. 创建核心表（novels/chapters/outline/characters/worldbuilding）
    with conn.cursor() as cur:
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        cur.execute(schema_sql)
        print("已创建核心表：novels, chapters, outline_sequences, outline_beats, characters, character_appearances, worldbuilding_entities")

    conn.close()

    # 2. 创建标签分级系统表
    print("\n创建标签分级系统表...")
    from scripts.migration.create_tag_tables import create_tag_tables
    create_tag_tables()

    print("\n数据库初始化完成!")


if __name__ == "__main__":
    init_db()
