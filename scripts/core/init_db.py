#!/usr/bin/env python
"""初始化 PostgreSQL 数据库，创建所有表和索引。"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("错误: 请设置 DATABASE_URL 环境变量或配置 .env 文件")
    exit(1)

SCHEMA_FILE = os.path.join(os.path.dirname(__file__), "schema.sql")

def init_db():
    print("正在连接数据库...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True

    with conn.cursor() as cur:
        # 执行 schema.sql（包含 CREATE EXTENSION IF NOT EXISTS vector）
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        cur.execute(schema_sql)
        print("已启用 pgvector 扩展，创建所有表和索引")

    conn.close()
    print("数据库初始化完成!")

if __name__ == "__main__":
    init_db()
