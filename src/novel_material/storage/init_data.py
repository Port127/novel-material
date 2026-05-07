"""初始化数据库基础数据。"""
import psycopg2
import os
import sys
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("错误: 请设置 DATABASE_URL 环境变量")
    raise RuntimeError("DATABASE_URL 未配置")


def check_table_exists(conn, table_name):
    """检查表是否存在。"""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = %s
            )
        """, [table_name])
        return cur.fetchone()[0]


def init_genre_domain_map():
    """初始化 genre_domain_map 表数据。"""
    print("正在初始化 genre_domain_map...")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True

    if not check_table_exists(conn, "genre_domain_map"):
        print("错误: genre_domain_map 表不存在")
        print("请先运行 init_db.py 创建表结构")
        conn.close()
        sys.exit(1)

    with conn.cursor() as cur:
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
    print("已初始化 22 个一级题材的领域映射")


def init_data():
    """初始化所有基础数据。"""
    print("\n正在初始化数据库基础数据...")
    init_genre_domain_map()

    # 导入标签字典
    from .init_tags import init_tags
    init_tags()

    print("\n数据初始化完成!")


if __name__ == "__main__":
    init_data()