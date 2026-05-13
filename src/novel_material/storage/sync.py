"""数据库同步：把本地 YAML 文件同步到 PostgreSQL。

自动修复：
- 检测到 summary 长度不足、章节缺失或 schema 错误时会自动调用修复接口重试
- 修复成功后继续同步，失败则返回 False
"""
import os
import sys
import json
import yaml
import psycopg2
import psycopg2.extras
import numpy as np
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.progress import get_pipeline_logger
from novel_material.validation.schema import validate_material, get_schema_error_chapters
from novel_material.validation.quality import get_short_summary_chapters, get_missing_chapters
from novel_material.pipeline.analyze import repair_short_summaries

logger = get_pipeline_logger()
DATABASE_URL = os.getenv("DATABASE_URL")


def _load_embeddings_npz(npz_path: Path) -> dict:
    """从 NPZ 文件加载向量。

    支持两种格式：
    - 章节格式：chapters 数组（整数 key）
    - 通用格式：keys 数组（字符串 key）

    Args:
        npz_path: NPZ 文件路径

    Returns:
        dict: {key: embedding_list}
    """
    if not npz_path.exists():
        return {}
    data = np.load(str(npz_path))
    vectors_arr = data["vectors"]

    # 章节格式（整数 key）
    if "chapters" in data:
        chapters_arr = data["chapters"]
        return {str(int(ch)): vectors_arr[i].tolist() for i, ch in enumerate(chapters_arr)}

    # 通用格式（字符串 key）
    if "keys" in data:
        keys_arr = data["keys"]
        return {str(k): vectors_arr[i].tolist() for i, k in enumerate(keys_arr)}

    return {}


class DatabaseConfigError(Exception):
    """数据库配置错误（如 DATABASE_URL 未设置）。"""
    pass


class QualityCheckError(Exception):
    """数据质量检查失败，可尝试修复后重试。

    Attributes:
        material_id: 素材 ID
        short_chapters: summary 长度不足的章节列表
        missing_chapters: 缺失的章节列表
        schema_error_chapters: schema 校验失败的章节列表
    """

    def __init__(
        self,
        material_id: str,
        short_chapters: list[int] = None,
        missing_chapters: list[int] = None,
        schema_error_chapters: list[int] = None
    ):
        self.material_id = material_id
        self.short_chapters = short_chapters or []
        self.missing_chapters = missing_chapters or []
        self.schema_error_chapters = schema_error_chapters or []

        # 构建消息
        msg = f"Schema 预检失败: {material_id}"
        if short_chapters:
            msg += f"（{len(short_chapters)} 章 summary 长度不足）"
        if missing_chapters:
            msg += f"（{len(missing_chapters)} 章缺失）"
        if schema_error_chapters:
            msg += f"（{len(schema_error_chapters)} 章 schema 错误）"
        super().__init__(msg)


class SchemaValidationError(Exception):
    """Schema 校验失败（非 summary 问题，无法自动修复）。"""
    pass


