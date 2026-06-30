"""向量化模块：将文本数据转换为向量，用于语义搜索。

支持的数据类型：
- 章节摘要（已实现）
- 人物档案（新增）
- 世界观设定（新增）
- 大纲 premise（新增）
"""
import sys
import time
from pathlib import Path

import numpy as np

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.embedding import get_embedding, load_embedding_config
from novel_material.infra.logging_config import get_embedding_logger
from novel_material.infra.yaml_io import load_yaml, load_yaml_list
from novel_material.storage.embedding_manifest import (
    EmbeddingManifest,
    manifest_from_config,
    save_manifest,
    validate_vector,
)
from novel_material.worldbuilding.reader import load_worldbuilding_view

logger = get_embedding_logger()

_BATCH_SIZE = 20
_RATE_LIMIT = 0.5


# ============================================================
# 章节向量专用函数（向后兼容：整数 key + chapters 数组格式）
# ============================================================

def _load_chapter_embeddings(npz_path: Path) -> dict[int, list]:
    """加载章节向量（整数 key + chapters 数组格式）。

    Args:
        npz_path: NPZ 文件路径

    Returns:
        dict: {章节号(int): embedding_list}
    """
    if not npz_path.exists():
        return {}
    data = np.load(str(npz_path))
    chapters_arr = data["chapters"]
    vectors_arr = data["vectors"]
    return {int(ch): vectors_arr[i].tolist() for i, ch in enumerate(chapters_arr)}


def _save_chapter_embeddings(
    npz_path: Path,
    embeddings: dict[int, list],
    *,
    manifest: EmbeddingManifest,
) -> None:
    """保存章节向量（整数 key + chapters 数组格式）。

    Args:
        npz_path: NPZ 文件路径
        embeddings: {章节号(int): embedding_list}
    """
    if not embeddings:
        return
    for vector in embeddings.values():
        validate_vector(vector, manifest)
    chapters_sorted = sorted(embeddings.keys())
    vectors_matrix = np.array([embeddings[k] for k in chapters_sorted], dtype=np.float32)
    chapters_arr = np.array(chapters_sorted, dtype=np.int32)
    np.savez_compressed(str(npz_path), chapters=chapters_arr, vectors=vectors_matrix)
    save_manifest(npz_path, manifest)


# ============================================================
# 通用向量函数（字符串 key + keys 数组格式）
# ============================================================

def _load_embeddings(npz_path: Path) -> dict[str, list]:
    """加载向量（字符串 key + keys 数组格式）。

    Args:
        npz_path: NPZ 文件路径

    Returns:
        dict: {key(str): embedding_list}
    """
    if not npz_path.exists():
        return {}
    data = np.load(str(npz_path))
    keys_arr = data["keys"]
    vectors_arr = data["vectors"]
    return {str(k): vectors_arr[i].tolist() for i, k in enumerate(keys_arr)}


def _save_embeddings(
    npz_path: Path,
    embeddings: dict[str, list],
    *,
    manifest: EmbeddingManifest,
) -> None:
    """保存向量（字符串 key + keys 数组格式）。

    Args:
        npz_path: NPZ 文件路径
        embeddings: {key(str): embedding_list}
    """
    if not embeddings:
        return
    for vector in embeddings.values():
        validate_vector(vector, manifest)
    keys_sorted = sorted(embeddings.keys())
    vectors_matrix = np.array([embeddings[k] for k in keys_sorted], dtype=np.float32)
    keys_arr = np.array(keys_sorted, dtype=np.str_)
    np.savez_compressed(str(npz_path), keys=keys_arr, vectors=vectors_matrix)
    save_manifest(npz_path, manifest)


