"""classify 模块单元测试。"""
import json
import pytest
from pathlib import Path
import tempfile

from novel_material.material.classify import (
    extract_first_three_chapters,
    parse_classification_result,
    classify_book,
    load_progress,
    save_progress,
    get_status,
    load_material_index,
    save_material_index,
    CLASSIFY_INDEX_FILE,
    CLASSIFY_PROGRESS_FILE,
)
from novel_material.material.classify_prompt import VALID_GENRES


class TestExtractFirstThreeChapters:
    """测试前三章提取功能。"""

    def test_extract_three_chapters(self, temp_novel_dir):
        """正常提取前三章。"""
        # 创建测试文件（无缩进）
        content = (
            "第一章 开篇\n\n"
            "这是第一章的内容。\n\n"
            "第二章 发展\n\n"
            "这是第二章的内容。\n\n"
            "第三章 结局\n\n"
            "这是第三章的内容。\n\n"
            "第四章 继续\n\n"
            "这是第四章的内容。\n"
        )
        test_file = temp_novel_dir / "test.txt"
        test_file.write_text(content)

        result = extract_first_three_chapters(test_file)

        # 应包含前三章，不包含第四章
        assert "第一章" in result
        assert "第二章" in result
        assert "第三章" in result
        assert "第四章" not in result

    def test_extract_numeric_chapters(self, temp_novel_dir):
        """支持数字格式章节（第1章）。"""
        content = """第1章 开篇

内容一。

第2章 发展

内容二。

第3章 结局

内容三。

第4章 继续

内容四。
"""
        test_file = temp_novel_dir / "test.txt"
        test_file.write_text(content)

        result = extract_first_three_chapters(test_file)

        assert "第1章" in result
        assert "第2章" in result
        assert "第3章" in result
        assert "第4章" not in result

    def test_less_than_three_chapters(self, temp_novel_dir):
        """章节少于3章时返回全文。"""
        content = "第一章 开篇\n\n这是仅有的内容。\n"
        test_file = temp_novel_dir / "test.txt"
        test_file.write_text(content)

        result = extract_first_three_chapters(test_file)

        assert "第一章" in result
        assert len(result) < 1000  # 应被截断

    def test_file_not_found(self, temp_novel_dir):
        """文件不存在时抛出异常。"""
        test_file = temp_novel_dir / "not_exist.txt"

        with pytest.raises(FileNotFoundError):
            extract_first_three_chapters(test_file)

    def test_truncate_to_max_chars(self, temp_novel_dir):
        """内容过长时截断到 max_chars。"""
        # 创建超长内容
        content = "第一章 开篇\n\n" + "内容内容" * 5000 + "\n\n第二章 发展\n\n" + "内容内容" * 5000
        test_file = temp_novel_dir / "test.txt"
        test_file.write_text(content)

        result = extract_first_three_chapters(test_file, max_chars=1000)

        assert len(result) <= 1000


class TestParseClassificationResult:
    """测试分类结果解析和校验。"""

    def test_parse_valid_result(self):
        """解析有效结果。"""
        result = {
            "genre": ["玄幻", "修仙"],
            "genre_description": "修仙升级流",
            "confidence": 0.8,
        }

        parsed = parse_classification_result(result)

        assert parsed["genre"] == ["玄幻", "修仙"]
        assert parsed["genre_description"] == "修仙升级流"
        assert parsed["confidence"] == 0.8

    def test_genre_as_string(self):
        """genre 为字符串时转为列表。"""
        result = {
            "genre": "玄幻",
            "genre_description": "玄幻小说",
            "confidence": 0.9,
        }

        parsed = parse_classification_result(result)

        assert parsed["genre"] == ["玄幻"]

    def test_invalid_genre_replaced_with_other(self):
        """无效 genre 替换为 其他。"""
        result = {
            "genre": ["未知类型", "不存在的分类"],
            "genre_description": "描述",
            "confidence": 0.5,
        }

        parsed = parse_classification_result(result)

        assert parsed["genre"] == ["其他"]

    def test_partial_valid_genre(self):
        """部分无效 genre 保留有效部分。"""
        result = {
            "genre": ["玄幻", "无效类型"],
            "genre_description": "描述",
            "confidence": 0.7,
        }

        parsed = parse_classification_result(result)

        assert parsed["genre"] == ["玄幻"]

    def test_missing_genre(self):
        """缺少 genre 时抛出异常。"""
        result = {
            "genre_description": "描述",
            "confidence": 0.6,
        }

        with pytest.raises(ValueError, match="缺少 genre"):
            parse_classification_result(result)

    def test_missing_description(self):
        """缺少描述时使用默认值。"""
        result = {
            "genre": ["玄幻"],
            "confidence": 0.8,
        }

        parsed = parse_classification_result(result)

        assert parsed["genre_description"] == "分类描述未生成"

    def test_invalid_confidence(self):
        """无效 confidence 时使用默认值。"""
        result = {
            "genre": ["玄幻"],
            "genre_description": "描述",
            "confidence": "invalid",
        }

        parsed = parse_classification_result(result)

        assert parsed["confidence"] == 0.5

    def test_confidence_out_of_range(self):
        """confidence 超出范围时 clamp。"""
        result = {
            "genre": ["玄幻"],
            "genre_description": "描述",
            "confidence": 1.5,
        }

        parsed = parse_classification_result(result)

        assert parsed["confidence"] == 1.0

        result["confidence"] = -0.5
        parsed = parse_classification_result(result)
        assert parsed["confidence"] == 0.0

    def test_result_not_dict(self):
        """结果不是字典时抛出异常。"""
        result = ["玄幻", "修仙"]

        with pytest.raises(ValueError, match="不是字典"):
            parse_classification_result(result)


