"""数据库同步：把本地 YAML 文件同步到 PostgreSQL。"""
import os
import sys
import json
import yaml
import psycopg2
import psycopg2.extras
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.progress import get_pipeline_logger
from novel_material.validation.schema import validate_material

logger = get_pipeline_logger()
DATABASE_URL = os.getenv("DATABASE_URL")


def get_db_connection():
    """获取数据库连接。"""
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def _precheck_schema(material_id: str) -> bool:
    """同步前检查数据格式是否正确。"""
    if validate_material(material_id, verbose=True):
        logger.info(f"Schema 预检通过: {material_id}")
        return True

    logger.error(f"Schema 预检失败，终止同步: {material_id}")
    return False


def sync_novel(material_id):
    """同步单本小说到数据库。"""
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.warning(f"跳过: 目录不存在 {novel_dir}")
        return

    if not _precheck_schema(material_id):
        raise ValueError(f"Schema 预检未通过，中止同步: {material_id}")

    conn = get_db_connection()
    try:
        _sync_meta(conn, novel_dir, material_id)
        _sync_chapters(conn, novel_dir, material_id)
        _sync_outline(conn, novel_dir, material_id)
        _sync_characters(conn, novel_dir, material_id)
        _sync_worldbuilding(conn, novel_dir, material_id)
        conn.commit()
        logger.info(f"同步完成: {material_id}")
    except Exception as e:
        conn.rollback()
        logger.error(f"同步失败，已回滚: {e}")
        raise
    finally:
        conn.close()


def _sync_meta(conn, novel_dir, material_id):
    """同步 meta.yaml 到 novels 表。"""
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
    logger.info(f"已同步小说元信息: {meta.get('name')}")


def _sync_chapters(conn, novel_dir, material_id):
    """同步章节分析结果和向量。"""
    chapters_file = novel_dir / "chapters.yaml"
    if not chapters_file.exists():
        return

    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters = yaml.safe_load(f) or []

    if not chapters:
        return

    # 加载向量
    embeddings: dict = {}
    embeddings_npz = novel_dir / "chapter_embeddings.npz"
    embeddings_yaml = novel_dir / "chapter_embeddings.yaml"

    if embeddings_npz.exists():
        import numpy as np
        data = np.load(str(embeddings_npz))
        chapters_arr = data["chapters"]
        vectors_arr = data["vectors"]
        embeddings = {int(ch): vectors_arr[i].tolist() for i, ch in enumerate(chapters_arr)}
        logger.info(f"加载向量 (.npz): {len(embeddings)} 章")
    elif embeddings_yaml.exists():
        with open(embeddings_yaml, "r", encoding="utf-8") as f:
            embeddings = yaml.safe_load(f) or {}
        logger.info(f"加载向量 (.yaml 旧格式): {len(embeddings)} 章")

    BATCH_SIZE = 50
    synced = 0

    for i in range(0, len(chapters), BATCH_SIZE):
        batch = chapters[i:i + BATCH_SIZE]
        with conn.cursor() as cur:
            for ch in batch:
                ch_num = ch.get("chapter")
                ch_type = ch.get("type", "normal")
                vec = embeddings.get(ch_num)

                if vec is not None:
                    cur.execute("""
                        INSERT INTO chapters (
                            material_id, chapter, title, type, summary, word_count,
                            tension_level, pacing, setting, key_plot_point,
                            chapter_functions, characters_appear, summary_embedding
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (material_id, chapter) DO UPDATE SET
                            title = EXCLUDED.title,
                            type = EXCLUDED.type,
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
                        ch.get("title"), ch_type, ch.get("summary"), ch.get("word_count"),
                        ch.get("tension_level"), ch.get("pacing"),
                        ch.get("setting", []), ch.get("key_plot_point"),
                        ch.get("chapter_function", ch.get("chapter_functions", [])),
                        ch.get("characters_appear", []),
                        vec,
                    ))
                else:
                    cur.execute("""
                        INSERT INTO chapters (
                            material_id, chapter, title, type, summary, word_count,
                            tension_level, pacing, setting, key_plot_point,
                            chapter_functions, characters_appear
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (material_id, chapter) DO UPDATE SET
                            title = EXCLUDED.title,
                            type = EXCLUDED.type,
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
                        ch.get("title"), ch_type, ch.get("summary"), ch.get("word_count"),
                        ch.get("tension_level"), ch.get("pacing"),
                        ch.get("setting", []), ch.get("key_plot_point"),
                        ch.get("chapter_function", ch.get("chapter_functions", [])),
                        ch.get("characters_appear", []),
                    ))
        synced += len(batch)
        logger.info(f"已同步章节 {synced}/{len(chapters)}")

    logger.info(f"章节同步完成: 共 {len(chapters)} 章，其中 {len(embeddings)} 章含向量")


