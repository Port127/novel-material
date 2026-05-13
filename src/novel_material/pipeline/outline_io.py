"""大纲生成文件读写辅助函数。

此模块提供大纲生成过程中所需的文件读写功能：
- 读取 meta.yaml, chapter_index.yaml, source.txt
- 写入 _index.yaml, structure.yaml, sequences.yaml, beats.yaml, hooks_network.yaml
"""
from pathlib import Path

from novel_material.infra.yaml_io import load_yaml, save_yaml, load_yaml_list
from novel_material.infra.progress import get_pipeline_logger

logger = get_pipeline_logger()


def load_meta(novel_dir: Path) -> dict:
    """加载小说基本信息。

    Args:
        novel_dir: 小说目录路径

    Returns:
        meta 字典，若文件不存在则返回空字典
    """
    meta_file = novel_dir / "meta.yaml"
    return load_yaml(meta_file) or {}


def load_chapter_index(novel_dir: Path, material_id: str = "") -> tuple[list, bool]:
    """加载章节索引。

    Args:
        novel_dir: 小说目录路径
        material_id: 素材ID（用于日志）

    Returns:
        (chapter_index, success) 元组：
        - chapter_index: 章节索引列表，失败时为空列表
        - success: 是否成功加载
    """
    chapter_index_file = novel_dir / "chapter_index.yaml"
    if not chapter_index_file.exists():
        logger.error(f"[{material_id}] chapter_index.yaml 不存在")
        return [], False
    return load_yaml_list(chapter_index_file), True


def load_source_text(novel_dir: Path, max_chars: int = 5000) -> str:
    """加载原文文本（用于摘要缺失时的回退）。

    Args:
        novel_dir: 小说目录路径
        max_chars: 最大字符数

    Returns:
        原文文本（截取前 max_chars 字符）
    """
    source_file = novel_dir / "source.txt"
    if source_file.exists():
        with open(source_file, "r", encoding="utf-8") as f:
            return f.read()[:max_chars]
    return ""


def save_meta_with_premise(novel_dir: Path, meta: dict, premise_data: dict) -> None:
    """保存包含前提信息的 meta。

    Args:
        novel_dir: 小说目录路径
        meta: 原始 meta 字典
        premise_data: 前提数据（包含 premise, theme, tone, structure_type）
    """
    meta_file = novel_dir / "meta.yaml"
    meta["premise"] = premise_data.get("premise", "未知")
    meta["theme"] = premise_data.get("theme", [])
    meta["tone"] = premise_data.get("tone", [])
    meta["structure_type"] = premise_data.get("structure_type", "三幕式")
    save_yaml(meta_file, meta)


def save_outline_files(
    outline_dir: Path,
    meta: dict,
    acts: list,
    sequences_data: list,
    beats_data: list,
    failed_sequences: int = 0,
) -> None:
    """保存所有大纲输出文件。

    Args:
        outline_dir: 大纲目录路径
        meta: meta 字典
        acts: 幕数据列表
        sequences_data: 序列数据列表
        beats_data: 节拍数据列表
        failed_sequences: 失败序列数
    """
    import time

    total_sequences = sum(len(act.get("sequences", [])) for act in acts)

    # 保存 _index.yaml
    index_data = {
        "structure_type": meta.get("structure_type", "三幕式"),
        "act_count": len(acts),
        "sequence_count": total_sequences,
        "sequence_failed": failed_sequences,
        "hook_count": 0,
        "subplot_count": 0,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    save_yaml(outline_dir / "_index.yaml", index_data)

    # 保存 structure.yaml
    save_yaml(outline_dir / "structure.yaml", {"acts": acts})

    # 保存 sequences.yaml
    save_yaml(outline_dir / "sequences.yaml", sequences_data)

    # 保存 beats.yaml
    save_yaml(outline_dir / "beats.yaml", beats_data)

    # 保存 hooks_network.yaml
    save_yaml(outline_dir / "hooks_network.yaml", {"hooks": [], "subplots": []})


def build_sequences_data(acts: list, material_id: str) -> list:
    """从 acts 数据构建 sequences 数据列表。

    Args:
        acts: 幕数据列表
        material_id: 素材ID

    Returns:
        sequences 数据列表
    """
    sequences_data = []
    for act in acts:
        for seq in act.get("sequences", []):
            sequences_data.append({
                "material_id": material_id,
                "act": act["act_number"],
                "sequence": seq["sequence_number"],
                "title": seq.get("title", ""),
                "chapters_start": seq.get("chapter_start", 0),
                "chapters_end": seq.get("chapter_end", 0),
                "description": seq.get("description", ""),
            })
    return sequences_data


def build_beats_data(acts: list, material_id: str) -> list:
    """从 acts 数据构建 beats 数据列表。

    Args:
        acts: 幕数据列表
        material_id: 素材ID

    Returns:
        beats 数据列表
    """
    beats_data = []
    for act in acts:
        for seq in act.get("sequences", []):
            for beat in seq.get("beats", []):
                beats_data.append({
                    "material_id": material_id,
                    "act": act["act_number"],
                    "sequence": seq["sequence_number"],
                    "beat": beat.get("beat_number", 0),
                    "title": beat.get("title", ""),
                    "chapter": beat.get("chapter", 0),
                    "description": beat.get("description", ""),
                    "tension": beat.get("tension", 1),
                })
    return beats_data


__all__ = [
    "load_meta",
    "load_chapter_index",
    "load_source_text",
    "save_meta_with_premise",
    "save_outline_files",
    "build_sequences_data",
    "build_beats_data",
]