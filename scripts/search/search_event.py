#!/usr/bin/env python
"""事件检索：按语义描述检索章节（"雨中告别"、"主角初次突破"等）。"""
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

def search_events(query, setting=None, emotion=None, limit=10):
    """通过章节摘要语义检索事件。"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True

    results = []

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # 使用 FTS 全文搜索摘要（中文分词需额外扩展）
        # 或者使用向量搜索（需要 query embedding）
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

        if query:
            # 使用 ILIKE 进行模糊匹配（生产环境应使用向量搜索）
            keywords = query.replace("的", "").replace("了", "").split()
            conditions = []
            for kw in keywords:
                conditions.append("c.summary ILIKE %s")
                params.append(f"%{kw}%")
            if conditions:
                sql += " AND (" + " OR ".join(conditions) + ")"

        if setting:
            sql += " AND c.setting @> ARRAY[%s]"
            params.append(setting)

        if emotion:
            sql += " AND c.summary ILIKE %s"
            params.append(f"%{emotion}%")

        sql += " ORDER BY c.tension_level DESC LIMIT %s"
        params.append(limit)

        cur.execute(sql, params)
        results = cur.fetchall()

    conn.close()

    if not results:
        print("未找到匹配的事件")
        return

    print(f"找到 {len(results)} 个匹配事件:\n")

    for r in results:
        print(f"--- {r['novel_name']} 第{r['chapter']}章 ---")
        print(f"标题: {r['title']}")
        print(f"摘要: {r['summary']}")
        print(f"张力: {r['tension_level']}/5 | 节奏: {r['pacing']}")
        print(f"功能: {r['chapter_functions']}")
        print(f"人物: {r['characters_appear']}")
        print()

@click.command()
@click.argument("query")
@click.option("--setting", default=None, help="场景类型")
@click.option("--emotion", default=None, help="情绪基调")
@click.option("--limit", default=10, help="返回结果数")
def main(query, setting, emotion, limit):
    search_events(query=query, setting=setting, emotion=emotion, limit=limit)


if __name__ == "__main__":
    main()