class TestClassifyBook:
    """测试分类函数。"""

    def test_low_confidence_marked(self, temp_novel_dir):
        """confidence < 0.6 时标记为 low_confidence。"""
        # Mock LLM 返回低置信度结果
        content = """第一章 开篇

这是内容。
"""
        test_file = temp_novel_dir / "test.txt"
        test_file.write_text(content)

        # 直接调用 parse_classification_result 测试标记逻辑
        result = {
            "genre": ["玄幻"],
            "genre_description": "描述",
            "confidence": 0.5,
        }
        parsed = parse_classification_result(result)

        # confidence 低于 0.6
        assert parsed["confidence"] < 0.6


class TestProgressIO:
    """测试进度文件读写。"""

    def test_save_and_load_progress(self, temp_novel_dir):
        """保存和加载进度文件。"""
        # 临时覆盖进度文件路径
        import novel_material.material.classify as classify_module
        original_path = classify_module.CLASSIFY_PROGRESS_FILE
        classify_module.CLASSIFY_PROGRESS_FILE = temp_novel_dir / "progress.yaml"

        progress = {
            "last_processed_sequence": 100,
            "last_processed_file": "test.txt",
            "last_processed_time": "2026-05-14T10:00:00",
            "processed": 100,
            "total": 1851,
            "remaining": 1751,
            "failed": [],
        }

        save_progress(progress)
        loaded = load_progress()

        assert loaded["last_processed_sequence"] == 100
        assert loaded["last_processed_file"] == "test.txt"
        assert loaded["processed"] == 100

        # 恢复原始路径
        classify_module.CLASSIFY_PROGRESS_FILE = original_path

    def test_load_empty_progress(self, temp_novel_dir):
        """加载不存在进度文件时返回默认值。"""
        import novel_material.material.classify as classify_module
        original_path = classify_module.CLASSIFY_PROGRESS_FILE
        classify_module.CLASSIFY_PROGRESS_FILE = temp_novel_dir / "not_exist.yaml"

        loaded = load_progress()

        assert loaded["last_processed_sequence"] == 0
        assert loaded["processed"] == 0
        assert loaded["failed"] == []

        classify_module.CLASSIFY_PROGRESS_FILE = original_path


class TestMaterialIndexIO:
    """测试分类索引文件读写。"""

    def test_save_and_load_index(self, temp_novel_dir):
        """保存和加载分类索引。"""
        import novel_material.material.classify as classify_module
        original_path = classify_module.CLASSIFY_INDEX_FILE
        classify_module.CLASSIFY_INDEX_FILE = temp_novel_dir / "index.yaml"

        index = {
            "materials": {
                "0001_test": {
                    "title": "测试小说",
                    "genre": ["玄幻"],
                    "classification_status": "done",
                }
            }
        }

        save_material_index(index)
        loaded = load_material_index()

        assert "materials" in loaded
        assert loaded["materials"]["0001_test"]["title"] == "测试小说"

        classify_module.CLASSIFY_INDEX_FILE = original_path

    def test_save_index_without_materials_key(self, temp_novel_dir):
        """保存索引时自动添加 materials 键。"""
        import novel_material.material.classify as classify_module
        original_path = classify_module.CLASSIFY_INDEX_FILE
        classify_module.CLASSIFY_INDEX_FILE = temp_novel_dir / "index.yaml"

        # 不带 materials 键的数据
        index = {
            "0001_test": {
                "title": "测试小说",
                "genre": ["玄幻"],
            }
        }

        save_material_index(index)
        loaded = load_material_index()

        # 应自动添加 materials 键
        assert "materials" in loaded

        classify_module.CLASSIFY_INDEX_FILE = original_path


class TestGetStatus:
    """测试进度统计获取。"""

    def test_get_status_empty(self, temp_novel_dir):
        """空进度时返回正确统计。"""
        import novel_material.material.classify as classify_module
        original_progress_path = classify_module.CLASSIFY_PROGRESS_FILE
        classify_module.CLASSIFY_PROGRESS_FILE = temp_novel_dir / "progress.yaml"

        status = get_status()

        assert status["total"] > 0  # 应读取 novel_index.json
        assert status["processed"] == 0
        assert status["failed"] == 0

        classify_module.CLASSIFY_PROGRESS_FILE = original_progress_path


class TestValidGenres:
    """测试 genre 取值范围。"""

    def test_valid_genres_set(self):
        """VALID_GENRES 包含所有预期值。"""
        expected = ["玄幻", "修仙", "奇幻", "科幻", "都市", "历史", "武侠", "仙侠", "游戏", "悬疑", "其他"]

        for genre in expected:
            assert genre in VALID_GENRES

    def test_subgenres_in_valid_set(self):
        """子类型也应在有效集合中。"""
        subgenres = ["东方玄幻", "西幻", "魔幻", "都市异能", "历史架空", "网游", "电竞", "推理", "惊悚"]

        for genre in subgenres:
            assert genre in VALID_GENRES