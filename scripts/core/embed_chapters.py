#!/usr/bin/env python
"""章节向量化：把每章摘要转换成向量，用于语义搜索。

为什么要向量化？
- 向量化后的文字可以做"语义搜索"
- 比如搜索"主角打架"，能找到"战斗场面激烈"的章节
- 这是传统的关键词搜索做不到的

输出文件：
- chapter_embeddings.npz：压缩的向量数据文件
  （相比 YAML 格式，体积小 20-30 倍，读取速度更快）

特性：
- 断点续传：已向量化的章节自动跳过
- 格式迁移：自动把旧的 YAML 格式转换成 NPZ 格式
"""
import sys
import yaml
import time
from pathlib import Path

import numpy as np

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from dotenv import load_dotenv
load_dotenv()

from scripts.core.paths import NOVELS_DIR
from scripts.core.embedding import get_embedding, load_embedding_config

# 每批处理的章节数
_BATCH_SIZE = 20
# 批次间等待时间（秒），避免触发 API 限流
_RATE_LIMIT = 0.5


def _load_embeddings(embeddings_npz: Path) -> dict[int, list]:
    """从 NPZ 文件加载已有向量。

    返回：
        dict：{章节号: 向量列表}
    """
    if not embeddings_npz.exists():
        return {}
    data = np.load(str(embeddings_npz))
    chapters_arr = data["chapters"]
    vectors_arr = data["vectors"]
    return {int(ch): vectors_arr[i].tolist() for i, ch in enumerate(chapters_arr)}


def _save_embeddings(embeddings_npz: Path, embeddings: dict[int, list]) -> None:
    """把向量保存到 NPZ 文件。

    参数：
        embeddings_npz：目标文件路径
        embeddings：{章节号: 向量列表}
    """
    if not embeddings:
        return
    # 按章节号排序
    chapters_sorted = sorted(embeddings.keys())
    vectors_matrix = np.array([embeddings[k] for k in chapters_sorted], dtype=np.float32)
    chapters_arr = np.array(chapters_sorted, dtype=np.int32)
    np.savez_compressed(str(embeddings_npz), chapters=chapters_arr, vectors=vectors_matrix)


def _migrate_yaml_to_npz(novel_dir: Path, embeddings_npz: Path) -> dict[int, list]:
    """把旧的 YAML 格式向量文件迁移到 NPZ 格式。

    为什么迁移？
    - YAML 格式体积大（1600章 × 1536维 ≈ 49MB）
    - NPZ 格式体积小（约 2-3MB），读取更快

    迁移后会删除旧的 YAML 文件。
    """
    yaml_file = novel_dir / "chapter_embeddings.yaml"
    if not yaml_file.exists():
        return {}

    print("检测到旧格式 chapter_embeddings.yaml，正在迁移到 .npz...")
    with open(yaml_file, "r", encoding="utf-8") as f:
        old_data = yaml.safe_load(f) or {}

    if not old_data:
        return {}

    # 转换格式（键可能是 int 或 str）
    embeddings = {int(k): v for k, v in old_data.items()}
    _save_embeddings(embeddings_npz, embeddings)

    yaml_file.unlink()
    print(f"迁移完成: {len(embeddings)} 章向量 → {embeddings_npz.name}，已删除旧 YAML 文件")
    return embeddings


def embed_chapters(material_id: str) -> None:
    """为指定小说的所有章节摘要生成向量。

    流程：
    1. 读取 chapters.yaml（章节摘要）
    2. 检查已向量化的章节（断点续传）
    3. 为每个待处理章节调用 Embedding API
    4. 保存到 chapter_embeddings.npz

    参数：
        material_id：素材 ID
    """
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

    # 迁移旧格式
    existing = _migrate_yaml_to_npz(novel_dir, embeddings_npz)
    if not existing:
        existing = _load_embeddings(embeddings_npz)

    if existing:
        print(f"断点续传：已有 {len(existing)} 章向量，跳过")

    # 过滤待处理章节
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

        # 每批保存一次（断点续传）
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
        print("用法: python embed_chapters.py <material_id>")
        sys.exit(1)

    embed_chapters(sys.argv[1])