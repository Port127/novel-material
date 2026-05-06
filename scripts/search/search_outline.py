#!/usr/bin/env python
"""大纲检索：按类型、元素、主角设定等检索小说大纲。"""
import os
import sys
import psycopg2
import psycopg2.extras
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import click
from dotenv import load_dotenv
load_dotenv()

import json

from scripts.search._common import build_like_terms, require_database_url

DATABASE_URL = os.getenv("DATABASE_URL")

def search_outlines(query=None, genre=None, element=None, structure_type=None, premise_query=None, limit=5):
    """检索大纲。"""
    conn = psycopg2.connect(require_database_url(DATABASE_URL))
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

        if element:
            # tags JSONB 中的 elements 数组
            sql += " AND tags->'elements' @> %s::jsonb"
            params.append(json.dumps([element]))

        if structure_type:
            sql += " AND structure_type = %s"
            params.append(structure_type)

        terms = build_like_terms(premise_query or query)
        if terms:
            clauses = []
            for term in terms:
                fuzzy = f"%{term}%"
                clauses.append(
                    "(COALESCE(premise, '') ILIKE %s OR name ILIKE %s OR COALESCE(structure_type, '') ILIKE %s)"
                )
                params.extend([fuzzy, fuzzy, fuzzy])
            sql += " AND (" + " OR ".join(clauses) + ")"

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

@click.command()
@click.argument("query", required=False)
@click.option("--genre", default=None, help="按题材过滤")
@click.option("--element", default=None, help="元素标签（如：重生、系统）")
@click.option("--structure", "structure_type", default=None, help="叙事结构（三幕式/英雄之旅）")
@click.option("--query", "premise_query", default=None, help="前提关键词")
@click.option("--limit", default=5, help="返回结果数")
def main(query, genre, element, structure_type, premise_query, limit):
    search_outlines(query=query, genre=genre, element=element, structure_type=structure_type, premise_query=premise_query, limit=limit)


if __name__ == "__main__":
    main()
