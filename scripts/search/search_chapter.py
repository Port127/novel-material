#!/usr/bin/env python
"""章纲检索：按章节功能、关键词、张力等条件检索章节。"""
import os
import sys
import yaml
import json
import psycopg2
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import click
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def search_chapters(query, genre=None, chapter_function=None, chapter_num=None, tension_min=None, tension_max=None, limit=10):
    """检索章节。"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True

    results = []

    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        # 基础查询
        sql = """
            SELECT c.material_id, c.chapter, c.title, c.summary,
                   c.tension_level, c.pacing, c.chapter_functions,
                   c.characters_appear, c.key_plot_point,
                   n.name as novel_name, n.genre
            FROM chapters c
            JOIN novels n ON c.material_id = n.material_id
            WHERE 1=1
        """
        params = []

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

        sql += " LIMIT %s"
        params.append(limit)

        cur.execute(sql, params)
        results = cur.fetchall()

    conn.close()

    # 打印结果
    if not results:
        print("未找到匹配的章节")
        return

    print(f"找到 {len(results)} 个匹配结果:\n")

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
@click.option("--genre", default=None, help="按题材过滤（如：修仙、都市）")
@click.option("--function", "chapter_function", default=None, help="章节功能标签（如：开局困境）")
@click.option("--chapter", "chapter_num", default=None, type=int, help="精确章节号")
@click.option("--tension-min", default=None, type=int, help="张力最小值（1-5）")
@click.option("--tension-max", default=None, type=int, help="张力最大值（1-5）")
@click.option("--limit", default=10, help="返回结果数")
def main(query, genre, chapter_function, chapter_num, tension_min, tension_max, limit):
    search_chapters(query=query, genre=genre, chapter_function=chapter_function, chapter_num=chapter_num, tension_min=tension_min, tension_max=tension_max, limit=limit)


if __name__ == "__main__":
    main()
