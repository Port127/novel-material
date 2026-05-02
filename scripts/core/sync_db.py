#!/usr/bin/env python
"""YAML → PostgreSQL 数据同步工具。"""
import os
import sys
import json
import yaml
import psycopg2
import psycopg2.extras
from pathlib import Path
from datetime import datetime

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv()

from scripts.core.paths import NOVELS_DIR
from scripts.utils.schema_validator import validate_meta, validate_chapters

DATABASE_URL = os.getenv("DATABASE_URL")


def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def _precheck_schema(material_id: str) -> bool:
    """同步前执行 schema 预检，发现错误则打印并返回 False。"""
    meta_errs = validate_meta(material_id)
    chapter_errs = validate_chapters(material_id)
    all_errs = meta_errs + chapter_errs

    if all_errs:
        print(f"[sync_db] Schema 预检失败，共 {len(all_errs)} 个错误，终止同步：")
        for e in all_errs:
            print(f"  {e}")
        return False

    print(f"[sync_db] Schema 预检通过：{material_id}")
    return True


def sync_novel(material_id):
    """同步单本小说到数据库（同步前执行 schema 预检）。"""
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        print(f"跳过: 目录不存在 {novel_dir}")
        return

    if not _precheck_schema(material_id):
        raise ValueError(f"Schema 预检未通过，中止同步：{material_id}")

    conn = get_db_connection()
    try:
        _sync_meta(conn, novel_dir, material_id)
        _sync_chapters(conn, novel_dir, material_id)
        _sync_outline(conn, novel_dir, material_id)
        _sync_characters(conn, novel_dir, material_id)
        _sync_worldbuilding(conn, novel_dir, material_id)
        conn.commit()
        print(f"同步完成: {material_id}")
    except Exception as e:
        conn.rollback()
        print(f"同步失败，已回滚: {e}")
        raise
    finally:
        conn.close()