def get_db_connection():
    """获取数据库连接。

    Raises:
        DatabaseConfigError: DATABASE_URL 未设置
    """
    if not DATABASE_URL:
        raise DatabaseConfigError("DATABASE_URL 环境变量未设置")
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def _precheck_schema(material_id: str, verbose: bool = True) -> None:
    """同步前检查数据格式（纯校验，不修复）。

    参数：
        material_id: 素材 ID
        verbose: 是否输出详细信息

    Raises:
        QualityCheckError: 检查失败，包含可修复的章节列表
        SchemaValidationError: 检查失败且无法修复（非 summary/schema 问题）
    """
    if validate_material(material_id, verbose=verbose, skip_tags=True):
        logger.info(f"Schema 预检通过: {material_id}")
        return

    # 检查是否是 summary 长度问题、缺失章节问题或 schema 错误问题
    short_chapters = get_short_summary_chapters(material_id)
    missing_chapters = get_missing_chapters(material_id, strict=False)
    schema_error_chapters = get_schema_error_chapters(material_id)

    if short_chapters or missing_chapters or schema_error_chapters:
        # 是可修复问题（summary长度不足、章节缺失或 schema 错误）
        if short_chapters:
            logger.warning(f"Schema 预检失败: {material_id}，{len(short_chapters)} 章 summary 长度不足")
        if missing_chapters:
            logger.warning(f"Schema 预检失败: {material_id}，{len(missing_chapters)} 章缺失")
        if schema_error_chapters:
            logger.warning(f"Schema 预检失败: {material_id}，{len(schema_error_chapters)} 章 schema 错误")
        raise QualityCheckError(
            material_id,
            short_chapters=short_chapters,
            missing_chapters=missing_chapters,
            schema_error_chapters=schema_error_chapters
        )
    else:
        # 不是可修复问题，无法自动修复
        logger.error(f"Schema 预检失败（非 summary/缺失/schema 错误问题），无法自动修复: {material_id}")
        raise SchemaValidationError(f"Schema 预检失败（非可修复问题），中止同步: {material_id}")


