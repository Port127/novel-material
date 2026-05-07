"""Tests for validation.schema module."""
import pytest

from novel_material.validation.schema import MetaModel


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