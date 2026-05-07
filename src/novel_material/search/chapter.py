"""章纲检索：按章节功能、关键词、张力等条件检索章节，支持向量语义搜索。"""
import os
import json
import psycopg2
import psycopg2.extras
import click
from dotenv import load_dotenv

load_dotenv()

from .common import build_like_terms, require_database_url
from novel_material.infra.embedding import get_embedding, load_embedding_config
from novel_material.tags.resolve import resolve_tag_domain, suggest_genre_for_tag

DATABASE_URL = os.getenv("DATABASE_URL")


def search_chapters(query, genre=None, chapter_function=None, chapter_num=None, tension_min=None, tension_max=None, element=None, style=None, limit=10, semantic=False):
    """检索章节，支持向量语义搜索。"""
    conn = psycopg2.connect(require_database_url(DATABASE_URL))
    conn.autocommit = True

    results = []

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # 向量语义搜索（优先）
        if semantic:
            print(f"正在生成查询向量...")
            config = load_embedding_config()
            query_embedding = get_embedding(query, config)

            # 使用 pgvector 余弦距离搜索
            sql = """
                SELECT c.material_id, c.chapter, c.title, c.summary,
                       c.tension_level, c.pacing, c.chapter_functions,
                       c.characters_appear, c.key_plot_point,
                       n.name as novel_name, n.genre, n.tags,
                       c.summary_embedding <=> %s::vector as distance
                FROM chapters c
                JOIN novels n ON c.material_id = n.material_id
                WHERE c.summary_embedding IS NOT NULL
            """
            # 将 Python 列表转为 PostgreSQL vector 格式
            params = [str(query_embedding)]

            # 其他过滤条件
            if genre:
                sql += " AND n.genre @> ARRAY[%s]"
                params.append(genre)

            if chapter_function:
                sql += " AND c.chapter_functions @> ARRAY[%s]"
                params.append(chapter_function)

            if tension_min is not None:
                sql += " AND c.tension_level >= %s"
                params.append(tension_min)

            if tension_max is not None:
                sql += " AND c.tension_level <= %s"
                params.append(tension_max)

            sql += " ORDER BY distance ASC LIMIT %s"
            params.append(limit)

        else:
            # 关键词模糊搜索（默认）
            sql = """
                SELECT c.material_id, c.chapter, c.title, c.summary,
                       c.tension_level, c.pacing, c.chapter_functions,
                       c.characters_appear, c.key_plot_point,
                       n.name as novel_name, n.genre, n.tags
                FROM chapters c
                JOIN novels n ON c.material_id = n.material_id
                WHERE 1=1
            """
            params = []

            terms = build_like_terms(query)
            if terms:
                clauses = []
                for term in terms:
                    fuzzy = f"%{term}%"
                    clauses.append(
                        """(
                            c.title ILIKE %s
                            OR c.summary ILIKE %s
                            OR COALESCE(c.key_plot_point, '') ILIKE %s
                            OR array_to_string(c.chapter_functions, ' ') ILIKE %s
                        )"""
                    )
                    params.extend([fuzzy, fuzzy, fuzzy, fuzzy])
                sql += " AND (" + " OR ".join(clauses) + ")"

            if genre:
                sql += " AND n.genre @> ARRAY[%s]"
                params.append(genre)

            if chapter_function:
                sql += " AND c.chapter_functions @> ARRAY[%s]"
                params.append(chapter_function)

            if chapter_num is not None:
                sql += " AND c.chapter = %s"
                params.append(chapter_num)

            if tension_min is not None:
                sql += " AND c.tension_level >= %s"
                params.append(tension_min)

            if tension_max is not None:
                sql += " AND c.tension_level <= %s"
                params.append(tension_max)

            if element:
                # 标签领域定位（提示用户）
                try:
                    domain, is_common = resolve_tag_domain("element", element)
                    if not is_common:
                        suggested = suggest_genre_for_tag("element", element)
                        if suggested and not genre:
                            print(f"提示: '{element}' 是 {suggested} 题材专属标签")
                            print(f"建议加 --genre 参数获得更精准结果")
                except ValueError:
                    print(f"警告: '{element}' 不在标签字典中")

                sql += " AND n.tags->'elements' @> %s::jsonb"
                params.append(json.dumps([element]))

            if style:
                # 标签领域定位（提示用户）
                try:
                    domain, is_common = resolve_tag_domain("style", style)
                    # style 通常都是 common，所以不需要特别提示
                except ValueError:
                    print(f"警告: '{style}' 不在标签字典中")

                sql += " AND n.tags->'style' @> %s::jsonb"
                params.append(json.dumps([style]))

            sql += " ORDER BY c.tension_level DESC NULLS LAST, c.chapter ASC LIMIT %s"
            params.append(limit)

        cur.execute(sql, params)
        results = cur.fetchall()

    conn.close()

    # 打印结果
    if not results:
        print("未找到匹配的章节")
        return

    print(f"找到 {len(results)} 个匹配结果:\n")

    for r in results:
        print(f"--- {r['novel_name']} 第{r['chapter']}章 ---")
        print(f"标题: {r['title']}")
        print(f"摘要: {r['summary']}")
        if semantic and 'distance' in r:
            # 余弦距离转换为相似度：similarity = 1 - distance
            similarity = 1 - r['distance']
            print(f"相似度: {similarity:.2%}")
        print(f"张力: {r['tension_level']}/5 | 节奏: {r['pacing']}")
        print(f"功能: {r['chapter_functions']}")
        print(f"人物: {r['characters_appear']}")
        print()


@click.command()
@click.argument("query")
@click.option("--genre", default=None, help="按题材过滤（如：修仙、都市）")
@click.option("--function", "chapter_function", default=None, help="章节功能标签（如：开局困境）")
@click.option("--chapter", "chapter_num", default=None, type=int, help="精确章节号")
@click.option("--tension-min", default=None, type=int, help="张力最小值（1-5）")
@click.option("--tension-max", default=None, type=int, help="张力最大值（1-5）")
@click.option("--element", default=None, help="元素标签过滤（如：重生、系统）")
@click.option("--style", default=None, help="风格标签过滤（如：热血、治愈）")
@click.option("--limit", default=10, help="返回结果数")
@click.option("--semantic", is_flag=True, help="启用向量语义搜索（更精准的语义匹配）")
def main(query, genre, chapter_function, chapter_num, tension_min, tension_max, element, style, limit, semantic):
    search_chapters(query=query, genre=genre, chapter_function=chapter_function, chapter_num=chapter_num, tension_min=tension_min, tension_max=tension_max, element=element, style=style, limit=limit, semantic=semantic)


if __name__ == "__main__":
    main()