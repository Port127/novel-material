"""细纲检索：按幕/序列/节拍检索大纲结构。"""
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

from .db import readonly_connection
from .models import SearchRequest, SearchResult
from .text import tokenize_for_search
from novel_material.infra.embedding import get_embedding, load_embedding_config


def search_detail(query=None, genre=None, act=None, description_query=None, limit=10, material_id=None):
    """检索细纲（序列+节拍）。"""
    with readonly_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 先找匹配的序列
        sql_seq = """
            SELECT s.material_id, s.act, s.sequence, s.title, s.chapters_start,
                   s.chapters_end, s.description,
                   n.name as novel_name, n.genre as novel_genre
            FROM outline_sequences s
            JOIN novels n ON s.material_id = n.material_id
            WHERE 1=1
        """
        params = []

        if material_id:
            sql_seq += " AND s.material_id = %s"
            params.append(material_id)

        if genre:
            sql_seq += " AND n.genre @> ARRAY[%s]"
            params.append(genre)

        if act is not None:
            sql_seq += " AND s.act = %s"
            params.append(act)

        lexical_query = description_query or query or ""
        query_tokens = tokenize_for_search(lexical_query)
        if query_tokens:
            sql_seq += """ AND (
                s.search_document @@ plainto_tsquery('simple', %s)
                OR s.title %% %s
            )"""
            params.extend([query_tokens, lexical_query])

        if query_tokens:
            sql_seq += """ ORDER BY
                ts_rank_cd(s.search_document, plainto_tsquery('simple', %s)) DESC,
                similarity(s.title, %s) DESC,
                s.act ASC, s.sequence ASC LIMIT %s
            """
            params.extend([query_tokens, lexical_query, limit])
        else:
            sql_seq += " ORDER BY s.act ASC, s.sequence ASC LIMIT %s"
            params.append(limit)

        cur.execute(sql_seq, params)
        seq_results = cur.fetchall()

        # 对于每个匹配的序列，获取其节拍
        for s in seq_results:
            cur.execute("""
                SELECT beat, title, chapter, description, tension
                FROM outline_beats
                WHERE material_id = %s AND act = %s AND sequence = %s
                ORDER BY beat
            """, (s["material_id"], s["act"], s["sequence"]))
            beats = cur.fetchall()
            s["beats"] = beats


    return [
        SearchResult(
            result_id=(
                f"detail:{row['material_id']}:{row['act']}:{row['sequence']}"
            ),
            document_type="detail",
            material_id=row["material_id"],
            title=row.get("title") or "",
            summary=row.get("description") or "",
            metadata={
                "novel_name": row.get("novel_name"),
                "genre": row.get("novel_genre") or [],
                "act": row.get("act"),
                "sequence": row.get("sequence"),
                "chapters_start": row.get("chapters_start"),
                "chapters_end": row.get("chapters_end"),
                "beats": row.get("beats") or [],
            },
        )
        for row in seq_results
    ]


def retrieve_details_lexical(request: SearchRequest) -> list[SearchResult]:
    """使用细纲序列中文词法索引召回。"""
    return search_detail(
        query=request.query,
        limit=request.candidate_limit,
        **_detail_filters(request),
    )


def retrieve_details_semantic(request: SearchRequest) -> list[SearchResult]:
    """使用完整 4096 维节拍描述向量精确召回细纲。"""
    query_embedding = get_embedding(request.query, load_embedding_config())
    filters = _detail_filters(request)
    sql = """
        SELECT b.material_id, b.act, b.sequence, b.beat, b.title,
               b.chapter, b.description, b.tension,
               n.name AS novel_name, n.genre AS novel_genre,
               b.description_embedding <=> %s::vector AS distance
        FROM outline_beats b
        JOIN novels n ON b.material_id = n.material_id
        WHERE b.description_embedding IS NOT NULL
    """
    params: list = [str(query_embedding)]
    if filters.get("genre"):
        sql += " AND n.genre @> ARRAY[%s]"
        params.append(filters["genre"])
    if filters.get("act") is not None:
        sql += " AND b.act = %s"
        params.append(filters["act"])
    if filters.get("material_id"):
        sql += " AND b.material_id = %s"
        params.append(filters["material_id"])
    sql += " ORDER BY distance ASC LIMIT %s"
    params.append(request.candidate_limit)

    with readonly_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    return [
        SearchResult(
            result_id=(
                f"detail:{row['material_id']}:{row['act']}:"
                f"{row['sequence']}:{row['beat']}"
            ),
            document_type="detail",
            material_id=row["material_id"],
            chapter=row.get("chapter"),
            title=row.get("title") or "",
            summary=row.get("description") or "",
            metadata={
                "novel_name": row.get("novel_name"),
                "genre": row.get("novel_genre") or [],
                "act": row.get("act"),
                "sequence": row.get("sequence"),
                "beat": row.get("beat"),
                "tension": row.get("tension"),
            },
            scores={"semantic": 1 - float(row["distance"])},
            matched_fields=["description"],
        )
        for row in rows
    ]


def retrieve_details_structured(request: SearchRequest) -> list[SearchResult]:
    """仅在存在细纲过滤条件时执行结构化召回。"""
    filters = _detail_filters(request)
    if not filters:
        return []
    return search_detail(query="", limit=request.candidate_limit, **filters)


def _detail_filters(request: SearchRequest) -> dict:
    names = ("genre", "act", "material_id")
    return {name: request.filters[name] for name in names if name in request.filters}
