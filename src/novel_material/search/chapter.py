"""章纲检索：按章节功能、关键词、张力等条件检索章节，支持向量语义搜索。"""
import json
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

from .common import build_like_terms
from .db import readonly_connection
from .models import SearchResult
from novel_material.infra.embedding import get_embedding, load_embedding_config


def search_chapters(query, genre=None, chapter_function=None, chapter_num=None, tension_min=None, tension_max=None, element=None, style=None, plot_point=None, limit=10, semantic=False):
    """检索章节，支持向量语义搜索。"""
    with readonly_connection() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        # 向量语义搜索（优先）
        if semantic:
            config = load_embedding_config()
            query_embedding = get_embedding(query, config)

            # 使用 pgvector 余弦距离搜索
            sql = """
                SELECT c.material_id, c.chapter, c.title, c.summary,
                       c.tension_level, c.pacing, c.chapter_functions,
                       c.characters_appear, c.key_plot_point, c.key_event,
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

            if plot_point:
                sql += " AND c.key_plot_point = %s"
                params.append(plot_point)

            sql += " ORDER BY distance ASC LIMIT %s"
            params.append(limit)

        else:
            # 关键词模糊搜索（默认）
            sql = """
                SELECT c.material_id, c.chapter, c.title, c.summary,
                       c.tension_level, c.pacing, c.chapter_functions,
                       c.characters_appear, c.key_plot_point, c.key_event,
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
                            OR COALESCE(c.key_event, '') ILIKE %s
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
                sql += " AND n.tags->'elements' @> %s::jsonb"
                params.append(json.dumps([element]))

            if style:
                sql += " AND n.tags->'style' @> %s::jsonb"
                params.append(json.dumps([style]))

            if plot_point:
                sql += " AND c.key_plot_point = %s"
                params.append(plot_point)

            sql += " ORDER BY c.tension_level DESC NULLS LAST, c.chapter ASC LIMIT %s"
            params.append(limit)

        cur.execute(sql, params)
        rows = cur.fetchall()

    return [
        SearchResult(
            result_id=f"chapter:{row['material_id']}:{row['chapter']}",
            document_type="chapter",
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
                "key_event": row.get("key_event"),
                "key_plot_point": row.get("key_plot_point"),
            },
            scores={"semantic": 1 - float(row["distance"])}
            if row.get("distance") is not None
            else {},
            matched_fields=["summary"] if row.get("distance") is not None else [],
        )
        for row in rows
    ]
