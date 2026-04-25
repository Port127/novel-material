#!/usr/bin/env python3
"""
migrate_refine_batches.py — 迁移 legacy 顶层 refine_batches 到 pipeline.refine_batches

默认 dry-run，仅报告将发生的变更。

用法:
    python scripts/core/migrate_refine_batches.py
    python scripts/core/migrate_refine_batches.py --material <material_id>
    python scripts/core/migrate_refine_batches.py --write
"""

import argparse
import sys
from pathlib import Path

import yaml


NOVELS_DIR = Path("data/novels")


def iter_meta_paths(material_id: str | None):
    if material_id:
        yield NOVELS_DIR / material_id / "meta.yaml"
        return
    for meta_path in sorted(NOVELS_DIR.glob("*/meta.yaml")):
        yield meta_path


def migrate_meta(meta_path: Path, write: bool) -> str:
    if not meta_path.exists():
        return f"SKIP {meta_path}: meta.yaml 不存在"

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}

    legacy = meta.get("refine_batches")
    pipeline = meta.get("pipeline")
    pipeline_refine = pipeline.get("refine_batches") if isinstance(pipeline, dict) else None

    if legacy is None:
        return f"OK   {meta_path}: 无 legacy refine_batches"

    if pipeline_refine is not None and pipeline_refine != legacy:
        return f"CONFLICT {meta_path}: 顶层 refine_batches 与 pipeline.refine_batches 不一致，未自动迁移"

    if not isinstance(pipeline, dict):
        pipeline = {}
        meta["pipeline"] = pipeline

    pipeline["refine_batches"] = legacy
    del meta["refine_batches"]

    if write:
        with open(meta_path, "w", encoding="utf-8") as f:
            yaml.dump(meta, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        return f"MIGRATED {meta_path}"

    return f"DRY-RUN {meta_path}: 将顶层 refine_batches 迁移到 pipeline.refine_batches"


def main():
    parser = argparse.ArgumentParser(description="迁移 legacy 顶层 refine_batches 到 pipeline.refine_batches")
    parser.add_argument("--material", help="仅迁移指定 material_id", default=None)
    parser.add_argument("--write", action="store_true", help="实际写入文件；默认仅 dry-run")
    args = parser.parse_args()

    statuses = [migrate_meta(meta_path, args.write) for meta_path in iter_meta_paths(args.material)]
    for status in statuses:
        print(status)

    conflicts = [s for s in statuses if s.startswith("CONFLICT")]
    if conflicts:
        sys.exit(1)


if __name__ == "__main__":
    main()