def _sync_meta(conn, novel_dir, material_id):
    """同步 meta.yaml → novels 表。"""
    meta_file = novel_dir / "meta.yaml"
    if not meta_file.exists():
        return

    with open(meta_file, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f)

    tags_value = json.dumps(meta.get("tags", {}), ensure_ascii=False) if meta.get("tags") else None

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO novels (
                material_id, name, author, genre, word_count,
                chapter_count, status, tags, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (material_id) DO UPDATE SET
                name = EXCLUDED.name,
                author = EXCLUDED.author,
                genre = EXCLUDED.genre,
                word_count = EXCLUDED.word_count,
                chapter_count = EXCLUDED.chapter_count,
                status = EXCLUDED.status,
                tags = EXCLUDED.tags,
                updated_at = EXCLUDED.updated_at
        """, (
            meta.get("material_id"),
            meta.get("name"),
            meta.get("author"),
            meta.get("genre", []),
            meta.get("word_count"),
            meta.get("chapter_count"),
            meta.get("status"),
            tags_value,
            meta.get("created_at"),
            meta.get("updated_at"),
        ))
    print(f"  已同步小说元信息: {meta.get('name')}")


def _sync_chapters(conn, novel_dir, material_id):
    """同步 chapters.yaml + chapter_embeddings.npz → chapters 表，按批次提交。"""
    chapters_file = novel_dir / "chapters.yaml"
    if not chapters_file.exists():
        return

    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters = yaml.safe_load(f) or []

    if not chapters:
        return

    # 加载向量（可选，不存在则不写入向量字段）
    # 优先读 .npz（新格式），兜底读旧 .yaml（向后兼容）
    embeddings: dict = {}
    embeddings_npz = novel_dir / "chapter_embeddings.npz"
    embeddings_yaml = novel_dir / "chapter_embeddings.yaml"
    if embeddings_npz.exists():
        import numpy as np
        data = np.load(str(embeddings_npz))
        chapters_arr = data["chapters"]
        vectors_arr = data["vectors"]
        embeddings = {int(ch): vectors_arr[i].tolist() for i, ch in enumerate(chapters_arr)}
        print(f"  加载向量 (.npz): {len(embeddings)} 章")
    elif embeddings_yaml.exists():
        with open(embeddings_yaml, "r", encoding="utf-8") as f:
            embeddings = yaml.safe_load(f) or {}
        print(f"  加载向量 (.yaml 旧格式): {len(embeddings)} 章")

    BATCH_SIZE = 50
    synced = 0

    for i in range(0, len(chapters), BATCH_SIZE):
        batch = chapters[i:i + BATCH_SIZE]
        with conn.cursor() as cur:
            for ch in batch:
                ch_num = ch.get("chapter")
                vec = embeddings.get(ch_num)

                if vec is not None:
                    cur.execute("""
                        INSERT INTO chapters (
                            material_id, chapter, title, summary, word_count,
                            tension_level, pacing, setting, key_plot_point,
                            chapter_functions, characters_appear, summary_embedding
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (material_id, chapter) DO UPDATE SET
                            title = EXCLUDED.title,
                            summary = EXCLUDED.summary,
                            word_count = EXCLUDED.word_count,
                            tension_level = EXCLUDED.tension_level,
                            pacing = EXCLUDED.pacing,
                            setting = EXCLUDED.setting,
                            key_plot_point = EXCLUDED.key_plot_point,
                            chapter_functions = EXCLUDED.chapter_functions,
                            characters_appear = EXCLUDED.characters_appear,
                            summary_embedding = EXCLUDED.summary_embedding
                    """, (
                        material_id, ch_num,
                        ch.get("title"), ch.get("summary"), ch.get("word_count"),
                        ch.get("tension_level"), ch.get("pacing"),
                        ch.get("setting", []), ch.get("key_plot_point"),
                        ch.get("chapter_function", ch.get("chapter_functions", [])),
                        ch.get("characters_appear", []),
                        vec,
                    ))
                else:
                    cur.execute("""
                        INSERT INTO chapters (
                            material_id, chapter, title, summary, word_count,
                            tension_level, pacing, setting, key_plot_point,
                            chapter_functions, characters_appear
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (material_id, chapter) DO UPDATE SET
                            title = EXCLUDED.title,
                            summary = EXCLUDED.summary,
                            word_count = EXCLUDED.word_count,
                            tension_level = EXCLUDED.tension_level,
                            pacing = EXCLUDED.pacing,
                            setting = EXCLUDED.setting,
                            key_plot_point = EXCLUDED.key_plot_point,
                            chapter_functions = EXCLUDED.chapter_functions,
                            characters_appear = EXCLUDED.characters_appear
                    """, (
                        material_id, ch_num,
                        ch.get("title"), ch.get("summary"), ch.get("word_count"),
                        ch.get("tension_level"), ch.get("pacing"),
                        ch.get("setting", []), ch.get("key_plot_point"),
                        ch.get("chapter_function", ch.get("chapter_functions", [])),
                        ch.get("characters_appear", []),
                    ))
        synced += len(batch)
        print(f"  已同步章节 {synced}/{len(chapters)}")

    print(f"  章节同步完成: 共 {len(chapters)} 章，其中 {len(embeddings)} 章含向量")


def _sync_outline(conn, novel_dir, material_id):
    """同步 outline/_index.yaml → novels 表，outline/structure.yaml → outline_sequences/beats 表。"""
    # 1. _index.yaml → novels 表元信息
    outline_index = novel_dir / "outline" / "_index.yaml"
    if outline_index.exists():
        with open(outline_index, "r", encoding="utf-8") as f:
            index_data = yaml.safe_load(f) or {}

        summary = index_data.get("structure_summary", {})
        hooks = index_data.get("hooks_stats", {})
        subplots = index_data.get("subplots_stats", {})

        theme = index_data.get("theme", [])
        tone = index_data.get("tone", [])
        if isinstance(theme, str):
            theme = [theme]
        if isinstance(tone, str):
            tone = [tone]

        with conn.cursor() as cur:
            cur.execute("""
                UPDATE novels SET
                    premise = %s,
                    theme = %s,
                    tone = %s,
                    act_count = %s,
                    sequence_count = %s,
                    hook_count = %s,
                    subplot_count = %s
                WHERE material_id = %s
            """, (
                index_data.get("premise"),
                theme,
                tone,
                summary.get("acts"),
                summary.get("sequences"),
                hooks.get("total"),
                subplots.get("count"),
                material_id,
            ))
        print(f"  已同步大纲元信息（premise/theme/tone）")

    # 2. structure.yaml → outline_sequences + outline_beats 表
    structure_file = novel_dir / "outline" / "structure.yaml"
    if not structure_file.exists():
        return

    with open(structure_file, "r", encoding="utf-8") as f:
        structure_data = yaml.safe_load(f) or {}

    acts = structure_data.get("acts", [])
    if not acts:
        return

    # 先判断 structure_type
    structure_type = structure_data.get("structure_pattern", {}).get("type")

    seq_count = 0
    beat_count = 0
    with conn.cursor() as cur:
        # 更新 novels 的 structure_type
        if structure_type:
            cur.execute(
                "UPDATE novels SET structure_type = %s WHERE material_id = %s",
                (structure_type, material_id)
            )

        # 清除旧数据，重新写入（幂等）
        cur.execute("DELETE FROM outline_beats WHERE material_id = %s", (material_id,))
        cur.execute("DELETE FROM outline_sequences WHERE material_id = %s", (material_id,))

        for act_data in acts:
            act_num = act_data.get("act")
            for seq_data in act_data.get("sequences", []):
                seq_num = seq_data.get("sequence")
                chapters_range = seq_data.get("chapters", [None, None])
                chapters_start = chapters_range[0] if len(chapters_range) > 0 else None
                chapters_end = chapters_range[1] if len(chapters_range) > 1 else None

                cur.execute("""
                    INSERT INTO outline_sequences (
                        material_id, act, sequence, title,
                        chapters_start, chapters_end, description
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    material_id, act_num, seq_num,
                    seq_data.get("title"),
                    chapters_start, chapters_end,
                    seq_data.get("description"),
                ))
                seq_count += 1

                for beat_data in seq_data.get("beats", []):
                    cur.execute("""
                        INSERT INTO outline_beats (
                            material_id, act, sequence, beat,
                            title, chapter, description, tension
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        material_id, act_num, seq_num,
                        beat_data.get("beat"),
                        beat_data.get("title"),
                        beat_data.get("chapter"),
                        beat_data.get("description"),
                        beat_data.get("tension"),
                    ))
                    beat_count += 1

    print(f"  已同步大纲结构：{seq_count} 个序列，{beat_count} 个节拍")


def _sync_characters(conn, novel_dir, material_id):
    """同步 characters/profiles/*.yaml → characters + character_appearances 表。"""
    profiles_dir = novel_dir / "characters" / "profiles"
    if not profiles_dir.exists():
        return

    profile_files = list(profiles_dir.glob("*.yaml"))
    if not profile_files:
        return

    with conn.cursor() as cur:
        for profile_file in profile_files:
            with open(profile_file, "r", encoding="utf-8") as pf:
                profile = yaml.safe_load(pf)

            if not profile:
                continue

            psychology_value = json.dumps(
                profile.get("psychology", {}), ensure_ascii=False
            )
            char_name = profile.get("name") or profile.get("character_name")

            cur.execute("""
                INSERT INTO characters (
                    material_id, name, role, archetype,
                    moral_spectrum, arc_summary, narrative_function,
                    psychology, first_appearance, last_appearance,
                    appearance_count, file_path, description
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (material_id, name) DO UPDATE SET
                    role = EXCLUDED.role,
                    archetype = EXCLUDED.archetype,
                    moral_spectrum = EXCLUDED.moral_spectrum,
                    arc_summary = EXCLUDED.arc_summary,
                    narrative_function = EXCLUDED.narrative_function,
                    psychology = EXCLUDED.psychology,
                    first_appearance = EXCLUDED.first_appearance,
                    last_appearance = EXCLUDED.last_appearance,
                    appearance_count = EXCLUDED.appearance_count,
                    description = EXCLUDED.description,
                    file_path = EXCLUDED.file_path
            """, (
                material_id,
                char_name,
                profile.get("role"),
                profile.get("archetype"),
                profile.get("moral_spectrum"),
                profile.get("arc_summary"),
                profile.get("narrative_function"),
                psychology_value,
                profile.get("first_appearance"),
                profile.get("last_appearance"),
                profile.get("appearance_count", 0),
                str(profile_file),
                profile.get("description"),
            ))

    print(f"  已同步人物: {len(profile_files)} 个")

    # 从 chapters.yaml 的 characters_appear 字段提取出场记录
    _sync_character_appearances(conn, novel_dir, material_id)


def _sync_character_appearances(conn, novel_dir, material_id):
    """从 chapters.yaml 提取人物出场记录 → character_appearances 表。"""
    chapters_file = novel_dir / "chapters.yaml"
    if not chapters_file.exists():
        return

    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters = yaml.safe_load(f) or []

    with conn.cursor() as cur:
        # 先清除旧记录（幂等）
        cur.execute("DELETE FROM character_appearances WHERE material_id = %s", (material_id,))

        for ch in chapters:
            ch_num = ch.get("chapter")
            for char_name in ch.get("characters_appear", []):
                cur.execute("""
                    INSERT INTO character_appearances (
                        material_id, character_name, chapter, significance
                    ) VALUES (%s, %s, %s, %s)
                """, (material_id, char_name, ch_num, "major"))

    print(f"  已同步人物出场记录")


def _sync_worldbuilding(conn, novel_dir, material_id):
    """同步 worldbuilding/ → worldbuilding_entities 表。"""
    wb_index = novel_dir / "worldbuilding" / "_index.yaml"
    if not wb_index.exists():
        return

    synced = 0
    with conn.cursor() as cur:
        for entity_type in ["factions", "regions", "power_systems"]:
            entity_file = novel_dir / "worldbuilding" / f"{entity_type}.yaml"
            if not entity_file.exists():
                continue

            with open(entity_file, "r", encoding="utf-8") as ef:
                entities = yaml.safe_load(ef) or []
            if isinstance(entities, dict):
                entities = [entities]

            for entity in entities:
                if not isinstance(entity, dict):
                    continue
                properties_value = json.dumps(
                    entity.get("properties", {}), ensure_ascii=False
                )
                cur.execute("""
                    INSERT INTO worldbuilding_entities (
                        material_id, entity_type, name, description,
                        properties, first_appearance, importance
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (material_id, entity_type, name) DO UPDATE SET
                        description = EXCLUDED.description,
                        properties = EXCLUDED.properties,
                        first_appearance = EXCLUDED.first_appearance,
                        importance = EXCLUDED.importance
                """, (
                    material_id,
                    entity_type,
                    entity.get("name", ""),
                    entity.get("description", ""),
                    properties_value,
                    entity.get("first_appearance"),
                    entity.get("importance", "secondary"),
                ))
                synced += 1

    print(f"  已同步世界观实体: {synced} 个")


def sync_all():
    """同步所有小说。"""
    if not NOVELS_DIR.exists():
        print("没有小说目录")
        return

    for novel_dir in sorted(NOVELS_DIR.iterdir()):
        if novel_dir.is_dir() and novel_dir.name.startswith("nm_"):
            sync_novel(novel_dir.name)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python sync_db.py <material_id> 或 python sync_db.py all")
        sys.exit(1)

    if sys.argv[1] == "all":
        sync_all()
    else:
        sync_novel(sys.argv[1])
