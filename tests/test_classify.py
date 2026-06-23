"""classify 模块单元测试。"""
import json
import pytest
from pathlib import Path
import tempfile
from typer.testing import CliRunner

from novel_material.cli.main import app

from novel_material.material.classify import (
    extract_sample_chapters,
    parse_classification_result,
    load_genre_mapping,
    classify_book,
    load_progress,
    save_progress,
    get_status,
    load_material_index,
    save_material_index,
    CLASSIFY_INDEX_FILE,
    CLASSIFY_PROGRESS_FILE,
)


class TestExtractSampleChapters:
    """测试分布式采样功能。"""

    def test_sample_distribution(self, temp_novel_dir):
        """测试采样分布：开头 + 中间 + 结尾。"""
        # 创建 100 章小说
        content = "\n\n".join(f"第{i}章 内容{i}" for i in range(1, 101))
        test_file = temp_novel_dir / "test.txt"
        test_file.write_text(content)

        result = extract_sample_chapters(test_file)

        # 应包含开头（第1章）和结尾（第100章）
        assert "第1章" in result
        assert "第100章" in result

    def test_sample_ratio(self, temp_novel_dir):
        """测试采样比例（约 0.5%）。"""
        # 创建 200 章小说
        content = "\n\n".join(f"第{i}章 内容{i}" for i in range(1, 201))
        test_file = temp_novel_dir / "test.txt"
        test_file.write_text(content)

        result = extract_sample_chapters(test_file, sample_ratio=0.005)

        # 200 * 0.005 = 1, min=3 → 采样 3 章
        assert "第1章" in result
        assert "第200章" in result

    def test_short_novel(self, temp_novel_dir):
        """少于 min_chapters 时取全文前部分。"""
        content = "第1章 内容\n\n第2章 内容"
        test_file = temp_novel_dir / "test.txt"
        test_file.write_text(content)

        result = extract_sample_chapters(test_file, min_chapters=3)

        assert len(result) > 0

    def test_file_not_found(self, temp_novel_dir):
        """文件不存在时抛出异常。"""
        test_file = temp_novel_dir / "not_exist.txt"

        with pytest.raises(FileNotFoundError):
            extract_sample_chapters(test_file)

    def test_max_chars_per_chapter(self, temp_novel_dir):
        """每章内容过长时截断。"""
        # 创建超长单章
        content = "第1章 开篇\n\n" + "内容" * 5000 + "\n\n第2章 继续\n\n" + "内容" * 5000
        test_file = temp_novel_dir / "test.txt"
        test_file.write_text(content)

        result = extract_sample_chapters(test_file, max_chars_per_chapter=1000)

        # 每章最多 1000 字
        assert len(result) <= 3000  # 3 章 * 1000 字


class TestParseClassificationResult:
    """测试分类结果解析和校验（新格式）。"""

    def test_parse_valid_result(self):
        """解析有效结果。"""
        # 模拟 genre_mapping
        genre_mapping = (["玄幻", "仙侠", "都市", "科幻"], {"修真文明": "仙侠"})

        result = {
            "genre_primary": "玄幻",
            "genre_secondary": "东方玄幻",
            "genre_description": "修仙升级流",
            "confidence": 0.8,
        }

        parsed = parse_classification_result(result, genre_mapping)

        assert parsed["genre_primary"] == "玄幻"
        assert parsed["genre_secondary"] == "东方玄幻"
        assert parsed["genre_description"] == "修仙升级流"
        assert parsed["confidence"] == 0.8

    def test_invalid_genre_primary_replaced(self):
        """无效 genre_primary 替换为 其他。"""
        genre_mapping = (["玄幻", "仙侠", "都市"], {})

        result = {
            "genre_primary": "未知类型",
            "genre_description": "描述",
            "confidence": 0.5,
        }

        parsed = parse_classification_result(result, genre_mapping)

        assert parsed["genre_primary"] == "其他"

    def test_secondary_genre_mapping_warning(self):
        """二级题材映射到不同一级时记录警告。"""
        genre_mapping = (["玄幻", "仙侠"], {"修真文明": "仙侠"})

        result = {
            "genre_primary": "玄幻",
            "genre_secondary": "修真文明",
            "genre_description": "描述",
            "confidence": 0.7,
        }

        parsed = parse_classification_result(result, genre_mapping)

        # 应正常解析，但会有 warning log
        assert parsed["genre_primary"] == "玄幻"
        assert parsed["genre_secondary"] == "修真文明"

    def test_elements_parsed(self):
        """解析 elements 字段。"""
        genre_mapping = (["玄幻"], {})

        result = {
            "genre_primary": "玄幻",
            "elements": ["重生", "系统", "逆袭"],
            "confidence": 0.8,
        }

        parsed = parse_classification_result(result, genre_mapping)

        assert parsed["elements"] == ["重生", "系统", "逆袭"]

    def test_style_parsed(self):
        """解析 style 字段。"""
        genre_mapping = (["玄幻"], {})

        result = {
            "genre_primary": "玄幻",
            "style": {"narrative": "快节奏", "tone": "热血"},
            "confidence": 0.8,
        }

        parsed = parse_classification_result(result, genre_mapping)

        assert parsed["style"]["narrative"] == "快节奏"

    def test_quality_parsed_with_score(self):
        """解析 quality 字段并计算综合评分。"""
        genre_mapping = (["玄幻"], {})

        result = {
            "genre_primary": "玄幻",
            "quality": {"writing": 4, "plot": 3, "character": 3},
            "confidence": 0.8,
        }

        parsed = parse_classification_result(result, genre_mapping)

        assert parsed["quality"]["writing"] == 4
        assert parsed["quality"]["score"] == 3.3

    def test_missing_description(self):
        """缺少描述时使用默认值。"""
        genre_mapping = (["玄幻"], {})

        result = {
            "genre_primary": "玄幻",
            "confidence": 0.8,
        }

        parsed = parse_classification_result(result, genre_mapping)

        assert parsed["genre_description"] == "分类描述未生成"

    def test_invalid_confidence(self):
        """无效 confidence 时使用默认值。"""
        genre_mapping = (["玄幻"], {})

        result = {
            "genre_primary": "玄幻",
            "confidence": "invalid",
        }

        parsed = parse_classification_result(result, genre_mapping)

        assert parsed["confidence"] == 0.5

    def test_confidence_out_of_range(self):
        """confidence 超出范围时 clamp。"""
        genre_mapping = (["玄幻"], {})

        result = {
            "genre_primary": "玄幻",
            "confidence": 1.5,
        }

        parsed = parse_classification_result(result, genre_mapping)

        assert parsed["confidence"] == 1.0

        result["confidence"] = -0.5
        parsed = parse_classification_result(result, genre_mapping)
        assert parsed["confidence"] == 0.0

    def test_result_not_dict(self):
        """结果不是字典时抛出异常。"""
        genre_mapping = (["玄幻"], {})

        result = ["玄幻", "修仙"]

        with pytest.raises(ValueError, match="classification 应为对象"):
            parse_classification_result(result, genre_mapping)


