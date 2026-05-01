#!/usr/bin/env python
"""大纲检索：按类型、元素、主角设定等检索小说大纲。"""
import os
import sys
import yaml
import psycopg2
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def search_outlines(genre=None, element=None, structure_type=None, premise_query=None, limit=5):
    """检索大纲。"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True

    results = []

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        sql = """
            SELECT material_id, name, genre, premise, structure_type,
                   act_count, sequence_count, tags
            FROM novels
            WHERE 1=1
        """
        params = []

        if genre:
            sql += " AND genre @> ARRAY[%s]"
            params.append(genre)

        if structure_type:
            sql += " AND structure_type = %s"
            params.append(structure_type)

        sql += " ORDER BY chapter_count DESC LIMIT %s"
        params.append(limit)

        cur.execute(sql, params)
        results = cur.fetchall()

    conn.close()

    if not results:
        print("未找到匹配的大纲")
        return

    print(f"找到 {len(results)} 部小说的大纲:\n")

    for r in results:
        print(f"--- {r['name']} ---")
        print(f"类型: {r['genre']}")
        print(f"结构: {r['structure_type']} ({r['act_count']}幕 / {r['sequence_count']}序列)")
        print(f"前提: {r['premise']}")
        print()

if __name__ == "__main__":
    search_outlines(genre="修仙", limit=3)
