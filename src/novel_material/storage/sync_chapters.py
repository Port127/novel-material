"""同步章节分析结果和向量。"""
import yaml

from novel_material.infra.common import is_special_chapter_type
from novel_material.storage.sync_utils import logger, _load_embeddings_npz


def sync_chapters(conn, novel_dir, material_id):
    """同步章节分析结果和向量。"""
    chapters_file = novel_dir / "chapters.yaml"
    if not chapters_file.exists():
        return

    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters = yaml.safe_load(f) or []

    if not chapters:
        return

    # 加载向量（统一使用 _load_embeddings_npz）
    embeddings_npz = novel_dir / "chapter_embeddings.npz"
    embeddings_yaml = novel_dir / "chapter_embeddings.yaml"

    embeddings: dict = {}
    if embeddings_npz.exists():
        embeddings = _load_embeddings_npz(embeddings_npz)
        # 转换为整数 key（章节同步需要）
        embeddings = {int(k): v for k, v in embeddings.items()}
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
                            tension_level, pacing, setting, key_plot_point, key_event,
                            tension_change, emotion_transition, plot_progress,
                            chapter_functions, characters_appear,
                            emotional_tone, scene_type, technique, hook_type,
                            summary_embedding
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (material_id, chapter) DO UPDATE SET
                            title = EXCLUDED.title,
                            type = EXCLUDED.type,
                            summary = EXCLUDED.summary,
                            word_count = EXCLUDED.word_count,
                            tension_level = EXCLUDED.tension_level,
                            pacing = EXCLUDED.pacing,
                            setting = EXCLUDED.setting,
                            key_plot_point = EXCLUDED.key_plot_point,
                            key_event = EXCLUDED.key_event,
                            tension_change = EXCLUDED.tension_change,
                            emotion_transition = EXCLUDED.emotion_transition,
                            plot_progress = EXCLUDED.plot_progress,
                            chapter_functions = EXCLUDED.chapter_functions,
                            characters_appear = EXCLUDED.characters_appear,
                            emotional_tone = EXCLUDED.emotional_tone,
                            scene_type = EXCLUDED.scene_type,
                            technique = EXCLUDED.technique,
                            hook_type = EXCLUDED.hook_type,
                            summary_embedding = EXCLUDED.summary_embedding
                    """, (
                        material_id, ch_num,
                        ch.get("title"), ch_type, ch.get("summary"), ch.get("word_count"),
                        ch.get("tension_level"), ch.get("pacing"),
                        ch.get("setting", []), ch.get("key_plot_point"), ch.get("key_event"),
                        ch.get("tension_change"), ch.get("emotion_transition"), ch.get("plot_progress"),
                        ch.get("chapter_function", ch.get("chapter_functions", [])),
                        ch.get("characters_appear", []),
                        ch.get("emotional_tone", []),
                        ch.get("scene_type", []),
                        ch.get("technique", []),
                        ch.get("hook_type"),
                        vec,
                    ))
                else:
                    cur.execute("""
                        INSERT INTO chapters (
                            material_id, chapter, title, type, summary, word_count,
                            tension_level, pacing, setting, key_plot_point, key_event,
                            tension_change, emotion_transition, plot_progress,
                            chapter_functions, characters_appear,
                            emotional_tone, scene_type, technique, hook_type
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (material_id, chapter) DO UPDATE SET
                            title = EXCLUDED.title,
                            type = EXCLUDED.type,
                            summary = EXCLUDED.summary,
                            word_count = EXCLUDED.word_count,
                            tension_level = EXCLUDED.tension_level,
                            pacing = EXCLUDED.pacing,
                            setting = EXCLUDED.setting,
                            key_plot_point = EXCLUDED.key_plot_point,
                            key_event = EXCLUDED.key_event,
                            tension_change = EXCLUDED.tension_change,
                            emotion_transition = EXCLUDED.emotion_transition,
                            plot_progress = EXCLUDED.plot_progress,
                            chapter_functions = EXCLUDED.chapter_functions,
                            characters_appear = EXCLUDED.characters_appear,
                            emotional_tone = EXCLUDED.emotional_tone,
                            scene_type = EXCLUDED.scene_type,
                            technique = EXCLUDED.technique,
                            hook_type = EXCLUDED.hook_type
                    """, (
                        material_id, ch_num,
                        ch.get("title"), ch_type, ch.get("summary"), ch.get("word_count"),
                        ch.get("tension_level"), ch.get("pacing"),
                        ch.get("setting", []), ch.get("key_plot_point"), ch.get("key_event"),
                        ch.get("tension_change"), ch.get("emotion_transition"), ch.get("plot_progress"),
                        ch.get("chapter_function", ch.get("chapter_functions", [])),
                        ch.get("characters_appear", []),
                        ch.get("emotional_tone", []),
                        ch.get("scene_type", []),
                        ch.get("technique", []),
                        ch.get("hook_type"),
                    ))
        synced += len(batch)
        logger.info(f"已同步章节 {synced}/{len(chapters)}")

    logger.info(f"章节同步完成: 共 {len(chapters)} 章，其中 {len(embeddings)} 章含向量")


def sync_character_appearances(conn, novel_dir, material_id):
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

            # 跳过特殊类型章节
            if is_special_chapter_type(ch.get("type", "normal")):
                continue

            for char_name in ch.get("characters_appear", []):
                cur.execute("""
                    INSERT INTO character_appearances (
                        material_id, character_name, chapter, significance
                    ) VALUES (%s, %s, %s, %s)
                """, (material_id, char_name, ch_num, "major"))
                synced_count += 1

    logger.info(f"已同步人物出场记录: {synced_count} 条")