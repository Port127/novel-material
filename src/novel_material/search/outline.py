"""大纲检索：按类型、元素、主角设定等检索小说大纲，支持向量语义搜索。"""
import json
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

from .db import readonly_connection
from .models import SearchRequest, SearchResult
from .text import tokenize_for_search
from novel_material.infra.embedding import get_embedding, load_embedding_config


def search_outlines(query=None, genre=None, element=None, structure_type=None, premise_query=None, limit=5, semantic=False, material_id=None):
    """检索大纲，支持向量语义搜索。"""
    with readonly_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 向量语义搜索
        if semantic:
            config = load_embedding_config()
            query_embedding = get_embedding(query, config)

            sql = """
                SELECT material_id, name, genre, premise, structure_type,
                       act_count, sequence_count, tags,
                       premise_embedding <=> %s::vector as distance
                FROM novels
                WHERE premise_embedding IS NOT NULL
            """
            params = [str(query_embedding)]

            if material_id:
                sql += " AND material_id = %s"
                params.append(material_id)

            if genre:
                sql += " AND genre @> ARRAY[%s]"
                params.append(genre)

            if element:
                sql += " AND tags->'elements' @> %s::jsonb"
                params.append(json.dumps([element]))

            if structure_type:
                sql += " AND structure_type = %s"
                params.append(structure_type)

            sql += " ORDER BY distance ASC LIMIT %s"
            params.append(limit)

        else:
            # 关键词模糊搜索（默认）
            sql = """
                SELECT material_id, name, genre, premise, structure_type,
                       act_count, sequence_count, tags
                FROM novels
                WHERE 1=1
            """
            params = []

            if material_id:
                sql += " AND material_id = %s"
                params.append(material_id)

            if genre:
                sql += " AND genre @> ARRAY[%s]"
                params.append(genre)

            if element:
                # tags JSONB 中的 elements 数组
                sql += " AND tags->'elements' @> %s::jsonb"
                params.append(json.dumps([element]))

            if structure_type:
                sql += " AND structure_type = %s"
                params.append(structure_type)

            lexical_query = premise_query or query or ""
            query_tokens = tokenize_for_search(lexical_query)
            if query_tokens:
                sql += """ AND (
                    search_document @@ plainto_tsquery('simple', %s)
                    OR name %% %s
                )"""
                params.extend([query_tokens, lexical_query])

            if query_tokens:
                sql += """ ORDER BY
                    ts_rank_cd(search_document, plainto_tsquery('simple', %s)) DESC,
                    similarity(name, %s) DESC,
                    chapter_count DESC LIMIT %s
                """
                params.extend([query_tokens, lexical_query, limit])
            else:
                sql += " ORDER BY chapter_count DESC LIMIT %s"
                params.append(limit)

        cur.execute(sql, params)
        rows = cur.fetchall()

    return [
        SearchResult(
            result_id=f"outline:{row['material_id']}",
            document_type="outline",
            material_id=row["material_id"],
            title=row.get("name") or "",
            summary=row.get("premise") or "",
            metadata={
                "genre": row.get("genre") or [],
                "structure_type": row.get("structure_type"),
                "act_count": row.get("act_count"),
                "sequence_count": row.get("sequence_count"),
                "tags": row.get("tags") or {},
            },
            scores={"semantic": 1 - float(row["distance"])}
            if row.get("distance") is not None
            else {},
            matched_fields=["premise"] if row.get("distance") is not None else [],
        )
        for row in rows
    ]


def retrieve_outlines_lexical(request: SearchRequest) -> list[SearchResult]:
    """使用小说级中文词法索引召回大纲。"""
    return search_outlines(
        query=request.query,
        limit=request.candidate_limit,
        semantic=False,
        **_outline_filters(request),
    )


def retrieve_outlines_semantic(request: SearchRequest) -> list[SearchResult]:
    """使用完整 4096 维前提向量精确召回大纲。"""
    return search_outlines(
        query=request.query,
        limit=request.candidate_limit,
        semantic=True,
        **_outline_filters(request),
    )


def retrieve_outlines_structured(request: SearchRequest) -> list[SearchResult]:
    """仅在存在大纲过滤条件时执行结构化召回。"""
    filters = _outline_filters(request)
    if not filters:
        return []
    return search_outlines(query="", limit=request.candidate_limit, **filters)


def _outline_filters(request: SearchRequest) -> dict:
    names = ("genre", "element", "structure_type", "material_id")
    return {name: request.filters[name] for name in names if name in request.filters}
