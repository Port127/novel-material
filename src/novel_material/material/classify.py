"""素材分类核心逻辑。

根据小说样本内容，使用 LLM 进行 genre 分类。
支持分布式采样（开头 + 中间 + 后期）。
"""
import json
import re
import logging
from pathlib import Path
from typing import Optional

from novel_material.infra.llm import call_llm, load_config
from novel_material.infra.llm_contracts import require_mapping, require_number
from novel_material.infra.yaml_io import load_yaml, save_yaml
from novel_material.infra.config import PROJECT_ROOT, DATA_DIR, get_settings
from novel_material.material.classify_prompt import (
    build_classify_prompt,
    USER_PROMPT_TEMPLATE,
)
from novel_material.tags.load import get_all_genres, infer_primary_from_secondary

logger = logging.getLogger(__name__)

# 加载配置
_settings = get_settings()

# 素材索引文件路径
CLASSIFY_INDEX_FILE = DATA_DIR / "material_index.yaml"
CLASSIFY_PROGRESS_FILE = DATA_DIR / "classify_progress.yaml"

# 原始素材索引文件路径（爬虫数据）- 支持配置
NOVEL_INDEX_FILE = PROJECT_ROOT / _settings.get(
    "MATERIAL_INDEX_JSON", "material/知轩藏书/novel_index.json"
)

# 素材文件目录 - 支持配置
MATERIAL_DIR = PROJECT_ROOT / _settings.get(
    "MATERIAL_SOURCE_DIR", "material/知轩藏书/仙草排行榜-前2000"
)


def extract_sample_chapters(
    file_path: Path,
    total_chapters: int = None,
    sample_ratio: float = 0.005,
    min_chapters: int = 3,
    max_chapters: int = 30,
    max_chars_per_chapter: int = 1500,
) -> str:
    """分布式采样章节内容。

    采样分布：
    - 开头：1 章（了解设定）
    - 中间：按比例分配
    - 后期：1 章（了解结局/转折）

    Args:
        file_path: 小说文件路径
        total_chapters: 总章数（可选，自动检测）
        sample_ratio: 采样比例（默认 0.5%）
        min_chapters: 最少采样章数
        max_chapters: 最多采样章数
        max_chars_per_chapter: 每章最多字符

    Returns:
        str: 采样内容（章节标题 + 内容）
    """
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 章节检测
    chapter_pattern = re.compile(
        r"(?:^|\n)(第[一二三四五六七八九十百千万零\d]+章|第\d+章)",
        re.MULTILINE
    )
    matches = list(chapter_pattern.finditer(content))

    if len(matches) < min_chapters:
        # 少于最少章数，取全文前 max_chars
        return content[:min_chapters * max_chars_per_chapter]

    # 计算采样数量
    n_chapters = len(matches)
    sample_count = max(
        min_chapters,
        min(max_chapters, int(n_chapters * sample_ratio))
    )

    # 分布采样位置
    positions = []

    # 开头：第 1 章
    positions.append(0)

    # 中间：均匀分布
    if sample_count > 2:
        mid_count = sample_count - 2  # 减去开头和结尾
        mid_positions = [
            int(n_chapters * (i + 1) / (mid_count + 1))
            for i in range(mid_count)
        ]
        positions.extend(mid_positions)

    # 结尾：最后一章
    if sample_count > 1:
        positions.append(n_chapters - 1)

    # 提取章节内容
    samples = []
    for pos in positions:
        if pos >= len(matches):
            continue

        start = matches[pos].start()
        if content[start] == '\n':
            start += 1

        # 结束位置：下一章开始或文件末尾
        end_pos = matches[pos + 1].start() if pos + 1 < len(matches) else len(content)

        chapter_content = content[start:end_pos]
        if len(chapter_content) > max_chars_per_chapter:
            chapter_content = chapter_content[:max_chars_per_chapter]

        samples.append(chapter_content)

    return "\n\n---\n\n".join(samples)


