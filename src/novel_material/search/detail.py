"""细纲检索：按幕/序列/节拍检索大纲结构。"""
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

from .common import build_like_terms
from .db import readonly_connection
from .models import SearchResult


def search_detail(query=None, genre=None, act=None, description_query=None, limit=10):
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

        if genre:
            sql_seq += " AND n.genre @> ARRAY[%s]"
            params.append(genre)

        if act is not None:
            sql_seq += " AND s.act = %s"
            params.append(act)

        terms = build_like_terms(description_query or query)
        if terms:
            clauses = []
            for term in terms:
                fuzzy = f"%{term}%"
                clauses.append("(COALESCE(s.title, '') ILIKE %s OR COALESCE(s.description, '') ILIKE %s)")
                params.extend([fuzzy, fuzzy])
            sql_seq += " AND (" + " OR ".join(clauses) + ")"

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
