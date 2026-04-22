#!/usr/bin/env python
"""
extract_source_entities.py — 从原文提取客观实体清单

不依赖 AI 判断，基于已构建的人物/世界观实体名册对 source.txt 做
正向匹配，统计每个实体在各章节的出现次数。输出 source_entities.json，
供后续交叉验证（validate_completeness.py）使用。

用法:
    python scripts/core/extract_source_entities.py <material_id>
    python scripts/core/extract_source_entities.py <material_id> --output /custom/path.json
"""

import argparse
import json
import re
import sys
from pathlib import Path

import yaml


def load_character_names(characters_dir: Path) -> list[str]:
    """从 characters/_index.yaml 和 profiles/ 中提取角色名清单。"""
    names = []
    index_path = characters_dir / "_index.yaml"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        roster = data.get("roster", [])
        for entry in roster:
            name = entry.get("name")
            if name:
                names.append(str(name))
    # 补充 profiles/ 中的文件名（去掉 .yaml）
    profiles_dir = characters_dir / "profiles"
    if profiles_dir.is_dir():
        for pf in profiles_dir.glob("*.yaml"):
            name = pf.stem
            if name and name not in names:
                names.append(name)
    return names


def load_worldbuilding_entities(worldbuilding_dir: Path) -> dict[str, list[str]]:
    """从 worldbuilding/ 提取地点、势力、物品、术语清单。"""
    entities: dict[str, list[str]] = {
        "locations": [],
        "factions": [],
        "items": [],
        "terminology": [],
    }

    # ── geography ──
    geo_folder = worldbuilding_dir / "geography"
    geo_file = worldbuilding_dir / "geography.yaml"
    if geo_folder.is_dir():
        for gf in sorted(geo_folder.glob("*.yaml")):
            if gf.name == "_index.yaml":
                continue
            with open(gf, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            region_name = data.get("region_name", gf.stem)
            if region_name:
                entities["locations"].append(str(region_name))
    elif geo_file.exists():
        with open(geo_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for region in data.get("regions", []):
            name = region.get("name")
            if name:
                entities["locations"].append(str(name))

    # ── factions ──
    factions_folder = worldbuilding_dir / "factions"
    factions_file = worldbuilding_dir / "factions.yaml"
    if factions_folder.is_dir():
        for ff in sorted(factions_folder.glob("*.yaml")):
            if ff.name == "_index.yaml":
                continue
            with open(ff, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            faction_name = data.get("faction_name", ff.stem)
            if faction_name:
                entities["factions"].append(str(faction_name))
    elif factions_file.exists():
        with open(factions_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for faction in data.get("factions", []):
            name = faction.get("name")
            if name:
                entities["factions"].append(str(name))

    # ── lore/artifacts.yaml ──
    artifacts_path = worldbuilding_dir / "lore" / "artifacts.yaml"
    if artifacts_path.exists():
        with open(artifacts_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for artifact in data.get("artifacts", []):
            name = artifact.get("name")
            if name:
                entities["items"].append(str(name))

    # ── lore/terminology.yaml ──
    terminology_path = worldbuilding_dir / "lore" / "terminology.yaml"
    if terminology_path.exists():
        with open(terminology_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for term in data.get("terminology", []):
            name = term.get("term")
            if name:
                entities["terminology"].append(str(name))

    return entities


def split_source_by_chapters(source_text: str, base_dir: Path) -> tuple[list[tuple[int, str]], int]:
    """
    将原文按章节切分。优先用 chapter_index.yaml 标题匹配，
    失败时退回正则表达式匹配（第X章/第X节/Chapter X）。
    返回 ([(chapter_number, chapter_text), ...], total_chapters) 元组。
    """
    ci_path = base_dir / "chapter_index.yaml"
    total_chapters = 0

    # 尝试用 chapter_index.yaml 的标题匹配
    if ci_path.exists():
        with open(ci_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        ci_chapters = data.get("chapters", [])
        if ci_chapters:
            titles = []
            if isinstance(ci_chapters[0], dict):
                titles = [c.get("title", "") for c in ci_chapters]
            else:
                titles = [str(c) for c in ci_chapters]
            titles = [t for t in titles if t]

            if titles:
                positions = []
                for i, ch_title in enumerate(titles):
                    match = re.search(re.escape(ch_title), source_text)
                    if match:
                        positions.append((i + 1, match.start()))

                if len(positions) >= len(titles) * 0.8:
                    # 80% 以上标题匹配成功，认为切分有效
                    results = []
                    for idx, (ch_num, ch_start) in enumerate(positions):
                        ch_end = (
                            positions[idx + 1][1]
                            if idx + 1 < len(positions)
                            else len(source_text)
                        )
                        results.append((ch_num, source_text[ch_start:ch_end]))
                    total_chapters = max(ch for ch, _ in results) if results else 0
                    return results, total_chapters

    # 退回正则表达式匹配：第X章、第X节、Chapter X
    patterns = [
        re.compile(r"第\s*(\d+)\s*章"),
        re.compile(r"第\s*(\d+)\s*节"),
        re.compile(r"Chapter\s+(\d+)", re.IGNORECASE),
    ]

    positions = []
    for pattern in patterns:
        positions = [(int(m.group(1)), m.start()) for m in pattern.finditer(source_text)]
        if len(positions) >= 10:
            break

    if not positions:
        return [(1, source_text)], 1

    positions.sort(key=lambda x: x[1])

    # 去重（同一段可能被多个正则匹配）
    deduped = [positions[0]]
    for ch_num, ch_start in positions[1:]:
        if ch_start - deduped[-1][1] > 20:
            deduped.append((ch_num, ch_start))

    results = []
    for idx, (ch_num, ch_start) in enumerate(deduped):
        ch_end = deduped[idx + 1][1] if idx + 1 < len(deduped) else len(source_text)
        results.append((ch_num, source_text[ch_start:ch_end]))

    total_chapters = max(ch for ch, _ in results) if results else 0
    return results, total_chapters


def count_mentions_in_chapter(text: str, entity_name: str) -> int:
    """统计实体在章节文本中的出现次数（精确匹配，区分大小写）。"""
    if not entity_name or not text:
        return 0
    # 使用正则精确匹配完整词（中文不需要 word boundary）
    pattern = re.compile(re.escape(entity_name))
    return len(pattern.findall(text))


def extract_entities(material_id: str, output_path: Path | None = None) -> dict:
    """从原文提取所有实体的出场统计。"""
    base_dir = Path(f"data/novels/{material_id}")
    source_path = base_dir / "source.txt"
    characters_dir = base_dir / "characters"
    worldbuilding_dir = base_dir / "worldbuilding"

    if not source_path.exists():
        print(f"ERROR: source.txt 不存在: {source_path}", file=sys.stderr)
        sys.exit(1)

    with open(source_path, "r", encoding="utf-8") as f:
        source_text = f.read()

    # 加载实体名册
    char_names = load_character_names(characters_dir) if characters_dir.is_dir() else []
    wb_entities = load_worldbuilding_entities(worldbuilding_dir) if worldbuilding_dir.is_dir() else {
        "locations": [], "factions": [], "items": [], "terminology": []
    }

    # 章节切分
    chapter_segments, total_chapters = split_source_by_chapters(source_text, base_dir)

    print(f"原文长度: {len(source_text):,} 字符")
    print(f"章节数: {total_chapters}")
    print(f"角色名数: {len(char_names)}")
    print(f"地点数: {len(wb_entities['locations'])}")
    print(f"势力数: {len(wb_entities['factions'])}")
    print(f"物品数: {len(wb_entities['items'])}")
    print(f"术语数: {len(wb_entities['terminology'])}")

    # 提取统计
    def _scan_entity_list(entity_list: list[str]) -> dict:
        result = {}
        for name in entity_list:
            total_mentions = 0
            appearance_chapters = []
            for ch_num, ch_text in chapter_segments:
                count = count_mentions_in_chapter(ch_text, name)
                if count > 0:
                    total_mentions += count
                    appearance_chapters.append(ch_num)
            if total_mentions > 0:
                result[name] = {
                    "total_mentions": total_mentions,
                    "chapters": appearance_chapters,
                }
        return result

    char_stats = _scan_entity_list(char_names)
    location_stats = _scan_entity_list(wb_entities["locations"])
    faction_stats = _scan_entity_list(wb_entities["factions"])
    item_stats = _scan_entity_list(wb_entities["items"])
    terminology_stats = _scan_entity_list(wb_entities["terminology"])

    output = {
        "material_id": material_id,
        "total_chapters": total_chapters,
        "extracted_at": __import__("datetime").datetime.now().isoformat(),
        "characters": char_stats,
        "locations": location_stats,
        "factions": faction_stats,
        "items": item_stats,
        "terminology": terminology_stats,
        "summary": {
            "characters_found": len(char_stats),
            "locations_found": len(location_stats),
            "factions_found": len(faction_stats),
            "items_found": len(item_stats),
            "terminology_found": len(terminology_stats),
        },
    }

    # 输出
    if output_path is None:
        output_path = base_dir / "source_entities.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n📄 实体数据已写入: {output_path}")
    print(f"  角色: {len(char_stats)}")
    print(f"  地点: {len(location_stats)}")
    print(f"  势力: {len(faction_stats)}")
    print(f"  物品: {len(item_stats)}")
    print(f"  术语: {len(terminology_stats)}")

    return output


def main():
    parser = argparse.ArgumentParser(description="从原文提取客观实体清单")
    parser.add_argument("material_id", help="素材 ID")
    parser.add_argument("--output", help="自定义输出路径", default=None)

    args = parser.parse_args()
    output_path = Path(args.output) if args.output else None
    extract_entities(args.material_id, output_path)


if __name__ == "__main__":
    main()
