#!/usr/bin/env python
"""人物检索：按原型、角色、类型等条件检索人物。"""
import os
import sys
import yaml
import psycopg2
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import click
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def search_characters(archetype=None, role=None, genre=None, name_query=None, limit=10):
    """检索人物。"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True

    results = []

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
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

        if archetype:
            sql += " AND c.archetype = %s"
            params.append(archetype)

        if role:
            sql += " AND c.role = %s"
            params.append(role)

        if genre:
            sql += " AND n.genre @> ARRAY[%s]"
            params.append(genre)

        if name_query:
            sql += " AND c.name ILIKE %s"
            params.append(f"%{name_query}%")

        sql += " ORDER BY c.appearance_count DESC LIMIT %s"
        params.append(limit)

        cur.execute(sql, params)
        results = cur.fetchall()

    conn.close()

    if not results:
        print("未找到匹配的人物")
        return

    print(f"找到 {len(results)} 个人物:\n")

    for r in results:
        print(f"--- {r['name']} ({r['novel_name']}) ---")
        print(f"角色: {r['role']} | 原型: {r['archetype']}")
        print(f"道德立场: {r['moral_spectrum']}")
        print(f"弧线: {r['arc_summary']}")
        print(f"功能: {r['narrative_function']}")
        print(f"出场次数: {r['appearance_count']}")
        print()

@click.command()
@click.option("--archetype", default=None, help="人物原型（如：英雄、导师）")
@click.option("--role", default=None, help="角色类型（protagonist/antagonist/supporting）")
@click.option("--genre", default=None, help="按题材过滤")
@click.option("--name", "name_query", default=None, help="人物名字关键词")
@click.option("--limit", default=10, help="返回结果数")
def main(archetype, role, genre, name_query, limit):
    search_characters(archetype=archetype, role=role, genre=genre, name_query=name_query, limit=limit)


if __name__ == "__main__":
    main()
