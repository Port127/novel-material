"""精调工具：基于章级分析数据调整 outline/characters/tags。"""
import sys
import yaml
import time

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.llm import load_config, call_llm
from novel_material.infra.progress import get_pipeline_logger

logger = get_pipeline_logger()


def refine_outline(material_id, chapters_data):
    """基于章级数据精调大纲。"""
    novel_dir = NOVELS_DIR / material_id
    outline_dir = novel_dir / "outline"
    outline_index_file = outline_dir / "_index.yaml"

    if not outline_index_file.exists():
        logger.info("跳过大纲精调：outline/_index.yaml 不存在")
        return False

    with open(outline_index_file, "r", encoding="utf-8") as f:
        outline_index = yaml.safe_load(f) or {}

    with open(outline_dir / "structure.yaml", "r", encoding="utf-8") as f:
        structure = yaml.safe_load(f) or {}

    function_counts = {}
    tension_avg = 0
    for ch in chapters_data:
        funcs = ch.get("chapter_functions", [])
        for f in funcs:
            function_counts[f] = function_counts.get(f, 0) + 1
        tension_avg += ch.get("tension_level", 0)

    tension_avg = tension_avg / max(len(chapters_data), 1)

    hooks_count = sum(1 for ch in chapters_data if "章末悬念" in ch.get("chapter_functions", []))

    outline_index["hook_count"] = hooks_count
    outline_index["avg_tension"] = round(tension_avg, 2)
    outline_index["refined_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    with open(outline_index_file, "w", encoding="utf-8") as f:
        yaml.dump(outline_index, f, allow_unicode=True, default_flow_style=False)

    logger.info(f"大纲精调完成: {hooks_count} 个钩子, 平均张力 {tension_avg:.2f}")
    return True


def refine_characters(material_id, chapters_data):
    """基于章级数据精调人物。"""
    novel_dir = NOVELS_DIR / material_id
    char_dir = novel_dir / "characters"
    profiles_dir = char_dir / "profiles"
    char_index_file = char_dir / "_index.yaml"

    if not char_index_file.exists():
        logger.info("跳过人物精调：characters/_index.yaml 不存在")
        return False

    with open(char_index_file, "r", encoding="utf-8") as f:
        char_index = yaml.safe_load(f) or {}

    appearance_counts = {}
    chapter_appearances = {}

    for ch in chapters_data:
        ch_num = ch.get("chapter", 0)
        chars = ch.get("characters_appear", [])
        for c in chars:
            appearance_counts[c] = appearance_counts.get(c, 0) + 1
            if c not in chapter_appearances:
                chapter_appearances[c] = []
            chapter_appearances[c].append(ch_num)

    for profile_file in profiles_dir.glob("*.yaml"):
        with open(profile_file, "r", encoding="utf-8") as f:
            profile = yaml.safe_load(f) or {}

        name = profile.get("name", "")
        if name in appearance_counts:
            profile["appearance_count"] = appearance_counts[name]
            profile["first_appearance_chapter"] = min(chapter_appearances[name])
            profile["last_appearance_chapter"] = max(chapter_appearances[name])

        with open(profile_file, "w", encoding="utf-8") as f:
            yaml.dump(profile, f, allow_unicode=True, default_flow_style=False)

    char_index["refined_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    with open(char_index_file, "w", encoding="utf-8") as f:
        yaml.dump(char_index, f, allow_unicode=True, default_flow_style=False)

    logger.info(f"人物精调完成: 更新了 {len(appearance_counts)} 个人物的出场统计")
    return True


def refine_tags(material_id, chapters_data):
    """基于章级数据精调标签。"""
    novel_dir = NOVELS_DIR / material_id
    tags_file = novel_dir / "tags.yaml"

    if not tags_file.exists():
        logger.info("跳过标签精调：tags.yaml 不存在")
        return False

    with open(tags_file, "r", encoding="utf-8") as f:
        tags = yaml.safe_load(f) or {}

    function_counts = {}
    for ch in chapters_data:
        for f in ch.get("chapter_functions", []):
            function_counts[f] = function_counts.get(f, 0) + 1

    top_functions = sorted(function_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    tags["top_chapter_functions"] = [{"function": f, "count": c} for f, c in top_functions]
    tags["refined_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    with open(tags_file, "w", encoding="utf-8") as f:
        yaml.dump(tags, f, allow_unicode=True, default_flow_style=False)

    logger.info(f"标签精调完成: 更新了章节功能分布")
    return True


def refine(material_id):
    """主精调函数：调整 outline/characters/tags。"""
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"小说目录不存在: {novel_dir}")
        return

    chapters_file = novel_dir / "chapters.yaml"
    if not chapters_file.exists():
        logger.error("错误: chapters.yaml 不存在，无法精调")
        return

    with open(chapters_file, "r", encoding="utf-8") as f:
        chapters_data = yaml.safe_load(f) or []

    logger.info(f"开始精调: {material_id} ({len(chapters_data)} 章)")
    logger.info("=" * 60)

    refined = {
        "outline": refine_outline(material_id, chapters_data),
        "characters": refine_characters(material_id, chapters_data),
        "tags": refine_tags(material_id, chapters_data)
    }

    meta_file = novel_dir / "meta.yaml"
    with open(meta_file, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f)

    meta["refined_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    with open(meta_file, "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True, default_flow_style=False)

    logger.info("=" * 60)
    logger.info("精调完成")
    for module, success in refined.items():
        status = "已精调" if success else "跳过"
        logger.info(f"  {module}: {status}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python refine.py <material_id>")
        sys.exit(1)

    refine(sys.argv[1])