#!/usr/bin/env python
"""YAML → PostgreSQL 数据同步工具。"""
import os
import sys
import yaml
import psycopg2
import psycopg2.extras
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def sync_novel(material_id):
    """同步单本小说到数据库。"""
    novel_dir = Path("data/novels") / material_id
    if not novel_dir.exists():
        print(f"跳过: 目录不存在 {novel_dir}")
        return

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            # 1. 同步 meta.yaml → novels 表
            meta_file = novel_dir / "meta.yaml"
            if meta_file.exists():
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = yaml.safe_load(f)

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
                    yaml.dump(meta.get("tags", {})) if meta.get("tags") else None,
                    meta.get("created_at"),
                    meta.get("updated_at")
                ))
                print(f"已同步小说: {meta.get('name')}")

            # 2. 同步 chapters.yaml → chapters 表
            chapters_file = novel_dir / "chapters.yaml"
            if chapters_file.exists():
                with open(chapters_file, "r", encoding="utf-8") as f:
                    chapters = yaml.safe_load(f) or []

                for ch in chapters:
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
                        material_id,
                        ch.get("chapter"),
                        ch.get("title"),
                        ch.get("summary"),
                        ch.get("word_count"),
                        ch.get("tension_level"),
                        ch.get("pacing"),
                        ch.get("setting", []),
                        ch.get("key_plot_point"),
                        ch.get("chapter_function", ch.get("chapter_functions", [])),
                        ch.get("characters_appear", [])
                    ))

                print(f"已同步 {len(chapters)} 章")

            # 3. 同步 outline → outline_sequences + outline_beats
            outline_index = novel_dir / "outline" / "_index.yaml"
            if outline_index.exists():
                with open(outline_index, "r", encoding="utf-8") as f:
                    outline_data = yaml.safe_load(f) or {}

                # 更新 novels 表中的大纲元信息
                if outline_data.get("structure_type"):
                    cur.execute("""
                        UPDATE novels SET
                            structure_type = %s,
                            act_count = %s,
                            sequence_count = %s,
                            hook_count = %s,
                            subplot_count = %s
                        WHERE material_id = %s
                    """, (
                        outline_data.get("structure_type"),
                        outline_data.get("act_count"),
                        outline_data.get("sequence_count"),
                        outline_data.get("hook_count"),
                        outline_data.get("subplot_count"),
                        material_id
                    ))

            # 4. 同步 characters → characters 表
            characters_index = novel_dir / "characters" / "_index.yaml"
            if characters_index.exists():
                with open(characters_index, "r", encoding="utf-8") as f:
                    char_index = yaml.safe_load(f) or {}

                profiles_dir = novel_dir / "characters" / "profiles"
                if profiles_dir.exists():
                    for profile_file in profiles_dir.glob("*.yaml"):
                        with open(profile_file, "r", encoding="utf-8") as pf:
                            profile = yaml.safe_load(pf)

                        if profile:
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
                                    arc_summary = EXCLUDED.arc_summary,
                                    psychology = EXCLUDED.psychology,
                                    appearance_count = EXCLUDED.appearance_count,
                                    updated_at = NOW()
                            """, (
                                material_id,
                                profile.get("name"),
                                profile.get("role"),
                                profile.get("archetype"),
                                profile.get("moral_spectrum"),
                                profile.get("arc_summary"),
                                profile.get("narrative_function"),
                                yaml.dump(profile.get("psychology", {})),
                                profile.get("first_appearance"),
                                profile.get("last_appearance"),
                                profile.get("appearance_count", 0),
                                str(profile_file),
                                profile.get("description")
                            ))

                print(f"已同步人物")

            # 5. 同步 worldbuilding → worldbuilding_entities 表
            wb_index = novel_dir / "worldbuilding" / "_index.yaml"
            if wb_index.exists():
                with open(wb_index, "r", encoding="utf-8") as f:
                    wb_data = yaml.safe_load(f) or {}

                for entity_type in ["factions", "regions", "power_systems"]:
                    entity_file = novel_dir / "worldbuilding" / f"{entity_type}.yaml"
                    if entity_file.exists():
                        with open(entity_file, "r", encoding="utf-8") as ef:
                            entities = yaml.safe_load(ef) or []
                            if isinstance(entities, dict):
                                entities = [entities]

                        for entity in entities:
                            if isinstance(entity, dict):
                                cur.execute("""
                                    INSERT INTO worldbuilding_entities (
                                        material_id, entity_type, name, description,
                                        properties, first_appearance, importance
                                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                                """, (
                                    material_id,
                                    entity_type,
                                    entity.get("name", ""),
                                    entity.get("description", ""),
                                    yaml.dump(entity.get("properties", {})),
                                    entity.get("first_appearance"),
                                    entity.get("importance", "secondary")
                                ))

                print(f"已同步世界观")

            conn.commit()
            print(f"同步完成: {material_id}")

    except Exception as e:
        conn.rollback()
        print(f"同步失败: {e}")
        raise
    finally:
        conn.close()

def sync_all():
    """同步所有小说。"""
    novels_dir = Path("data/novels")
    if not novels_dir.exists():
        print("没有小说目录")
        return

    for novel_dir in novels_dir.iterdir():
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
