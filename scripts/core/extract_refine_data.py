#!/usr/bin/env python
"""
extract_refine_data.py — 从事件数据提取精简统计摘要，供 refine 使用

不读原文，只读 events/*.yaml。将所有事件数据聚合成精简的统计 JSON，
大幅降低 refine 的上下文压力。

输出内容：
  - 人物出场统计表（人物名 → 出场次数、活跃章节范围、涉及事件列表）
  - tension 按章聚合（章号 → tension 均值、最大值）
  - 钩子清单（所有事件的 hooks 字段汇总）
  - 地点/势力出场统计
  - event_type 分布
  - relationship / interaction 分布

用法:
    python scripts/core/extract_refine_data.py <material_id>
    python scripts/core/extract_refine_data.py <material_id> --output /custom/path.json
"""

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path

import yaml


def _get_tension(data: dict, default: int = 0) -> int:
    """统一读取张力，兼容 legacy tension_peak。"""
    tension = data.get("tension")
    if tension is None:
        tension = data.get("tension_peak", default)
    try:
        return int(tension)
    except (ValueError, TypeError):
        return default


def hash_events_directory(events_dir: Path) -> str:
    """
    计算 events 目录下所有 YAML 文件的 hash。

    用于检测事件数据是否有变化，决定是否需要重新运行 refine。

    Hash 算法：
    1. 遍历所有 ev*.yaml 文件（按文件名排序）
    2. 对每个文件计算 SHA256 hash
    3. 将所有 hash 拼接后再计算最终 hash

    返回 16 字符的短 hash（用于 meta.yaml）。
    """
    if not events_dir.is_dir():
        return ""

    event_files = sorted(events_dir.glob("ev*.yaml"))
    if not event_files:
        return ""

    combined_hashes = ""
    for ef in event_files:
        try:
            with open(ef, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()[:8]
            combined_hashes += file_hash
        except Exception:
            continue

    if not combined_hashes:
        return ""

    final_hash = hashlib.sha256(combined_hashes.encode()).hexdigest()[:16]
    return final_hash


def extract_refine_data(material_id: str, output_path: Path | None = None, update_meta: bool = True) -> dict:
    """从 events/ 提取精炼统计摘要。"""
    base_dir = Path(f"data/novels/{material_id}")
    events_dir = base_dir / "events"
    manifest_path = base_dir / "events_manifest.yaml"
    meta_path = base_dir / "meta.yaml"

    if not events_dir.is_dir():
        print(f"ERROR: events/ 目录不存在: {events_dir}", file=sys.stderr)
        sys.exit(1)

    event_files = sorted(events_dir.glob("ev*.yaml"))
    if not event_files:
        print("ERROR: 无事件文件", file=sys.stderr)
        sys.exit(1)

    # 计算事件数据 hash
    events_hash = hash_events_directory(events_dir)

    # ── 人物出场统计 ──
    char_appearances = defaultdict(lambda: {
        "total_events": 0,
        "chapters": [],
        "event_ids": [],
        "roles": [],
        "moments": [],
    })

    # ── tension 按章聚合 ──
    tension_by_chapter = defaultdict(list)

    # ── 钩子清单 ──
    hooks_list = []

    # ── 地点统计 ──
    location_stats = defaultdict(int)

    # ── event_type 分布 ──
    event_type_dist = defaultdict(int)

    # ── relationship / interaction 分布 ──
    relationship_dist = defaultdict(int)
    interaction_dist = defaultdict(int)

    # ── plot_function 分布 ──
    plot_function_dist = defaultdict(int)

    # ── chapter → events 映射 ──
    chapter_events = defaultdict(list)

    total_events = 0

    for ef in event_files:
        try:
            with open(ef, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception:
            continue
        if not data:
            continue

        total_events += 1
        event_id = data.get("id", ef.stem)
        chapters = data.get("chapters", [])
        if not isinstance(chapters, list):
            chapters = [chapters]
        ch_nums = []
        for ch in chapters:
            try:
                ch_nums.append(int(ch))
            except (ValueError, TypeError):
                pass

        # 人物出场
        characters = data.get("characters", [])
        if isinstance(characters, list):
            for entry in characters:
                if isinstance(entry, dict):
                    name = entry.get("name")
                    role = entry.get("role", "")
                    moment = entry.get("moment", "")
                else:
                    name = str(entry)
                    role = ""
                    moment = ""
                if name:
                    name = str(name)
                    char_appearances[name]["total_events"] += 1
                    char_appearances[name]["chapters"].extend(ch_nums)
                    char_appearances[name]["event_ids"].append(event_id)
                    if role:
                        char_appearances[name]["roles"].append(str(role))
                    if moment:
                        char_appearances[name]["moments"].append(str(moment))

        # tension
        t_val = _get_tension(data, 0)
        if t_val:
            for ch in ch_nums:
                tension_by_chapter[ch].append(t_val)

        # 钩子
        hooks = data.get("hooks", {})
        if isinstance(hooks, dict) and hooks:
            for hook_key in ["chapter_end", "items_crossing", "character_crossing", "info_hint"]:
                val = hooks.get(hook_key)
                if val:
                    if isinstance(val, list):
                        for v in val:
                            # 结构化提取
                            if isinstance(v, dict):
                                # items_crossing: {item, planted_chapter, planted_event, ...}
                                # character_crossing: {character, first_appearance, first_event, ...}
                                # chapter_end: {chapter, type, hook_text, ...}
                                # info_hint: {detail, chapter, context, ...}
                                display_value = (
                                    v.get("item")
                                    or v.get("character")
                                    or v.get("hook_text")
                                    or v.get("detail")
                                    or v.get("type")
                                    or str(v)
                                )
                            else:
                                display_value = str(v)
                            hooks_list.append({
                                "event_id": event_id,
                                "chapters": ch_nums,
                                "hook_key": hook_key,
                                "value": display_value,
                                "chapters_involved": ch_nums,
                            })
                    else:
                        hooks_list.append({
                            "event_id": event_id,
                            "chapters": ch_nums,
                            "hook_key": hook_key,
                            "value": str(val),
                            "chapters_involved": ch_nums,
                        })

        # 地点
        settings = data.get("setting", [])
        if isinstance(settings, list):
            for loc in settings:
                loc = str(loc)
                location_stats[loc] += 1

        # 势力：事件数据中无独立的 faction 字段，跳过
        # 势力关联通过人物的 characters/_index.yaml 体现

        # event_type
        event_type = data.get("event_type", [])
        if isinstance(event_type, list):
            for et in event_type:
                event_type_dist[str(et)] += 1
        elif event_type:
            event_type_dist[str(event_type)] += 1

        # relationship / interaction
        relationship = data.get("relationship", [])
        if isinstance(relationship, list):
            for r in relationship:
                relationship_dist[str(r)] += 1
        interaction = data.get("interaction", [])
        if isinstance(interaction, list):
            for i in interaction:
                interaction_dist[str(i)] += 1

        # plot_function
        pf = data.get("plot_function", [])
        if isinstance(pf, list):
            for p in pf:
                plot_function_dist[str(p)] += 1

        # chapter → events 映射
        for ch in ch_nums:
            chapter_events[ch].append(event_id)

    # ── 压缩输出 ──
    # 人物：去重章节，计算活跃范围
    char_output = {}
    for name, stats in char_appearances.items():
        chapters_unique = sorted(set(stats["chapters"]))
        roles_unique = list(dict.fromkeys(stats["roles"]))
        moments_unique = list(dict.fromkeys(stats["moments"]))
        char_output[name] = {
            "total_events": stats["total_events"],
            "chapter_range": [chapters_unique[0], chapters_unique[-1]] if chapters_unique else [],
            "active_chapters": chapters_unique,
            "event_ids": stats["event_ids"],
            "roles": roles_unique,
            "character_moments": moments_unique,
        }

    # tension 聚合
    tension_output = {}
    for ch, t_vals in sorted(tension_by_chapter.items()):
        tension_output[str(ch)] = {
            "mean": round(sum(t_vals) / len(t_vals), 2),
            "max": max(t_vals),
            "min": min(t_vals),
            "count": len(t_vals),
        }

    output = {
        "material_id": material_id,
        "total_events": total_events,
        "events_hash": events_hash,
        "extracted_at": __import__("datetime").datetime.now().isoformat(),
        "character_appearances": char_output,
        "tension_by_chapter": tension_output,
        "hooks": hooks_list,
        "location_stats": dict(sorted(location_stats.items(), key=lambda x: -x[1])),
        "event_type_distribution": dict(sorted(event_type_dist.items(), key=lambda x: -x[1])),
        "relationship_distribution": dict(sorted(relationship_dist.items(), key=lambda x: -x[1])),
        "interaction_distribution": dict(sorted(interaction_dist.items(), key=lambda x: -x[1])),
        "plot_function_distribution": dict(sorted(plot_function_dist.items(), key=lambda x: -x[1])),
        "chapter_events_map": {str(k): v for k, v in sorted(chapter_events.items())},
        "summary": {
            "total_characters": len(char_output),
            "total_hooks": len(hooks_list),
            "total_locations": len(location_stats),
            "tension_chapters": len(tension_output),
        },
    }

    # 输出
    if output_path is None:
        output_path = base_dir / "refine_input.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 更新 meta.yaml 的 refine_hash
    if update_meta and meta_path.exists():
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = yaml.safe_load(f) or {}
            pipeline = meta.get("pipeline", {})
            pipeline["refine_hash"] = events_hash
            meta["pipeline"] = pipeline
            with open(meta_path, "w", encoding="utf-8") as f:
                yaml.dump(meta, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            print(f"📄 meta.yaml refine_hash 已更新: {events_hash}")
        except Exception as e:
            print(f"⚠️ 更新 meta.yaml 失败: {e}", file=sys.stderr)

    print(f"📄 精炼数据已写入: {output_path}")
    print(f"  事件总数: {total_events}")
    print(f"  人物数: {len(char_output)}")
    print(f"  钩子数: {len(hooks_list)}")
    print(f"  地点数: {len(location_stats)}")
    print(f"  Hash: {events_hash}")

    return output


def main():
    parser = argparse.ArgumentParser(description="从事件数据提取精炼统计摘要")
    parser.add_argument("material_id", help="素材 ID")
    parser.add_argument("--output", help="自定义输出路径", default=None)
    parser.add_argument("--no-update-meta", help="不更新 meta.yaml 的 refine_hash", action="store_true")

    args = parser.parse_args()
    output_path = Path(args.output) if args.output else None
    extract_refine_data(args.material_id, output_path, update_meta=not args.no_update_meta)


if __name__ == "__main__":
    main()
