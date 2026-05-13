"""结构角色推断：基于章级统计数据推断 key_plot_point。

职责：
- 读取 chapters.yaml 获取全书视角
- 根据位置、张力、功能标签推断结构角色
- 更新 chapters/*.yaml 文件

调用时机：refine 阶段调用，或在 analyze 后手动调用。

推断规则：
- inciting_incident: 前 10% 章节，张力 ≥ 3
- first_turning_point: 前 25% 章节，张力 ≥ 4，含"转折"相关功能标签
- midpoint: 40-60% 章节，张力 ≥ 4
- second_turning_point: 60-80% 章节，张力 ≥ 4，含"转折"相关功能标签
- climax: 后 20% 章节，张力 = 5 或含"高潮战斗"功能标签
- resolution: 最后 10% 章节，张力 ≤ 2
"""
import sys
from pathlib import Path

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.yaml_io import load_yaml, save_yaml, load_yaml_list
from novel_material.infra.progress import get_pipeline_logger
from novel_material.infra.common import KEY_PLOT_POINT_VALUES

logger = get_pipeline_logger()

# 功能标签关键词匹配
TURNING_POINT_FUNCTIONS = ["转折", "冲突爆发", "反转", "转折点"]
CLIMAX_FUNCTIONS = ["高潮战斗", "高潮", "决战", "最终对决"]


def _infer_single(
    chapter_num: int,
    total_chapters: int,
    tension_level: int,
    chapter_functions: list[str],
) -> str | None:
    """推断单章的结构角色标记。

    参数：
        chapter_num: 章节号（1-based）
        total_chapters: 总章数
        tension_level: 张力等级（1-5）
        chapter_functions: 章节功能标签列表

    返回：
        结构角色标记字符串，或 None（普通章节）

    推断规则（按优先级从高到低判断，互斥）：
    1. inciting_incident: 前 10% 章节，张力 ≥ 3
    2. first_turning_point: 前 25% 章节，张力 ≥ 4，含"转折"相关功能标签
    3. midpoint: 40-60% 章节，张力 ≥ 4
    4. second_turning_point: 60-80% 章节，张力 ≥ 4，含"转折"相关功能标签
    5. climax: 后 20% 章节，张力 = 5 或含"高潮战斗"功能标签
    6. resolution: 最后 10% 章节，张力 ≤ 2
    """
    if total_chapters <= 0:
        return None

    # 计算位置比例
    position_ratio = chapter_num / total_chapters

    # 跳过特殊类型章节（由 caller 过滤）

    # 检查功能标签匹配
    has_turning_function = any(
        any(kw in f for kw in TURNING_POINT_FUNCTIONS)
        for f in chapter_functions
    )
    has_climax_function = any(
        any(kw in f for kw in CLIMAX_FUNCTIONS)
        for f in chapter_functions
    )

    # 按优先级判断（从高到低）
    # 1. inciting_incident: 前 10% 章节，张力 ≥ 3
    if position_ratio <= 0.10 and tension_level >= 3:
        return "inciting_incident"

    # 2. first_turning_point: 前 25% 章节，张力 ≥ 4，含转折功能
    if position_ratio <= 0.25 and tension_level >= 4 and has_turning_function:
        return "first_turning_point"

    # 3. midpoint: 40-60% 章节，张力 ≥ 4
    if 0.40 <= position_ratio <= 0.60 and tension_level >= 4:
        return "midpoint"

    # 4. second_turning_point: 60-80% 章节，张力 ≥ 4，含转折功能
    if 0.60 <= position_ratio <= 0.80 and tension_level >= 4 and has_turning_function:
        return "second_turning_point"

    # 5. climax: 后 20% 章节，张力 = 5 或含高潮功能
    if position_ratio >= 0.80:
        if tension_level == 5 or has_climax_function:
            return "climax"

    # 6. resolution: 最后 10% 章节，张力 ≤ 2
    if position_ratio >= 0.90 and tension_level <= 2:
        return "resolution"

    # 普通章节：不满足任何条件
    return None


def infer_key_plot_points(material_id: str) -> bool:
    """批量推断所有章节的 key_plot_point。

    流程：
    1. 加载章节数据（从 chapters/ 目录或 chapters.yaml）
    2. 加载章节索引获取 type 信息，过滤特殊类型
    3. 遍历每章推断 key_plot_point
    4. 更新 chapters/*.yaml 文件
    5. 重写 chapters.yaml 合并文件

    参数：
        material_id: 素材 ID

    返回：
        True 表示成功，False 表示失败
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.error(f"[{material_id}] 小说目录不存在: {novel_dir}")
        return False

    # 加载章节索引获取 type 信息
    chapter_index_file = novel_dir / "chapter_index.yaml"
    chapter_types: dict[int, str] = {}
    total_chapters = 0
    if chapter_index_file.exists():
        chapter_index = load_yaml_list(chapter_index_file)
        total_chapters = len(chapter_index)
        for ch in chapter_index:
            ch_num = ch.get("chapter")
            ch_type = ch.get("type", "normal")
            if ch_num is not None:
                chapter_types[ch_num] = ch_type

    if total_chapters == 0:
        logger.error(f"[{material_id}] 章节索引为空或不存在")
        return False

    # 加载章节数据
    chapters_dir = novel_dir / "chapters"
    chapters_file = novel_dir / "chapters.yaml"

    all_chapters: list[dict] = []
    if chapters_dir.exists():
        for f in sorted(chapters_dir.glob("*.yaml")):
            try:
                data = load_yaml(f)
                if isinstance(data, dict) and "chapter" in data:
                    all_chapters.append(data)
            except Exception:
                logger.warning(f"[{material_id}] 跳过异常文件: {f.name}")

    if not all_chapters and chapters_file.exists():
        all_chapters = load_yaml_list(chapters_file)

    if not all_chapters:
        logger.error(f"[{material_id}] 无章节数据")
        return False

    # 推断并更新
    inferred_count = 0
    skipped_special = 0

    for ch_data in all_chapters:
        ch_num = ch_data.get("chapter")
        if ch_num is None:
            continue

        # 跳过特殊类型章节
        ch_type = chapter_types.get(ch_num, "normal")
        if ch_type in ("afterword", "author_note"):
            ch_data["key_plot_point"] = None  # 清空
            skipped_special += 1
            continue

        # 推断
        tension = ch_data.get("tension_level", 0)
        functions = ch_data.get("chapter_functions", ch_data.get("chapter_function", []))
        if isinstance(functions, str):
            functions = [functions]

        inferred = _infer_single(ch_num, total_chapters, tension, functions)
        ch_data["key_plot_point"] = inferred

        if inferred:
            inferred_count += 1

    # 更新分散文件
    if chapters_dir.exists():
        for ch_data in all_chapters:
            ch_num = ch_data.get("chapter")
            if ch_num is None:
                continue
            chapter_file = chapters_dir / f"{ch_num:04d}.yaml"
            save_yaml(chapter_file, ch_data)

    # 重写合并文件
    all_chapters.sort(key=lambda x: x.get("chapter", 0))
    save_yaml(chapters_file, all_chapters)

    logger.info(
        f"[{material_id}] 结构角色推断完成: {inferred_count} 章标记 | "
        f"{len(all_chapters) - inferred_count - skipped_special} 章普通 | "
        f"{skipped_special} 章特殊类型跳过"
    )

    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python infer.py <material_id>")
        sys.exit(1)

    if not infer_key_plot_points(sys.argv[1]):
        sys.exit(1)