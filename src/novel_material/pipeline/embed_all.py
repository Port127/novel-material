"""统一向量化入口：集中管理所有向量化调用并记录历史。

处理顺序：chapters → characters → worldbuilding → outline

注意：embedding API 不按 token 计费，stage_times 中 tokens 记录为 0。
api_calls 记录处理条数而非实际 API 调用次数（底层 embed 函数内部批量处理）。
"""
import time

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.logging_config import get_embedding_logger
from novel_material.infra.progress import save_run_history
from novel_material.infra.yaml_io import load_yaml
from novel_material.storage.embedding import (
    embed_chapters,
    embed_characters,
    embed_worldbuilding,
    embed_outline,
)

logger = get_embedding_logger()


def embed_all(material_id: str) -> dict:
    """统一向量化入口，返回完成状态。

    处理顺序: chapters → characters → worldbuilding → outline

    Args:
        material_id: 素材 ID

    Returns:
        {"chapters": bool, "characters": bool, "worldbuilding": bool, "outline": bool}
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"[{material_id}] 小说目录不存在")
        return {"chapters": False, "characters": False, "worldbuilding": False, "outline": False}

    results = {}
    stage_times = []
    wall_start = time.monotonic()

    # 1. 章节向量（可选，analyze 已生成）
    chapters_npz = novel_dir / "chapter_embeddings.npz"
    if chapters_npz.exists():
        logger.info(f"[{material_id}] 章节向量已存在，跳过")
        results["chapters"] = True
    else:
        ch_start = time.monotonic()
        try:
            embed_chapters(material_id)
            results["chapters"] = True
            stage_times.append({
                "name": "章节向量",
                "elapsed_sec": time.monotonic() - ch_start,
            })
        except Exception as e:
            logger.warning(f"[{material_id}] 章节向量化失败: {e}")
            results["chapters"] = False

    # 2. 人物向量
    char_start = time.monotonic()
    try:
        embed_characters(material_id)
        results["characters"] = True
        stage_times.append({
            "name": "人物向量",
            "elapsed_sec": time.monotonic() - char_start,
        })
    except Exception as e:
        logger.warning(f"[{material_id}] 人物向量化失败: {e}")
        results["characters"] = False

    # 3. 世界观向量
    wb_start = time.monotonic()
    try:
        embed_worldbuilding(material_id)
        results["worldbuilding"] = True
        stage_times.append({
            "name": "世界观向量",
            "elapsed_sec": time.monotonic() - wb_start,
        })
    except Exception as e:
        logger.warning(f"[{material_id}] 世界观向量化失败: {e}")
        results["worldbuilding"] = False

    # 4. 大纲向量
    outline_start = time.monotonic()
    try:
        embed_outline(material_id)
        results["outline"] = True
        stage_times.append({
            "name": "大纲向量",
            "elapsed_sec": time.monotonic() - outline_start,
        })
    except Exception as e:
        logger.warning(f"[{material_id}] 大纲向量化失败: {e}")
        results["outline"] = False

    total_elapsed = time.monotonic() - wall_start

    # 保存运行历史（tokens/api_calls 对于 embedding API 不适用）
    all_success = all(results.values())
    save_run_history(
        novel_dir=novel_dir,
        pipeline_name="向量化",
        stage_times=stage_times,
        total_elapsed=total_elapsed,
        status="success" if all_success else "partial",
    )

    logger.info(f"[{material_id}] 向量化完成: {results}")
    return results