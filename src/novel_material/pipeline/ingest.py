"""小说入库：把原始小说文件导入到素材库。

流程：
1. 检测文件编码并转换为 UTF-8
2. 预处理：去广告、归一化空白、标准化章节标题
3. 检测章节标题，切分为独立章节
4. 写入 source.txt、chapter_index.yaml、meta.yaml
5. 更新全局索引
"""
import sys
import yaml
import re
from datetime import datetime
from pathlib import Path
from collections.abc import Callable

from novel_material.infra.config import NOVELS_DIR, INDEX_FILE
from novel_material.infra.common import generate_material_id
from novel_material.infra.progress import get_pipeline_logger
from .preprocess import preprocess

logger = get_pipeline_logger()


def _detect_chapter_type(title: str) -> str:
    """识别章节类型。

    返回：
        'normal' - 正文章节
        'afterword' - 后记/完本感言
        'extra' - 番外/外传
        'author_note' - 作者说/作者的话
    """
    # 后记模式（严格匹配，避免误判正文标题）
    afterword_patterns = [
        r"^后记$",           # 纯"后记"
        r"完本感言",         # 完本感言
        r"完本感想",         # 完本感想
        r"完结感言",         # 完结感言
        r"^完本$",           # 纯"完本"
        r"^完结$",           # 纯"完结"
        r"完本说",           # 完本说
    ]

    # 番外模式
    extra_patterns = [
        r"番外",
        r"外传",
        r"番外篇",
        r"番篇",
    ]

    # 作者说模式
    author_note_patterns = [
        r"^作者说",
        r"^作者的话",
        r"^PS[:：]",
        r"^ps[:：]",
    ]

    for pat in afterword_patterns:
        if re.search(pat, title, re.IGNORECASE):
            return "afterword"

    for pat in extra_patterns:
        if re.search(pat, title, re.IGNORECASE):
            return "extra"

    for pat in author_note_patterns:
        if re.search(pat, title):
            return "author_note"

    return "normal"


def detect_chapter_pattern(lines):
    """检测章节标题，返回章节所在行号列表。

    支持的章节标题格式：
    - 标准格式：第X章/节/回/篇/卷/部（含中文数字）
    - 特殊章节：楔子/引子/序章/终章/尾声
    - 数字格式：1、标题 / 1 标题（数字后跟标题）
    """
    # 主模式：标准章节标题（含卷、部）
    # 注意：排除 "第X节课" 这种课程表格式
    main_pattern = re.compile(
        r"^\s*(?:第\s*\d+\s*[章回篇卷部]|第\s*\d+\s*节(?![课])|楔子|引子|序章|终章|尾声)\s*"
    )

    # 备选模式：数字+分隔符+标题（如 "1、重生"，"1 重生"）
    # 限制：标题长度 2-50 字，避免误判数字串
    alt_pattern = re.compile(
        r"^\s*\d{1,4}[、\s]\s*[^\d\s].{1,50}$"
    )

    chapter_lines = []

    for i, line in enumerate(lines):
        # 主模式匹配
        if main_pattern.match(line):
            chapter_lines.append(i)
            continue

        # 备选模式匹配（更严格的条件）
        if alt_pattern.match(line):
            stripped = line.strip()
            # 排除纯数字行（如 "1、2、3"）
            if not re.match(r'^\d+[、\s]\s*\d', stripped):
                title_part = re.sub(r'^\d+[、\s]\s*', '', stripped)
                # 标题部分至少 2 字，且不以"第"开头（避免与主模式重复）
                if len(title_part) >= 2 and not title_part.startswith('第'):
                    chapter_lines.append(i)

    return chapter_lines


def split_chapters(lines, chapter_lines):
    """按检测到的章节行切分文本。

    word_count 统计规则：去除空白后的纯字符数（含标点）。
    type 字段：根据标题识别章节类型（normal/afterword/extra/author_note）。
    """
    chapters = []
    for idx, start_line in enumerate(chapter_lines):
        end_line = chapter_lines[idx + 1] if idx + 1 < len(chapter_lines) else len(lines)
        chapter_text = "\n".join(lines[start_line:end_line]).strip()
        title = lines[start_line].strip()

        # word_count：去除空白后的纯字符数（含标点，不含空格/换行）
        word_count = len(re.sub(r'\s', '', chapter_text))

        # 识别章节类型
        ch_type = _detect_chapter_type(title)

        chapters.append({
            "title": title,
            "type": ch_type,
            "start_line": start_line,
            "end_line": end_line - 1,
            "content": chapter_text,
            "word_count": word_count
        })
    return chapters


