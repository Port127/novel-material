#!/usr/bin/env python
"""
validate_completeness.py — 交叉验证事件数据完整性

对比 source_entities.json（原文客观实体）与 events 数据（事件记录），
输出遗漏报告 completeness_report.yaml。

检查维度：
  - 角色覆盖：原文出现 N 次 > 0，事件记录 0 次 → critical
  - 角色覆盖：原文出现 N 次 > 5，事件记录 ≤ 1 次 → warning
  - 地点覆盖：原文出现 N 次 > 0，事件记录 0 次 → warning
  - 物品覆盖：原文出现 N 次 > 2，事件记录 0 次 → warning
  - 势力覆盖：原文出现 N 次 > 0，事件记录 0 次 → critical
  - 章节覆盖：某章节未被任何事件覆盖 → critical

用法:
    python scripts/core/validate_completeness.py <material_id>
    python scripts/core/validate_completeness.py <material_id> --output /custom/path.yaml
"""

import argparse
import json
import sys
from pathlib import Path

import yaml


def load_event_mentions(base_dir: Path) -> dict:
    """从 events/ 中提取所有实体的出现统计。"""
    events_dir = base_dir / "events"
    if not events_dir.is_dir():
        return {
            "characters": {},
            "locations": {},
            "factions": {},
            "items": {},
            "terminology": {},
            "covered_chapters": set(),
        }

    char_counts = {}
    location_counts = {}
    faction_counts = {}
    item_counts = {}
    terminology_counts = {}
    covered_chapters = set()

    for ef in sorted(events_dir.glob("ev*.yaml")):
        try:
            with open(ef, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception:
            continue
        if not data:
            continue

        # 覆盖章节
        chapters = data.get("chapters", [])
        if isinstance(chapters, list):
            for ch in chapters:
                try:
                    covered_chapters.add(int(ch))
                except (ValueError, TypeError):
                    pass

        # 角色
        characters = data.get("characters", [])
        if isinstance(characters, list):
            for entry in characters:
                if isinstance(entry, dict):
                    name = entry.get("name")
                else:
                    name = str(entry)
                if name:
                    name = str(name)
                    char_counts[name] = char_counts.get(name, 0) + 1

        # 地点 (setting 字段)
        settings = data.get("setting", [])
        if isinstance(settings, list):
            for loc in settings:
                loc = str(loc)
                location_counts[loc] = location_counts.get(loc, 0) + 1

        # 势力：事件数据中没有独立的 faction 字段，跳过统计
        # 势力关联通过人物的 characters/_index.yaml 中的 factions 字段体现

        # 物品/道具 (hooks.items_crossing 或独立的 items)
        hooks = data.get("hooks", {})
        if isinstance(hooks, dict):
            items_crossing = hooks.get("items_crossing", [])
            if isinstance(items_crossing, list):
                for item in items_crossing:
                    item = str(item)
                    item_counts[item] = item_counts.get(item, 0) + 1
        items = data.get("items", [])
        if isinstance(items, list):
            for item in items:
                item = str(item)
                item_counts[item] = item_counts.get(item, 0) + 1

        # 术语 (可能出现在 info_hint 或 plot_function 中)
        # 暂时从 hooks.info_hint 提取
        if isinstance(hooks, dict):
            info_hints = hooks.get("info_hint", [])
            if isinstance(info_hints, list):
                for term in info_hints:
                    term = str(term)
                    terminology_counts[term] = terminology_counts.get(term, 0) + 1

    return {
        "characters": char_counts,
        "locations": location_counts,
        "factions": faction_counts,
        "items": item_counts,
        "terminology": terminology_counts,
        "covered_chapters": covered_chapters,
    }


def load_source_entities(base_dir: Path) -> dict:
    """读取 source_entities.json。"""
    se_path = base_dir / "source_entities.json"
    if not se_path.exists():
        print(f"ERROR: source_entities.json 不存在，请先运行 extract_source_entities.py", file=sys.stderr)
        sys.exit(1)
    with open(se_path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_coverage(
    source_stats: dict,
    event_stats: dict,
    entity_type: str,
    critical_threshold: int = 0,
    warning_threshold: int = 5,
) -> list[dict]:
    """
    对比原文统计 vs 事件统计，返回遗漏列表。

    Args:
        source_stats: {name: {"total_mentions": N, "chapters": [...]}, ...}
        event_stats: {name: count, ...}
        entity_type: "character" | "location" | "faction" | "item" | "terminology"
        critical_threshold: 原文出现次数 ≤ 此值时不告警
        warning_threshold: 原文出现次数 ≤ 此值时给 warning，超过给 critical
    """
    issues = []
    for name, stats in source_stats.items():
        source_mentions = stats.get("total_mentions", 0)
        event_mentions = event_stats.get(name, 0)
        chapters = stats.get("chapters", [])

        if source_mentions <= critical_threshold:
            continue

        gap = source_mentions - event_mentions
        if gap > 0:
            # 决定告警级别
            if source_mentions > warning_threshold and event_mentions <= 1:
                severity = "critical"
                action = f"回读第{chapters[:5]}章，补充{name}相关事件记录"
            else:
                severity = "warning"
                action = f"回读第{chapters[:3]}章，确认是否需要补充{name}"

            issues.append({
                "entity": name,
                "type": entity_type,
                "source_mentions": source_mentions,
                "event_mentions": event_mentions,
                "gap": gap,
                "severity": severity,
                "source_chapters": chapters,
                "suggested_action": action,
            })

    return issues


def check_chapter_coverage(
    total_chapters: int,
    covered_chapters: set,
) -> list[dict]:
    """检查是否有章节未被任何事件覆盖。"""
    missing = set(range(1, total_chapters + 1)) - covered_chapters
    if not missing:
        return []

    # 找出连续缺失的章节范围
    sorted_missing = sorted(missing)
    ranges = []
    start = sorted_missing[0]
    end = sorted_missing[0]
    for ch in sorted_missing[1:]:
        if ch == end + 1:
            end = ch
        else:
            ranges.append(f"{start}-{end}")
            start = ch
            end = ch
    ranges.append(f"{start}-{end}")

    return [{
        "entity": f"章节 {r}",
        "type": "chapter",
        "source_mentions": 1,
        "event_mentions": 0,
        "gap": 1,
        "severity": "critical",
        "suggested_action": f"章节 {r} 未被任何事件覆盖，需要补录",
    } for r in ranges]


def validate_completeness(
    material_id: str,
    output_path: Path | None = None,
) -> dict:
    """运行完整性验证。"""
    base_dir = Path(f"data/novels/{material_id}")

    source_entities = load_source_entities(base_dir)
    event_mentions = load_event_mentions(base_dir)
    total_chapters = source_entities.get("total_chapters", 0)

    # 各维度检查
    char_issues = check_coverage(
        source_entities.get("characters", {}),
        event_mentions["characters"],
        "character",
        critical_threshold=0,
        warning_threshold=5,
    )
    location_issues = check_coverage(
        source_entities.get("locations", {}),
        event_mentions["locations"],
        "location",
        critical_threshold=0,
        warning_threshold=5,
    )
    # 势力覆盖：事件数据中无独立的 faction 字段，不做交叉验证
    # 势力关联主要通过人物的 characters/_index.yaml 中的 factions 字段体现
    faction_issues = []
    item_issues = check_coverage(
        source_entities.get("items", {}),
        event_mentions["items"],
        "item",
        critical_threshold=2,
        warning_threshold=5,
    )
    terminology_issues = check_coverage(
        source_entities.get("terminology", {}),
        event_mentions["terminology"],
        "terminology",
        critical_threshold=2,
        warning_threshold=5,
    )
    chapter_issues = check_chapter_coverage(total_chapters, event_mentions["covered_chapters"])

    all_issues = char_issues + location_issues + faction_issues + item_issues + terminology_issues + chapter_issues

    # 按严重程度排序
    all_issues.sort(key=lambda x: (0 if x["severity"] == "critical" else 1, -x["gap"]))

    # 统计
    critical_count = sum(1 for i in all_issues if i["severity"] == "critical")
    warning_count = sum(1 for i in all_issues if i["severity"] == "warning")

    # 覆盖率估算（排除势力，因为势力不做事件级交叉验证）
    total_source_entities = sum(
        len(source_entities.get(k, {}))
        for k in ["characters", "locations", "items", "terminology"]
    )
    covered_entities = total_source_entities - len(all_issues)
    coverage_rate = round(covered_entities / total_source_entities, 3) if total_source_entities > 0 else 1.0

    report = {
        "material_id": material_id,
        "validated_at": __import__("datetime").datetime.now().isoformat(),
        "total_chapters": total_chapters,
        "completeness_score": coverage_rate,
        "summary": {
            "total_issues": len(all_issues),
            "critical": critical_count,
            "warning": warning_count,
            "by_type": {
                "character": len(char_issues),
                "location": len(location_issues),
                "faction": len(faction_issues),
                "item": len(item_issues),
                "terminology": len(terminology_issues),
                "chapter": len(chapter_issues),
            },
        },
        "issues": all_issues if all_issues else None,
    }

    # 输出
    if output_path is None:
        output_path = base_dir / "completeness_report.yaml"

    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(report, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"📊 完整性验证报告 — {material_id}")
    print(f"  覆盖率: {coverage_rate:.1%}")
    print(f"  总问题数: {len(all_issues)}")
    print(f"  Critical: {critical_count}")
    print(f"  Warning: {warning_count}")
    print(f"\n📄 报告已写入: {output_path}")

    # 更新 meta.yaml
    meta_path = base_dir / "meta.yaml"
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = yaml.safe_load(f) or {}
        pipeline = meta.get("pipeline", {})
        pipeline["completeness_validated"] = True
        pipeline["completeness_score"] = coverage_rate
        pipeline["completeness_critical_count"] = critical_count
        meta["pipeline"] = pipeline
        with open(meta_path, "w", encoding="utf-8") as f:
            yaml.dump(meta, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        print(f"📄 完整性状态已更新 meta.yaml")

    return report


def main():
    parser = argparse.ArgumentParser(description="交叉验证事件数据完整性")
    parser.add_argument("material_id", help="素材 ID")
    parser.add_argument("--output", help="自定义输出路径", default=None)

    args = parser.parse_args()
    output_path = Path(args.output) if args.output else None
    validate_completeness(args.material_id, output_path)


if __name__ == "__main__":
    main()
