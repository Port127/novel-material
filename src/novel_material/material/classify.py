"""素材分类核心逻辑。

根据小说前三章内容，使用 LLM 进行 genre 分类。
"""
import json
import re
import logging
from pathlib import Path
from typing import Optional

from novel_material.infra.llm import call_llm, load_config
from novel_material.infra.yaml_io import load_yaml, save_yaml
from novel_material.infra.config import PROJECT_ROOT, DATA_DIR, get_settings
from novel_material.material.classify_prompt import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    VALID_GENRES,
)

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


def extract_first_three_chapters(file_path: Path, max_chars: int = 8000) -> str:
    """从小说文件提取前三章内容。

    Args:
        file_path: 小说 txt 文件路径
        max_chars: 最大字符数（约 5000-8000 字）

    Returns:
        str: 前三章内容文本
    """
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # 章节标题匹配模式（支持多种格式）
    # 格式1: 第一章 xxx（行首）
    # 格式2: 第1章 xxx（行首）
    # 格式3: 一、xxx（部分小说用数字章节）
    # 要求章节标题必须在行首（前面是换行符或文件开头）
    chapter_pattern = re.compile(
        r"(?:^|\n)(第[一二三四五六七八九十百千万零\d]+章|第\d+章|[一二三四五六七八九十]+、)",
        re.MULTILINE
    )

    # 找到所有章节标题的位置
    matches = list(chapter_pattern.finditer(content))

    if len(matches) < 3:
        # 章节少于3章，取全文前 max_chars
        logger.warning(f"章节少于3章: {file_path.name}")
        return content[:max_chars]

    # 提取前三章内容
    # matches[0] 是第一章开始，matches[1] 是第二章，matches[2] 是第三章
    # matches[3] 是第四章开始（作为第三章结束位置）
    start_pos = matches[0].start()
    # 如果匹配到的换行符位置是标题开始的前一个字符，需要调整
    if content[start_pos] == '\n':
        start_pos += 1

    # 第四章开始位置作为结束（如果没有第四章，取到文件末尾）
    end_match = matches[3] if len(matches) >= 4 else None
    if end_match:
        end_pos = end_match.start()
        # 如果是换行符，保持换行符（作为章节分隔）
        if content[end_pos] == '\n':
            end_pos += 1
    else:
        end_pos = len(content)

    chapter_content = content[start_pos:end_pos]

    # 截断到最大字符数
    if len(chapter_content) > max_chars:
        chapter_content = chapter_content[:max_chars]

    return chapter_content


def parse_classification_result(result: dict) -> dict:
    """解析并校验 LLM 分类结果。

    Args:
        result: LLM 返回的 JSON 结果

    Returns:
        dict: 校验后的分类结果

    Raises:
        ValueError: 结果格式无效
    """
    if not isinstance(result, dict):
        raise ValueError("LLM 返回结果不是字典")

    genre = result.get("genre")
    if not genre:
        raise ValueError("缺少 genre 字段")

    if isinstance(genre, str):
        genre = [genre]
    elif not isinstance(genre, list):
        raise ValueError("genre 必须是字符串或列表")

    # 校验 genre 取值
    valid_genre = []
    for g in genre:
        if g in VALID_GENRES:
            valid_genre.append(g)
        else:
            logger.warning(f"无效 genre: {g}")

    if not valid_genre:
        valid_genre = ["其他"]

    genre_description = result.get("genre_description", "")
    if not genre_description:
        genre_description = "分类描述未生成"

    confidence = result.get("confidence", 0.5)
    if not isinstance(confidence, (int, float)):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    return {
        "genre": valid_genre,
        "genre_description": genre_description,
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
        dict: 分类结果，包含 genre、genre_description、confidence、status

    Raises:
        FileNotFoundError: 文件不存在
        ValueError: LLM 结果无效
    """
    if config is None:
        config = load_config()

    # 提取前三章内容
    content = extract_first_three_chapters(file_path)

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
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            config=config,
            context=context,
        )
    except json.JSONDecodeError as e:
        logger.error(f"{context} JSON 解析失败: {e}")
        return {
            "genre": ["其他"],
            "genre_description": "LLM 返回格式错误",
            "confidence": 0.0,
            "status": "failed",
            "error": str(e),
        }
    except Exception as e:
        logger.error(f"{context} LLM 调用失败: {e}")
        return {
            "genre": ["其他"],
            "genre_description": f"LLM 调用失败: {type(e).__name__}",
            "confidence": 0.0,
            "status": "failed",
            "error": str(e),
        }

    # 解析结果
    try:
        parsed = parse_classification_result(result)
    except ValueError as e:
        logger.error(f"{context} 结果校验失败: {e}")
        return {
            "genre": ["其他"],
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
        "genre": parsed["genre"],
        "genre_description": parsed["genre_description"],
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
    "extract_first_three_chapters",
    "classify_book",
    "parse_classification_result",
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