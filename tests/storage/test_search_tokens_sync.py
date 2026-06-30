"""同步阶段词法检索文本构造测试。"""

import json

import numpy as np
import pytest

from novel_material.infra.yaml_io import save_yaml
from novel_material.storage.sync_chapters import (
    build_chapter_search_tokens,
    sync_chapters,
)
from novel_material.storage.sync_characters import (
    build_character_search_tokens,
    sync_characters,
)
from novel_material.storage.sync_meta import build_novel_search_tokens, sync_meta
from novel_material.storage.sync_outline import (
    build_outline_beat_search_tokens,
    build_outline_sequence_search_tokens,
    sync_outline,
)
from novel_material.storage.sync_worldbuilding import (
    build_worldbuilding_search_tokens,
    sync_worldbuilding,
)


class RecordingCursor:
    def __init__(self, connection):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        self.connection.executions.append((sql, params))


class RecordingConnection:
    def __init__(self):
        self.executions = []

    def cursor(self):
        return RecordingCursor(self)


def _search_token_writes(connection):
    return [
        (sql, params)
        for sql, params in connection.executions
        if "search_tokens" in sql
    ]


def test_build_chapter_search_tokens_uses_all_retrieval_fields():
    tokens = build_chapter_search_tokens({
        "title": "雨夜告别",
        "summary": "主角向导师辞行。",
        "key_event": "师徒分别",
        "plot_progress": "主角独自上路",
        "chapter_functions": ["关系转折"],
        "emotional_tone": ["悲伤"],
        "scene_type": ["雨夜"],
        "technique": ["环境烘托"],
        "hook_type": "新旅程",
    })

    for term in ("导师", "分别", "关系", "悲伤", "雨夜", "环境", "旅程"):
        assert term in tokens


def test_build_novel_search_tokens_uses_planning_fields():
    tokens = build_novel_search_tokens({
        "name": "青云纪",
        "premise": "废柴少年逆袭",
        "genre": ["玄幻"],
        "theme": ["成长"],
        "tone": ["热血"],
        "structure_type": "三幕式",
        "tags": {"elements": ["宗门"]},
    })

    for term in ("青云", "废柴", "玄幻", "成长", "热血", "三幕", "宗门"):
        assert term in tokens


def test_build_character_search_tokens_uses_profile_and_psychology():
    tokens = build_character_search_tokens({
        "name": "林师",
        "archetype": "导师",
        "role": "supporting",
        "arc_summary": "引导主角独立",
        "narrative_function": "传承",
        "description": "隐居高人",
        "psychology": {"fatal_flaw": "过度保护"},
    })

    for term in ("林师", "导师", "独立", "传承", "隐居", "保护"):
        assert term in tokens


def test_build_worldbuilding_search_tokens_uses_entity_properties():
    tokens = build_worldbuilding_search_tokens({
        "name": "青云宗",
        "description": "山中宗门",
        "properties": {"leader": "林师", "strength": "一流"},
    }, "factions")

    for term in ("青云", "宗门", "林师", "一流", "factions"):
        assert term in tokens


def test_build_outline_search_tokens_include_structure_coordinates():
    sequence_tokens = build_outline_sequence_search_tokens(
        {"title": "局势反转", "description": "主角识破骗局"},
        act=2,
        sequence=4,
    )
    beat_tokens = build_outline_beat_search_tokens(
        {"title": "揭露", "description": "证据出现"},
        act=2,
        sequence=4,
        beat=1,
    )

    assert all(term in sequence_tokens for term in ("反转", "骗局", "第2幕", "序列4"))
    assert all(term in beat_tokens for term in ("揭露", "证据", "第2幕", "序列4", "节拍1"))


def test_sync_meta_writes_search_tokens(tmp_path):
    save_yaml(tmp_path / "meta.yaml", {
        "material_id": "nm_demo",
        "name": "青云纪",
        "premise": "废柴少年逆袭",
        "genre": ["玄幻"],
    })
    connection = RecordingConnection()

    sync_meta(connection, tmp_path, "nm_demo")

    writes = _search_token_writes(connection)
    assert len(writes) == 1
    assert "青云" in writes[0][1][-1]


def test_sync_chapters_writes_search_tokens_without_embedding(tmp_path):
    save_yaml(tmp_path / "chapters.yaml", [{
        "chapter": 1,
        "title": "雨夜告别",
        "summary": "主角向导师辞行。",
    }])
    connection = RecordingConnection()

    sync_chapters(connection, tmp_path, "nm_demo")

    writes = _search_token_writes(connection)
    assert len(writes) == 1
    assert "导师" in writes[0][1][-1]


def test_sync_characters_writes_search_tokens_without_embedding(tmp_path):
    profiles = tmp_path / "characters" / "profiles"
    profiles.mkdir(parents=True)
    save_yaml(profiles / "lin.yaml", {
        "name": "林师",
        "archetype": "导师",
        "arc_summary": "引导主角独立",
    })
    connection = RecordingConnection()

    sync_characters(connection, tmp_path, "nm_demo")

    writes = _search_token_writes(connection)
    assert len(writes) == 1
    assert "导师" in writes[0][1][-1]