def ingest_file(file_path, progress_callback: Callable[[int, int, str], None] | None = None) -> str | None:
    """入库单本小说。

    流程：
    1. 检测文件存在性
    2. 生成唯一 material_id
    3. 预处理（编码转换、去广告、标准化）
    4. 检测章节并切分
    5. 写入 source.txt、chapter_index.yaml、meta.yaml
    6. 更新全局索引

    参数：
        file_path：小说文件路径
        progress_callback：可选进度回调 (done: int, total: int, desc: str) -> None

    返回：
        material_id 成功时返回，失败返回 None
    """
    file_path = Path(file_path).resolve()
    if not file_path.exists():
        logger.error(f"文件不存在: {file_path}")
        return None

    if progress_callback:
        progress_callback(0, 5, "生成素材 ID")
    else:
        logger.info(f"正在处理: {file_path.name}")

    material_id = generate_material_id(novels_dir=NOVELS_DIR)
    novel_dir = NOVELS_DIR / material_id
    novel_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"生成 material_id: {material_id}")

    # ── 步骤 1：读取并预处理 ──
    if progress_callback:
        progress_callback(1, 5, "读取并预处理文件")
    else:
        logger.info("读取文件...")

    try:
        with open(file_path, "rb") as f:
            raw_bytes = f.read()
        content = preprocess(raw_bytes)
    except Exception as e:
        logger.error(f"预处理失败: {e}")
        # 清理已创建的空目录
        novel_dir.rmdir() if novel_dir.exists() and not any(novel_dir.iterdir()) else None
        return None

    lines = content.split("\n")

    # ── 步骤 2：检测章节 ──
    if progress_callback:
        progress_callback(2, 5, "检测章节标题")
    else:
        logger.info("检测章节...")

    chapter_lines = detect_chapter_pattern(lines)
    if not chapter_lines:
        logger.error("未检测到章节标题，请检查文件格式")
        logger.error(f"文件前 5 行内容：\n" + "\n".join(lines[:5]))
        novel_dir.rmdir() if novel_dir.exists() and not any(novel_dir.iterdir()) else None
        return None

    # ── 步骤 3：切分章节 ──
    if progress_callback:
        progress_callback(3, 5, "切分章节")
    else:
        logger.info("切分章节...")

    chapters = split_chapters(lines, chapter_lines)
    logger.info(f"识别到 {len(chapters)} 个章节")

    # ── 步骤 4：构建并写入文件 ──
    if progress_callback:
        progress_callback(4, 5, "写入文件")
    else:
        logger.info("写入文件...")

    source_lines = []
    chapter_index = []
    current_line = 1

    for ch in chapters:
        chapter_lines_count = ch["content"].count("\n") + 1
        start_line = current_line
        end_line = current_line + chapter_lines_count - 1

        source_lines.append(ch["content"])

        chapter_index.append({
            "chapter": len(chapter_index) + 1,
            "title": ch["title"],
            "type": ch["type"],
            "start_line": start_line,
            "end_line": end_line,
            "word_count": ch["word_count"]
        })

        current_line = end_line + 1

    # 写入 chapter_index.yaml
    with open(novel_dir / "chapter_index.yaml", "w", encoding="utf-8") as f:
        yaml.dump(chapter_index, f, allow_unicode=True, default_flow_style=False)

    # 写入 source.txt（章节之间保留空行分隔）
    clean_content = "\n\n".join(source_lines)
    with open(novel_dir / "source.txt", "w", encoding="utf-8") as f:
        f.write(clean_content)

    # 计算总字数（不含空白）
    total_word_count = len(re.sub(r'\s', '', clean_content))

    # 写入 meta.yaml
    meta = {
        "material_id": material_id,
        "name": file_path.stem,
        "author": "TBD",
        "genre": [],
        "word_count": total_word_count,
        "chapter_count": len(chapters),
        "status": "clean",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    with open(novel_dir / "meta.yaml", "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True, default_flow_style=False)

    # ── 步骤 5：更新全局索引 ──
    if progress_callback:
        progress_callback(5, 5, "更新全局索引")
    else:
        logger.info("更新全局索引...")

    update_global_index(material_id, meta)

    logger.info(f"入库完成: {novel_dir}")
    return material_id


def update_global_index(material_id, meta):
    """更新全局索引文件。"""
    index_file = INDEX_FILE
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            index = yaml.safe_load(f) or {}
    else:
        index = {}

    index[material_id] = {
        "name": meta["name"],
        "status": meta["status"],
        "path": f"data/novels/{material_id}"
    }

    with open(index_file, "w", encoding="utf-8") as f:
        yaml.dump(index, f, allow_unicode=True, default_flow_style=False)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python ingest.py <小说文件路径>")
        sys.exit(1)

    ingest_file(sys.argv[1])