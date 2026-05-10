"""世界观检索：按类型、势力、地理、力量体系等条件检索，支持向量语义搜索。"""
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

_ENTITY_TYPE_ALIASES = {
    "faction": "factions",
    "factions": "factions",
    "region": "regions",
    "regions": "regions",
    "power_system": "power_systems",
    "power-system": "power_systems",
    "power_systems": "power_systems",
}


def _normalize_entity_type(entity_type):
    if not entity_type:
        return entity_type
    return _ENTITY_TYPE_ALIASES.get(entity_type, entity_type)


def search_worldbuilding(query=None, entity_type=None, genre=None, importance=None, name_query=None, limit=10, semantic=False):
    """检索世界观设定，支持向量语义搜索。"""
    entity_type = _normalize_entity_type(entity_type)
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
                SELECT w.material_id, w.entity_type, w.name, w.description,
                       w.properties, w.importance, w.first_appearance,
                       n.name as novel_name, n.genre as novel_genre,
                       w.description_embedding <=> %s::vector as distance
                FROM worldbuilding_entities w
                JOIN novels n ON w.material_id = n.material_id
                WHERE w.description_embedding IS NOT NULL
            """
            params = [str(query_embedding)]

            if entity_type:
                sql += " AND w.entity_type = %s"
                params.append(entity_type)

            if genre:
                sql += " AND n.genre @> ARRAY[%s]"
                params.append(genre)

            if importance:
                sql += " AND w.importance = %s"
                params.append(importance)

            sql += " ORDER BY distance ASC LIMIT %s"
            params.append(limit)

        else:
            # 关键词模糊搜索（默认）
            sql = """
                SELECT w.material_id, w.entity_type, w.name, w.description,
                       w.properties, w.importance, w.first_appearance,
                       n.name as novel_name, n.genre as novel_genre
                FROM worldbuilding_entities w
                JOIN novels n ON w.material_id = n.material_id
                WHERE 1=1
            """
            params = []

            if entity_type:
                sql += " AND w.entity_type = %s"
                params.append(entity_type)

            if genre:
                sql += " AND n.genre @> ARRAY[%s]"
                params.append(genre)

            if importance:
                sql += " AND w.importance = %s"
                params.append(importance)

            terms = build_like_terms(name_query or query)
            if terms:
                clauses = []
                for term in terms:
                    fuzzy = f"%{term}%"
                    clauses.append(
                        """(
                            w.name ILIKE %s
                            OR COALESCE(w.description, '') ILIKE %s
                            OR COALESCE(w.properties::text, '') ILIKE %s
                        )"""
                    )
                    params.extend([fuzzy, fuzzy, fuzzy])
                sql += " AND (" + " OR ".join(clauses) + ")"

            sql += " ORDER BY w.importance ASC NULLS LAST, w.name ASC LIMIT %s"
            params.append(limit)

        cur.execute(sql, params)
        results = cur.fetchall()

    conn.close()

    if not results:
        print("未找到匹配的世界观设定")
        return

    print(f"找到 {len(results)} 个世界观设定:\n")

    for r in results:
        print(f"--- {r['name']} ({r['novel_name']}) ---")
        print(f"类型: {r['entity_type']} | 重要性: {r['importance']}")
        print(f"描述: {r['description']}")
        if semantic and 'distance' in r:
            similarity = 1 - r['distance']
            print(f"相似度: {similarity:.2%}")
        print()


@click.command()
@click.argument("query", required=False)
@click.option("--type", "entity_type", default=None, help="实体类型（factions/regions/power_systems）")
@click.option("--genre", default=None, help="按题材过滤")
@click.option("--importance", default=None, help="重要性（primary/secondary/minor）")
@click.option("--name", "name_query", default=None, help="名称关键词")
@click.option("--limit", default=10, help="返回结果数")
@click.option("--semantic", is_flag=True, help="启用向量语义搜索（更精准的语义匹配）")
def main(query, entity_type, genre, importance, name_query, limit, semantic):
    search_worldbuilding(query=query, entity_type=entity_type, genre=genre, importance=importance, name_query=name_query, limit=limit, semantic=semantic)


if __name__ == "__main__":
    main()