def load_genre_mapping() -> tuple[list[str], dict[str, str]]:
    """从数据库加载 genre 映射，返回一级和二级题材列表。

    Returns:
        tuple: (一级题材列表, 二级题材→一级题材映射)
    """
    primary_genres = get_all_genres()
    secondary_mapping = {}
    # 构建二级→一级映射（从 infer_primary_from_secondary 的逻辑）
    for secondary in [
        "东方玄幻", "异世大陆", "王朝争霸", "高武世界",
        "修真文明", "幻想修仙", "现代修真", "古典仙侠",
        "都市生活", "都市异能", "都市修仙", "都市神医",
        "星际文明", "时空穿梭", "末世危机", "进化变异", "超级科技",
        "悬疑侦探", "探险生存", "灵异神怪", "诡秘悬疑",
        "传统武侠", "武侠幻想", "国术无双",
        "架空历史", "历史穿越", "秦汉三国",
        "游戏异界", "电子竞技", "虚拟网游",
    ]:
        primary = infer_primary_from_secondary(secondary)
        if primary != secondary:  # 有映射
            secondary_mapping[secondary] = primary

    return primary_genres, secondary_mapping


def parse_classification_result(result: object, genre_mapping: tuple) -> dict:
    """解析并校验 LLM 分类结果（新格式）。

    Args:
        result: LLM 返回的 JSON 结果
        genre_mapping: (primary_genres, secondary_mapping)

    Returns:
        dict: 校验后的分类结果

    Raises:
        ValueError: 结果格式无效
    """
    result = require_mapping(result, "classification")

    primary_genres, secondary_mapping = genre_mapping

    # 解析 genre_primary
    genre_primary = result.get("genre_primary", "其他")
    if not isinstance(genre_primary, str):
        genre_primary = str(genre_primary)

    # 校验 genre_primary 是否在系统标签中
    valid_primary = None
    for g in primary_genres:
        if g == genre_primary:
            valid_primary = g
            break

    if not valid_primary:
        logger.warning(f"无效 genre_primary: {genre_primary}")
        valid_primary = "其他"

    # 解析 genre_secondary
    genre_secondary = result.get("genre_secondary", "")
    if genre_secondary:
        # 校验二级题材并归一化
        inferred = secondary_mapping.get(genre_secondary)
        if inferred and inferred != valid_primary:
            logger.warning(f"二级题材 {genre_secondary} 映射到 {inferred}，与 {valid_primary} 不同")

    # 解析 elements（批次3扩展）
    elements = result.get("elements", [])
    if not isinstance(elements, list):
        elements = []

    # 解析 style（批次3扩展）
    style = result.get("style", {})

    # 解析 quality（批次3扩展）
    quality = require_mapping(result.get("quality", {}), "classification.quality")
    writing = require_number(quality.get("writing", 3), "classification.quality.writing")
    plot = require_number(quality.get("plot", 3), "classification.quality.plot")
    character = require_number(quality.get("character", 3), "classification.quality.character")
    quality_score = round((writing + plot + character) / 3, 1)

    genre_description = result.get("genre_description", "")
    if not genre_description:
        genre_description = "分类描述未生成"

    confidence = result.get("confidence", 0.5)
    if not isinstance(confidence, (int, float)):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    return {
        "genre_primary": valid_primary,
        "genre_secondary": genre_secondary,
        "genre_description": genre_description,
        "elements": elements,
        "elements_description": result.get("elements_description", ""),
        "style": style,
        "quality": {
            "writing": writing,
            "plot": plot,
            "character": character,
            "score": quality_score,
        },
        "confidence": confidence,
    }


