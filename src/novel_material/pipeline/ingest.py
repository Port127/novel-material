"""小说入库：把原始小说文件导入到素材库。"""
import sys
import yaml
import re
import random
import string
from datetime import datetime
from pathlib import Path

from novel_material.infra.config import NOVELS_DIR, INDEX_FILE
from novel_material.infra.progress import get_pipeline_logger
from .preprocess import preprocess

logger = get_pipeline_logger()


def generate_material_id():
    """生成唯一的素材 ID。"""
    date_str = datetime.now().strftime("%Y%m%d")
    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"nm_novel_{date_str}_{random_str}"


def detect_chapter_pattern(lines):
    """检测章节标题，返回章节所在行号列表。"""
    main_pattern = re.compile(
        r"^\s*(?:第\s*\d+\s*[章节回篇]|楔子|引子|序章|终章|尾声)\s*"
    )
    alt_pattern = re.compile(
        r"^\s*\d{1,4}[、\s]\s*[^\d\s].{0,30}$"
    )

    chapter_lines = []

    for i, line in enumerate(lines):
        if main_pattern.match(line):
            chapter_lines.append(i)
            continue

        if alt_pattern.match(line) and len(line.strip()) < 40:
            stripped = line.strip()
            if not re.match(r'^\d+[、\s]\s*\d', stripped):
                title_part = re.sub(r'^\d+[、\s]\s*', '', stripped)
                if len(title_part) >= 2 and not title_part.startswith('第'):
                    chapter_lines.append(i)

    return chapter_lines


def split_chapters(lines, chapter_lines):
    """按检测到的章节行切分文本。"""
    chapters = []
    for idx, start_line in enumerate(chapter_lines):
        end_line = chapter_lines[idx + 1] if idx + 1 < len(chapter_lines) else len(lines)
        chapter_text = "\n".join(lines[start_line:end_line]).strip()
        title = lines[start_line].strip()
        chapters.append({
            "title": title,
            "start_line": start_line,
            "end_line": end_line - 1,
            "content": chapter_text,
            "word_count": len(chapter_text.replace("\n", ""))
        })
    return chapters


def ingest_file(file_path):
    """入库单本小说。"""
    file_path = Path(file_path).resolve()
    if not file_path.exists():
        logger.error(f"文件不存在: {file_path}")
        return None

    material_id = generate_material_id()
    novel_dir = NOVELS_DIR / material_id
    novel_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"正在处理: {file_path.name}")
    logger.info(f"生成 material_id: {material_id}")

    with open(file_path, "rb") as f:
        raw_bytes = f.read()

    content = preprocess(raw_bytes)
    lines = content.split("\n")

    chapter_lines = detect_chapter_pattern(lines)
    if not chapter_lines:
        logger.warning("未检测到章节名，请检查文件格式")
        return None

    chapters = split_chapters(lines, chapter_lines)
    logger.info(f"识别到 {len(chapters)} 个章节")

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
            "start_line": start_line,
            "end_line": end_line,
            "word_count": ch["word_count"]
        })

        current_line = end_line + 1

    with open(novel_dir / "chapter_index.yaml", "w", encoding="utf-8") as f:
        yaml.dump(chapter_index, f, allow_unicode=True, default_flow_style=False)

    clean_content = "\n".join(source_lines)
    with open(novel_dir / "source.txt", "w", encoding="utf-8") as f:
        f.write(clean_content)

    meta = {
        "material_id": material_id,
        "name": file_path.stem,
        "author": "TBD",
        "genre": [],
        "word_count": len(clean_content.replace("\n", "")),
        "chapter_count": len(chapters),
        "status": "clean",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    with open(novel_dir / "meta.yaml", "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True, default_flow_style=False)

    (novel_dir / "outline").mkdir(exist_ok=True)
    (novel_dir / "characters").mkdir(exist_ok=True)
    (novel_dir / "characters" / "profiles").mkdir(exist_ok=True)
    (novel_dir / "worldbuilding").mkdir(exist_ok=True)
    (novel_dir / "chapters").mkdir(exist_ok=True)

    with open(novel_dir / "chapters.yaml", "w", encoding="utf-8") as f:
        yaml.dump([], f, allow_unicode=True, default_flow_style=False)

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