def _sync_outline(conn, novel_dir, material_id):
    """同步大纲结构。"""
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
        logger.info(f"已同步大纲元信息（premise/theme/tone）")

    structure_file = novel_dir / "outline" / "structure.yaml"
    if not structure_file.exists():
        return

    with open(structure_file, "r", encoding="utf-8") as f:
        structure_data = yaml.safe_load(f) or {}

    acts = structure_data.get("acts", [])
    if not acts:
        return

    structure_type = structure_data.get("structure_pattern", {}).get("type")

    seq_count = 0
    beat_count = 0
    with conn.cursor() as cur:
        if structure_type:
            cur.execute(
                "UPDATE novels SET structure_type = %s WHERE material_id = %s",
                (structure_type, material_id)
            )

        cur.execute("DELETE FROM outline_beats WHERE material_id = %s", (material_id,))
        cur.execute("DELETE FROM outline_sequences WHERE material_id = %s", (material_id,))

        for act_data in acts:
            act_num = act_data.get("act") or act_data.get("act_number")
            for seq_data in act_data.get("sequences", []):
                seq_num = seq_data.get("sequence") or seq_data.get("sequence_number")

                chapters_start = seq_data.get("chapter_start")
                chapters_end = seq_data.get("chapter_end")
                if chapters_start is None or chapters_end is None:
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
                    beat_num = beat_data.get("beat") or beat_data.get("beat_number")

                    cur.execute("""
                        INSERT INTO outline_beats (
                            material_id, act, sequence, beat,
                            title, chapter, description, tension
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        material_id, act_num, seq_num, beat_num,
                        beat_data.get("title"),
                        beat_data.get("chapter"),
                        beat_data.get("description"),
                        beat_data.get("tension"),
                    ))
                    beat_count += 1

    logger.info(f"已同步大纲结构: {seq_count} 个序列，{beat_count} 个节拍")


def _sync_characters(conn, novel_dir, material_id):
    """同步人物档案。"""
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

    logger.info(f"已同步人物: {len(profile_files)} 个")

    _sync_character_appearances(conn, novel_dir, material_id)


def _sync_character_appearances(conn, novel_dir, material_id):
    """从章节分析结果提取人物出场记录。

    特殊类型章节（afterword/author_note）不参与人物出场统计。
    """
    chapters_file = novel_dir / "chapters.yaml"
    if not chapters_file.exists():
        return

    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters = yaml.safe_load(f) or []

    with conn.cursor() as cur:
        cur.execute("DELETE FROM character_appearances WHERE material_id = %s", (material_id,))

        synced_count = 0
        for ch in chapters:
            ch_num = ch.get("chapter")
            ch_type = ch.get("type", "normal")

            # 跳过特殊类型章节
            if ch_type in ("afterword", "author_note"):
                continue

            for char_name in ch.get("characters_appear", []):
                cur.execute("""
                    INSERT INTO character_appearances (
                        material_id, character_name, chapter, significance
                    ) VALUES (%s, %s, %s, %s)
                """, (material_id, char_name, ch_num, "major"))
                synced_count += 1

    logger.info(f"已同步人物出场记录: {synced_count} 条")


def _sync_worldbuilding(conn, novel_dir, material_id):
    """同步世界观元素。"""
    wb_index = novel_dir / "worldbuilding" / "_index.yaml"
    if not wb_index.exists():
        return

    def _load_worldbuilding_entities(entity_type: str) -> list[dict]:
        """加载世界观实体数据，兼容新旧格式。"""
        files_by_type = {
            "factions": ["factions.yaml"],
            "regions": ["regions.yaml", "geography.yaml"],
            "power_systems": ["power_systems.yaml", "power_system.yaml"],
        }

        loaded = None
        for filename in files_by_type.get(entity_type, []):
            path = novel_dir / "worldbuilding" / filename
            if path.exists():
                with open(path, "r", encoding="utf-8") as ef:
                    loaded = yaml.safe_load(ef) or []
                break

        if loaded is None:
            return []

        if entity_type == "regions" and isinstance(loaded, dict):
            loaded = loaded.get("regions", [])
        elif entity_type == "power_systems" and isinstance(loaded, dict):
            loaded = [{
                "name": loaded.get("name", ""),
                "description": loaded.get("description", ""),
                "importance": "primary",
                "properties": {
                    "levels": loaded.get("levels", []),
                    "rules": loaded.get("rules", []),
                },
            }]
        elif isinstance(loaded, dict):
            loaded = [loaded]

        return [entity for entity in loaded if isinstance(entity, dict)]

    synced = 0
    with conn.cursor() as cur:
        for entity_type in ["factions", "regions", "power_systems"]:
            entities = _load_worldbuilding_entities(entity_type)
            if not entities:
                continue

            for entity in entities:
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

    logger.info(f"已同步世界观实体: {synced} 个")


def sync_all():
    """同步所有小说到数据库。"""
    if not NOVELS_DIR.exists():
        logger.warning("没有小说目录")
        return

    for novel_dir in sorted(NOVELS_DIR.iterdir()):
        if novel_dir.is_dir() and novel_dir.name.startswith("nm_"):
            sync_novel(novel_dir.name)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python sync.py <material_id> 或 python sync.py all")
        sys.exit(1)

    if sys.argv[1] == "all":
        sync_all()
    else:
        sync_novel(sys.argv[1])