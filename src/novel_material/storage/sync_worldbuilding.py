"""同步世界观元素和向量。"""
import json

from novel_material.storage.sync_utils import logger, _load_embeddings_npz
from novel_material.search.text import build_search_text, tokenize_for_search
from novel_material.worldbuilding.reader import load_worldbuilding_view


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

    view = load_worldbuilding_view(novel_dir)

    synced = 0
    synced_with_vec = 0
    with conn.cursor() as cur:
        for entity in view.entities:
            entity_type = entity.type
            entity_name = entity.name
            entity_payload = _entity_payload(entity)
            properties_value = json.dumps(
                entity_payload["properties"],
                ensure_ascii=False,
            )
            vec = _find_embedding(
                embeddings,
                entity_type=entity_type,
                entity_name=entity_name,
            )
            search_tokens = build_worldbuilding_search_tokens(
                entity_payload,
                entity_type,
            )

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
                    entity.description,
                    properties_value,
                    entity.first_appearance_chapter,
                    entity.importance,
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
                    entity.description,
                    properties_value,
                    entity.first_appearance_chapter,
                    entity.importance,
                    search_tokens,
                ))
            synced += 1

    logger.info(f"已同步世界观实体: {synced} 个，其中 {synced_with_vec} 条含向量")


def _entity_payload(entity) -> dict:
    properties = dict(entity.properties)
    properties.update(
        {
            "entity_id": entity.id,
            "aliases": list(entity.aliases),
            "evidence": [
                item.model_dump(mode="json") for item in entity.evidence
            ],
            "key_appearances": list(entity.key_appearances),
        }
    )
    return {
        "name": entity.name,
        "description": entity.description,
        "properties": properties,
    }


def _find_embedding(
    embeddings: dict,
    *,
    entity_type: str,
    entity_name: str,
):
    keys = [f"{entity_type}:{entity_name}"]
    legacy_aliases = {
        "faction": "factions",
        "organization": "factions",
        "region": "regions",
        "location": "regions",
        "power_system": "power_systems",
        "power_systems": "power_systems",
    }
    alias = legacy_aliases.get(entity_type)
    if alias:
        keys.append(f"{alias}:{entity_name}")
    for key in keys:
        if key in embeddings:
            return embeddings[key]
    return None
