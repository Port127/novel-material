#!/usr/bin/env python
"""
build_db.py — 从事件 YAML 构建 SQLite 索引数据库

YAML 文件仍是 source of truth，SQLite 是派生的查询加速层。
可随时从 YAML 重建，无数据损失。

用法:
    python scripts/core/build_db.py                         # 全量重建（所有小说）
    python scripts/core/build_db.py --material <id>         # 仅重建指定小说
    python scripts/core/build_db.py --incremental <id>      # 增量更新指定小说

输出:
    data/material.db
"""

import argparse
import sqlite3
import sys
import yaml
from pathlib import Path
from datetime import datetime


DB_PATH = Path("data/material.db")

TAG_LIST_FIELDS = [
    'event_type', 'conflict', 'stakes',
    'relationship', 'interaction', 'character_moment',
    'emotion', 'reader_effect',
    'plot_function',
    'technique', 'dialogue_type', 'info_delivery',
    'setting', 'time_weather',
]

TAG_SCALAR_FIELDS = [
    'power_dynamic', 'moral_spectrum',
    'plot_stage', 'pacing', 'pov', 'scale',
]


def _str_or_first(val):
    """Convert a value to string; if list, join or take first element."""
    if val is None:
        return ''
    if isinstance(val, list):
        return ', '.join(str(v) for v in val) if val else ''
    return str(val)


def _as_list(val):
    if val is None:
        return []
    if isinstance(val, list):
        return [str(v) for v in val if not isinstance(v, dict)]
    if isinstance(val, dict):
        return []
    return [str(val)]


# Nested format (legacy) → flat field mapping
_NESTED_MAP = {
    'content': ['event_type', 'conflict', 'stakes'],
    'people': ['relationship', 'interaction', 'power_dynamic', 'character_moment', 'moral_spectrum'],
    'emotion': ['emotion', 'reader_effect'],
    'structure': ['plot_stage', 'plot_function', 'pacing'],
    'craft': ['technique', 'dialogue_type', 'pov', 'info_delivery'],
    'setting': ['scale', 'time_weather'],
}

_NESTED_REMAP = {
    'location': 'setting',
}


def _flatten_event(raw: dict) -> dict:
    """Normalize nested event format to flat format for uniform DB ingestion.

    Handles both flat format (event-unit.schema.yaml Flat Output Contract)
    and legacy nested format (content/people/emotion/structure/craft/setting groups).
    """
    flat = dict(raw)

    if 'event_id' in flat and 'id' not in flat:
        flat['id'] = flat.pop('event_id')

    for group_key, fields in _NESTED_MAP.items():
        if group_key in flat and isinstance(flat[group_key], dict):
            group = flat.pop(group_key)
            for f in fields:
                if f in group and f not in flat:
                    flat[f] = group[f]
            for old_name, new_name in _NESTED_REMAP.items():
                if old_name in group and new_name not in flat:
                    flat[new_name] = group[old_name]

    if 'tension' not in flat:
        emo = raw.get('emotion')
        if isinstance(emo, dict) and 'tension' in emo:
            flat['tension'] = emo['tension']

    if 'characters' in flat and isinstance(flat['characters'], list):
        first = flat['characters'][0] if flat['characters'] else None
        if isinstance(first, dict) and 'name' in first:
            flat['characters'] = [c['name'] for c in flat['characters'] if isinstance(c, dict)]

    if 'moral_spectrum' in flat and isinstance(flat['moral_spectrum'], list):
        flat['moral_spectrum'] = flat['moral_spectrum'][0] if flat['moral_spectrum'] else ''

    return flat


