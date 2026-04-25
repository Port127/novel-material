#!/usr/bin/env python
"""
search.py — SQLite 结构化查询脚本

LLM 不再需要读索引文件，调用此脚本即可完成多维检索。
输出精简的 YAML 结果，只含 top-N 关键字段。

子命令:
    event       多维标签检索事件
    character   检索人物
    text        全文搜索（summary）
    stats       数据库统计

用法:
    python scripts/core/search.py event --event-type 对决 --emotion 燃 --limit 10
    python scripts/core/search.py event --conflict 人与命运 --reader-effect 催泪 --tension-min 4
    python scripts/core/search.py event --character 陈汉升 --event-type 对决
    python scripts/core/search.py event --material nm_novel_20260405_zhbk --emotion 悲伤
    python scripts/core/search.py character --archetype 导师 --material nm_novel_20260405_zhbk
    python scripts/core/search.py character --name 陈汉升
    python scripts/core/search.py text --query 告别 --limit 10
    python scripts/core/search.py stats
"""

import argparse
import sqlite3
import sys
import yaml
from pathlib import Path

DB_PATH = Path("data/material.db")

TAG_DIMENSIONS = [
    'event_type', 'conflict', 'stakes',
    'relationship', 'interaction', 'character_moment',
    'emotion', 'reader_effect',
    'plot_function', 'plot_stage',
    'technique', 'dialogue_type', 'info_delivery',
    'setting', 'time_weather',
    'pacing', 'pov', 'power_dynamic', 'moral_spectrum', 'scale',
]


def get_conn():
    if not DB_PATH.exists():
        print(f"ERROR: 数据库不存在: {DB_PATH}", file=sys.stderr)
        print("请先运行: python scripts/core/build_db.py", file=sys.stderr)
        sys.exit(1)
    return sqlite3.connect(str(DB_PATH))


def _fetch_event_pairs(conn, query: str, params: tuple) -> set[tuple[str, str]]:
    cursor = conn.execute(query, params)
    return {(row[0], row[1]) for row in cursor}


def search_events(args):
    conn = get_conn()
    conn.row_factory = sqlite3.Row

    # Build query from tag filters
    tag_filters = {}
    for dim in TAG_DIMENSIONS:
        attr = dim.replace('-', '_')
        val = getattr(args, attr, None)
        if val:
            tag_filters[dim] = val

    character_filter = getattr(args, 'character', None)
    material_filter = getattr(args, 'material', None)
    tension_min = getattr(args, 'tension_min', None)
    tension_max = getattr(args, 'tension_max', None)
    limit = getattr(args, 'limit', 20)

    if not tag_filters and not character_filter and not material_filter and tension_min is None:
        print("ERROR: 请至少提供一个筛选条件", file=sys.stderr)
        sys.exit(1)

    # Strategy: intersect (event_id, material_id) pairs from each filter
    candidate_sets = []

    for dim, val in tag_filters.items():
        event_pairs = _fetch_event_pairs(
            conn,
            "SELECT DISTINCT event_id, material_id FROM event_tags WHERE dimension = ? AND value = ?",
            (dim, val),
        )
        candidate_sets.append(event_pairs)

    if character_filter:
        event_pairs = _fetch_event_pairs(
            conn,
            "SELECT DISTINCT event_id, material_id FROM event_characters WHERE character_name = ?",
            (character_filter,),
        )
        candidate_sets.append(event_pairs)

    if material_filter:
        event_pairs = _fetch_event_pairs(
            conn,
            "SELECT event_id, material_id FROM events WHERE material_id = ?",
            (material_filter,),
        )
        candidate_sets.append(event_pairs)

    # Intersect all sets (AND logic)
    if candidate_sets:
        result_pairs = candidate_sets[0]
        for s in candidate_sets[1:]:
            result_pairs &= s
    else:
        result_pairs = set()

    if not result_pairs:
        # Relaxation: try OR on the weakest filters
        if len(candidate_sets) > 1:
            print(f"# AND 匹配: 0 个，尝试放宽...", file=sys.stderr)
            # Union all, then rank by match count
            all_pairs = {}
            for cs in candidate_sets:
                for pair in cs:
                    all_pairs[pair] = all_pairs.get(pair, 0) + 1
            # Sort by match count desc
            ranked = sorted(all_pairs.items(), key=lambda x: -x[1])
            result_pairs = {pair for pair, _ in ranked[:limit * 2]}

    only_tension_filter = not candidate_sets and (tension_min is not None or tension_max is not None)

    if not result_pairs and not only_tension_filter:
        print("results: []")
        print("total: 0")
        conn.close()
        return

    # Fetch event details
    query = """
        SELECT s.event_id, s.material_id, s.chapter, s.title, s.summary,
               s.tension, s.pacing, s.plot_stage, s.power_dynamic, s.scale,
               n.name as novel_name
        FROM events s
        LEFT JOIN novels n ON s.material_id = n.material_id
    """
    params = []

    if result_pairs:
        pair_clauses = ["(s.event_id = ? AND s.material_id = ?)"] * len(result_pairs)
        query += f" WHERE {' OR '.join(pair_clauses)}"
        for event_id, material_id in sorted(result_pairs):
            params.extend([event_id, material_id])
    else:
        query += " WHERE 1=1"

    if tension_min is not None:
        query += " AND s.tension >= ?"
        params.append(tension_min)
    if tension_max is not None:
        query += " AND s.tension <= ?"
        params.append(tension_max)

    query += " ORDER BY s.tension DESC, s.material_id, s.event_id"
    query += f" LIMIT {limit}"

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    # Compute match score for each result
    results = []
    for row in rows:
        event_id = row['event_id']
        material_id = row['material_id']

        # Get all tags for this event
        tag_cursor = conn.execute(
            "SELECT dimension, value FROM event_tags WHERE event_id = ? AND material_id = ?",
            (event_id, material_id)
        )
        event_tags = {}
        for tr in tag_cursor:
            dim = tr[0]
            event_tags.setdefault(dim, []).append(tr[1])

        # Get characters
        char_cursor = conn.execute(
            "SELECT character_name FROM event_characters WHERE event_id = ? AND material_id = ?",
            (event_id, material_id)
        )
        chars = [cr[0] for cr in char_cursor]

        # Compute match score
        match_count = 0
        matched_dims = []
        for dim, val in tag_filters.items():
            if val in event_tags.get(dim, []):
                match_count += 1
                matched_dims.append(f"{dim}={val}")
        if character_filter and character_filter in chars:
            match_count += 1
            matched_dims.append(f"character={character_filter}")

        total_filters = len(tag_filters) + (1 if character_filter else 0)
        score = round(match_count / total_filters, 2) if total_filters > 0 else 1.0

        results.append({
            'event_id': event_id,
            'material_id': material_id,
            'novel': row['novel_name'] or material_id,
            'chapter': row['chapter'],
            'title': row['title'],
            'summary': row['summary'],
            'tension': row['tension'],
            'matched': matched_dims,
            'score': score,
        })

    results.sort(key=lambda x: (-x['score'], -x['tension']))
    results = results[:limit]

    output = {
        'query': {**tag_filters},
        'total': len(results),
        'results': results,
    }
    if character_filter:
        output['query']['character'] = character_filter
    if material_filter:
        output['query']['material'] = material_filter

    print(yaml.dump(output, allow_unicode=True, default_flow_style=False, sort_keys=False))
    conn.close()


