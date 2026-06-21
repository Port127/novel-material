"""同步世界观元素和向量。"""
import json

from novel_material.infra.yaml_io import load_yaml_list
from novel_material.storage.sync_utils import logger, _load_embeddings_npz
from novel_material.search.text import build_search_text, tokenize_for_search


def build_worldbuilding_search_tokens(entity: dict, entity_type: str) -> str:
    """构造世界观实体词法检索文本。"""
    text = build_search_text(
        entity.get("name"),
        entity_type,
        entity.get("description"),
        entity.get("properties"),
    )
    return tokenize_for_search(text)


def sync_worldbuilding(conn, novel_dir, material_id):
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
                loaded = load_yaml_list(path)
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
                search_tokens = build_worldbuilding_search_tokens(entity, entity_type)

                if vec is not None:
                    cur.execute("""
                        INSERT INTO worldbuilding_entities (
                            material_id, entity_type, name, description,
                            properties, first_appearance, importance,
                            description_embedding, search_tokens
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (material_id, entity_type, name) DO UPDATE SET
                            description = EXCLUDED.description,
                            properties = EXCLUDED.properties,
                            first_appearance = EXCLUDED.first_appearance,
                            importance = EXCLUDED.importance,
                            description_embedding = EXCLUDED.description_embedding,
                            search_tokens = EXCLUDED.search_tokens
                    """, (
                        material_id,
                        entity_type,
                        entity_name,
                        entity.get("description", ""),
                        properties_value,
                        entity.get("first_appearance"),
                        entity.get("importance", "secondary"),
                        vec,
                        search_tokens,
                    ))
                    synced_with_vec += 1
                else:
                    cur.execute("""
                        INSERT INTO worldbuilding_entities (
                            material_id, entity_type, name, description,
                            properties, first_appearance, importance, search_tokens
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (material_id, entity_type, name) DO UPDATE SET
                            description = EXCLUDED.description,
                            properties = EXCLUDED.properties,
                            first_appearance = EXCLUDED.first_appearance,
                            importance = EXCLUDED.importance,
                            search_tokens = EXCLUDED.search_tokens
                    """, (
                        material_id,
                        entity_type,
                        entity_name,
                        entity.get("description", ""),
                        properties_value,
                        entity.get("first_appearance"),
                        entity.get("importance", "secondary"),
                        search_tokens,
                    ))
                synced += 1

    logger.info(f"已同步世界观实体: {synced} 个，其中 {synced_with_vec} 条含向量")
