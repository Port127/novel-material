"""章节向量化：把每章摘要转换成向量，用于语义搜索。"""
import sys
import yaml
import time
from pathlib import Path

import numpy as np

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.embedding import get_embedding, load_embedding_config

_BATCH_SIZE = 20
_RATE_LIMIT = 0.5


def _load_embeddings(embeddings_npz: Path) -> dict[int, list]:
    """从 NPZ 文件加载已有向量。"""
    if not embeddings_npz.exists():
        return {}
    data = np.load(str(embeddings_npz))
    chapters_arr = data["chapters"]
    vectors_arr = data["vectors"]
    return {int(ch): vectors_arr[i].tolist() for i, ch in enumerate(chapters_arr)}


def _save_embeddings(embeddings_npz: Path, embeddings: dict[int, list]) -> None:
    """把向量保存到 NPZ 文件。"""
    if not embeddings:
        return
    chapters_sorted = sorted(embeddings.keys())
    vectors_matrix = np.array([embeddings[k] for k in chapters_sorted], dtype=np.float32)
    chapters_arr = np.array(chapters_sorted, dtype=np.int32)
    np.savez_compressed(str(embeddings_npz), chapters=chapters_arr, vectors=vectors_matrix)


def embed_chapters(material_id: str) -> None:
    """为指定小说的所有章节摘要生成向量。"""
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        print(f"错误: 小说目录不存在: {novel_dir}")
        return

    chapters_file = novel_dir / "chapters.yaml"
    if not chapters_file.exists():
        print("错误: chapters.yaml 不存在，请先运行 chapter_analyze")
        return

    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters = yaml.safe_load(f) or []

    if not chapters:
        print("chapters.yaml 为空，跳过向量化")
        return

    embeddings_npz = novel_dir / "chapter_embeddings.npz"

    existing = _load_embeddings(embeddings_npz)

    if existing:
        print(f"断点续传：已有 {len(existing)} 章向量，跳过")

    pending = [
        ch for ch in chapters
        if ch.get("summary") and ch.get("chapter") not in existing
    ]

    if not pending:
        print("所有章节已向量化，无需处理")
        _print_stats(existing)
        return

    print(f"待向量化: {len(pending)} 章（共 {len(chapters)} 章）")

    config = load_embedding_config()
    done = 0

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
                print(f"  警告: 第{ch_num}章向量化失败: {e}")
                continue

        _save_embeddings(embeddings_npz, existing)
        print(f"  已完成 {done}/{len(pending)} 章")

        if i + _BATCH_SIZE < len(pending):
            time.sleep(_RATE_LIMIT)

    _print_stats(existing)


def _print_stats(embeddings: dict) -> None:
    """打印向量化统计信息。"""
    sample_vec = next(iter(embeddings.values()), None)
    if sample_vec:
        dim = len(sample_vec) if isinstance(sample_vec, list) else sample_vec.shape[0]
        print(f"向量化完成: {len(embeddings)} 章，维度 {dim}")
    else:
        print(f"向量化完成: {len(embeddings)} 章")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python embedding.py <material_id>")
        sys.exit(1)

    embed_chapters(sys.argv[1])