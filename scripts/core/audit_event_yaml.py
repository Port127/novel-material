#!/usr/bin/env python3
"""
audit_event_yaml.py — 审计 / 迁移事件 YAML

目标：
1. 审计事件文件与当前 schema / tags 字典的偏差
2. 统计 tension / tension_peak 的使用情况
3. 在显式 --write 时，规范化 legacy tension_peak

默认 dry-run，不修改文件。

用法:
    python scripts/core/audit_event_yaml.py
    python scripts/core/audit_event_yaml.py --material <material_id>
    python scripts/core/audit_event_yaml.py --report /tmp/event-audit.yaml
    python scripts/core/audit_event_yaml.py --write
"""

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from validate_yaml import EventValidator, SchemaLoader, TagsDomainLoader


NOVELS_DIR = Path("data/novels")
SCHEMA_PATH = Path("docs/schemas/event-unit.schema.yaml")
TAGS_PATH = Path("data/tags.yaml")


@dataclass
class TensionAction:
    state: str
    fixable: bool
    changed: bool
    reason: str


def iter_material_dirs(material_id: str | None):
    if material_id:
        yield NOVELS_DIR / material_id
        return
    for novel_dir in sorted(NOVELS_DIR.glob("nm_*")):
        if novel_dir.is_dir():
            yield novel_dir


def analyze_tension_state(event: dict) -> TensionAction:
    has_tension = event.get("tension") is not None
    has_peak = event.get("tension_peak") is not None

    if has_tension and has_peak:
        if event["tension"] == event["tension_peak"]:
            return TensionAction(
                state="both_equal",
                fixable=True,
                changed=True,
                reason="同时存在 tension 与 tension_peak，且值一致；可删除 legacy 字段",
            )
        return TensionAction(
            state="both_conflict",
            fixable=False,
            changed=False,
            reason="同时存在 tension 与 tension_peak，但值不一致；需人工确认",
        )

    if has_peak:
        return TensionAction(
            state="tension_peak_only",
            fixable=True,
            changed=True,
            reason="仅存在 legacy tension_peak；可迁移为 tension",
        )

    if has_tension:
        return TensionAction(
            state="tension_only",
            fixable=False,
            changed=False,
            reason="已使用规范字段 tension",
        )

    return TensionAction(
        state="missing",
        fixable=False,
        changed=False,
        reason="缺少 tension / tension_peak",
    )


def normalize_tension_fields(event: dict) -> tuple[dict, TensionAction]:
    normalized = dict(event)
    action = analyze_tension_state(normalized)

    if action.state == "both_equal":
        del normalized["tension_peak"]
    elif action.state == "tension_peak_only":
        normalized["tension"] = normalized.pop("tension_peak")

    return normalized, action