def search_characters(args):
    conn = get_conn()
    conn.row_factory = sqlite3.Row

    conditions = []
    params = []

    if args.name:
        conditions.append("c.name LIKE ?")
        params.append(f"%{args.name}%")
    if args.archetype:
        conditions.append("c.archetype = ?")
        params.append(args.archetype)
    if args.role:
        conditions.append("c.role = ?")
        params.append(args.role)
    if args.material:
        conditions.append("c.material_id = ?")
        params.append(args.material)
    if args.moral_spectrum:
        conditions.append("c.moral_spectrum = ?")
        params.append(args.moral_spectrum)

    if not conditions:
        print("ERROR: 请至少提供一个筛选条件", file=sys.stderr)
        sys.exit(1)

    where = " AND ".join(conditions)
    query = f"""
        SELECT c.*, n.name as novel_name
        FROM characters c
        LEFT JOIN novels n ON c.material_id = n.material_id
        WHERE {where}
        LIMIT {args.limit}
    """

    cursor = conn.execute(query, params)
    rows = cursor.fetchall()

    results = []
    for row in rows:
        item = {
            'name': row['name'],
            'novel': row['novel_name'] or row['material_id'],
            'material_id': row['material_id'],
            'role': row['role'],
            'archetype': row['archetype'],
            'moral_spectrum': row['moral_spectrum'],
            'arc_summary': row['arc_summary'],
            'narrative_function': row['narrative_function'],
        }
        # Add psychology fields if non-empty
        psych = {}
        for field in ('fatal_flaw', 'obsession', 'soft_spot', 'misbelief'):
            val = row[field]
            if val:
                psych[field] = val
        if psych:
            item['psychology'] = psych

        # Count event appearances
        count_cursor = conn.execute(
            "SELECT COUNT(*) FROM event_characters WHERE character_name = ? AND material_id = ?",
            (row['name'], row['material_id'])
        )
        item['appearance_count'] = count_cursor.fetchone()[0]

        results.append(item)

    output = {
        'total': len(results),
        'results': results,
    }
    print(yaml.dump(output, allow_unicode=True, default_flow_style=False, sort_keys=False))
    conn.close()


