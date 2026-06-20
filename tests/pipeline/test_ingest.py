"""Tests for ingest module."""
import re

import pytest
from novel_material.pipeline.ingest import (
    detect_chapter_pattern,
    split_chapters,
    generate_material_id,
)


class TestChapterDetection:
    """章节检测测试。"""

    def test_arabic_numbers(self):
        """阿拉伯数字章节。"""
        lines = [
            "第1章 开篇",
            "正文内容",
            "第2章 发展",
            "更多内容",
        ]
        result = detect_chapter_pattern(lines)
        assert result == [0, 2]

    def test_chinese_numbers(self):
        """预处理后的中文数字章节（已转为阿拉伯数字）。"""
        lines = [
            "第1章 开篇",
            "正文内容",
            "第10章 高潮",
        ]
        result = detect_chapter_pattern(lines)
        assert 0 in result
        assert 2 in result

    def test_special_chapters(self):
        """特殊章节名。"""
        lines = [
            "楔子",
            "引言内容",
            "第1章 正文",
            "终章",
            "结局内容",
        ]
        result = detect_chapter_pattern(lines)
        # 楔子、第1章、终章都应被检测
        assert 0 in result
        assert 2 in result
        assert 3 in result

    def test_alt_pattern(self):
        """数字+顿号格式。"""
        lines = [
            "1、开篇标题",
            "正文内容",
            "2、发展标题",
        ]
        result = detect_chapter_pattern(lines)
        assert result == [0, 2]

    def test_no_chapters(self):
        """无章节返回空列表。"""
        lines = ["普通文本", "没有章节标题"]
        result = detect_chapter_pattern(lines)
        assert result == []


class TestChapterSplit:
    """章节切分测试。"""

    def test_split_basic(self):
        """基本切分。"""
        lines = [
            "第1章 开篇",
            "第一章内容",
            "第2章 发展",
            "第二章内容",
        ]
        chapter_lines = detect_chapter_pattern(lines)
        chapters = split_chapters(lines, chapter_lines)

        assert len(chapters) == 2
        assert chapters[0]["title"] == "第1章 开篇"
        assert chapters[1]["title"] == "第2章 发展"

    def test_split_content(self):
        """内容切分正确。"""
        lines = [
            "第1章 开篇",
            "内容行1",
            "内容行2",
            "第2章 发展",
            "内容行3",
        ]
        chapter_lines = detect_chapter_pattern(lines)
        chapters = split_chapters(lines, chapter_lines)

        assert "内容行1" in chapters[0]["content"]
        assert "内容行2" in chapters[0]["content"]
        assert "内容行3" in chapters[1]["content"]

    def test_word_count(self):
        """字数统计正确。"""
        lines = [
            "第1章 开篇",
            "这是一段测试内容",
        ]
        chapter_lines = detect_chapter_pattern(lines)
        chapters = split_chapters(lines, chapter_lines)

        # word_count 包含标题+内容，但不含空格、换行等空白字符
        full_content = "第1章 开篇\n这是一段测试内容"
        assert chapters[0]["word_count"] == len(re.sub(r"\s", "", full_content))


class TestMaterialId:
    """素材 ID 生成测试。"""

    def test_format(self):
        """ID 格式正确。"""
        id = generate_material_id()
        assert id.startswith("nm_novel_")
        # nm_novel_YYYYMMDD_XXXX
        parts = id.split("_")
        assert len(parts) == 4
        assert len(parts[2]) == 8  # YYYYMMDD
        assert len(parts[3]) == 4  # random

    def test_unique(self):
        """ID 应唯一。"""
        ids = [generate_material_id() for _ in range(10)]
        assert len(set(ids)) == 10
