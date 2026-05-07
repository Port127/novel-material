"""Tests for preprocess module."""
import pytest
from novel_material.pipeline.preprocess import (
    preprocess_text,
    detect_and_convert_encoding,
    normalize_line_endings,
    remove_ad_lines,
    convert_cn_chapter_numbers,
    normalize_whitespace,
)


class TestEncoding:
    """编码检测测试。"""

    def test_utf8_encoding(self):
        """UTF-8 文本检测。"""
        text = "这是一个测试文本"
        raw_bytes = text.encode("utf-8")
        result = detect_and_convert_encoding(raw_bytes)
        assert result == text

    def test_gbk_encoding(self):
        """GBK 文本检测。"""
        text = "这是一个测试文本"
        raw_bytes = text.encode("gbk")
        result = detect_and_convert_encoding(raw_bytes)
        assert result == text

    def test_latin1_fallback(self):
        """Latin-1 兜底。"""
        raw_bytes = b"\xff\xfe invalid utf8"
        result = detect_and_convert_encoding(raw_bytes)
        # 应返回某种字符串，不抛异常
        assert isinstance(result, str)


class TestLineEndings:
    """换行符归一化测试。"""

    def test_crlf_to_lf(self):
        """CRLF 转 LF。"""
        text = "line1\r\nline2\r\nline3"
        result = normalize_line_endings(text)
        assert result == "line1\nline2\nline3"

    def test_cr_to_lf(self):
        """CR 转 LF。"""
        text = "line1\rline2\rline3"
        result = normalize_line_endings(text)
        assert result == "line1\nline2\nline3"


class TestAdRemoval:
    """广告去除测试。"""

    def test_remove_url_line(self, sample_ad_text):
        """去除 URL 行。"""
        result = remove_ad_lines(sample_ad_text)
        assert "www.example.com" not in result
        assert "看书网" not in result

    def test_remove_ad_inline(self):
        """去除行内广告。"""
        text = "正文内容（请记住网站www.test.com）继续正文"
        result = remove_ad_lines(text)
        assert "www.test.com" not in result

    def test_preserve_content(self, sample_ad_text):
        """保留正文内容。"""
        result = remove_ad_lines(sample_ad_text)
        assert "这是正文内容" in result
        assert "这是更多正文" in result


class TestChineseNumbers:
    """中文数字转换测试。"""

    def test_simple_chinese(self, sample_cn_chapter_text):
        """简单中文数字转换。"""
        result = convert_cn_chapter_numbers(sample_cn_chapter_text)
        assert "第1章" in result
        assert "第123章" in result
        assert "第1005章" in result

    def test_ten_prefix(self):
        """"十"开头转换。"""
        text = "第十章 内容"
        result = convert_cn_chapter_numbers(text)
        assert "第10章" in result

    def test_complex_chinese(self):
        """复杂中文数字转换。"""
        text = "第一百二十三章"
        result = convert_cn_chapter_numbers(text)
        assert "第123章" in result


class TestWhitespace:
    """空白归一化测试。"""

    def test_fullwidth_space(self):
        """全角空格转换。"""
        text = "这里　有全角空格"
        result = normalize_whitespace(text)
        assert "　" not in result
        assert "这里 有全角空格" in result

    def test_multiple_blank_lines(self):
        """多余空行合并。"""
        text = "line1\n\n\n\n\nline2"
        result = normalize_whitespace(text)
        # 只保留一个空行
        assert result.count("\n\n") <= 1


class TestFullPipeline:
    """完整预处理测试。"""

    def test_full_pipeline(self, sample_chapter_text):
        """完整预处理流程。"""
        result = preprocess_text(sample_chapter_text)
        # 应不抛异常
        assert isinstance(result, str)
        assert len(result) > 0