#!/usr/bin/env python3
"""将项目 Skills 从 .agents 镜像到 .claude，并检测内容漂移。"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = PROJECT_ROOT / ".agents" / "skills"
DEFAULT_TARGET = PROJECT_ROOT / ".claude" / "skills"


def managed_files(root: Path) -> dict[str, Path]:
    """返回非隐藏的受管文件，键为 POSIX 相对路径。"""
    if not root.is_dir():
        return {}
    files: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part.startswith(".") for part in relative.parts):
            continue
        files[relative.as_posix()] = path
    return files


def check_skills(source: Path, target: Path) -> list[str]:
    """比较源与镜像，返回确定性排序的问题列表。"""
    if not source.is_dir():
        return [f"源目录不存在: {source}"]
    source_files = managed_files(source)
    target_files = managed_files(target)
    issues = [
        f"目标缺失: {name}"
        for name in sorted(source_files.keys() - target_files.keys())
    ]
    issues.extend(
        f"目标多余: {name}"
        for name in sorted(target_files.keys() - source_files.keys())
    )
    issues.extend(
        f"内容不同: {name}"
        for name in sorted(source_files.keys() & target_files.keys())
        if source_files[name].read_bytes() != target_files[name].read_bytes()
    )
    return issues


def sync_skills(source: Path, target: Path) -> None:
    """从源目录覆盖目标受管文件，并移除目标侧多余受管文件。"""
    if not source.is_dir():
        raise FileNotFoundError(f"Skills 源目录不存在: {source}")
    source_files = managed_files(source)
    target_files = managed_files(target)

    for name, source_path in source_files.items():
        target_path = target / name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)

    for name, target_path in target_files.items():
        if name not in source_files:
            target_path.unlink()

    for directory in sorted(target.rglob("*"), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="同步或检查项目 Skills 镜像")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--check", action="store_true", help="只检查，不写文件")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.check:
        issues = check_skills(args.source, args.target)
        for issue in issues:
            print(issue)
        return 1 if issues else 0

    sync_skills(args.source, args.target)
    print(f"已同步 {len(managed_files(args.source))} 个 Skills 文件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
