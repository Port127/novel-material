"""精调工具：基于章级分析数据调整 outline/characters/tags，并推断结构角色。

注意：精调阶段不调用 LLM，仅基于章级分析数据进行统计聚合和推断。
向量化已移至 embed_all.py 统一处理。
"""
import sys
import time

from novel_material.infra.config import NOVELS_DIR, update_meta_status
from novel_material.infra.yaml_io import load_yaml, save_yaml, load_yaml_list
from novel_material.infra.progress import get_pipeline_logger
from novel_material.pipeline.infer import infer_key_plot_points
from novel_material.pipeline.embed_all import embed_all

logger = get_pipeline_logger()


def refine_outline(material_id, chapters_data):
    """基于章级数据精调大纲。"""
    novel_dir = NOVELS_DIR / material_id
    outline_dir = novel_dir / "outline"
    outline_index_file = outline_dir / "_index.yaml"

    if not outline_index_file.exists():
        logger.info(f"[{material_id}] 跳过大纲精调：outline/_index.yaml 不存在")
        return False

    outline_index = load_yaml(outline_index_file)
    structure = load_yaml(outline_dir / "structure.yaml")

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

    save_yaml(outline_index_file, outline_index)

    logger.info(f"[{material_id}] 大纲精调完成: {hooks_count} 个钩子, 平均张力 {tension_avg:.2f}")
    return True


def refine_characters(material_id, chapters_data):
    """基于章级数据精调人物。"""
    novel_dir = NOVELS_DIR / material_id
    char_dir = novel_dir / "characters"
    profiles_dir = char_dir / "profiles"
    char_index_file = char_dir / "_index.yaml"

    if not char_index_file.exists():
        logger.info(f"[{material_id}] 跳过人物精调：characters/_index.yaml 不存在")
        return False

    char_index = load_yaml(char_index_file)

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
        profile = load_yaml(profile_file)

        name = profile.get("name", "")
        if name in appearance_counts:
            profile["appearance_count"] = appearance_counts[name]
            profile["first_appearance_chapter"] = min(chapter_appearances[name])
            profile["last_appearance_chapter"] = max(chapter_appearances[name])

        save_yaml(profile_file, profile)

    char_index["refined_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    save_yaml(char_index_file, char_index)

    logger.info(f"[{material_id}] 人物精调完成: 更新了 {len(appearance_counts)} 个人物的出场统计")
    return True


def refine_tags(material_id, chapters_data):
    """基于章级数据精调标签。"""
    novel_dir = NOVELS_DIR / material_id
    tags_file = novel_dir / "tags.yaml"

    if not tags_file.exists():
        logger.info(f"[{material_id}] 跳过标签精调：tags.yaml 不存在")
        return False

    tags = load_yaml(tags_file)

    function_counts = {}
    for ch in chapters_data:
        for f in ch.get("chapter_functions", []):
            function_counts[f] = function_counts.get(f, 0) + 1

    top_functions = sorted(function_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    tags["top_chapter_functions"] = [{"function": f, "count": c} for f, c in top_functions]
    tags["refined_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")

    save_yaml(tags_file, tags)

    logger.info(f"[{material_id}] 标签精调完成: 更新了章节功能分布")
    return True


def refine(material_id) -> bool:
    """主精调函数：推断结构角色 + 调整 outline/characters/tags。

    注意：精调阶段不调用 LLM，仅基于章级分析数据进行统计聚合和推断。
    特殊类型章节（afterword/author_note）不参与统计。

    参数：
        material_id: 素材 ID

    返回 True 表示成功。
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"[{material_id}] 小说目录不存在: {novel_dir}")
        return False

    # 新增：先推断结构角色 key_plot_point
    logger.info(f"[{material_id}] 开始推断结构角色...")
    if not infer_key_plot_points(material_id):
        logger.error(f"[{material_id}] 结构角色推断失败，中止精调")
        return False

    chapters_file = novel_dir / "chapters.yaml"
    if not chapters_file.exists():
        logger.error(f"[{material_id}] 错误: chapters.yaml 不存在，无法精调")
        return False

    # 加载小说基本信息
    meta = load_yaml(novel_dir / "meta.yaml")

    title = meta.get("name", material_id)
    word_count = meta.get("word_count", "?")
    status = meta.get("status", "raw")

    # 读取章节索引获取章数和类型映射
    chapter_index_file = novel_dir / "chapter_index.yaml"
    chapter_count = 0
    chapter_types = {}  # {章节号: 类型}
    if chapter_index_file.exists():
        chapter_index = load_yaml_list(chapter_index_file)
        chapter_count = len(chapter_index)
        for ch in chapter_index:
            ch_num = ch.get("chapter")
            ch_type = ch.get("type", "normal")
            if ch_num is not None:
                chapter_types[ch_num] = ch_type

    chapters_data = load_yaml_list(chapters_file)

    # 过滤特殊类型章节（不参与统计）
    filtered_chapters = [
        ch for ch in chapters_data
        if chapter_types.get(ch.get("chapter"), "normal") in ("normal", "extra")
    ]
    skipped_count = len(chapters_data) - len(filtered_chapters)

    # 输出小说基本信息
    logger.info(f"[{material_id}] 小说: {title} | {chapter_count} 章 | {word_count} 字 | 状态: {status}")
    logger.info(f"[{material_id}] 输入: {len(chapters_data)} 章章级分析数据（跳过 {skipped_count} 章特殊类型）")

    refined = {
        "outline": refine_outline(material_id, filtered_chapters),
        "characters": refine_characters(material_id, filtered_chapters),
        "tags": refine_tags(material_id, filtered_chapters)
    }

    # 一次性更新状态和 refined_at（避免重复 IO）
    update_meta_status(material_id, "finalized", {"refined_at": time.strftime("%Y-%m-%dT%H:%M:%S")})

    logger.info(f"[{material_id}] 精调完成")
    for module, success in refined.items():
        status = "已精调" if success else "跳过"
        logger.info(f"  {module}: {status}")

    # 统一向量化入口（章节/人物/世界观/大纲）
    logger.info(f"[{material_id}] 执行统一向量化...")
    embed_all(material_id)

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python refine.py <material_id>")
        sys.exit(1)

    refine(sys.argv[1])