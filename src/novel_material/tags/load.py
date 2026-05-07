"""标签加载工具：根据题材动态加载相关标签。

用于 LLM 分析时精简 prompt，只加载与题材相关的标签。
"""
import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    """获取数据库连接。"""
    return psycopg2.connect(DATABASE_URL)


def load_tags_for_genre(genre_primary, genre_secondary=None):
    """根据题材加载相关标签（用于 LLM 分析）。

    Args:
        genre_primary: 一级题材（如：玄幻、仙侠）
        genre_secondary: 二级题材（可选，如：东方玄幻）

    Returns:
        dict: 按 dimension → domain → group 组织的标签数据

    示例:
        tags = load_tags_for_genre("玄幻")
        # 返回 common + xuanhuan 相关标签

        tags = load_tags_for_genre("玄幻", "都市异能")
        # 返回 common + xuanhuan + dushi 相关标签
    """
    conn = get_connection()

    # 1. 获取领域配置
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT domains FROM genre_domain_map WHERE genre_primary = %s
        """, [genre_primary])
        result = cur.fetchone()

    if not result:
        # 题材不在映射表中，使用 common
        domains = {"element": ["common"], "setting": ["common"]}
    else:
        domains = result["domains"]

    # 2. 合并次题材领域（如果有）
    if genre_secondary:
        # 二级题材可能属于不同一级题材
        inferred_primary = infer_primary_from_secondary(genre_secondary)
        if inferred_primary != genre_primary:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT domains FROM genre_domain_map WHERE genre_primary = %s
                """, [inferred_primary])
                sec_result = cur.fetchone()

                if sec_result:
                    # 合并领域
                    for dim, dom_list in sec_result["domains"].items():
                        if dim in domains:
                            domains[dim] = list(set(domains[dim] + dom_list))
                        else:
                            domains[dim] = dom_list

    # 3. 查询标签
    element_domains = domains.get("element", ["common"])
    setting_domains = domains.get("setting", ["common"])

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute("""
            SELECT dimension, tag, domain, group_name, is_common
            FROM tags
            WHERE (dimension = 'element' AND domain IN %s)
               OR (dimension = 'setting' AND domain IN %s)
               OR dimension IN ('style', 'structure', 'chapter_function')
               OR synonym_of IS NOT NULL
            ORDER BY dimension, domain, group_name, tag
        """, [tuple(element_domains), tuple(setting_domains)])

        tags = cur.fetchall()

    conn.close()

    # 4. 组织成嵌套结构
    return format_tags_for_prompt(tags)


def format_tags_for_prompt(tags):
    """将标签数据格式化为 prompt 格式。"""
    result = {}

    for row in tags:
        dim = row["dimension"]
        domain = row["domain"]
        group = row["group_name"] or "默认"
        tag = row["tag"]

        # 同义词不单独显示
        if row.get("synonym_of"):
            continue

        if dim not in result:
            result[dim] = {}
        if domain not in result[dim]:
            result[dim][domain] = {}
        if group not in result[dim][domain]:
            result[dim][domain][group] = []

        result[dim][domain][group].append(tag)

    return result


def infer_primary_from_secondary(genre_secondary):
    """从二级题材推断一级题材。"""
    MAPPING = {
        "东方玄幻": "玄幻",
        "异世大陆": "玄幻",
        "王朝争霸": "玄幻",
        "高武世界": "玄幻",
        "修真文明": "仙侠",
        "幻想修仙": "仙侠",
        "现代修真": "仙侠",
        "古典仙侠": "仙侠",
        "都市生活": "都市",
        "都市异能": "都市",
        "都市修仙": "都市",
        "都市神医": "都市",
        "星际文明": "科幻",
        "时空穿梭": "科幻",
        "末世危机": "科幻",
        "进化变异": "科幻",
        "超级科技": "科幻",
        "悬疑侦探": "悬疑灵异",
        "探险生存": "悬疑灵异",
        "灵异神怪": "悬疑灵异",
        "诡秘悬疑": "悬疑灵异",
        "传统武侠": "武侠",
        "武侠幻想": "武侠",
        "国术无双": "武侠",
        "架空历史": "历史",
        "历史穿越": "历史",
        "秦汉三国": "历史",
        "游戏异界": "游戏",
        "电子竞技": "游戏",
        "虚拟网游": "游戏",
    }
    return MAPPING.get(genre_secondary, genre_secondary)


def get_all_genres():
    """获取所有一级题材列表。"""
    conn = get_connection()

    with conn.cursor() as cur:
        cur.execute("SELECT genre_primary FROM genre_domain_map ORDER BY genre_primary")
        genres = [row[0] for row in cur.fetchall()]

    conn.close()
    return genres


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python load.py <genre_primary> [genre_secondary]")
        print("示例: python load.py 玄幻")
        sys.exit(1)

    genre_primary = sys.argv[1]
    genre_secondary = sys.argv[2] if len(sys.argv) > 2 else None

    tags = load_tags_for_genre(genre_primary, genre_secondary)

    # 统计各维度标签数
    total = 0
    for dim, domains in tags.items():
        dim_count = 0
        for dom, groups in domains.items():
            for group, tag_list in groups.items():
                dim_count += len(tag_list)
        print(f"{dim}: {dim_count} 个")
        total += dim_count

    print(f"\n总计: {total} 个标签（精简后）")
    print(f"原始: 600+ 个标签")