def test_sync_worldbuilding_writes_search_tokens_without_embedding(tmp_path):
    world_dir = tmp_path / "worldbuilding"
    world_dir.mkdir()
    save_yaml(world_dir / "_index.yaml", {})
    save_yaml(world_dir / "factions.yaml", [{
        "name": "青云宗",
        "description": "山中宗门",
    }])
    connection = RecordingConnection()

    sync_worldbuilding(connection, tmp_path, "nm_demo")

    writes = _search_token_writes(connection)
    assert len(writes) == 1
    assert "宗门" in writes[0][1][-1]


def test_sync_worldbuilding_reads_layered_entities(tmp_path):
    world_dir = tmp_path / "worldbuilding" / "entities"
    world_dir.mkdir(parents=True)
    save_yaml(
        tmp_path / "worldbuilding" / "_index.yaml",
        {"layout": "layered", "llm_success": True},
    )
    save_yaml(
        world_dir / "organization_x.yaml",
        {
            "id": "organization_x",
            "type": "organization",
            "name": "公司",
            "description": "创业组织",
            "properties": {"dimension_ids": ["business_rules"]},
            "importance": "primary",
            "first_appearance_chapter": 3,
            "evidence": [{"chapter": 3, "summary": "成立公司"}],
        },
    )

    connection = RecordingConnection()
    sync_worldbuilding(connection, tmp_path, "nm_demo")

    writes = _search_token_writes(connection)
    assert len(writes) == 1
    params = writes[0][1]
    properties = json.loads(params[4])
    assert params[1] == "organization"
    assert params[2] == "公司"
    assert properties["entity_id"] == "organization_x"
    assert properties["dimension_ids"] == ["business_rules"]
    assert properties["evidence"][0]["summary"] == "成立公司"
    assert params[5] == 3
    assert "创业" in params[-1]


def test_sync_worldbuilding_adds_relation_summaries_to_layered_entities(tmp_path):
    world_dir = tmp_path / "worldbuilding" / "entities"
    world_dir.mkdir(parents=True)
    save_yaml(
        tmp_path / "worldbuilding" / "_index.yaml",
        {"layout": "layered", "llm_success": True},
    )
    save_yaml(
        world_dir / "organization_x.yaml",
        {
            "id": "organization_x",
            "type": "organization",
            "name": "公司",
            "description": "创业组织",
        },
    )
    save_yaml(
        world_dir / "person_y.yaml",
        {
            "id": "person_y",
            "type": "social_group",
            "name": "资本方",
            "description": "投资人群体",
        },
    )
    save_yaml(
        tmp_path / "worldbuilding" / "relations.yaml",
        {
            "relations": [
                {
                    "id": "rel_0001",
                    "source_id": "organization_x",
                    "target_id": "person_y",
                    "relation_type": "funded_by",
                    "description": "公司依赖资本方融资。",
                    "evidence": [{"chapter": 4, "summary": "获得投资"}],
                }
            ],
        },
    )

    connection = RecordingConnection()
    sync_worldbuilding(connection, tmp_path, "nm_demo")

    company_write = next(
        params for _sql, params in _search_token_writes(connection)
        if params[2] == "公司"
    )
    properties = json.loads(company_write[4])
    assert properties["relation_summaries"] == [
        {
            "relation_id": "rel_0001",
            "related_entity_id": "person_y",
            "relation_type": "funded_by",
            "description": "公司依赖资本方融资。",
            "evidence": [{"chapter": 4, "basis": "fact", "summary": "获得投资"}],
        }
    ]


def test_sync_worldbuilding_uses_legacy_vector_alias_for_layered_entity(tmp_path):
    world_dir = tmp_path / "worldbuilding" / "entities"
    world_dir.mkdir(parents=True)
    save_yaml(
        tmp_path / "worldbuilding" / "_index.yaml",
        {"layout": "layered", "llm_success": True},
    )
    save_yaml(
        world_dir / "organization_x.yaml",
        {
            "id": "organization_x",
            "type": "organization",
            "name": "公司",
            "description": "创业组织",
        },
    )
    np.savez_compressed(
        tmp_path / "worldbuilding" / "wb_embeddings.npz",
        keys=np.array(["factions:公司"], dtype=np.str_),
        vectors=np.array([[0.1, 0.2, 0.3]], dtype=np.float32),
    )

    connection = RecordingConnection()
    sync_worldbuilding(connection, tmp_path, "nm_demo")

    writes = _search_token_writes(connection)
    assert len(writes) == 1
    assert len(writes[0][1]) == 9
    assert writes[0][1][7] == pytest.approx([0.1, 0.2, 0.3])


def test_sync_outline_writes_sequence_and_beat_search_tokens(tmp_path):
    outline_dir = tmp_path / "outline"
    outline_dir.mkdir()
    save_yaml(outline_dir / "structure.yaml", {
        "acts": [{
            "act": 2,
            "sequences": [{
                "sequence": 4,
                "title": "局势反转",
                "description": "主角识破骗局",
                "chapters": [31, 40],
                "beats": [{
                    "beat": 1,
                    "title": "揭露",
                    "description": "证据出现",
                }],
            }],
        }],
    })
    connection = RecordingConnection()

    sync_outline(connection, tmp_path, "nm_demo")

    writes = _search_token_writes(connection)
    assert len(writes) == 2
    assert "反转" in writes[0][1][-1]
    assert "揭露" in writes[1][1][-1]
