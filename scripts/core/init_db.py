#!/usr/bin/env python
"""数据库初始化：创建所有表结构并初始化基础数据。

运行此脚本会：
1. 创建核心表：novels（小说）、chapters（章节）、outline（大纲）、characters（人物）、worldbuilding（世界观）
2. 创建标签表：tags、genre_domain_map、new_tag_candidates、new_genre_candidates、free_tags_stats
3. 初始化基础数据：genre_domain_map 的 22 个题材映射

使用方法：
    python scripts/core/init_db.py

注意：运行前需要：
1. 安装 PostgreSQL
2. 设置 DATABASE_URL 环境变量（或配置 .env）
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
    """初始化数据库，创建所有表和索引。

    步骤：
    1. 连接数据库
    2. 执行 schema.sql（创建所有表，含标签表）
    3. 初始化基础数据（genre_domain_map）
    """
    print("正在连接数据库...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True

    # 创建所有表（核心表 + 标签表）
    with conn.cursor() as cur:
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        cur.execute(schema_sql)
        print("已创建所有表：novels, chapters, outline, characters, worldbuilding, tags, genre_domain_map, ...")

    conn.close()

    # 初始化基础数据
    from scripts.core.init_data import init_data
    init_data()

    print("\n数据库初始化完成!")


if __name__ == "__main__":
    init_db()