def create_schema(conn: sqlite3.Connection):
    """Create database schema."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS novels (
            material_id TEXT PRIMARY KEY,
            name TEXT,
            author TEXT,
            status TEXT,
            total_events INTEGER DEFAULT 0,
            built_at TEXT
        );

        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT NOT NULL,
            material_id TEXT NOT NULL,
            chapter TEXT,
            title TEXT,
            summary TEXT,
            tension INTEGER DEFAULT 0,
            pacing TEXT,
            pov TEXT,
            power_dynamic TEXT,
            moral_spectrum TEXT,
            plot_stage TEXT,
            scale TEXT,
            PRIMARY KEY (event_id, material_id),
            FOREIGN KEY (material_id) REFERENCES novels(material_id)
        );

        CREATE TABLE IF NOT EXISTS event_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL,
            material_id TEXT NOT NULL,
            dimension TEXT NOT NULL,
            value TEXT NOT NULL,
            FOREIGN KEY (event_id, material_id) REFERENCES events(event_id, material_id)
        );

        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT,
            archetype TEXT,
            moral_spectrum TEXT,
            arc_summary TEXT,
            narrative_function TEXT,
            fatal_flaw TEXT,
            obsession TEXT,
            soft_spot TEXT,
            misbelief TEXT,
            FOREIGN KEY (material_id) REFERENCES novels(material_id)
        );

        CREATE TABLE IF NOT EXISTS event_characters (
            event_id TEXT NOT NULL,
            material_id TEXT NOT NULL,
            character_name TEXT NOT NULL,
            PRIMARY KEY (event_id, material_id, character_name),
            FOREIGN KEY (event_id, material_id) REFERENCES events(event_id, material_id)
        );

        CREATE INDEX IF NOT EXISTS idx_event_tags_dim_val ON event_tags(dimension, value);
        CREATE INDEX IF NOT EXISTS idx_event_tags_material ON event_tags(material_id);
        CREATE INDEX IF NOT EXISTS idx_event_tags_event ON event_tags(event_id);
        CREATE INDEX IF NOT EXISTS idx_events_material ON events(material_id);
        CREATE INDEX IF NOT EXISTS idx_events_tension ON events(tension);
        CREATE INDEX IF NOT EXISTS idx_characters_material ON characters(material_id);
        CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(name);
        CREATE INDEX IF NOT EXISTS idx_event_characters_name ON event_characters(character_name);
    """)
    conn.commit()


