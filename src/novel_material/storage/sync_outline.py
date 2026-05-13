"""同步大纲结构和向量。"""
import yaml

from novel_material.storage.sync_utils import logger, _load_embeddings_npz


def sync_outline(conn, novel_dir, material_id):
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