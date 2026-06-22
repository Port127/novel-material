#!/usr/bin/env python3
"""记录或校验运行可靠性改造期间受保护文件的摘要。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys


SCHEMA_VERSION = 1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_prefix(path: Path, size: int) -> str:
    digest = hashlib.sha256()
    remaining = size
    with path.open("rb") as source:
        while remaining:
            chunk = source.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            digest.update(chunk)
            remaining -= len(chunk)
    if remaining:
        raise ValueError(f"文件长度小于基线：{path}")
    return digest.hexdigest()


def protected_files(root: Path) -> list[Path]:
    data_dir = root / "data" / "novels"
    logs_dir = root / "logs"
    paths: set[Path] = set()

    if data_dir.exists():
        paths.update(path for path in data_dir.rglob("*") if path.is_file())
    if logs_dir.exists():
        paths.update(path for path in logs_dir.rglob("*.log") if path.is_file())

    return sorted(paths, key=lambda path: path.relative_to(root).as_posix())


def snapshot(root: Path, excluded: set[str] | None = None) -> dict[str, str]:
    excluded = excluded or set()
    return {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in protected_files(root)
        if path.relative_to(root).as_posix() not in excluded
    }


def resolve_append_only_logs(root: Path, values: list[str]) -> dict[str, Path]:
    logs_root = (root / "logs").resolve()
    resolved: dict[str, Path] = {}
    for value in values:
        relative = Path(value)
        target = (root / relative).resolve()
        if (
            relative.is_absolute()
            or target.suffix != ".log"
            or not target.is_relative_to(logs_root)
            or not target.is_file()
        ):
            raise ValueError(f"无效的可追加旧日志：{value}")
        resolved[target.relative_to(root).as_posix()] = target
    return resolved


def record(root: Path, baseline: Path, append_only_values: list[str]) -> int:
    try:
        append_only_paths = resolve_append_only_logs(root, append_only_values)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    payload = {
        "schema_version": SCHEMA_VERSION,
        "files": snapshot(root, set(append_only_paths)),
        "append_only_logs": {
            relative: {
                "size": path.stat().st_size,
                "sha256_prefix": sha256_file(path),
            }
            for relative, path in sorted(append_only_paths.items())
        },
    }
    baseline.parent.mkdir(parents=True, exist_ok=True)
    temp = baseline.with_suffix(f"{baseline.suffix}.tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temp.replace(baseline)
    return 0


def verify(root: Path, baseline: Path) -> int:
    if not baseline.is_file():
        print(f"基线文件不存在：{baseline}", file=sys.stderr)
        return 1

    try:
        payload = json.loads(baseline.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"无法读取基线：{exc}", file=sys.stderr)
        return 1

    if payload.get("schema_version") != SCHEMA_VERSION:
        print("基线 schema_version 不受支持", file=sys.stderr)
        return 1
    expected = payload.get("files")
    if not isinstance(expected, dict):
        print("基线 files 字段无效", file=sys.stderr)
        return 1

    append_only = payload.get("append_only_logs", {})
    if not isinstance(append_only, dict):
        print("基线 append_only_logs 字段无效", file=sys.stderr)
        return 1

    actual = snapshot(root, set(append_only))
    changed = sorted(
        path
        for path in set(expected) | set(actual)
        if expected.get(path) != actual.get(path)
    )
    for relative, metadata in append_only.items():
        path = root / relative
        try:
            expected_size = int(metadata["size"])
            expected_hash = str(metadata["sha256_prefix"])
            if path.stat().st_size < expected_size:
                changed.append(relative)
                continue
            if sha256_prefix(path, expected_size) != expected_hash:
                changed.append(relative)
        except (KeyError, OSError, TypeError, ValueError):
            changed.append(relative)

    changed = sorted(set(changed))
    if changed:
        print("受保护工作区发生变化：", file=sys.stderr)
        for path in changed:
            print(f"- {path}", file=sys.stderr)
        return 1
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("record", "verify"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument(
        "--allow-appending-log",
        action="append",
        default=[],
        help="record 时允许继续追加、但禁止改写既有前缀的旧日志相对路径",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    baseline = args.baseline.resolve()
    if args.action == "record":
        return record(root, baseline, args.allow_appending_log)
    return verify(root, baseline)


if __name__ == "__main__":
    raise SystemExit(main())