def load_novel_meta(base_dir: Path) -> dict:
    """Load novel metadata."""
    meta_path = base_dir / "meta.yaml"
    if not meta_path.exists():
        return {}
    with open(meta_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {}


def load_novel_characters(base_dir: Path) -> list:
    """Load character data from characters.yaml."""
    chars_path = base_dir / "characters.yaml"
    if not chars_path.exists():
        return []
    with open(chars_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    return data.get('roster', data.get('characters', []))


def ingest_novel(conn: sqlite3.Connection, material_id: str):
    """Ingest one novel's data into SQLite."""
    base_dir = Path(f"data/novels/{material_id}")
    events_dir = base_dir / "events"

    if not base_dir.exists():
        print(f"  SKIP: {base_dir} 不存在", file=sys.stderr)
        return 0

    # Clear existing data for this novel
    conn.execute("DELETE FROM event_tags WHERE material_id = ?", (material_id,))
    conn.execute("DELETE FROM event_characters WHERE material_id = ?", (material_id,))
    conn.execute("DELETE FROM events WHERE material_id = ?", (material_id,))
    conn.execute("DELETE FROM characters WHERE material_id = ?", (material_id,))
    conn.execute("DELETE FROM novels WHERE material_id = ?", (material_id,))

    # Load meta
    meta = load_novel_meta(base_dir)
    name = meta.get('name', meta.get('title', material_id))
    author = meta.get('author', '')
    status = meta.get('status', 'unknown')

    # Load events
    event_count = 0
    if events_dir.exists():
        event_files = sorted(events_dir.glob("ev*.yaml"))

        for ef in event_files:
            try:
                with open(ef, 'r', encoding='utf-8') as f:
                    event = yaml.safe_load(f)
            except yaml.YAMLError:
                continue

            if not event:
                continue

            event = _flatten_event(event)

            event_id = event.get('id', ef.stem)
            chapter = event.get('chapter', '')
            title = event.get('title', '')
            summary = event.get('summary', '')
            tension = event.get('tension', 0)
            pacing = _str_or_first(event.get('pacing', ''))
            pov = _str_or_first(event.get('pov', ''))
            power_dynamic = _str_or_first(event.get('power_dynamic', ''))
            moral_spectrum = _str_or_first(event.get('moral_spectrum', ''))
            plot_stage = _str_or_first(event.get('plot_stage', ''))
            scale = _str_or_first(event.get('scale', ''))

            conn.execute(
                """INSERT OR REPLACE INTO events
                   (event_id, material_id, chapter, title, summary, tension,
                    pacing, pov, power_dynamic, moral_spectrum, plot_stage, scale)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_id, material_id, chapter, title, summary, tension,
                 pacing, pov, power_dynamic, moral_spectrum, plot_stage, scale)
            )

            # List tag fields → event_tags
            for field in TAG_LIST_FIELDS:
                for val in _as_list(event.get(field)):
                    conn.execute(
                        "INSERT INTO event_tags (event_id, material_id, dimension, value) VALUES (?, ?, ?, ?)",
                        (event_id, material_id, field, val)
                    )

            # Scalar tag fields → event_tags
            for field in TAG_SCALAR_FIELDS:
                val = event.get(field)
                if val:
                    conn.execute(
                        "INSERT INTO event_tags (event_id, material_id, dimension, value) VALUES (?, ?, ?, ?)",
                        (event_id, material_id, field, str(val))
                    )

            # Characters
            for char_name in _as_list(event.get('characters')):
                conn.execute(
                    "INSERT OR IGNORE INTO event_characters (event_id, material_id, character_name) VALUES (?, ?, ?)",
                    (event_id, material_id, char_name)
                )

            event_count += 1

    # Insert novel record
    conn.execute(
        "INSERT INTO novels (material_id, name, author, status, total_events, built_at) VALUES (?, ?, ?, ?, ?, ?)",
        (material_id, name, author, status, event_count, datetime.now().isoformat())
    )

    # Load characters
    characters = load_novel_characters(base_dir)
    for char in characters:
        if not isinstance(char, dict):
            continue
        psychology = char.get('psychology', {})
        if not isinstance(psychology, dict):
            psychology = {}
        conn.execute(
            """INSERT INTO characters
               (material_id, name, role, archetype, moral_spectrum,
                arc_summary, narrative_function, fatal_flaw, obsession, soft_spot, misbelief)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                material_id,
                char.get('name', ''),
                char.get('role', ''),
                char.get('archetype', ''),
                char.get('moral_spectrum', ''),
                char.get('arc_summary', str(char.get('arc', ''))),
                char.get('narrative_function', ''),
                psychology.get('fatal_flaw', ''),
                psychology.get('obsession', ''),
                psychology.get('soft_spot', ''),
                psychology.get('misbelief', ''),
            )
        )

    conn.commit()
    return event_count


def build_all(conn: sqlite3.Connection):
    """Rebuild database from all novels."""
    index_path = Path("data/index.yaml")
    if not index_path.exists():
        print("ERROR: data/index.yaml 不存在", file=sys.stderr)
        sys.exit(1)

    with open(index_path, 'r', encoding='utf-8') as f:
        index = yaml.safe_load(f) or {}

    materials = index.get('materials', index.get('entries', []))
    if isinstance(materials, dict):
        material_ids = list(materials.keys())
    elif isinstance(materials, list):
        material_ids = [m.get('id', m.get('material_id', '')) for m in materials if isinstance(m, dict)]
    else:
        material_ids = []

    # Also scan data/novels/ directory for any not in index
    novels_dir = Path("data/novels")
    if novels_dir.exists():
        for d in novels_dir.iterdir():
            if d.is_dir() and d.name.startswith('nm_') and d.name not in material_ids:
                material_ids.append(d.name)

    total_events = 0
    for mid in material_ids:
        if not mid:
            continue
        print(f"  处理: {mid}")
        count = ingest_novel(conn, mid)
        total_events += count
        print(f"    事件: {count}")

    return len(material_ids), total_events


def main():
    parser = argparse.ArgumentParser(description='从事件 YAML 构建 SQLite 索引')
    parser.add_argument('--material', help='仅重建指定素材', default=None)
    parser.add_argument('--incremental', help='增量更新指定素材', default=None)
    args = parser.parse_args()

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    if args.incremental:
        if not DB_PATH.exists():
            print("ERROR: 数据库不存在，请先全量构建", file=sys.stderr)
            sys.exit(1)
        conn = sqlite3.connect(str(DB_PATH))
        create_schema(conn)
        print(f"增量更新: {args.incremental}")
        count = ingest_novel(conn, args.incremental)
        print(f"✅ 更新完成，事件: {count}")
        conn.close()
        return

    conn = sqlite3.connect(str(DB_PATH))
    create_schema(conn)

    if args.material:
        print(f"重建: {args.material}")
        count = ingest_novel(conn, args.material)
        print(f"✅ 重建完成，事件: {count}")
    else:
        print("全量重建数据库...")
        novel_count, event_count = build_all(conn)
        print(f"\n✅ 全量重建完成")
        print(f"  小说: {novel_count}")
        print(f"  事件: {event_count}")

    # Print DB stats
    cursor = conn.execute("SELECT COUNT(*) FROM novels")
    n_novels = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM events")
    n_events = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM event_tags")
    n_tags = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM characters")
    n_chars = cursor.fetchone()[0]

    print(f"\n📊 数据库统计:")
    print(f"  小说: {n_novels}")
    print(f"  事件: {n_events}")
    print(f"  标签记录: {n_tags}")
    print(f"  人物: {n_chars}")
    print(f"  文件: {DB_PATH}")

    conn.close()


if __name__ == '__main__':
    main()