def embed_chapters(material_id: str) -> None:
    """为指定小说的所有章节摘要生成向量。

    使用章节专用 NPZ 格式（chapters 数组 + 整数 key），向后兼容。
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"小说目录不存在: {novel_dir}")
        return

    chapters_file = novel_dir / "chapters.yaml"
    if not chapters_file.exists():
        logger.error("chapters.yaml 不存在，请先运行 chapter_analyze")
        return

    chapters = load_yaml_list(chapters_file)

    if not chapters:
        logger.warning("chapters.yaml 为空，跳过向量化")
        return

    embeddings_npz = novel_dir / "chapter_embeddings.npz"

    existing = _load_chapter_embeddings(embeddings_npz)

    if existing:
        logger.info(f"断点续传：已有 {len(existing)} 章向量，跳过")

    pending = [
        ch for ch in chapters
        if ch.get("summary") and ch.get("chapter") not in existing
    ]

    if not pending:
        logger.info("所有章节已向量化，无需处理")
        _log_stats(existing)
        return

    logger.info(f"待向量化: {len(pending)} 章（共 {len(chapters)} 章）")

    config = load_embedding_config()
    manifest = manifest_from_config(config, "chapter-summary-v1")
    done = 0
    errors = 0

    for i in range(0, len(pending), _BATCH_SIZE):
        batch = pending[i:i + _BATCH_SIZE]
        for ch in batch:
            ch_num = ch["chapter"]
            summary = ch["summary"]
            try:
                vec = get_embedding(summary, config)
                existing[ch_num] = vec
                done += 1
            except Exception as e:
                logger.warning(f"第{ch_num}章向量化失败: {e}")
                errors += 1
                continue

        _save_chapter_embeddings(
            embeddings_npz,
            existing,
            manifest=manifest,
        )
        logger.info(f"已完成 {done}/{len(pending)} 章")

        if i + _BATCH_SIZE < len(pending):
            time.sleep(_RATE_LIMIT)

    _log_stats(existing)
    if errors > 0:
        logger.warning(f"向量化失败: {errors} 章")


def _log_stats(embeddings: dict) -> None:
    """记录向量化统计信息。"""
    sample_vec = next(iter(embeddings.values()), None)
    if sample_vec:
        dim = len(sample_vec) if isinstance(sample_vec, list) else sample_vec.shape[0]
        logger.info(f"向量化完成: {len(embeddings)} 条，维度 {dim}")
    else:
        logger.info(f"向量化完成: {len(embeddings)} 条")


def _build_character_text(profile: dict) -> str:
    """拼接人物档案文本用于向量化。

    拼接内容: arc_summary + description + psychology 关键属性
    """
    parts = []

    # arc_summary（核心弧线）
    if profile.get("arc_summary"):
        parts.append(f"弧线: {profile['arc_summary']}")

    # description（描述）
    if profile.get("description"):
        parts.append(f"描述: {profile['description']}")

    # psychology 关键属性
    psychology = profile.get("psychology", {})
    if psychology:
        psych_keys = ["fatal_flaw", "obsession", "soft_spot", "motivation"]
        for key in psych_keys:
            if psychology.get(key):
                parts.append(f"{key}: {psychology[key]}")

    # narrative_function（叙事功能）
    if profile.get("narrative_function"):
        parts.append(f"功能: {profile['narrative_function']}")

    return " | ".join(parts) if parts else profile.get("name", "")


def embed_characters(material_id: str) -> None:
    """生成人物向量，保存到 characters/character_embeddings.npz。

    拼接内容: arc_summary + description + psychology 关键属性
    """
    novel_dir = NOVELS_DIR / material_id
    profiles_dir = novel_dir / "characters" / "profiles"

    if not profiles_dir.exists():
        logger.warning(f"[{material_id}] 人物 profiles 目录不存在，跳过向量化")
        return

    profile_files = list(profiles_dir.glob("*.yaml"))
    if not profile_files:
        logger.warning(f"[{material_id}] 无人物档案文件，跳过向量化")
        return

    embeddings_npz = novel_dir / "characters" / "character_embeddings.npz"
    existing = _load_embeddings(embeddings_npz)

    if existing:
        logger.info(f"[{material_id}] 断点续传：已有 {len(existing)} 人物向量，跳过")

    pending = []
    for f in profile_files:
        profile = load_yaml(f)
        name = profile.get("name")
        if name and name not in existing:
            text = _build_character_text(profile)
            if text:
                pending.append((name, text))

    if not pending:
        logger.info(f"[{material_id}] 所有人物已向量化，无需处理")
        _log_stats(existing)
        return

    logger.info(f"[{material_id}] 待向量化人物: {len(pending)} 人（共 {len(profile_files)} 人）")

    config = load_embedding_config()
    manifest = manifest_from_config(config, "character-profile-v1")
    done = 0
    errors = 0

    for name, text in pending:
        try:
            vec = get_embedding(text, config)
            existing[name] = vec
            done += 1
        except Exception as e:
            logger.warning(f"[{material_id}] 人物 '{name}' 向量化失败: {e}")
            errors += 1

        # 每 10 条保存一次
        if done % 10 == 0:
            _save_embeddings(embeddings_npz, existing, manifest=manifest)

    # 最终保存
    if existing:
        _save_embeddings(embeddings_npz, existing, manifest=manifest)
    _log_stats(existing)
    if errors > 0:
        logger.warning(f"[{material_id}] 人物向量化失败: {errors} 人")


def _build_worldbuilding_text(entity: dict, entity_type: str) -> str:
    """拼接世界观实体文本用于向量化。

    拼接内容: name + description + properties 关键属性
    """
    parts = []

    # name
    if entity.get("name"):
        parts.append(f"名称: {entity['name']}")

    # description
    if entity.get("description"):
        parts.append(f"描述: {entity['description']}")

    # properties 关键属性（根据类型提取）
    properties = entity.get("properties", {})
    if properties:
        if entity_type == "power_systems":
            for key in ["levels", "rules"]:
                if properties.get(key):
                    val = properties[key]
                    if isinstance(val, list):
                        parts.append(f"{key}: {', '.join(str(v) for v in val[:5])}")
                    else:
                        parts.append(f"{key}: {val}")
        elif entity_type == "factions":
            for key in ["leader", "strength", "allies", "enemies"]:
                if properties.get(key):
                    parts.append(f"{key}: {properties[key]}")
        elif entity_type == "regions":
            for key in ["notable_features", "importance"]:
                if properties.get(key):
                    parts.append(f"{key}: {properties[key]}")
        else:
            for key, value in properties.items():
                if value:
                    parts.append(f"{key}: {_stringify_property(value)}")

    evidence = entity.get("evidence", [])
    if evidence:
        summaries = [
            item.get("summary", "")
            for item in evidence
            if isinstance(item, dict) and item.get("summary")
        ]
        if summaries:
            parts.append(f"证据: {'; '.join(summaries[:5])}")

    return " | ".join(parts) if parts else entity.get("name", "")


def _stringify_property(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value[:8])
    if isinstance(value, dict):
        return ", ".join(f"{key}={item}" for key, item in list(value.items())[:8])
    return str(value)


def embed_worldbuilding(material_id: str) -> None:
    """生成世界观向量，保存到 worldbuilding/wb_embeddings.npz。

    处理统一世界观实体，兼容 legacy 与 layered。
    """
    novel_dir = NOVELS_DIR / material_id
    wb_dir = novel_dir / "worldbuilding"

    if not wb_dir.exists():
        logger.warning(f"[{material_id}] 世界观目录不存在，跳过向量化")
        return

    embeddings_npz = novel_dir / "worldbuilding" / "wb_embeddings.npz"
    existing = _load_embeddings(embeddings_npz)

    if existing:
        logger.info(f"[{material_id}] 断点续传：已有 {len(existing)} 世界观向量，跳过")

    pending = []
    try:
        view = load_worldbuilding_view(novel_dir)
    except Exception as exc:
        logger.warning(f"[{material_id}] 世界观读取失败，跳过向量化: {exc}")
        return

    for entity in view.entities:
        key = f"{entity.type}:{entity.name}"
        if key in existing:
            continue
        payload = {
            "name": entity.name,
            "description": entity.description,
            "properties": dict(entity.properties),
            "evidence": [
                item.model_dump(mode="json") for item in entity.evidence
            ],
        }
        text = _build_worldbuilding_text(payload, entity.type)
        if text:
            pending.append((key, text))

    if not pending:
        logger.info(f"[{material_id}] 所有世界观实体已向量化，无需处理")
        _log_stats(existing)
        return

    logger.info(f"[{material_id}] 待向量化世界观: {len(pending)} 条")

    config = load_embedding_config()
    manifest = manifest_from_config(config, "worldbuilding-entity-v1")
    done = 0
    errors = 0

    for key, text in pending:
        try:
            vec = get_embedding(text, config)
            existing[key] = vec
            done += 1
        except Exception as e:
            logger.warning(f"[{material_id}] 世界观 '{key}' 向量化失败: {e}")
            errors += 1
            continue

        # 每 10 条保存一次
        if done % 10 == 0:
            _save_embeddings(embeddings_npz, existing, manifest=manifest)

    # 最终保存
    if existing:
        _save_embeddings(embeddings_npz, existing, manifest=manifest)
    _log_stats(existing)
    if errors > 0:
        logger.warning(f"[{material_id}] 世界观向量化失败: {errors} 条")


def embed_outline(material_id: str) -> None:
    """生成大纲向量，保存到 outline/outline_embeddings.npz。

    处理内容:
    - premise（来自 meta.yaml）
    - beats（来自 outline/structure.yaml，可选）
    """
    novel_dir = NOVELS_DIR / material_id
    outline_dir = novel_dir / "outline"

    if not outline_dir.exists():
        logger.warning(f"[{material_id}] 大纲目录不存在，跳过向量化")
        return

    embeddings_npz = novel_dir / "outline" / "outline_embeddings.npz"
    existing = _load_embeddings(embeddings_npz)

    config = load_embedding_config()
    manifest = manifest_from_config(config, "outline-premise-beat-v1")
    done = 0
    errors = 0

    # 1. 向量化 premise（从 meta.yaml 读取）
    premise_key = "premise"
    if premise_key not in existing:
        meta_file = novel_dir / "meta.yaml"
        premise_text = ""

        if meta_file.exists():
            meta = load_yaml(meta_file)

            parts = []
            if meta.get("premise"):
                parts.append(f"前提: {meta['premise']}")
            if meta.get("theme"):
                theme = meta["theme"]
                if isinstance(theme, list):
                    parts.append(f"主题: {', '.join(theme)}")
                else:
                    parts.append(f"主题: {theme}")
            if meta.get("tone"):
                tone = meta["tone"]
                if isinstance(tone, list):
                    parts.append(f"基调: {', '.join(tone)}")
                else:
                    parts.append(f"基调: {tone}")

            premise_text = " | ".join(parts)

        if premise_text:
            try:
                vec = get_embedding(premise_text, config)
                existing[premise_key] = vec
                done += 1
                logger.info(f"[{material_id}] 大纲 premise 向量化完成")
            except Exception as e:
                logger.warning(f"[{material_id}] premise 向量化失败: {e}")
                errors += 1

    # 2. 向量化 beats（可选，低优先级）
    structure_file = outline_dir / "structure.yaml"
    if structure_file.exists():
        structure = load_yaml(structure_file)

        beats = {}
        acts = structure.get("acts", [])
        for act_data in acts:
            act_num = act_data.get("act") or act_data.get("act_number")
            for seq_data in act_data.get("sequences", []):
                seq_num = seq_data.get("sequence") or seq_data.get("sequence_number")
                for beat_data in seq_data.get("beats", []):
                    beat_num = beat_data.get("beat") or beat_data.get("beat_number")
                    title = beat_data.get("title", "")
                    desc = beat_data.get("description", "")
                    if title or desc:
                        beat_key = f"beat:{act_num}:{seq_num}:{beat_num}"
                        beat_text = f"{title} | {desc}" if title and desc else title or desc
                        beats[beat_key] = beat_text

        if beats:
            logger.info(f"[{material_id}] 待向量化节拍: {len(beats)} 条")
            for beat_key, beat_text in beats.items():
                if beat_key not in existing:
                    try:
                        vec = get_embedding(beat_text, config)
                        existing[beat_key] = vec
                        done += 1
                    except Exception as e:
                        logger.warning(f"[{material_id}] 节拍 '{beat_key}' 向量化失败: {e}")
                        errors += 1

    # 统一保存（premise + beats）
    if existing:
        _save_embeddings(embeddings_npz, existing, manifest=manifest)
    _log_stats(existing)
    if errors > 0:
        logger.warning(f"[{material_id}] 大纲向量化失败: {errors} 条")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python embedding.py <material_id> [characters|worldbuilding|outline]")
        sys.exit(1)

    material_id = sys.argv[1]
    target = sys.argv[2] if len(sys.argv) > 2 else "chapters"

    if target == "chapters":
        embed_chapters(material_id)
    elif target == "characters":
        embed_characters(material_id)
    elif target == "worldbuilding":
        embed_worldbuilding(material_id)
    elif target == "outline":
        embed_outline(material_id)
    else:
        print(f"未知目标: {target}")
        sys.exit(1)