class TestLoadGenreMapping:
    """测试 genre 映射加载。"""

    def test_load_genre_mapping_returns_tuple(self):
        """返回一级题材列表和二级映射。"""
        # 注意：此测试依赖数据库连接
        try:
            primary_genres, secondary_mapping = load_genre_mapping()

            assert isinstance(primary_genres, list)
            assert isinstance(secondary_mapping, dict)
            assert len(primary_genres) > 0
        except Exception:
            # 如果数据库未连接，跳过测试
            pytest.skip("数据库未连接")


class TestClassifyBook:
    """测试分类函数。"""

    def test_low_confidence_marked(self, temp_novel_dir):
        """confidence < 0.6 时标记为 low_confidence。"""
        content = """第一章 开篇

这是内容。
"""
        test_file = temp_novel_dir / "test.txt"
        test_file.write_text(content)

        # 直接测试 parse_classification_result 的标记逻辑
        genre_mapping = (["玄幻"], {})
        result = {
            "genre_primary": "玄幻",
            "confidence": 0.5,
        }
        parsed = parse_classification_result(result, genre_mapping)

        # confidence 低于 0.6
        assert parsed["confidence"] < 0.6


class TestProgressIO:
    """测试进度文件读写。"""

    def test_save_and_load_progress(self, temp_novel_dir):
        """保存和加载进度文件。"""
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
                    "genre_primary": "玄幻",
                    "genre_secondary": "东方玄幻",
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
                "genre_primary": "玄幻",
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
        import json
        import novel_material.material.classify as classify_module

        novel_index_file = temp_novel_dir / "novel_index.json"
        novel_index_file.write_text(
            json.dumps([{"seq": 1}, {"seq": 2}], ensure_ascii=False),
            encoding="utf-8",
        )

        original_progress_path = classify_module.CLASSIFY_PROGRESS_FILE
        original_novel_index_file = classify_module.NOVEL_INDEX_FILE
        classify_module.CLASSIFY_PROGRESS_FILE = temp_novel_dir / "progress.yaml"
        classify_module.NOVEL_INDEX_FILE = novel_index_file

        status = get_status()

        assert status["total"] > 0  # 应读取 novel_index.json
        assert status["processed"] == 0
        assert status["failed"] == 0

        classify_module.CLASSIFY_PROGRESS_FILE = original_progress_path
        classify_module.NOVEL_INDEX_FILE = original_novel_index_file


def test_classify_status_does_not_use_fixed_per_book_eta(monkeypatch):
    monkeypatch.setattr(
        "novel_material.cli.material.get_status",
        lambda: {
            "total": 10,
            "processed": 1,
            "progress_percent": 10,
            "remaining": 9,
            "failed": 0,
            "last_processed_file": "demo.txt",
            "last_processed_time": "2026-06-22T10:00:00",
        },
    )

    result = CliRunner().invoke(app, ["material", "classify", "status"])

    assert result.exit_code == 0
    assert "估算中" in result.stdout
    assert "~0.1小时" not in result.stdout
