"""人物检索：按原型、角色、类型等条件检索人物，支持向量语义搜索。"""
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

from .db import readonly_connection
from .models import SearchRequest, SearchResult
from .text import tokenize_for_search
from novel_material.infra.embedding import get_embedding, load_embedding_config


def search_characters(query=None, archetype=None, role=None, genre=None, name_query=None, limit=10, semantic=False, material_id=None):
    """检索人物，支持向量语义搜索。"""
    with readonly_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 向量语义搜索
        if semantic:
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

            if material_id:
                sql += " AND c.material_id = %s"
                params.append(material_id)

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

            if material_id:
                sql += " AND c.material_id = %s"
                params.append(material_id)

            if archetype:
                sql += " AND c.archetype = %s"
                params.append(archetype)

            if role:
                sql += " AND c.role = %s"
                params.append(role)

            if genre:
                sql += " AND n.genre @> ARRAY[%s]"
                params.append(genre)

            lexical_query = name_query or query or ""
            query_tokens = tokenize_for_search(lexical_query)
            if query_tokens:
                sql += """ AND (
                    c.search_document @@ plainto_tsquery('simple', %s)
                    OR c.name %% %s
                )"""
                params.extend([query_tokens, lexical_query])

            if query_tokens:
                sql += """ ORDER BY
                    ts_rank_cd(c.search_document, plainto_tsquery('simple', %s)) DESC,
                    similarity(c.name, %s) DESC,
                    c.appearance_count DESC LIMIT %s
                """
                params.extend([query_tokens, lexical_query, limit])
            else:
                sql += " ORDER BY c.appearance_count DESC LIMIT %s"
                params.append(limit)

        cur.execute(sql, params)
        rows = cur.fetchall()

    return [
        SearchResult(
            result_id=f"character:{row['material_id']}:{row['name']}",
            document_type="character",
            material_id=row["material_id"],
            title=row.get("name") or "",
            summary=row.get("arc_summary") or "",
            content=row.get("description") or "",
            metadata={
                "novel_name": row.get("novel_name"),
                "genre": row.get("novel_genre") or [],
                "role": row.get("role"),
                "archetype": row.get("archetype"),
                "moral_spectrum": row.get("moral_spectrum"),
                "narrative_function": row.get("narrative_function"),
                "appearance_count": row.get("appearance_count"),
            },
            scores={"semantic": 1 - float(row["distance"])}
            if row.get("distance") is not None
            else {},
            matched_fields=["arc_summary"] if row.get("distance") is not None else [],
        )
        for row in rows
    ]


def retrieve_characters_lexical(request: SearchRequest) -> list[SearchResult]:
    """使用人物中文词法索引召回。"""
    return search_characters(
        query=request.query,
        limit=request.candidate_limit,
        semantic=False,
        **_character_filters(request),
    )


def retrieve_characters_semantic(request: SearchRequest) -> list[SearchResult]:
    """使用完整 4096 维人物弧向量精确召回。"""
    return search_characters(
        query=request.query,
        limit=request.candidate_limit,
        semantic=True,
        **_character_filters(request),
    )


def retrieve_characters_structured(request: SearchRequest) -> list[SearchResult]:
    """仅在存在人物过滤条件时执行结构化召回。"""
    filters = _character_filters(request)
    if not filters:
        return []
    return search_characters(query="", limit=request.candidate_limit, **filters)


def _character_filters(request: SearchRequest) -> dict:
    names = ("archetype", "role", "genre", "material_id")
    return {name: request.filters[name] for name in names if name in request.filters}
