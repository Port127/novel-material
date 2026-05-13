"""章节分析文件操作：IO 相关操作，无业务逻辑。

此模块包含 analyze 流水线所需的文件操作函数，
用于断点续传、章节文件读写和合并。
"""
from pathlib import Path

from novel_material.infra.progress import get_pipeline_logger
from novel_material.infra.yaml_io import load_yaml, save_yaml, load_yaml_list

logger = get_pipeline_logger()


def _load_existing_chapters(novel_dir: Path) -> dict[int, dict]:
    """加载已分析的章节，用于断点续传。

    优先从 chapters/ 子目录读取（分析过程中的中间文件），
    如果不存在则读取 chapters.yaml（分析完成后的合并文件）。

    返回：
        dict：{章节号: 分析数据}
    """
    chapters_dir = novel_dir / "chapters"
    if chapters_dir.exists():
        result = {}
        for f in chapters_dir.glob("*.yaml"):
            data = load_yaml(f)
            if isinstance(data, dict) and "chapter" in data:
                result[data["chapter"]] = data
        if result:
            return result

    chapters_file = novel_dir / "chapters.yaml"
    if not chapters_file.exists():
        return {}
    existing = load_yaml_list(chapters_file)
    return {ch["chapter"]: ch for ch in existing if isinstance(ch, dict) and "chapter" in ch}


def _append_chapter(novel_dir: Path, chapter_data: dict) -> None:
    """将单章分析结果写入独立文件。

    文件路径：chapters/{章节号}.yaml

    这样做的好处：
    - 每章分析完立即保存，中断也不会丢失
    - 不需要每次重写整个 chapters.yaml（性能更好）
    """
    chapters_dir = novel_dir / "chapters"
    chapters_dir.mkdir(exist_ok=True)
    ch_num = chapter_data["chapter"]
    chapter_file = chapters_dir / f"{ch_num:04d}.yaml"
    save_yaml(chapter_file, chapter_data)


def _merge_chapters(novel_dir: Path, material_id: str = "") -> None:
    """合并所有独立章节文件为 chapters.yaml。

    在分析完成后调用，生成一个完整快照供其他脚本使用。
    """
    chapters_dir = novel_dir / "chapters"
    if not chapters_dir.exists():
        return
    all_chapters = []
    for f in sorted(chapters_dir.glob("*.yaml")):
        data = load_yaml(f)
        if isinstance(data, dict):
            all_chapters.append(data)
    all_chapters.sort(key=lambda x: x.get("chapter", 0))
    chapters_file = novel_dir / "chapters.yaml"
    save_yaml(chapters_file, all_chapters)
    prefix = f"[{material_id}] " if material_id else ""
    logger.info(f"{prefix}已合并 {len(all_chapters)} 章 → chapters.yaml")


__all__ = [
    "_load_existing_chapters",
    "_append_chapter",
    "_merge_chapters",
]