def search_text(args):
    conn = get_conn()
    conn.row_factory = sqlite3.Row

    query_text = args.query
    limit = args.limit

    cursor = conn.execute(
        """SELECT s.event_id, s.material_id, s.chapter, s.title, s.summary,
                  s.tension, s.plot_stage, n.name as novel_name
           FROM events s
           LEFT JOIN novels n ON s.material_id = n.material_id
           WHERE s.summary LIKE ? OR s.title LIKE ?
           ORDER BY s.event_id
           LIMIT ?""",
        (f"%{query_text}%", f"%{query_text}%", limit)
    )
    rows = cursor.fetchall()

    results = []
    for row in rows:
        results.append({
            'event_id': row['event_id'],
            'novel': row['novel_name'] or row['material_id'],
            'chapter': row['chapter'],
            'title': row['title'],
            'summary': row['summary'],
            'tension': row['tension'],
        })

    output = {
        'query': query_text,
        'total': len(results),
        'results': results,
    }
    print(yaml.dump(output, allow_unicode=True, default_flow_style=False, sort_keys=False))
    conn.close()


def show_stats(args):
    conn = get_conn()

    cursor = conn.execute("SELECT COUNT(*) FROM novels")
    n_novels = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM events")
    n_events = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(DISTINCT dimension) FROM event_tags")
    n_dims = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM event_tags")
    n_tags = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM characters")
    n_chars = cursor.fetchone()[0]

    print(f"novels: {n_novels}")
    print(f"events: {n_events}")
    print(f"tag_dimensions: {n_dims}")
    print(f"tag_records: {n_tags}")
    print(f"characters: {n_chars}")

    if n_novels > 0:
        print(f"\nper_novel:")
        cursor = conn.execute(
            "SELECT material_id, name, total_events FROM novels ORDER BY material_id"
        )
        for row in cursor:
            print(f"  - {row[0]}: {row[1]} ({row[2]} events)")

    # Top tag values
    if n_tags > 0:
        print(f"\ntop_event_types:")
        cursor = conn.execute(
            """SELECT value, COUNT(*) as cnt FROM event_tags
               WHERE dimension = 'event_type' GROUP BY value ORDER BY cnt DESC LIMIT 10"""
        )
        for row in cursor:
            print(f"  - {row[0]}: {row[1]}")

        print(f"\ntop_emotions:")
        cursor = conn.execute(
            """SELECT value, COUNT(*) as cnt FROM event_tags
               WHERE dimension = 'emotion' GROUP BY value ORDER BY cnt DESC LIMIT 10"""
        )
        for row in cursor:
            print(f"  - {row[0]}: {row[1]}")

    conn.close()


def main():
    parser = argparse.ArgumentParser(description='素材库结构化检索')
    subparsers = parser.add_subparsers(dest='command', help='子命令')

    # event subcommand
    event_parser = subparsers.add_parser('event', help='多维标签检索事件')
    event_parser.add_argument('--event-type', dest='event_type')
    event_parser.add_argument('--conflict')
    event_parser.add_argument('--stakes')
    event_parser.add_argument('--relationship')
    event_parser.add_argument('--interaction')
    event_parser.add_argument('--character-moment', dest='character_moment')
    event_parser.add_argument('--emotion')
    event_parser.add_argument('--reader-effect', dest='reader_effect')
    event_parser.add_argument('--plot-function', dest='plot_function')
    event_parser.add_argument('--plot-stage', dest='plot_stage')
    event_parser.add_argument('--technique')
    event_parser.add_argument('--dialogue-type', dest='dialogue_type')
    event_parser.add_argument('--info-delivery', dest='info_delivery')
    event_parser.add_argument('--setting')
    event_parser.add_argument('--time-weather', dest='time_weather')
    event_parser.add_argument('--pacing')
    event_parser.add_argument('--pov')
    event_parser.add_argument('--power-dynamic', dest='power_dynamic')
    event_parser.add_argument('--moral-spectrum', dest='moral_spectrum')
    event_parser.add_argument('--scale')
    event_parser.add_argument('--character', help='按人物名过滤')
    event_parser.add_argument('--material', help='限定素材ID')
    event_parser.add_argument('--tension-min', type=int, dest='tension_min')
    event_parser.add_argument('--tension-max', type=int, dest='tension_max')
    event_parser.add_argument('--limit', type=int, default=20)

    # character subcommand
    char_parser = subparsers.add_parser('character', help='检索人物')
    char_parser.add_argument('--name')
    char_parser.add_argument('--archetype')
    char_parser.add_argument('--role', choices=['protagonist', 'antagonist', 'supporting', 'minor'])
    char_parser.add_argument('--material')
    char_parser.add_argument('--moral-spectrum', dest='moral_spectrum')
    char_parser.add_argument('--limit', type=int, default=20)

    # text subcommand
    text_parser = subparsers.add_parser('text', help='全文搜索（summary/title）')
    text_parser.add_argument('--query', required=True)
    text_parser.add_argument('--limit', type=int, default=20)

    # stats subcommand
    subparsers.add_parser('stats', help='数据库统计')

    args = parser.parse_args()

    if args.command == 'event':
        search_events(args)
    elif args.command == 'character':
        search_characters(args)
    elif args.command == 'text':
        search_text(args)
    elif args.command == 'stats':
        show_stats(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