def _execute_sync(conn, novel_dir: Path, material_id: str) -> bool:
    """执行同步操作（内部函数，消除重复代码）。

    参数：
        conn: 数据库连接
        novel_dir: 小说目录
        material_id: 素材 ID

    返回：
        True 表示成功，False 表示失败
    """
    try:
        _sync_meta(conn, novel_dir, material_id)
        _sync_chapters(conn, novel_dir, material_id)
        _sync_outline(conn, novel_dir, material_id)
        _sync_characters(conn, novel_dir, material_id)
        _sync_worldbuilding(conn, novel_dir, material_id)
        conn.commit()
        logger.info(f"同步完成: {material_id}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"同步失败，已回滚: {e}")
        return False


def _do_sync_with_connection(novel_dir: Path, material_id: str) -> bool:
    """获取连接并执行同步（内部函数）。

    返回：
        True 表示成功，False 表示失败
    """
    try:
        conn = get_db_connection()
    except DatabaseConfigError as e:
        logger.error(str(e))
        return False

    try:
        return _execute_sync(conn, novel_dir, material_id)
    finally:
        conn.close()


def sync_novel(material_id: str, provider: str | None = None, use_window: bool = False) -> bool:
    """同步单本小说到数据库。

    参数：
        material_id: 素材 ID
        provider: LLM 服务商（用于修复时的参数传递）
        use_window: 是否使用滑动窗口（用于修复时的参数传递）

    返回：
        True 表示成功，False 表示失败（需人工干预）
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.warning(f"跳过: 目录不存在 {novel_dir}")
        return False

    # 预检
    try:
        _precheck_schema(material_id, verbose=True)
    except QualityCheckError as e:
        # 合并短摘要、缺失章节和 schema 错误章节
        chapters_to_fix = sorted(set(e.short_chapters) | set(e.missing_chapters) | set(e.schema_error_chapters))
        logger.info(f"[{material_id}] 自动修复 {len(chapters_to_fix)} 章...")
        success, repaired, total = repair_short_summaries(
            material_id,
            short_chapters=chapters_to_fix,  # 传入合并后的章节列表
            provider=provider,
            use_window=use_window,
        )
        if not success:
            logger.warning(f"[{material_id}] 修复失败（成功率 < 80%），需人工干预")
            return False

        # 修复成功，再次预检
        logger.info(f"[{material_id}] 修复成功: {repaired}/{total} 章")
        try:
            _precheck_schema(material_id, verbose=True)
        except QualityCheckError:
            # 修复后仍有问题
            remaining_short = get_short_summary_chapters(material_id)
            remaining_missing = get_missing_chapters(material_id, strict=False)
            remaining_schema_error = get_schema_error_chapters(material_id)
            total_remaining = len(remaining_short) + len(remaining_missing) + len(remaining_schema_error)
            logger.warning(
                f"[{material_id}] 修复后仍有 {total_remaining} 章问题"
                f"（{len(remaining_short)} 章短摘要，{len(remaining_missing)} 章缺失，{len(remaining_schema_error)} 章 schema 错误），需人工干预"
            )
            return False
        except SchemaValidationError:
            return False

    except SchemaValidationError:
        return False

    # 预检通过，执行同步
    return _do_sync_with_connection(novel_dir, material_id)


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


def _sync_outline(conn, novel_dir, material_id):
    """同步大纲结构和向量。"""
    # 加载大纲向量
    embeddings_npz = novel_dir / "outline" / "outline_embeddings.npz"
    embeddings = _load_embeddings_npz(embeddings_npz)
    if embeddings:
        logger.info(f"加载大纲向量: {len(embeddings)} 条")

    premise_vec = embeddings.get("premise")

    # 从 meta.yaml 读取 premise/theme/tone（与 embedding 数据源一致）
    meta_file = novel_dir / "meta.yaml"
    premise = None
    theme = []
    tone = []
    if meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = yaml.safe_load(f) or {}
        premise = meta.get("premise")
        theme = meta.get("theme", [])
        tone = meta.get("tone", [])
        if isinstance(theme, str):
            theme = [theme]
        if isinstance(tone, str):
            tone = [tone]

    outline_index = novel_dir / "outline" / "_index.yaml"
    if outline_index.exists():
        with open(outline_index, "r", encoding="utf-8") as f:
            index_data = yaml.safe_load(f) or {}

        summary = index_data.get("structure_summary", {})
        hooks = index_data.get("hooks_stats", {})
        subplots = index_data.get("subplots_stats", {})

        with conn.cursor() as cur:
            if premise_vec is not None:
                cur.execute("""
                    UPDATE novels SET
                        premise = %s,
                        theme = %s,
                        tone = %s,
                        act_count = %s,
                        sequence_count = %s,
                        hook_count = %s,
                        subplot_count = %s,
                        premise_embedding = %s
                    WHERE material_id = %s
                """, (
                    premise,
                    theme,
                    tone,
                    summary.get("acts"),
                    summary.get("sequences"),
                    hooks.get("total"),
                    subplots.get("count"),
                    premise_vec,
                    material_id,
                ))
            else:
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
                    premise,
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
    beat_with_vec = 0
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
                    beat_key = f"beat:{act_num}:{seq_num}:{beat_num}"
                    beat_vec = embeddings.get(beat_key)

                    if beat_vec is not None:
                        cur.execute("""
                            INSERT INTO outline_beats (
                                material_id, act, sequence, beat,
                                title, chapter, description, tension,
                                description_embedding
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            material_id, act_num, seq_num, beat_num,
                            beat_data.get("title"),
                            beat_data.get("chapter"),
                            beat_data.get("description"),
                            beat_data.get("tension"),
                            beat_vec,
                        ))
                        beat_with_vec += 1
                    else:
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

    logger.info(f"已同步大纲结构: {seq_count} 个序列，{beat_count} 个节拍，其中 {beat_with_vec} 个含向量")


