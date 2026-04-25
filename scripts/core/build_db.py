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


def _normalize_tension(raw: dict, flat: dict) -> dict:
    """统一 tension 字段，兼容 tension_peak / nested emotion。"""
    if 'tension' in flat and flat['tension'] is not None:
        return flat
    if 'tension_peak' in flat and flat['tension_peak'] is not None:
        flat['tension'] = flat['tension_peak']
        return flat

    emotion = raw.get('emotion')
    if isinstance(emotion, dict):
        if emotion.get('tension') is not None:
            flat['tension'] = emotion['tension']
        elif emotion.get('tension_peak') is not None:
            flat['tension'] = emotion['tension_peak']
    return flat


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

    flat = _normalize_tension(raw, flat)

    if 'characters' in flat and isinstance(flat['characters'], list):
        first = flat['characters'][0] if flat['characters'] else None
        if isinstance(first, dict) and 'name' in first:
            flat['characters'] = [c['name'] for c in flat['characters'] if isinstance(c, dict)]

    if 'moral_spectrum' in flat and isinstance(flat['moral_spectrum'], list):
        flat['moral_spectrum'] = flat['moral_spectrum'][0] if flat['moral_spectrum'] else ''

    return flat


def create_schema(conn: sqlite3.Connection):
    """Create database schema with folder structure support."""
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

        -- Characters table (supports folder structure)
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id TEXT NOT NULL,
            name TEXT NOT NULL,
            role TEXT,                    -- protagonist/antagonist/supporting/minor
            archetype TEXT,
            moral_spectrum TEXT,
            arc_summary TEXT,
            narrative_function TEXT,
            fatal_flaw TEXT,
            obsession TEXT,
            soft_spot TEXT,
            misbelief TEXT,
            contrast_habit TEXT,
            tragedy_trigger TEXT,
            first_appearance TEXT,
            last_appearance TEXT,
            appearance_count INTEGER DEFAULT 0,
            file_path TEXT,               -- profiles/{name}.yaml or NULL for minor
            description TEXT,
            FOREIGN KEY (material_id) REFERENCES novels(material_id)
        );

        -- Character-Event cross-reference (双向引用)
        CREATE TABLE IF NOT EXISTS character_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id TEXT NOT NULL,
            character_name TEXT NOT NULL,
            event_id TEXT NOT NULL,
            chapter TEXT,
            significance TEXT,
            role_in_event TEXT,
            FOREIGN KEY (material_id) REFERENCES novels(material_id)
        );

        CREATE TABLE IF NOT EXISTS event_characters (
            event_id TEXT NOT NULL,
            material_id TEXT NOT NULL,
            character_name TEXT NOT NULL,
            PRIMARY KEY (event_id, material_id, character_name),
            FOREIGN KEY (event_id, material_id) REFERENCES events(event_id, material_id)
        );

        -- Factions table (势力组织)
        CREATE TABLE IF NOT EXISTS factions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT,
            territory TEXT,
            stance TEXT,
            power_level TEXT,
            importance TEXT,              -- primary/secondary/minor
            first_appearance TEXT,
            file_path TEXT,               -- factions/{name}.yaml or NULL
            description TEXT,
            FOREIGN KEY (material_id) REFERENCES novels(material_id)
        );

        -- Faction-Event cross-reference
        CREATE TABLE IF NOT EXISTS faction_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id TEXT NOT NULL,
            faction_name TEXT NOT NULL,
            event_id TEXT NOT NULL,
            chapter TEXT,
            significance TEXT,
            FOREIGN KEY (material_id) REFERENCES novels(material_id)
        );

        -- Regions table (地理空间)
        CREATE TABLE IF NOT EXISTS regions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT,                    -- 星球/城市/秘境/国度/建筑/概念空间
            importance TEXT,              -- primary/secondary/thematic/background
            first_appearance TEXT,
            file_path TEXT,               -- geography/{name}.yaml or NULL
            description TEXT,
            significance TEXT,
            FOREIGN KEY (material_id) REFERENCES novels(material_id)
        );

        -- Region-Event cross-reference
        CREATE TABLE IF NOT EXISTS region_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id TEXT NOT NULL,
            region_name TEXT NOT NULL,
            event_id TEXT NOT NULL,
            chapter TEXT,
            role TEXT,                    -- 场景/转折点/战场/...
            FOREIGN KEY (material_id) REFERENCES novels(material_id)
        );

        -- Hooks table (钩子网络)
        CREATE TABLE IF NOT EXISTS hooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id TEXT NOT NULL,
            hook_id TEXT NOT NULL,
            hook_type TEXT,
            crossing_type TEXT,
            planted_event TEXT,
            planted_chapter TEXT,
            harvested_event TEXT,
            harvested_chapter TEXT,
            confidence TEXT,              -- high/medium/low
            description TEXT,
            FOREIGN KEY (material_id) REFERENCES novels(material_id)
        );

        -- Indexes
        CREATE INDEX IF NOT EXISTS idx_event_tags_dim_val ON event_tags(dimension, value);
        CREATE INDEX IF NOT EXISTS idx_event_tags_material ON event_tags(material_id);
        CREATE INDEX IF NOT EXISTS idx_event_tags_event ON event_tags(event_id);
        CREATE INDEX IF NOT EXISTS idx_events_material ON events(material_id);
        CREATE INDEX IF NOT EXISTS idx_events_tension ON events(tension);
        CREATE INDEX IF NOT EXISTS idx_characters_material ON characters(material_id);
        CREATE INDEX IF NOT EXISTS idx_characters_name ON characters(name);
        CREATE INDEX IF NOT EXISTS idx_characters_file ON characters(file_path);
        CREATE INDEX IF NOT EXISTS idx_event_characters_name ON event_characters(character_name);
        CREATE INDEX IF NOT EXISTS idx_character_events_char ON character_events(character_name);
        CREATE INDEX IF NOT EXISTS idx_character_events_event ON character_events(event_id);
        CREATE INDEX IF NOT EXISTS idx_factions_material ON factions(material_id);
        CREATE INDEX IF NOT EXISTS idx_factions_name ON factions(name);
        CREATE INDEX IF NOT EXISTS idx_faction_events_faction ON faction_events(faction_name);
        CREATE INDEX IF NOT EXISTS idx_regions_material ON regions(material_id);
        CREATE INDEX IF NOT EXISTS idx_regions_name ON regions(name);
        CREATE INDEX IF NOT EXISTS idx_region_events_region ON region_events(region_name);
        CREATE INDEX IF NOT EXISTS idx_hooks_material ON hooks(material_id);
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
    """Load character data from characters/ folder structure.

    Supports both:
    - Folder structure: characters/_index.yaml + profiles/*.yaml
    - Legacy single file: characters.yaml
    """
    chars_dir = base_dir / "characters"
    chars_file = base_dir / "characters.yaml"

    characters = []

    # Folder structure (preferred)
    if chars_dir.exists() and chars_dir.is_dir():
        index_path = chars_dir / "_index.yaml"
        if index_path.exists():
            with open(index_path, 'r', encoding='utf-8') as f:
                index_data = yaml.safe_load(f) or {}

            roster = index_data.get('roster', {})
            # Process each role category
            for role_category in ['protagonists', 'antagonists', 'supporting', 'minor']:
                for char in roster.get(role_category, []) or []:
                    if not isinstance(char, dict):
                        continue
                    char_entry = dict(char)
                    char_entry['role'] = role_category.rstrip('s')  # protagonist/antagonist/supporting/minor

                    # Load detailed profile if file exists
                    file_path = char.get('file')
                    if file_path:
                        profile_path = chars_dir / file_path
                        if profile_path.exists():
                            with open(profile_path, 'r', encoding='utf-8') as f:
                                profile_data = yaml.safe_load(f) or {}
                            # Merge profile data
                            char_entry.update(profile_data)
                            psychology = profile_data.get('psychology', {}) or {}
                            for key in ['fatal_flaw', 'obsession', 'soft_spot', 'misbelief', 'contrast_habit', 'tragedy_trigger']:
                                if key in psychology and key not in char_entry:
                                    char_entry[key] = psychology[key]

                    characters.append(char_entry)

    # Legacy single file fallback
    elif chars_file.exists():
        with open(chars_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        characters = data.get('roster', data.get('characters', []))

    return characters


def load_novel_factions(base_dir: Path) -> list:
    """Load faction data from worldbuilding/factions/ folder.

    Supports both:
    - Folder structure: worldbuilding/factions/_index.yaml + *.yaml
    - Legacy: worldbuilding.yaml (factions section)
    """
    wb_dir = base_dir / "worldbuilding"
    wb_file = base_dir / "worldbuilding.yaml"
    factions_dir = wb_dir / "factions"
    factions_file = wb_dir / "factions.yaml"

    factions = []

    # Folder structure (preferred)
    if factions_dir.exists() and factions_dir.is_dir():
        index_path = factions_dir / "_index.yaml"
        if index_path.exists():
            with open(index_path, 'r', encoding='utf-8') as f:
                index_data = yaml.safe_load(f) or {}

            factions_index = index_data.get('factions_index', [])
            for fac in factions_index:
                if not isinstance(fac, dict):
                    continue
                fac_entry = dict(fac)

                # Load detailed file if exists
                file_path = fac.get('file')
                if file_path:
                    fac_file_path = factions_dir / file_path
                    if fac_file_path.exists():
                        with open(fac_file_path, 'r', encoding='utf-8') as f:
                            fac_data = yaml.safe_load(f) or {}
                        fac_entry.update(fac_data)

                factions.append(fac_entry)

    # Single file factions.yaml
    elif factions_file.exists():
        with open(factions_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        factions = data.get('factions', [])

    # Legacy worldbuilding.yaml
    elif wb_file.exists() and not wb_dir.exists():
        with open(wb_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        factions = data.get('factions', {}).get('factions', []) if isinstance(data.get('factions'), dict) else data.get('factions', [])

    return factions


def load_novel_regions(base_dir: Path) -> list:
    """Load region/geography data from worldbuilding/geography/ folder.

    Supports both:
    - Folder structure: worldbuilding/geography/_index.yaml + *.yaml
    - Legacy: worldbuilding.yaml (geography section)
    """
    wb_dir = base_dir / "worldbuilding"
    wb_file = base_dir / "worldbuilding.yaml"
    geo_dir = wb_dir / "geography"
    geo_file = wb_dir / "geography.yaml"

    regions = []

    # Folder structure (preferred)
    if geo_dir.exists() and geo_dir.is_dir():
        index_path = geo_dir / "_index.yaml"
        if index_path.exists():
            with open(index_path, 'r', encoding='utf-8') as f:
                index_data = yaml.safe_load(f) or {}

            regions_index = index_data.get('regions_index', [])
            for reg in regions_index:
                if not isinstance(reg, dict):
                    continue
                reg_entry = dict(reg)

                # Load detailed file if exists
                file_path = reg.get('file')
                if file_path:
                    reg_file_path = geo_dir / file_path
                    if reg_file_path.exists():
                        with open(reg_file_path, 'r', encoding='utf-8') as f:
                            reg_data = yaml.safe_load(f) or {}
                        reg_entry.update(reg_data)

                regions.append(reg_entry)

    # Single file geography.yaml
    elif geo_file.exists():
        with open(geo_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        regions = data.get('regions', [])

    # Legacy worldbuilding.yaml
    elif wb_file.exists() and not wb_dir.exists():
        with open(wb_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        geo = data.get('geography', {})
        regions = geo.get('regions', []) if isinstance(geo, dict) else []

    return regions


def load_novel_hooks(base_dir: Path) -> list:
    """Load hooks data from outline/hooks_network.yaml."""
    outline_dir = base_dir / "outline"
    hooks_file = outline_dir / "hooks_network.yaml"

    hooks = []

    if hooks_file.exists():
        with open(hooks_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        # Process chains (verified hooks)
        for chain in data.get('chains', []) or []:
            if isinstance(chain, dict):
                hooks.append(chain)

        # Process pending hooks
        for pending in data.get('pending', []) or []:
            if isinstance(pending, dict):
                pending['confidence'] = pending.get('confidence', 'low')
                hooks.append(pending)

    return hooks


def ingest_novel(conn: sqlite3.Connection, material_id: str):
    """Ingest one novel's data into SQLite (supports folder structure)."""
    base_dir = Path(f"data/novels/{material_id}")
    events_dir = base_dir / "events"

    if not base_dir.exists():
        print(f"  SKIP: {base_dir} 不存在", file=sys.stderr)
        return 0

    # Clear existing data for this novel
    conn.execute("DELETE FROM event_tags WHERE material_id = ?", (material_id,))
    conn.execute("DELETE FROM event_characters WHERE material_id = ?", (material_id,))
    conn.execute("DELETE FROM character_events WHERE material_id = ?", (material_id,))
    conn.execute("DELETE FROM faction_events WHERE material_id = ?", (material_id,))
    conn.execute("DELETE FROM region_events WHERE material_id = ?", (material_id,))
    conn.execute("DELETE FROM events WHERE material_id = ?", (material_id,))
    conn.execute("DELETE FROM characters WHERE material_id = ?", (material_id,))
    conn.execute("DELETE FROM factions WHERE material_id = ?", (material_id,))
    conn.execute("DELETE FROM regions WHERE material_id = ?", (material_id,))
    conn.execute("DELETE FROM hooks WHERE material_id = ?", (material_id,))
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
            tension = _normalize_tension(event, dict(event)).get('tension', 0)
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

    # Load and insert characters (folder structure supported)
    characters = load_novel_characters(base_dir)
    for char in characters:
        if not isinstance(char, dict):
            continue
        psychology = char.get('psychology', {})
        if not isinstance(psychology, dict):
            psychology = {}

        # Get file path for cross-reference
        file_path = char.get('file', '')
        if file_path:
            file_path = f"characters/{file_path}"

        conn.execute(
            """INSERT INTO characters
               (material_id, name, role, archetype, moral_spectrum,
                arc_summary, narrative_function, fatal_flaw, obsession, soft_spot, misbelief,
                contrast_habit, tragedy_trigger, first_appearance, last_appearance,
                appearance_count, file_path, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                psychology.get('contrast_habit', ''),
                psychology.get('tragedy_trigger', ''),
                char.get('first_appearance', ''),
                char.get('last_appearance', ''),
                char.get('appearance_count', 0),
                file_path,
                char.get('description', char.get('brief_description', '')),
            )
        )

        # Insert key_events cross-reference
        key_events = char.get('key_events', []) or []
        for ke in key_events:
            if isinstance(ke, dict) and ke.get('event_id'):
                conn.execute(
                    """INSERT INTO character_events
                       (material_id, character_name, event_id, chapter, significance, role_in_event)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        material_id,
                        char.get('name', ''),
                        ke.get('event_id', ''),
                        str(ke.get('chapter', '')),
                        ke.get('significance', ''),
                        ke.get('role_in_event', ''),
                    )
                )

    # Load and insert factions
    factions = load_novel_factions(base_dir)
    for fac in factions:
        if not isinstance(fac, dict):
            continue

        file_path = fac.get('file', '')
        if file_path:
            file_path = f"worldbuilding/factions/{file_path}"

        conn.execute(
            """INSERT INTO factions
               (material_id, name, type, territory, stance, power_level, importance,
                first_appearance, file_path, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                material_id,
                fac.get('name', ''),
                fac.get('type', ''),
                fac.get('territory', ''),
                fac.get('stance', ''),
                fac.get('power_level', ''),
                fac.get('importance', ''),
                fac.get('first_appearance', ''),
                file_path,
                fac.get('description', ''),
            )
        )

        # Insert key_events cross-reference
        key_events = fac.get('key_events', []) or []
        for ke in key_events:
            if isinstance(ke, dict) and ke.get('event_id'):
                conn.execute(
                    """INSERT INTO faction_events
                       (material_id, faction_name, event_id, chapter, significance)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        material_id,
                        fac.get('name', ''),
                        ke.get('event_id', ''),
                        str(ke.get('chapter', '')),
                        ke.get('significance', ''),
                    )
                )

    # Load and insert regions
    regions = load_novel_regions(base_dir)
    for reg in regions:
        if not isinstance(reg, dict):
            continue

        file_path = reg.get('file', '')
        if file_path:
            file_path = f"worldbuilding/geography/{file_path}"

        conn.execute(
            """INSERT INTO regions
               (material_id, name, type, importance, first_appearance, file_path, description, significance)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                material_id,
                reg.get('name', ''),
                reg.get('type', ''),
                reg.get('importance', ''),
                reg.get('first_appearance', ''),
                file_path,
                reg.get('description', ''),
                reg.get('significance', ''),
            )
        )

        # Insert key_events cross-reference
        key_events = reg.get('key_events', []) or []
        for ke in key_events:
            if isinstance(ke, dict) and ke.get('event_id'):
                conn.execute(
                    """INSERT INTO region_events
                       (material_id, region_name, event_id, chapter, role)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        material_id,
                        reg.get('name', ''),
                        ke.get('event_id', ''),
                        str(ke.get('chapter', '')),
                        ke.get('role', ''),
                    )
                )

    # Load and insert hooks
    hooks = load_novel_hooks(base_dir)
    for hook in hooks:
        if not isinstance(hook, dict):
            continue

        planted = hook.get('planted', {}) or {}
        harvested = hook.get('harvested', {}) or {}

        conn.execute(
            """INSERT INTO hooks
               (material_id, hook_id, hook_type, crossing_type,
                planted_event, planted_chapter, harvested_event, harvested_chapter,
                confidence, description)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                material_id,
                hook.get('hook_id', ''),
                hook.get('hook_type', ''),
                hook.get('crossing_type', ''),
                planted.get('event', ''),
                str(planted.get('chapter', '')),
                harvested.get('event', ''),
                str(harvested.get('chapter', '')),
                hook.get('confidence', ''),
                planted.get('description', hook.get('detail', '')),
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
    cursor = conn.execute("SELECT COUNT(*) FROM character_events")
    n_char_events = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM factions")
    n_factions = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM faction_events")
    n_faction_events = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM regions")
    n_regions = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM region_events")
    n_region_events = cursor.fetchone()[0]
    cursor = conn.execute("SELECT COUNT(*) FROM hooks")
    n_hooks = cursor.fetchone()[0]

    print(f"\n📊 数据库统计:")
    print(f"  小说: {n_novels}")
    print(f"  事件: {n_events}")
    print(f"  标签记录: {n_tags}")
    print(f"  人物: {n_chars} (交叉引用: {n_char_events})")
    print(f"  势力: {n_factions} (交叉引用: {n_faction_events})")
    print(f"  地区: {n_regions} (交叉引用: {n_region_events})")
    print(f"  钩子: {n_hooks}")
    print(f"  文件: {DB_PATH}")

    conn.close()


if __name__ == '__main__':
    main()
