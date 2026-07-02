"""Tests for validation.schema module."""
import logging

import pytest

from novel_material.infra.yaml_io import save_yaml
from novel_material.validation.schema import EvaluationModel, MetaModel
from novel_material.validation.validators import validate_material


class TestMetaModel:
    """Meta YAML 模型测试。"""

    def test_valid_meta(self):
        """有效 meta.yaml。"""
        data = {
            "material_id": "nm_novel_20260101_abcd",
            "name": "测试小说",
            "status": "clean",
            "word_count": 1000,
            "chapter_count": 10,
        }
        model = MetaModel(**data)
        assert model.material_id == data["material_id"]
        assert model.name == data["name"]

    def test_invalid_material_id(self):
        """无效 material_id 格式。"""
        data = {
            "material_id": "invalid_id",
            "name": "测试",
            "status": "clean",
        }
        with pytest.raises(Exception):
            MetaModel(**data)

    def test_invalid_status(self):
        """无效 status 值。"""
        data = {
            "material_id": "nm_novel_20260101_abcd",
            "name": "测试",
            "status": "invalid_status",
        }
        with pytest.raises(Exception):
            MetaModel(**data)

    def test_empty_name(self):
        """空 name。"""
        data = {
            "material_id": "nm_novel_20260101_abcd",
            "name": "",
            "status": "clean",
        }
        with pytest.raises(Exception):
            MetaModel(**data)


class TestPydanticValidation:
    """Pydantic 校验测试。"""

    def test_model_serialization(self):
        """模型序列化。"""
        data = {
            "material_id": "nm_novel_20260101_abcd",
            "name": "测试",
            "status": "clean",
        }
        model = MetaModel(**data)
        # 验证可以序列化
        dumped = model.model_dump()
        assert dumped["material_id"] == data["material_id"]


def test_validation_accepts_evaluation_v3_navigation():
    model = EvaluationModel(
        schema_version="3.0.0",
        novel_type=["都市"],
        premise="重生者重新选择人生。",
        main_thread_summary=(
            "主角围绕事业与关系重建展开主线，在重新面对旧关系和商业机会时，"
            "不断调整自己的选择方式。故事重点呈现他如何利用先知优势破局，"
            "又如何在亲密关系、朋友利益和个人野心之间付出代价。随着阶段推进，"
            "他的行动从单纯弥补遗憾转向主动承担后果，人物关系也因此形成持续张力。"
        ),
        stage_map=[],
        core_character_candidates=[],
        worldbuilding_dimensions=[],
        analysis_focus=[],
        sample_coverage={
            "sampled_chapters": [],
            "covered_ranges": [],
            "limitations": [],
        },
    )
    assert model.schema_version == "3.0.0"


def test_unknown_chapter_functions_are_review_warnings_not_schema_crash(tmp_path, monkeypatch, caplog):
    material_id = "nm_novel_20260101_abcd"
    novel = tmp_path / material_id
    novel.mkdir()
    save_yaml(
        novel / "meta.yaml",
        {
            "material_id": material_id,
            "name": "示例",
            "status": "clean",
            "word_count": 100,
            "chapter_count": 1,
        },
    )
    save_yaml(
        novel / "chapters.yaml",
        [
            {
                "chapter": 1,
                "title": "一",
                "summary": (
                    "主角在压力下首次登场，遭遇关键阻碍并决定主动破局，"
                    "为后续主线推进建立清晰动机，同时埋下人物关系和外部冲突的伏笔。"
                ),
                "tension_level": 3,
                "chapter_functions": ["开篇建立"],
            }
        ],
    )

    monkeypatch.setattr("novel_material.validation.validators.NOVELS_DIR", tmp_path)
    monkeypatch.setattr(
        "novel_material.validation.validators.validate_tags_batch",
        lambda _dimension, tags: ([], list(tags)),
    )

    with caplog.at_level(logging.WARNING):
        passed = validate_material(material_id, verbose=False)

    assert passed is True
    assert "chapter_functions '开篇建立' 未在标签字典中，已降级为复核警告" in caplog.text
