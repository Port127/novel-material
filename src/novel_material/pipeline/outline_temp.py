"""大纲生成临时文件管理：断点续传支持。

此模块包含大纲生成过程中的临时文件读写函数，
供 outline_core.py 使用。
"""
import yaml
import time
from pathlib import Path


def _save_acts_temp(outline_dir: Path, acts: list) -> None:
    """保存幕/序列划分中间结果到临时文件。

    Args:
        outline_dir: outline 目录路径
        acts: 幕/序列数据列表
    """
    acts_temp_file = outline_dir / "acts_temp.yaml"
    with open(acts_temp_file, "w", encoding="utf-8") as f:
        yaml.dump({"acts": acts}, f, allow_unicode=True, default_flow_style=False)


def _load_acts_temp(outline_dir: Path) -> list | None:
    """加载幕/序列划分临时文件（断点续传）。

    Args:
        outline_dir: outline 目录路径

    Returns:
        acts 列表，如果不存在返回 None
    """
    acts_temp_file = outline_dir / "acts_temp.yaml"
    if not acts_temp_file.exists():
        return None
    with open(acts_temp_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("acts", [])


def _save_sequence_beats_temp(outline_dir: Path, act_num: int, seq_num: int, beats: list) -> None:
    """保存单个序列的 beats 到临时文件。

    Args:
        outline_dir: outline 目录路径
        act_num: 幕编号
        seq_num: 序列编号
        beats: beats 数据列表
    """
    beats_temp_dir = outline_dir / "beats_temp"
    beats_temp_dir.mkdir(exist_ok=True)
    beats_temp_file = beats_temp_dir / f"act{act_num}_seq{seq_num}.yaml"
    with open(beats_temp_file, "w", encoding="utf-8") as f:
        yaml.dump(beats, f, allow_unicode=True, default_flow_style=False)


def _load_sequence_beats_temp(outline_dir: Path, act_num: int, seq_num: int) -> list | None:
    """加载单个序列的 beats 临时文件（断点续传）。

    Args:
        outline_dir: outline 目录路径
        act_num: 幕编号
        seq_num: 序列编号

    Returns:
        beats 列表，如果不存在返回 None
    """
    beats_temp_file = outline_dir / "beats_temp" / f"act{act_num}_seq{seq_num}.yaml"
    if not beats_temp_file.exists():
        return None
    with open(beats_temp_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def _save_outline_progress(outline_dir: Path, completed_seqs: list, total_sequences: int) -> None:
    """保存大纲进度到临时文件。

    Args:
        outline_dir: outline 目录路径
        completed_seqs: 已完成的序列标识列表（如 ["1_1", "1_2", "2_1"]）
        total_sequences: 总序列数
    """
    progress_file = outline_dir / "_progress.yaml"
    progress_data = {
        "completed_sequences": completed_seqs,
        "total_sequences": total_sequences,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")
    }
    with open(progress_file, "w", encoding="utf-8") as f:
        yaml.dump(progress_data, f, allow_unicode=True, default_flow_style=False)


def _load_outline_progress(outline_dir: Path) -> dict:
    """加载大纲进度（断点续传）。

    Args:
        outline_dir: outline 目录路径

    Returns:
        dict: {"completed_sequences": [...], "total_sequences": int}
    """
    progress_file = outline_dir / "_progress.yaml"
    if not progress_file.exists():
        return {"completed_sequences": [], "total_sequences": 0}
    with open(progress_file, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"completed_sequences": [], "total_sequences": 0}


def _cleanup_outline_temp_files(outline_dir: Path) -> None:
    """清理 outline 临时文件。

    Args:
        outline_dir: outline 目录路径
    """
    # 清理 acts_temp.yaml
    acts_temp = outline_dir / "acts_temp.yaml"
    if acts_temp.exists():
        acts_temp.unlink()

    # 清理 beats_temp 目录
    beats_temp_dir = outline_dir / "beats_temp"
    if beats_temp_dir.exists():
        for f in beats_temp_dir.glob("*.yaml"):
            f.unlink()
        beats_temp_dir.rmdir()

    # 清理 _progress.yaml
    progress_file = outline_dir / "_progress.yaml"
    if progress_file.exists():
        progress_file.unlink()


__all__ = [
    "_save_acts_temp",
    "_load_acts_temp",
    "_save_sequence_beats_temp",
    "_load_sequence_beats_temp",
    "_save_outline_progress",
    "_load_outline_progress",
    "_cleanup_outline_temp_files",
]