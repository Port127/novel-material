#!/usr/bin/env python
"""世界观检索：按类型、势力、地理、力量体系等条件检索。"""
import os
import sys
import yaml
import psycopg2
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def search_worldbuilding(entity_type=None, genre=None, importance=None, name_query=None, limit=10):
    """检索世界观设定。"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True

    results = []

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
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

        if name_query:
            sql += " AND w.name ILIKE %s"
            params.append(f"%{name_query}%")

        sql += " LIMIT %s"
        params.append(limit)

        cur.execute(sql, params)
        results = cur.fetchall()

    conn.close()

    if not results:
        print("未找到匹配的世界观设定")
        return

    print(f"找到 {len(results)} 个世界观设定:\n")

    for r in results:
        print(f"--- {r['name']} ({r['novel_name']}) ---")
        print(f"类型: {r['entity_type']} | 重要性: {r['importance']}")
        print(f"描述: {r['description']}")
        print()

if __name__ == "__main__":
    search_worldbuilding(entity_type="faction", genre="修仙", limit=10)
