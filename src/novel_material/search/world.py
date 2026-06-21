"""世界观检索：按类型、势力、地理、力量体系等条件检索，支持向量语义搜索。"""
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

from .common import build_like_terms
from .db import readonly_connection
from .models import SearchResult
from novel_material.infra.embedding import get_embedding, load_embedding_config

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
    with readonly_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 向量语义搜索
        if semantic:
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
        rows = cur.fetchall()

    return [
        SearchResult(
            result_id=(
                f"world:{row['material_id']}:{row['entity_type']}:{row['name']}"
            ),
            document_type="world",
            material_id=row["material_id"],
            title=row.get("name") or "",
            summary=row.get("description") or "",
            metadata={
                "novel_name": row.get("novel_name"),
                "genre": row.get("novel_genre") or [],
                "entity_type": row.get("entity_type"),
                "properties": row.get("properties") or {},
                "importance": row.get("importance"),
                "first_appearance": row.get("first_appearance"),
            },
            scores={"semantic": 1 - float(row["distance"])}
            if row.get("distance") is not None
            else {},
            matched_fields=["description"] if row.get("distance") is not None else [],
        )
        for row in rows
    ]