def classify_book(
    file_path: Path,
    title: str,
    author: str,
    config: Optional[dict] = None,
) -> dict:
    """对单本书进行分类。

    Args:
        file_path: 小说 txt 文件路径
        title: 小说标题
        author: 作者
        config: LLM 配置（可选，默认使用默认配置）

    Returns:
        dict: 分类结果，包含 genre_primary、genre_secondary、confidence、status

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: LLM 结果无效
    """
    if config is None:
        config = load_config()

    # 加载动态 genre 映射
    genre_mapping = load_genre_mapping()
    primary_genres, secondary_mapping = genre_mapping

    # 动态构建系统提示词
    system_prompt = build_classify_prompt(primary_genres)

    # 提取样本章节内容（分布式采样）
    content = extract_sample_chapters(file_path)

    # 构建用户提示词
    user_prompt = USER_PROMPT_TEMPLATE.format(
        title=title,
        author=author,
        content=content,
    )

    # 调用 LLM
    context = f"[classify] {title}"
    try:
        result = call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            config=config,
            context=context,
        )
    except json.JSONDecodeError as e:
        logger.error(f"{context} JSON 解析失败: {e}")
        return {
            "genre_primary": "其他",
            "genre_secondary": "",
            "genre_description": "LLM 返回格式错误",
            "confidence": 0.0,
            "status": "failed",
            "error": str(e),
        }
    except Exception as e:
        logger.error(f"{context} LLM 调用失败: {e}")
        return {
            "genre_primary": "其他",
            "genre_secondary": "",
            "genre_description": f"LLM 调用失败: {type(e).__name__}",
            "confidence": 0.0,
            "status": "failed",
            "error": str(e),
        }

    # 解析结果
    try:
        parsed = parse_classification_result(result, genre_mapping)
    except ValueError as e:
        logger.error(f"{context} 结果校验失败: {e}")
        return {
            "genre_primary": "其他",
            "genre_secondary": "",
            "genre_description": "结果校验失败",
            "confidence": 0.0,
            "status": "failed",
            "error": str(e),
        }

    # 置信度低于 0.6 时标记
    status = "done"
    if parsed["confidence"] < 0.6:
        status = "low_confidence"
        logger.warning(f"{context} 置信度低: {parsed['confidence']}")

    return {
        "genre_primary": parsed["genre_primary"],
        "genre_secondary": parsed["genre_secondary"],
        "genre_description": parsed["genre_description"],
        "elements": parsed["elements"],
        "elements_description": parsed["elements_description"],
        "style": parsed["style"],
        "quality": parsed["quality"],
        "confidence": parsed["confidence"],
        "status": status,
    }


def load_novel_index() -> list[dict]:
    """加载原始素材索引（novel_index.json）。

    Returns:
        list: 素材列表
    """
    import json

    if not NOVEL_INDEX_FILE.exists():
        raise FileNotFoundError(f"素材索引不存在: {NOVEL_INDEX_FILE}")

    with open(NOVEL_INDEX_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_material_index() -> dict:
    """加载分类结果索引（material_index.yaml）。

    Returns:
        dict: 分类结果索引
    """
    return load_yaml(CLASSIFY_INDEX_FILE)


def save_material_index(index: dict) -> None:
    """保存分类结果索引。

    Args:
        index: 分类结果索引
    """
    # 确保顶层有 materials 键
    if "materials" not in index:
        index = {"materials": index}
    save_yaml(CLASSIFY_INDEX_FILE, index)


def load_progress() -> dict:
    """加载分类进度。

    Returns:
        dict: 进度信息
    """
    progress = load_yaml(CLASSIFY_PROGRESS_FILE)
    if not progress:
        progress = {
            "last_processed_sequence": 0,
            "last_processed_file": "",
            "last_processed_time": "",
            "total": 0,
            "processed": 0,
            "remaining": 0,
            "failed": [],
        }
    return progress


def save_progress(progress: dict) -> None:
    """保存分类进度。

    Args:
        progress: 进度信息
    """
    save_yaml(CLASSIFY_PROGRESS_FILE, progress)


def get_status() -> dict:
    """获取分类进度统计。

    Returns:
        dict: 进度统计
    """
    progress = load_progress()
    index = load_novel_index()

    total = len(index)
    processed = progress.get("processed", 0)
    remaining = total - processed
    failed = len(progress.get("failed", []))

    return {
        "total": total,
        "processed": processed,
        "remaining": remaining,
        "failed": failed,
        "progress_percent": round(processed / total * 100, 1) if total > 0 else 0,
        "last_processed_file": progress.get("last_processed_file", ""),
        "last_processed_time": progress.get("last_processed_time", ""),
    }


__all__ = [
    "extract_sample_chapters",
    "classify_book",
    "parse_classification_result",
    "load_genre_mapping",
    "load_novel_index",
    "load_material_index",
    "save_material_index",
    "load_progress",
    "save_progress",
    "get_status",
    "CLASSIFY_INDEX_FILE",
    "CLASSIFY_PROGRESS_FILE",
    "NOVEL_INDEX_FILE",
    "MATERIAL_DIR",
]
