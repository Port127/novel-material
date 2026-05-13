"""同步人物档案和向量。"""
import json

from novel_material.infra.yaml_io import load_yaml
from novel_material.storage.sync_utils import logger, _load_embeddings_npz
from novel_material.storage.sync_chapters import sync_character_appearances


def sync_characters(conn, novel_dir, material_id):
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
            profile = load_yaml(profile_file)

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

    sync_character_appearances(conn, novel_dir, material_id)