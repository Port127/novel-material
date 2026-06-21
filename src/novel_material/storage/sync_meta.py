"""同步 meta.yaml 到 novels 表。"""
import json

from novel_material.infra.yaml_io import load_yaml
from novel_material.storage.sync_utils import logger
from novel_material.search.text import build_search_text, tokenize_for_search


def build_novel_search_tokens(meta: dict) -> str:
    """构造小说级词法检索文本。"""
    text = build_search_text(
        meta.get("name"),
        meta.get("premise"),
        meta.get("genre"),
        meta.get("theme"),
        meta.get("tone"),
        meta.get("structure_type"),
        meta.get("tags"),
    )
    return tokenize_for_search(text)


def sync_meta(conn, novel_dir, material_id):
    """同步 meta.yaml 到 novels 表。"""
    meta_file = novel_dir / "meta.yaml"
    if not meta_file.exists():
        return

    meta = load_yaml(meta_file)

    tags_value = json.dumps(meta.get("tags", {}), ensure_ascii=False) if meta.get("tags") else None
    search_tokens = build_novel_search_tokens(meta)

    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO novels (
                material_id, name, author, genre, word_count,
                chapter_count, status, tags, created_at, updated_at,
                search_tokens
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (material_id) DO UPDATE SET
                name = EXCLUDED.name,
                author = EXCLUDED.author,
                genre = EXCLUDED.genre,
                word_count = EXCLUDED.word_count,
                chapter_count = EXCLUDED.chapter_count,
                status = EXCLUDED.status,
                tags = EXCLUDED.tags,
                updated_at = EXCLUDED.updated_at,
                search_tokens = EXCLUDED.search_tokens
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
            search_tokens,
        ))
    logger.info(f"已同步小说元信息: {meta.get('name')}")
