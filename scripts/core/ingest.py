#!/usr/bin/env python
"""小说入库：把原始小说文件导入到素材库。

入库做什么？
1. 读取原始 .txt 文件
2. 检测和清洗文本（去广告、统一编码、转换中文数字）
3. 切分章节（识别章节标题）
4. 生成章节索引（记录每章的起止行号）
5. 创建素材目录结构

入库后生成的文件：
- source.txt：清洗后的原文
- chapter_index.yaml：章节索引（章节号、标题、起止行号）
- meta.yaml：元信息（素材 ID、书名、章数、字数、状态）
"""
import sys
import yaml
import re
from datetime import datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.core.paths import NOVELS_DIR, INDEX_FILE
from scripts.core.preprocess import preprocess


def generate_material_id():
    """生成唯一的素材 ID。

    格式：nm_novel_日期_随机码
    例：nm_novel_20240101_abc1
    """
    import random
    import string
    date_str = datetime.now().strftime("%Y%m%d")
    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"nm_novel_{date_str}_{random_str}"


def detect_chapter_pattern(lines):
    """检测章节标题，返回章节所在行号列表。

    支持的章节格式：
    - 第N章/第N节/第N回/第N篇（中文或阿拉伯数字）
    - 楔子/引子/序章/终章/尾声
    - N、标题（数字+顿号格式，如"1、五千双皮鞋"）

    注意：第N卷/第N部是分卷标题，不作为章节识别。
    """
    # 主模式：标准章节格式（排除"卷"和"部"）
    main_pattern = re.compile(
        r"^\s*(?:第\s*\d+\s*[章节回篇]|楔子|引子|序章|终章|尾声)\s*"
    )
    # 备用模式：数字+顿号格式
    alt_pattern = re.compile(
        r"^\s*\d{1,4}[、\s]\s*[^\d\s].{0,30}$"
    )

    chapter_lines = []
    prev_line = ""

    for i, line in enumerate(lines):
        # 主模式匹配
        if main_pattern.match(line):
            chapter_lines.append(i)
            prev_line = line
            continue

        # 备用模式匹配
        if alt_pattern.match(line) and len(line.strip()) < 40:
            stripped = line.strip()
            # 排除纯数字编号（如"1、2"）
            if not re.match(r'^\d+[、\s]\s*\d', stripped):
                title_part = re.sub(r'^\d+[、\s]\s*', '', stripped)
                # 标题要有实际内容
                if len(title_part) >= 2 and not title_part.startswith('第'):
                    chapter_lines.append(i)
                    prev_line = line

    return chapter_lines


def split_chapters(lines, chapter_lines):
    """按检测到的章节行切分文本。

    参数：
        lines：原文所有行
        chapter_lines：章节标题所在行号列表

    返回：
        list：每个元素是一个章节的字典（标题、内容、起止行号、字数）
    """
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
    """入库单本小说。

    参数：
        file_path：原始小说文件路径（.txt 格式）

    返回：
        str：素材 ID，失败则返回 None
    """
    file_path = Path(file_path).resolve()
    if not file_path.exists():
        print(f"错误: 文件不存在: {file_path}")
        return None

    # 生成素材 ID 和创建目录
    material_id = generate_material_id()
    novel_dir = NOVELS_DIR / material_id
    novel_dir.mkdir(parents=True, exist_ok=True)

    print(f"正在处理: {file_path.name}")
    print(f"生成 material_id: {material_id}")

    # 读取原文（二进制模式，自动检测编码）
    with open(file_path, "rb") as f:
        raw_bytes = f.read()

    # 预处理：编码检测、去广告、中文数字转换、空白清理
    content = preprocess(raw_bytes)
    lines = content.split("\n")

    # 检测章节
    chapter_lines = detect_chapter_pattern(lines)
    if not chapter_lines:
        print("警告: 未检测到章节名，请检查文件格式")
        return None

    chapters = split_chapters(lines, chapter_lines)
    print(f"识别到 {len(chapters)} 个章节")

    # 构建 source.txt 和章节索引
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

    # 保存章节索引
    with open(novel_dir / "chapter_index.yaml", "w", encoding="utf-8") as f:
        yaml.dump(chapter_index, f, allow_unicode=True, default_flow_style=False)

    # 保存清洗后的原文
    clean_content = "\n".join(source_lines)
    with open(novel_dir / "source.txt", "w", encoding="utf-8") as f:
        f.write(clean_content)

    # 生成元信息
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

    # 创建子目录
    (novel_dir / "outline").mkdir(exist_ok=True)
    (novel_dir / "characters").mkdir(exist_ok=True)
    (novel_dir / "characters" / "profiles").mkdir(exist_ok=True)
    (novel_dir / "worldbuilding").mkdir(exist_ok=True)
    (novel_dir / "chapters").mkdir(exist_ok=True)

    # 初始化 chapters.yaml（空列表）
    with open(novel_dir / "chapters.yaml", "w", encoding="utf-8") as f:
        yaml.dump([], f, allow_unicode=True, default_flow_style=False)

    # 更新全局索引
    update_global_index(material_id, meta)

    print(f"入库完成: {novel_dir}")
    return material_id


def update_global_index(material_id, meta):
    """更新全局索引文件（记录所有已入库小说）。

    参数：
        material_id：素材 ID
        meta：元信息字典
    """
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