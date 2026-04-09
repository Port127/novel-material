"""Tests for source_format.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "core"))

from source_format import (
    cn_to_int,
    is_ad_line,
    fix_quotes,
    normalize_punctuation,
    normalize_whitespace,
    clean_garbled,
    analyze_chapters,
    normalize_chapter_titles,
    remove_ads,
    format_source,
)


class TestCnToInt:
    def test_simple_digits(self):
        assert cn_to_int("123") == 123

    def test_chinese_single(self):
        assert cn_to_int("一") == 1
        assert cn_to_int("九") == 9

    def test_chinese_tens(self):
        assert cn_to_int("十") == 10
        assert cn_to_int("十五") == 15
        assert cn_to_int("二十") == 20
        assert cn_to_int("二十三") == 23

    def test_chinese_hundreds(self):
        assert cn_to_int("一百") == 100
        assert cn_to_int("三百二十一") == 321

    def test_invalid(self):
        assert cn_to_int("abc") is None


class TestAdDetection:
    def test_url_pattern(self):
        assert is_ad_line("更多好书请访问 www.example.com") is True

    def test_http_pattern(self):
        assert is_ad_line("https://example.com/book/123") is True

    def test_normal_text(self):
        assert is_ad_line("他看着远方的山脉，心中百感交集。") is False

    def test_vote_pattern(self):
        assert is_ad_line("求票推荐月票") is True

    def test_separator_line(self):
        assert is_ad_line("──────────────") is True

    def test_chapter_end(self):
        assert is_ad_line("(本章完)") is True


class TestFixQuotes:
    def test_doubled_quotes(self):
        text, count = fix_quotes('他说：""你好""')
        assert '""' not in text
        assert count > 0

    def test_straight_to_curly(self):
        text, count = fix_quotes('他说："你好"')
        assert "\u201c" in text or count > 0


class TestNormalizePunctuation:
    def test_ellipsis(self):
        text, count = normalize_punctuation("他想了想...")
        assert "……" in text

    def test_dash(self):
        text, count = normalize_punctuation("这是--一段话")
        assert "——" in text


class TestNormalizeWhitespace:
    def test_consecutive_blank_lines(self):
        text = "line1\n\n\n\nline2"
        result, count = normalize_whitespace(text)
        assert "\n\n\n" not in result

    def test_trailing_spaces(self):
        text = "hello   \nworld  "
        result, count = normalize_whitespace(text)
        assert not any(line.endswith(" ") for line in result.split("\n"))


class TestCleanGarbled:
    def test_replacement_char(self):
        text, count = clean_garbled("hello\ufffdworld")
        assert "\ufffd" not in text
        assert count == 1

    def test_clean_text(self):
        text, count = clean_garbled("正常的中文文本")
        assert count == 0


class TestAnalyzeChapters:
    def test_standard_chapters(self):
        text = "第一章 开始\n内容1\n\n第二章 继续\n内容2\n\n第三章 结束\n内容3"
        result = analyze_chapters(text)
        assert result["total"] == 3
        assert result["missing"] == []

    def test_missing_chapter(self):
        text = "第一章 开始\n内容1\n\n第三章 跳过\n内容3"
        result = analyze_chapters(text)
        assert 2 in result["missing"]

    def test_arabic_numbers(self):
        text = "第1章 开始\n内容\n\n第2章 继续\n内容"
        result = analyze_chapters(text)
        assert result["total"] == 2


class TestNormalizeChapterTitles:
    def test_standardize(self):
        text = "第一章 开始的故事\n内容\n第二章 继续前行\n更多"
        chapters = analyze_chapters(text)["chapters"]
        result, count = normalize_chapter_titles(text, chapters)
        assert "第1章 开始的故事" in result


class TestRemoveAds:
    def test_remove_ads(self):
        text = "正文内容\n更多好书请访问 www.example.com\n继续正文"
        result, count = remove_ads(text)
        assert "www.example.com" not in result
        assert count == 1
        assert "正文内容" in result


class TestFormatSource:
    def test_full_pipeline(self, tmp_path):
        input_text = (
            "第一章 起始\n"
            "　　他站在那里，思考着未来...\n"
            "更多好书请访问 www.fake.com\n"
            "\n\n\n"
            "第二章 转折\n"
            "　　\"你好\"，她说。\n"
        )
        input_file = tmp_path / "input.txt"
        output_file = tmp_path / "output.txt"
        report_file = tmp_path / "report.yaml"

        input_file.write_text(input_text, encoding="utf-8")
        report = format_source(str(input_file), str(output_file), str(report_file))

        assert output_file.exists()
        assert report_file.exists()
        output_text = output_file.read_text(encoding="utf-8")
        assert "www.fake.com" not in output_text
        assert report["chapters"]["total_detected"] == 2
        assert report["fixes"]["ads_removed"] >= 1
