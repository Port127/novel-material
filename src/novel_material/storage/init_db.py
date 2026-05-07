"""数据库初始化：创建所有表结构。"""
import psycopg2
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("错误: 请设置 DATABASE_URL 环境变量")
    raise RuntimeError("DATABASE_URL 未配置")

SCHEMA_FILE = Path(__file__).parent / "schema.sql"


def init_db():
    """初始化数据库，创建所有表和索引。"""
    print("正在连接数据库...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True

    with conn.cursor() as cur:
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            schema_sql = f.read()

        cur.execute(schema_sql)
        print("已创建所有表：novels, chapters, outline, characters, worldbuilding, tags, ...")

    conn.close()

    # 初始化基础数据
    from .init_data import init_data
    init_data()

    print("\n数据库初始化完成!")


if __name__ == "__main__":
    init_db()