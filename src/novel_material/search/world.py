"""世界观检索：按类型、势力、地理、力量体系等条件检索，支持向量语义搜索。"""
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

from .db import readonly_connection
from .models import SearchRequest, SearchResult
from .text import tokenize_for_search
from novel_material.infra.embedding import get_embedding, load_embedding_config

_ENTITY_TYPE_ALIASES = {
    "organization": "organization",
    "faction": "factions",
    "factions": "factions",
    "location": "location",
    "region": "regions",
    "regions": "regions",
    "power_system": "power_systems",
    "power-system": "power_systems",
    "power_systems": "power_systems",
}


_ENTITY_TYPE_COMPATIBILITY = {
    "organization": ("organization", "factions"),
    "factions": ("organization", "factions"),
    "location": ("location", "region", "regions"),
    "regions": ("location", "region", "regions"),
    "power_systems": ("power_system", "power_systems"),
}


def _normalize_entity_type(entity_type: str | None) -> str | None:
    if not entity_type:
        return entity_type
    return _ENTITY_TYPE_ALIASES.get(entity_type, entity_type)


def _entity_type_candidates(entity_type: str | None) -> list[str]:
    normalized = _normalize_entity_type(entity_type)
    if not normalized:
        return []
    return list(_ENTITY_TYPE_COMPATIBILITY.get(normalized, (normalized,)))


def search_worldbuilding(query=None, entity_type=None, genre=None, importance=None, name_query=None, limit=10, semantic=False, material_id=None):
    """检索世界观设定，支持向量语义搜索。"""
    entity_types = _entity_type_candidates(entity_type)
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

            if material_id:
                sql += " AND w.material_id = %s"
                params.append(material_id)

            if entity_types:
                sql += " AND w.entity_type = ANY(%s)"
                params.append(entity_types)

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

            if material_id:
                sql += " AND w.material_id = %s"
                params.append(material_id)

            if entity_types:
                sql += " AND w.entity_type = ANY(%s)"
                params.append(entity_types)

            if genre:
                sql += " AND n.genre @> ARRAY[%s]"
                params.append(genre)

            if importance:
                sql += " AND w.importance = %s"
                params.append(importance)

            lexical_query = name_query or query or ""
            query_tokens = tokenize_for_search(lexical_query)
            if query_tokens:
                sql += """ AND (
                    w.search_document @@ plainto_tsquery('simple', %s)
                    OR w.name %% %s
                )"""
                params.extend([query_tokens, lexical_query])

            if query_tokens:
                sql += """ ORDER BY
                    ts_rank_cd(w.search_document, plainto_tsquery('simple', %s)) DESC,
                    similarity(w.name, %s) DESC,
                    w.importance ASC NULLS LAST,
                    w.name ASC LIMIT %s
                """
                params.extend([query_tokens, lexical_query, limit])
            else:
                sql += " ORDER BY w.importance ASC NULLS LAST, w.name ASC LIMIT %s"
                params.append(limit)

        cur.execute(sql, params)
        rows = cur.fetchall()

    return [_world_result(row) for row in rows]


def _world_result(row) -> SearchResult:
    properties = row.get("properties") or {}
    entity_id = properties.get("entity_id")
    return SearchResult(
        result_id=(
            f"world:{row['material_id']}:{row['entity_type']}:{row['name']}"
        ),
        document_type="world",
        material_id=row["material_id"],
        entity_id=entity_id,
        title=row.get("name") or "",
        summary=row.get("description") or "",
        metadata={
            "novel_name": row.get("novel_name"),
            "genre": row.get("novel_genre") or [],
            "entity_type": row.get("entity_type"),
            "properties": properties,
            "importance": row.get("importance"),
            "first_appearance": row.get("first_appearance"),
            "dimension_ids": properties.get("dimension_ids") or [],
            "evidence": properties.get("evidence") or [],
            "key_appearances": properties.get("key_appearances") or [],
            "relation_summaries": properties.get("relation_summaries") or [],
        },
        scores={"semantic": 1 - float(row["distance"])}
        if row.get("distance") is not None
        else {},
        matched_fields=["description"] if row.get("distance") is not None else [],
    )


def retrieve_worldbuilding_lexical(request: SearchRequest) -> list[SearchResult]:
    """使用世界观中文词法索引召回。"""
    return search_worldbuilding(
        query=request.query,
        limit=request.candidate_limit,
        semantic=False,
        **_world_filters(request),
    )


def retrieve_worldbuilding_semantic(request: SearchRequest) -> list[SearchResult]:
    """使用完整 4096 维设定描述向量精确召回。"""
    return search_worldbuilding(
        query=request.query,
        limit=request.candidate_limit,
        semantic=True,
        **_world_filters(request),
    )


def retrieve_worldbuilding_structured(request: SearchRequest) -> list[SearchResult]:
    """仅在存在世界观过滤条件时执行结构化召回。"""
    filters = _world_filters(request)
    if not filters:
        return []
    return search_worldbuilding(query="", limit=request.candidate_limit, **filters)


def _world_filters(request: SearchRequest) -> dict:
    aliases = {"dimension": "entity_type"}
    names = ("entity_type", "dimension", "genre", "importance", "material_id")
    return {
        aliases.get(name, name): request.filters[name]
        for name in names
        if name in request.filters
    }
