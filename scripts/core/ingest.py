#!/usr/bin/env python
"""小说入库：格式清洗 + 章节切分。"""
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
    """生成唯一的 material_id: nm_novel_YYYYMMDD_xxxx"""
    import random
    import string
    date_str = datetime.now().strftime("%Y%m%d")
    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"nm_novel_{date_str}_{random_str}"


def detect_chapter_pattern(lines):
    """检测章节名模式，返回章节行号列表。

    支持的章节格式：
    - 第N章/第N节/第N回/第N篇（中文或阿拉伯数字）
    - 楔子/引子/序章/终章/尾声
    - N、标题（数字+顿号格式，如"1、五千双皮鞋"）

    注意：第N卷/第N部通常是分卷/分部标题，不作为章节识别。
    """
    # 主模式：标准章节格式（排除"卷"和"部"，它们通常是分卷/分部标题）
    main_pattern = re.compile(
        r"^\s*(?:第\s*\d+\s*[章节回篇]|楔子|引子|序章|终章|尾声)\s*"
    )
    # 备用模式：数字+顿号格式（如"1、标题"，需满足一定条件）
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

        # 备用模式：数字+顿号（需排除纯数字行和正文中的编号）
        if alt_pattern.match(line) and len(line.strip()) < 40:
            # 检查是否是真正的章节标题而非正文编号
            # 条件：行长度较短、下一行不是同格式、标题有明显内容
            stripped = line.strip()
            # 排除看起来像正文编号的情况
            if not re.match(r'^\d+[、\s]\s*\d', stripped):  # 不是"1、2"这种
                # 检查标题部分是否有足够内容
                title_part = re.sub(r'^\d+[、\s]\s*', '', stripped)
                if len(title_part) >= 2 and not title_part.startswith('第'):  # 不是"1、第一章"这种重复
                    chapter_lines.append(i)
                    prev_line = line

    return chapter_lines


def split_chapters(lines, chapter_lines):
    """按检测到的章节行切分。"""
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
        print(f"错误: 文件不存在: {file_path}")
        return None

    material_id = generate_material_id()
    novel_dir = NOVELS_DIR / material_id
    novel_dir.mkdir(parents=True, exist_ok=True)

    print(f"正在处理: {file_path.name}")
    print(f"生成 material_id: {material_id}")

    # 读取原文（以二进制模式，自动检测编码）
    with open(file_path, "rb") as f:
        raw_bytes = f.read()

    # 预处理：编码检测 → 换行符统一 → 去广告 → 中文数字转换 → 空白清理
    content = preprocess(raw_bytes)
    lines = content.split("\n")

    # 章节切分（正则此时只需匹配阿拉伯数字，预处理已完成转换）
    chapter_lines = detect_chapter_pattern(lines)
    if not chapter_lines:
        print("警告: 未检测到章节名，请检查文件格式")
        return None

    chapters = split_chapters(lines, chapter_lines)
    print(f"识别到 {len(chapters)} 个章节")

    # 先构建 source.txt 内容，同时计算每章在 source.txt 中的实际行号
    source_lines = []
    chapter_index = []
    current_line = 1  # source.txt 的行号从 1 开始

    for ch in chapters:
        # 计算当前章节在 source.txt 中的行数
        chapter_lines_count = ch["content"].count("\n") + 1
        start_line = current_line
        end_line = current_line + chapter_lines_count - 1

        # 添加章节内容到 source_lines
        source_lines.append(ch["content"])

        # 记录正确的行号
        chapter_index.append({
            "chapter": len(chapter_index) + 1,
            "title": ch["title"],
            "start_line": start_line,
            "end_line": end_line,
            "word_count": ch["word_count"]
        })

        # 更新下一章的起始行号（章节间的分隔符不产生额外行）
        current_line = end_line + 1

    # 保存章节索引（行号现在对应 source.txt）
    with open(novel_dir / "chapter_index.yaml", "w", encoding="utf-8") as f:
        yaml.dump(chapter_index, f, allow_unicode=True, default_flow_style=False)

    # 保存清洗后原文
    clean_content = "\n".join(source_lines)
    with open(novel_dir / "source.txt", "w", encoding="utf-8") as f:
        f.write(clean_content)

    # 生成 meta.yaml
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

    # 创建空的 outline/characters/worldbuilding 目录
    (novel_dir / "outline").mkdir(exist_ok=True)
    (novel_dir / "characters").mkdir(exist_ok=True)
    (novel_dir / "characters" / "profiles").mkdir(exist_ok=True)
    (novel_dir / "worldbuilding").mkdir(exist_ok=True)
    # chapters/ 子目录：chapter_analyze 逐章写入独立文件，完成后合并为 chapters.yaml
    (novel_dir / "chapters").mkdir(exist_ok=True)

    # 初始化 chapters.yaml（空列表占位，待 chapter_analyze 合并填充）
    with open(novel_dir / "chapters.yaml", "w", encoding="utf-8") as f:
        yaml.dump([], f, allow_unicode=True, default_flow_style=False)

    # 更新全局路由表
    update_global_index(material_id, meta)

    print(f"入库完成: {novel_dir}")
    return material_id


def update_global_index(material_id, meta):
    """更新全局索引。"""
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