def _sync_characters(conn, novel_dir, material_id):
    """同步人物档案和向量。"""
    profiles_dir = novel_dir / "characters" / "profiles"
    if not profiles_dir.exists():
        return

    profile_files = list(profiles_dir.glob("*.yaml"))
    if not profile_files:
        return

    # 加载人物向量
    embeddings_npz = novel_dir / "characters" / "character_embeddings.npz"
    embeddings = _load_embeddings_npz(embeddings_npz)
    if embeddings:
        logger.info(f"加载人物向量: {len(embeddings)} 条")

    with conn.cursor() as cur:
        for profile_file in profile_files:
            with open(profile_file, "r", encoding="utf-8") as pf:
                profile = yaml.safe_load(pf)

            if not profile:
                continue

            psychology_value = json.dumps(
                profile.get("psychology", {}), ensure_ascii=False
            )
            char_name = profile.get("name")
            if not char_name:
                continue
            vec = embeddings.get(char_name)

            if vec is not None:
                cur.execute("""
                    INSERT INTO characters (
                        material_id, name, role, archetype,
                        moral_spectrum, arc_summary, narrative_function,
                        psychology, first_appearance, last_appearance,
                        appearance_count, file_path, description,
                        arc_summary_embedding
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                        file_path = EXCLUDED.file_path,
                        arc_summary_embedding = EXCLUDED.arc_summary_embedding
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
                    vec,
                ))
            else:
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

    logger.info(f"已同步人物: {len(profile_files)} 个，其中 {len(embeddings)} 条含向量")

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
    """同步世界观元素和向量。"""
    wb_index = novel_dir / "worldbuilding" / "_index.yaml"
    if not wb_index.exists():
        return

    # 加载世界观向量
    embeddings_npz = novel_dir / "worldbuilding" / "wb_embeddings.npz"
    embeddings = _load_embeddings_npz(embeddings_npz)
    if embeddings:
        logger.info(f"加载世界观向量: {len(embeddings)} 条")

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
    synced_with_vec = 0
    with conn.cursor() as cur:
        for entity_type in ["factions", "regions", "power_systems"]:
            entities = _load_worldbuilding_entities(entity_type)
            if not entities:
                continue

            for entity in entities:
                properties_value = json.dumps(
                    entity.get("properties", {}), ensure_ascii=False
                )
                entity_name = entity.get("name", "")
                vec_key = f"{entity_type}:{entity_name}"
                vec = embeddings.get(vec_key)

                if vec is not None:
                    cur.execute("""
                        INSERT INTO worldbuilding_entities (
                            material_id, entity_type, name, description,
                            properties, first_appearance, importance,
                            description_embedding
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (material_id, entity_type, name) DO UPDATE SET
                            description = EXCLUDED.description,
                            properties = EXCLUDED.properties,
                            first_appearance = EXCLUDED.first_appearance,
                            importance = EXCLUDED.importance,
                            description_embedding = EXCLUDED.description_embedding
                    """, (
                        material_id,
                        entity_type,
                        entity_name,
                        entity.get("description", ""),
                        properties_value,
                        entity.get("first_appearance"),
                        entity.get("importance", "secondary"),
                        vec,
                    ))
                    synced_with_vec += 1
                else:
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
                        entity_name,
                        entity.get("description", ""),
                        properties_value,
                        entity.get("first_appearance"),
                        entity.get("importance", "secondary"),
                    ))
                synced += 1

    logger.info(f"已同步世界观实体: {synced} 个，其中 {synced_with_vec} 条含向量")


def sync_all(provider: str | None = None, use_window: bool = False) -> int:
    """同步所有小说到数据库。

    参数：
        provider: LLM 服务商（用于修复时的参数传递）
        use_window: 是否使用滑动窗口（用于修复时的参数传递）

    返回：
        成功同步的素材数量
    """
    if not NOVELS_DIR.exists():
        logger.warning("没有小说目录")
        return 0

    success_count = 0
    for novel_dir in sorted(NOVELS_DIR.iterdir()):
        if novel_dir.is_dir() and novel_dir.name.startswith("nm_"):
            if sync_novel(novel_dir.name, provider=provider, use_window=use_window):
                success_count += 1

    return success_count


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python sync.py <material_id> 或 python sync.py all")
        sys.exit(1)

    if sys.argv[1] == "all":
        count = sync_all()
        print(f"已同步 {count} 个素材")
    else:
        success = sync_novel(sys.argv[1])
        if success:
            print(f"同步完成: {sys.argv[1]}")
        else:
            print(f"同步失败: {sys.argv[1]}")
            sys.exit(1)