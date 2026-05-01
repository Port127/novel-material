#!/usr/bin/env python
"""细纲检索：按幕/序列/节拍检索大纲结构。"""
import os
import sys
import yaml
import psycopg2
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def search_detail(genre=None, act=None, description_query=None, limit=10):
    """检索细纲（序列+节拍）。"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True

    results = []

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
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

        if description_query:
            sql_seq += " AND s.description ILIKE %s"
            params.append(f"%{description_query}%")

        sql_seq += " LIMIT %s"
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

        results = seq_results

    conn.close()

    if not results:
        print("未找到匹配的细纲")
        return

    print(f"找到 {len(results)} 个序列:\n")

    for s in results:
        print(f"--- {s['novel_name']} 第{s['act']}幕 序列{s['sequence']} ---")
        print(f"标题: {s['title']}")
        print(f"章节: {s['chapters_start']}-{s['chapters_end']}")
        print(f"描述: {s['description']}")
        print(f"节拍 ({len(s['beats'])}个):")
        for b in s["beats"]:
            print(f"  [{b['beat']}] {b['title']} (章{b['chapter']}) - 张力:{b['tension']}")
        print()

if __name__ == "__main__":
    search_detail(genre="悬疑", act=2, limit=5)
