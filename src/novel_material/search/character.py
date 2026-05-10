"""人物检索：按原型、角色、类型等条件检索人物，支持向量语义搜索。"""
import os
import psycopg2
import psycopg2.extras
import click
from dotenv import load_dotenv

load_dotenv()

from .common import build_like_terms, require_database_url
from novel_material.infra.embedding import get_embedding, load_embedding_config
from novel_material.infra.logging_config import get_search_logger

DATABASE_URL = os.getenv("DATABASE_URL")
logger = get_search_logger()


def search_characters(query=None, archetype=None, role=None, genre=None, name_query=None, limit=10, semantic=False):
    """检索人物，支持向量语义搜索。"""
    conn = psycopg2.connect(require_database_url(DATABASE_URL))
    conn.autocommit = True

    results = []

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # 向量语义搜索
        if semantic:
            print("正在生成查询向量...")
            config = load_embedding_config()
            query_embedding = get_embedding(query, config)

            sql = """
                SELECT c.material_id, c.name, c.role, c.archetype,
                       c.moral_spectrum, c.arc_summary, c.narrative_function,
                       c.appearance_count, c.description,
                       n.name as novel_name, n.genre as novel_genre,
                       c.arc_summary_embedding <=> %s::vector as distance
                FROM characters c
                JOIN novels n ON c.material_id = n.material_id
                WHERE c.arc_summary_embedding IS NOT NULL
            """
            params = [str(query_embedding)]

            if archetype:
                sql += " AND c.archetype = %s"
                params.append(archetype)

            if role:
                sql += " AND c.role = %s"
                params.append(role)

            if genre:
                sql += " AND n.genre @> ARRAY[%s]"
                params.append(genre)

            sql += " ORDER BY distance ASC LIMIT %s"
            params.append(limit)

        else:
            # 关键词模糊搜索（默认）
            sql = """
                SELECT c.material_id, c.name, c.role, c.archetype,
                       c.moral_spectrum, c.arc_summary, c.narrative_function,
                       c.appearance_count, c.description,
                       n.name as novel_name, n.genre as novel_genre
                FROM characters c
                JOIN novels n ON c.material_id = n.material_id
                WHERE 1=1
            """
            params = []

            if archetype:
                sql += " AND c.archetype = %s"
                params.append(archetype)

            if role:
                sql += " AND c.role = %s"
                params.append(role)

            if genre:
                sql += " AND n.genre @> ARRAY[%s]"
                params.append(genre)

            terms = build_like_terms(name_query or query)
            if terms:
                clauses = []
                for term in terms:
                    fuzzy = f"%{term}%"
                    clauses.append(
                        """(
                            c.name ILIKE %s
                            OR COALESCE(c.archetype, '') ILIKE %s
                            OR COALESCE(c.arc_summary, '') ILIKE %s
                            OR COALESCE(c.narrative_function, '') ILIKE %s
                        )"""
                    )
                    params.extend([fuzzy, fuzzy, fuzzy, fuzzy])
                sql += " AND (" + " OR ".join(clauses) + ")"

            sql += " ORDER BY c.appearance_count DESC LIMIT %s"
            params.append(limit)

        cur.execute(sql, params)
        results = cur.fetchall()

    conn.close()

    if not results:
        print("未找到匹配的人物")
        return

    print(f"找到 {len(results)} 个人物:\n")

    for r in results:
        print(f"--- {r['name']} ({r['novel_name']}) ---")
        print(f"角色: {r['role']} | 原型: {r['archetype']}")
        print(f"道德立场: {r['moral_spectrum']}")
        print(f"弧线: {r['arc_summary']}")
        print(f"功能: {r['narrative_function']}")
        print(f"出场次数: {r['appearance_count']}")
        if semantic and 'distance' in r:
            similarity = 1 - r['distance']
            print(f"相似度: {similarity:.2%}")
        print()


@click.command()
@click.argument("query", required=False)
@click.option("--archetype", default=None, help="人物原型（如：英雄、导师）")
@click.option("--role", default=None, help="角色类型（protagonist/antagonist/supporting）")
@click.option("--genre", default=None, help="按题材过滤")
@click.option("--name", "name_query", default=None, help="人物名字关键词")
@click.option("--limit", default=10, help="返回结果数")
@click.option("--semantic", is_flag=True, help="启用向量语义搜索（更精准的语义匹配）")
def main(query, archetype, role, genre, name_query, limit, semantic):
    search_characters(query=query, archetype=archetype, role=role, genre=genre, name_query=name_query, limit=limit, semantic=semantic)


if __name__ == "__main__":
    main()