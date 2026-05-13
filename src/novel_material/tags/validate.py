"""标签校验工具：校验标签是否在字典中，处理同义词。

供 generate_tags.py 调用。
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    """获取数据库连接。"""
    return psycopg2.connect(DATABASE_URL)


def validate_tag(dimension, tag):
    """校验单个标签是否合法，返回标准名称。

    Args:
        dimension: 维度（element/setting/style/structure）
        tag: 标签值

    Returns:
        str: 标准名称（如果是同义词则返回标准标签），None 表示不合法

    示例:
        canonical = validate_tag("element", "血脉觉醒")
        # 返回 "血脉"（同义词映射）

        canonical = validate_tag("element", "不存在的标签")
        # 返回 None
    """
    conn = get_connection()
    conn.autocommit = True

    with conn.cursor() as cur:
        # 直接查询：如果是同义词则返回 synonym_of，否则返回 tag
        cur.execute("""
            SELECT COALESCE(synonym_of, tag) as canonical
            FROM tags
            WHERE dimension = %s AND tag = %s
        """, [dimension, tag])
        result = cur.fetchone()

    conn.close()
    return result[0] if result else None


def validate_tags_batch(dimension, tags_list):
    """批量校验标签。

    Args:
        dimension: 维度
        tags_list: 标签列表

    Returns:
        tuple: (valid_tags, invalid_tags)

    示例:
        valid, invalid = validate_tags_batch("element", ["血脉", "不存在的", "血脉觉醒"])
        # valid = ["血脉", "血脉"]
        # invalid = ["不存在的"]
    """
    valid = []
    invalid = []

    for tag in tags_list:
        canonical = validate_tag(dimension, tag)
        if canonical:
            valid.append(canonical)
        else:
            invalid.append(tag)

    return valid, invalid


def check_dimension_usage(dimension):
    """检查某个维度在已有数据文件中的标签使用情况。

    Args:
        dimension: 维度名称
    """
    conn = get_connection()
    conn.autocommit = True

    # 查询所有小说中该维度使用的标签
    with conn.cursor() as cur:
        if dimension == "element":
            cur.execute("""
                SELECT DISTINCT jsonb_array_elements_text(n.tags->'elements') as tag
                FROM novels n WHERE n.tags->'elements' IS NOT NULL
            """)
        elif dimension == "style":
            cur.execute("""
                SELECT DISTINCT jsonb_array_elements_text(n.tags->'style') as tag
                FROM novels n WHERE n.tags->'style' IS NOT NULL
            """)
        elif dimension in ["setting", "structure"]:
            cur.execute(f"""
                SELECT DISTINCT n.tags->'{dimension}' as tag
                FROM novels n WHERE n.tags->'{dimension}' IS NOT NULL
            """)
        else:
            print(f"不支持的维度: {dimension}")
            conn.close()
            return

        used_tags = [row[0] for row in cur.fetchall() if row[0]]

    # 校验每个标签
    invalid = []
    for tag in used_tags:
        canonical = validate_tag(dimension, tag)
        if not canonical:
            invalid.append(tag)

    conn.close()

    if invalid:
        print(f"维度 {dimension}: 发现 {len(invalid)} 个字典外标签:")
        for t in sorted(invalid):
            print(f"  {t}")
    else:
        print(f"维度 {dimension}: 所有标签均合法 (已用 {len(used_tags)} 个)")


def check_dimension(dimension: str) -> None:
    """检查某个维度在已有数据文件中的标签使用情况。

    Args:
        dimension: 维度名称
    """
    check_dimension_usage(dimension)


def suggest_expand(dimension: str, new_tag: str) -> None:
    """提示用户是否扩展标签字典。

    Args:
        dimension: 维度名称
        new_tag: 待检查的标签
    """
    canonical = validate_tag(dimension, new_tag)

    if not canonical:
        print(f"\n标签 '{new_tag}' 不在维度 {dimension} 的字典中")
        print(f"如需添加，请使用:")
        print(f"  nm tags add {dimension} '{new_tag}' common")
        print(f"或运行审核流程:")
        print(f"  nm tags review list")


if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2:
        check_dimension(sys.argv[1])
    else:
        for dim in ["element", "style", "setting", "structure"]:
            check_dimension(dim)