def load_yaml(path: Path) -> dict | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def dump_yaml(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def audit_material(material_dir: Path, validator: EventValidator, write: bool) -> dict:
    material_id = material_dir.name
    events_dir = material_dir / "events"
    event_files = sorted(events_dir.glob("ev*.yaml")) if events_dir.is_dir() else []

    tension_counter = Counter()
    error_counter = Counter()
    warning_counter = Counter()
    changed_files = []
    skipped_conflicts = []
    parse_failures = []

    samples = {
        "both_equal": [],
        "both_conflict": [],
        "tension_peak_only": [],
        "missing": [],
        "missing_material_id": [],
        "missing_emotion_arc": [],
    }

    files_with_errors = 0
    files_with_warnings = 0

    for event_path in event_files:
        raw = load_yaml(event_path)
        if raw is None:
            parse_failures.append(event_path.name)
            continue

        tension_action = analyze_tension_state(raw)
        tension_counter[tension_action.state] += 1
        if tension_action.state in samples and len(samples[tension_action.state]) < 10:
            samples[tension_action.state].append(event_path.name)

        if write and tension_action.fixable:
            normalized, action_after = normalize_tension_fields(raw)
            if action_after.changed and normalized != raw:
                dump_yaml(event_path, normalized)
                changed_files.append(event_path.name)
                raw = normalized
        elif tension_action.state == "both_conflict":
            skipped_conflicts.append(event_path.name)

        errors, warnings = validator.validate(event_path)
        if errors:
            files_with_errors += 1
            for error in errors:
                error_counter[error] += 1
                if error == "缺少必填字段: material_id" and len(samples["missing_material_id"]) < 10:
                    samples["missing_material_id"].append(event_path.name)
                if error == "缺少必填字段: emotion_arc" and len(samples["missing_emotion_arc"]) < 10:
                    samples["missing_emotion_arc"].append(event_path.name)
        if warnings:
            files_with_warnings += 1
            for warning in warnings:
                warning_counter[warning] += 1

    return {
        "material_id": material_id,
        "total_events": len(event_files),
        "parse_failures": parse_failures,
        "files_with_errors": files_with_errors,
        "files_with_warnings": files_with_warnings,
        "tension_usage": dict(tension_counter),
        "top_errors": [
            {"error": error, "count": count}
            for error, count in error_counter.most_common(10)
        ],
        "top_warnings": [
            {"warning": warning, "count": count}
            for warning, count in warning_counter.most_common(10)
        ],
        "changed_files": changed_files,
        "skipped_conflicts": skipped_conflicts,
        "samples": samples,
    }


def build_summary(results: list[dict], write: bool) -> dict:
    summary = {
        "generated_at": datetime.now().isoformat(),
        "mode": "write" if write else "dry-run",
        "materials": results,
        "totals": {
            "materials": len(results),
            "events": sum(r["total_events"] for r in results),
            "files_with_errors": sum(r["files_with_errors"] for r in results),
            "files_with_warnings": sum(r["files_with_warnings"] for r in results),
            "changed_files": sum(len(r["changed_files"]) for r in results),
            "parse_failures": sum(len(r["parse_failures"]) for r in results),
        },
    }
    return summary


def print_summary(summary: dict):
    totals = summary["totals"]
    print(f"📊 事件 YAML 审计完成（mode={summary['mode']}）")
    print(f"  materials: {totals['materials']}")
    print(f"  events: {totals['events']}")
    print(f"  files_with_errors: {totals['files_with_errors']}")
    print(f"  files_with_warnings: {totals['files_with_warnings']}")
    print(f"  changed_files: {totals['changed_files']}")
    print(f"  parse_failures: {totals['parse_failures']}")

    for result in summary["materials"]:
        print(f"\n# {result['material_id']}")
        print(f"  total_events: {result['total_events']}")
        print(f"  tension_usage: {result['tension_usage']}")
        if result["top_errors"]:
            print("  top_errors:")
            for item in result["top_errors"][:5]:
                print(f"    - {item['count']} × {item['error']}")
        if result["changed_files"]:
            print(f"  changed_files: {', '.join(result['changed_files'][:10])}")
        if result["skipped_conflicts"]:
            print(f"  skipped_conflicts: {', '.join(result['skipped_conflicts'][:10])}")


def main():
    parser = argparse.ArgumentParser(description="审计 / 迁移事件 YAML")
    parser.add_argument("--material", help="仅处理指定 material_id", default=None)
    parser.add_argument("--report", help="将审计结果写入 YAML 文件", default=None)
    parser.add_argument("--write", action="store_true", help="实际写回 tension 字段规范化；默认 dry-run")
    args = parser.parse_args()

    schema_loader = SchemaLoader(SCHEMA_PATH)
    tags_loader = TagsDomainLoader(TAGS_PATH)
    validator = EventValidator(schema_loader, tags_loader, chapter_titles=None, lenient=False)

    results = [
        audit_material(material_dir, validator, args.write)
        for material_dir in iter_material_dirs(args.material)
        if material_dir.exists()
    ]

    summary = build_summary(results, args.write)
    print_summary(summary)

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        dump_yaml(report_path, summary)
        print(f"\n📄 审计报告已写入: {report_path}")


if __name__ == "__main__":
    main()
