#!/usr/bin/env python
"""
build_db.py — 从场景 YAML 构建 SQLite 索引数据库

YAML 文件仍是 source of truth，SQLite 是派生的查询加速层。
可随时从 YAML 重建，无数据损失。

用法:
    python scripts/build_db.py                         # 全量重建（所有小说）
    python scripts/build_db.py --material <id>         # 仅重建指定小说
    python scripts/build_db.py --incremental <id>      # 增量更新指定小说

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
    'scene_type', 'conflict', 'stakes',
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


def _as_list(val):
    if val is None:
        return []
    if isinstance(val, list):
        return [str(v) for v in val]
    return [str(val)]


def create_schema(conn: sqlite3.Connection):
    """Create database schema."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS novels (
            material_id TEXT PRIMARY KEY,
            name TEXT,
            author TEXT,
            status TEXT,
            total_scenes INTEGER DEFAULT 0,
            built_at TEXT
        );

        CREATE TABLE IF NOT EXISTS scenes (
            scene_id TEXT PRIMARY KEY,
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
            FOREIGN KEY (material_id) REFERENCES novels(material_id)
        );

        CREATE TABLE IF NOT EXISTS scene_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scene_id TEXT NOT NULL,
            material_id TEXT NOT NULL,
            dimension TEXT NOT NULL,
            value TEXT NOT NULL,
            FOREIGN KEY (scene_id) REFERENCES scenes(scene_id)
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

        CREATE TABLE IF NOT EXISTS scene_characters (
            scene_id TEXT NOT NULL,
            character_name TEXT NOT NULL,
            PRIMARY KEY (scene_id, character_name),
            FOREIGN KEY (scene_id) REFERENCES scenes(scene_id)
        );

        CREATE INDEX IF NOT EXISTS idx_scene_tags_dim_val ON scene_tags(dimension, value);
        CREATE INDEX IF NOT EXISTS idx_scene_tags_material ON scene_tags(material_id);
        CREATE INDEX IF NOT EXISTS idx_scene_tags_scene ON scene_tags(scene_id);
        CREATE INDEX IF NOT EXISTS idx_scenes_material ON scenes(material_id);
        CREATE INDEX IF NOT EXISTS idx_scenes_tension ON scenes(tension);
        CREATE INDEX IF NOT EXISTS idx_characters_material ON characters(material_id);
        CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(name);
        CREATE INDEX IF NOT EXISTS idx_scene_characters_name ON scene_characters(character_name);
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
    scenes_dir = base_dir / "scenes"

    if not base_dir.exists():
        print(f"  SKIP: {base_dir} 不存在", file=sys.stderr)
        return 0

    # Clear existing data for this novel
    conn.execute("DELETE FROM scene_tags WHERE material_id = ?", (material_id,))
    conn.execute("DELETE FROM scene_characters WHERE scene_id IN (SELECT scene_id FROM scenes WHERE material_id = ?)", (material_id,))
    conn.execute("DELETE FROM scenes WHERE material_id = ?", (material_id,))
    conn.execute("DELETE FROM characters WHERE material_id = ?", (material_id,))
    conn.execute("DELETE FROM novels WHERE material_id = ?", (material_id,))

    # Load meta
    meta = load_novel_meta(base_dir)
    name = meta.get('name', meta.get('title', material_id))
    author = meta.get('author', '')
    status = meta.get('status', 'unknown')

    # Load scenes
    scene_count = 0
    if scenes_dir.exists():
        scene_files = sorted(scenes_dir.glob("ch*.yaml"))

        for sf in scene_files:
            try:
                with open(sf, 'r', encoding='utf-8') as f:
                    scene = yaml.safe_load(f)
            except yaml.YAMLError:
                continue

            if not scene:
                continue

            scene_id = scene.get('id', sf.stem)
            chapter = scene.get('chapter', '')
            title = scene.get('title', '')
            summary = scene.get('summary', '')
            tension = scene.get('tension', 0)
            pacing = scene.get('pacing', '')
            pov = scene.get('pov', '')
            power_dynamic = scene.get('power_dynamic', '')
            moral_spectrum = scene.get('moral_spectrum', '')
            plot_stage = scene.get('plot_stage', '')
            scale = scene.get('scale', '')

            conn.execute(
                """INSERT OR REPLACE INTO scenes
                   (scene_id, material_id, chapter, title, summary, tension,
                    pacing, pov, power_dynamic, moral_spectrum, plot_stage, scale)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (scene_id, material_id, chapter, title, summary, tension,
                 pacing, pov, power_dynamic, moral_spectrum, plot_stage, scale)
            )

            # List tag fields → scene_tags
            for field in TAG_LIST_FIELDS:
                for val in _as_list(scene.get(field)):
                    conn.execute(
                        "INSERT INTO scene_tags (scene_id, material_id, dimension, value) VALUES (?, ?, ?, ?)",
                        (scene_id, material_id, field, val)
                    )

            # Scalar tag fields → scene_tags
            for field in TAG_SCALAR_FIELDS:
                val = scene.get(field)
                if val:
                    conn.execute(
                        "INSERT INTO scene_tags (scene_id, material_id, dimension, value) VALUES (?, ?, ?, ?)",
                        (scene_id, material_id, field, str(val))
                    )

            # Characters
            for char_name in _as_list(scene.get('characters')):
                conn.execute(
                    "INSERT OR IGNORE INTO scene_characters (scene_id, character_name) VALUES (?, ?)",
                    (scene_id, char_name)
                )

            scene_count += 1

    # Insert novel record
    conn.execute(
        "INSERT INTO novels (material_id, name, author, status, total_scenes, built_at) VALUES (?, ?, ?, ?, ?, ?)",
        (material_id, name, author, status, scene_count, datetime.now().isoformat())
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
    return scene_count


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

    total_scenes = 0
    for mid in material_ids:
        if not mid:
            continue
        print(f"  处理: {mid}")
        count = ingest_novel(conn, mid)
        total_scenes += count
        print(f"    场景: {count}")

    return len(material_ids), total_scenes


def main():
    parser = argparse.ArgumentParser(description='从场景 YAML 构建 SQLite 索引')
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
        print(f"✅ 更新完成，场景: {count}")
        conn.close()
        return

    conn = sqlite3.connect(str(DB_PATH))
    create_schema(conn)

    if args.material:
        print(f"重建: {args.material}")
        count = ingest_novel(conn, args.material)
        print(f"✅ 重建完成，场景: {count}")
    else:
        print("全量重建数据库...")
        novel_count, scene_count = build_all(conn)
        print(f"\n✅ 全量重建完成")
        print(f"  小说: {novel_count}")
        print(f"  场景: {scene_count}")

    # Print DB stats
    cursor = conn.execute("SELECT COUNT(*) FROM novels")
    n_novels = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM scenes")
    n_scenes = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM scene_tags")
    n_tags = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM characters")
    n_chars = cursor.fetchone()[0]

    print(f"\n📊 数据库统计:")
    print(f"  小说: {n_novels}")
    print(f"  场景: {n_scenes}")
    print(f"  标签记录: {n_tags}")
    print(f"  人物: {n_chars}")
    print(f"  文件: {DB_PATH}")

    conn.close()


if __name__ == '__main__':
    main()
