"""标签领域定位：供检索脚本使用。

根据标签定位所属领域，提供题材建议。
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    """获取数据库连接。"""
    return psycopg2.connect(DATABASE_URL)


def resolve_tag_domain(dimension, tag):
    """定位标签所属领域。

    Args:
        dimension: 维度
        tag: 标签值

    Returns:
        tuple: (domain, is_common)

    Raises:
        ValueError: 标签不在字典中

    示例:
        domain, is_common = resolve_tag_domain("element", "血脉")
        # 返回 ("xuanhuan", False)

        domain, is_common = resolve_tag_domain("element", "复仇")
        # 返回 ("common", True)
    """
    conn = get_connection()
    conn.autocommit = True

    with conn.cursor() as cur:
        # 先校验同义词
        cur.execute("""
            SELECT synonym_of FROM tags
            WHERE dimension = %s AND tag = %s AND synonym_of IS NOT NULL
        """, [dimension, tag])
        syn_result = cur.fetchone()

        canonical = tag
        if syn_result:
            canonical = syn_result[0]

        # 查找标准标签
        cur.execute("""
            SELECT domain, is_common FROM tags
            WHERE dimension = %s AND tag = %s AND synonym_of IS NULL
        """, [dimension, canonical])
        result = cur.fetchone()

    conn.close()

    if not result:
        raise ValueError(f"标签 '{tag}' 不在字典中")

    return result[0], result[1]


def suggest_genre_for_tag(dimension, tag):
    """根据标签建议题材。

    Args:
        dimension: 维度
        tag: 标签值

    Returns:
        list: 建议的一级题材列表，None 表示通用标签无需建议

    示例:
        genres = suggest_genre_for_tag("element", "血脉")
        # 返回 ["玄幻", "仙侠"]

        genres = suggest_genre_for_tag("element", "复仇")
        # 返回 None
    """
    try:
        domain, is_common = resolve_tag_domain(dimension, tag)
    except ValueError:
        return None

    if is_common:
        return None  # 通用标签，无需建议

    conn = get_connection()
    conn.autocommit = True

    with conn.cursor() as cur:
        cur.execute("""
            SELECT genre_primary FROM genre_domain_map
            WHERE domains->%s ? %s
        """, [dimension, domain])
        genres = [row[0] for row in cur.fetchall()]

    conn.close()

    return genres


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("用法: python resolve.py <dimension> <tag>")
        print("示例: python resolve.py element 血脉")
        sys.exit(1)

    dimension = sys.argv[1]
    tag = sys.argv[2]

    try:
        domain, is_common = resolve_tag_domain(dimension, tag)
        print(f"标签: {tag}")
        print(f"领域: {domain}")
        print(f"通用: {is_common}")

        if not is_common:
            genres = suggest_genre_for_tag(dimension, tag)
            if genres:
                print(f"建议题材: {', '.join(genres)}")

    except ValueError as e:
        print(f"错误: {e}")