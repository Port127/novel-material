"""事件检索：按语义描述检索章节（"雨中告别"、"主角初次突破"等），默认使用向量搜索。"""
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

from .db import readonly_connection
from .models import SearchRequest, SearchResult
from .text import tokenize_for_search
from novel_material.infra.embedding import get_embedding, load_embedding_config


def search_events(query, setting=None, emotion=None, limit=10, keyword=False, material_id=None):
    """通过章节摘要检索事件，默认向量语义搜索。"""
    with readonly_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 向量语义搜索（默认）
        if not keyword:
            config = load_embedding_config()
            query_embedding = get_embedding(query, config)

            sql = """
                SELECT c.material_id, c.chapter, c.title, c.summary,
                       c.tension_level, c.pacing, c.chapter_functions,
                       c.characters_appear,
                       n.name as novel_name, n.genre,
                       c.summary_embedding <=> %s::vector as distance
                FROM chapters c
                JOIN novels n ON c.material_id = n.material_id
                WHERE c.summary_embedding IS NOT NULL
            """
            params = [str(query_embedding)]

            if material_id:
                sql += " AND c.material_id = %s"
                params.append(material_id)

            if setting:
                sql += " AND c.setting @> ARRAY[%s]"
                params.append(setting)

            if emotion:
                sql += " AND c.summary ILIKE %s"
                params.append(f"%{emotion}%")

            sql += " ORDER BY distance ASC LIMIT %s"
            params.append(limit)

        else:
            # 关键词模糊搜索（回退模式）
            sql = """
                SELECT c.material_id, c.chapter, c.title, c.summary,
                       c.tension_level, c.pacing, c.chapter_functions,
                       c.characters_appear,
                       n.name as novel_name, n.genre
                FROM chapters c
                JOIN novels n ON c.material_id = n.material_id
                WHERE 1=1
            """
            params = []

            if material_id:
                sql += " AND c.material_id = %s"
                params.append(material_id)

            query_tokens = tokenize_for_search(query or "")
            if query_tokens:
                sql += """ AND (
                    c.search_document @@ plainto_tsquery('simple', %s)
                    OR c.title %% %s
                )"""
                params.extend([query_tokens, query])

            if setting:
                sql += " AND c.setting @> ARRAY[%s]"
                params.append(setting)

            if emotion:
                sql += " AND c.summary ILIKE %s"
                params.append(f"%{emotion}%")

            if query_tokens:
                sql += """ ORDER BY
                    ts_rank_cd(c.search_document, plainto_tsquery('simple', %s)) DESC,
                    similarity(c.title, %s) DESC,
                    c.chapter ASC LIMIT %s
                """
                params.extend([query_tokens, query, limit])
            else:
                sql += " ORDER BY c.tension_level DESC NULLS LAST, c.chapter ASC LIMIT %s"
                params.append(limit)

        cur.execute(sql, params)
        rows = cur.fetchall()

    return [
        SearchResult(
            result_id=f"event:{row['material_id']}:{row['chapter']}",
            document_type="event",
            material_id=row["material_id"],
            chapter=row["chapter"],
            title=row.get("title") or "",
            summary=row.get("summary") or "",
            metadata={
                "novel_name": row.get("novel_name"),
                "genre": row.get("genre") or [],
                "tension_level": row.get("tension_level"),
                "pacing": row.get("pacing"),
                "chapter_functions": row.get("chapter_functions") or [],
                "characters_appear": row.get("characters_appear") or [],
            },
            scores={"semantic": 1 - float(row["distance"])}
            if row.get("distance") is not None
            else {},
            matched_fields=["summary"] if row.get("distance") is not None else [],
        )
        for row in rows
    ]


def retrieve_events_lexical(request: SearchRequest) -> list[SearchResult]:
    """使用章节中文词法索引召回事件。"""
    return search_events(
        request.query,
        limit=request.candidate_limit,
        keyword=True,
        **_event_filters(request),
    )


def retrieve_events_semantic(request: SearchRequest) -> list[SearchResult]:
    """使用完整 4096 维向量精确召回事件。"""
    return search_events(
        request.query,
        limit=request.candidate_limit,
        keyword=False,
        **_event_filters(request),
    )


def retrieve_events_structured(request: SearchRequest) -> list[SearchResult]:
    """仅在存在事件过滤条件时执行结构化召回。"""
    filters = _event_filters(request)
    if not filters:
        return []
    return search_events("", limit=request.candidate_limit, keyword=True, **filters)


def _event_filters(request: SearchRequest) -> dict:
    names = ("setting", "emotion", "material_id")
    return {name: request.filters[name] for name in names if name in request.filters}
