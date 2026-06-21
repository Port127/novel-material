"""搜索模块的数据库边界与返回契约测试。"""

from contextlib import contextmanager

import pytest

from novel_material.search.chapter import search_chapters
from novel_material.search.character import search_characters
from novel_material.search.db import SearchDatabaseError, readonly_connection
from novel_material.search.detail import search_detail
from novel_material.search.event import search_events
from novel_material.search.models import SearchResult
from novel_material.search.outline import search_outlines
from novel_material.search.world import search_worldbuilding
from tests.search.fakes import FakeConnection


def test_readonly_connection_reports_missing_database_url(monkeypatch):
    """缺少数据库配置时应返回明确的搜索数据库错误。"""
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(SearchDatabaseError, match="DATABASE_URL"):
        with readonly_connection(database_url=None):
            pass


def test_readonly_connection_closes_connection(monkeypatch):
    """只读连接退出上下文后必须关闭。"""
    fake = FakeConnection()
    monkeypatch.setattr("psycopg2.connect", lambda *_args, **_kwargs: fake)

    with readonly_connection("postgresql://test") as conn:
        assert conn is fake

    assert fake.session_options == {"readonly": True, "autocommit": True}
    assert fake.closed is True


SEARCH_CASES = [
    (
        "novel_material.search.chapter.readonly_connection",
        lambda: search_chapters("告别"),
        FakeConnection(rows=[{
            "material_id": "nm_demo",
            "chapter": 7,
            "title": "第七章 告别",
            "summary": "主角在雨中告别导师。",
            "tension_level": 3,
            "pacing": "medium",
            "chapter_functions": ["关系转折"],
            "characters_appear": ["主角", "导师"],
            "key_plot_point": "turning_point",
            "key_event": "师徒分别",
            "novel_name": "示例小说",
            "genre": ["玄幻"],
            "tags": {},
        }]),
        "chapter",
        "chapter:nm_demo:7",
    ),
    (
        "novel_material.search.event.readonly_connection",
        lambda: search_events("告别", keyword=True),
        FakeConnection(rows=[{
            "material_id": "nm_demo",
            "chapter": 7,
            "title": "第七章 告别",
            "summary": "主角在雨中告别导师。",
            "tension_level": 3,
            "pacing": "medium",
            "chapter_functions": ["关系转折"],
            "characters_appear": ["主角", "导师"],
            "novel_name": "示例小说",
            "genre": ["玄幻"],
        }]),
        "event",
        "event:nm_demo:7",
    ),
    (
        "novel_material.search.outline.readonly_connection",
        lambda: search_outlines(query="复仇"),
        FakeConnection(rows=[{
            "material_id": "nm_demo",
            "name": "示例小说",
            "genre": ["玄幻"],
            "premise": "少年踏上复仇之路。",
            "structure_type": "三幕式",
            "act_count": 3,
            "sequence_count": 8,
            "tags": {"elements": ["复仇"]},
        }]),
        "outline",
        "outline:nm_demo",
    ),
    (
        "novel_material.search.character.readonly_connection",
        lambda: search_characters(query="导师"),
        FakeConnection(rows=[{
            "material_id": "nm_demo",
            "name": "林师",
            "role": "supporting",
            "archetype": "导师",
            "moral_spectrum": "善",
            "arc_summary": "引导主角独立。",
            "narrative_function": "传承",
            "appearance_count": 20,
            "description": "隐居高人。",
            "novel_name": "示例小说",
            "novel_genre": ["玄幻"],
        }]),
        "character",
        "character:nm_demo:林师",
    ),
    (
        "novel_material.search.world.readonly_connection",
        lambda: search_worldbuilding(query="宗门"),
        FakeConnection(rows=[{
            "material_id": "nm_demo",
            "entity_type": "factions",
            "name": "青云宗",
            "description": "山中宗门。",
            "properties": {"rank": "一流"},
            "importance": "primary",
            "first_appearance": 2,
            "novel_name": "示例小说",
            "novel_genre": ["玄幻"],
        }]),
        "world",
        "world:nm_demo:factions:青云宗",
    ),
    (
        "novel_material.search.detail.readonly_connection",
        lambda: search_detail(query="反转"),
        FakeConnection(result_sets=[
            [{
                "material_id": "nm_demo",
                "act": 2,
                "sequence": 4,
                "title": "局势反转",
                "chapters_start": 31,
                "chapters_end": 40,
                "description": "主角识破骗局。",
                "novel_name": "示例小说",
                "novel_genre": ["玄幻"],
            }],
            [{
                "beat": 1,
                "title": "揭露",
                "chapter": 35,
                "description": "证据出现。",
                "tension": 4,
            }],
        ]),
        "detail",
        "detail:nm_demo:2:4",
    ),
]


@pytest.mark.parametrize(
    ("target", "call", "fake", "expected_type", "expected_id"),
    SEARCH_CASES,
)
def test_db_search_functions_return_models_without_printing(
    monkeypatch,
    capsys,
    target,
    call,
    fake,
    expected_type,
    expected_id,
):
    """数据库检索只返回结构化模型，不负责终端展示。"""

    @contextmanager
    def fake_readonly_connection(*_args, **_kwargs):
        yield fake

    monkeypatch.setattr(target, fake_readonly_connection)

    results = call()

    assert len(results) == 1
    assert isinstance(results[0], SearchResult)
    assert results[0].document_type == expected_type
    assert results[0].result_id == expected_id
    assert capsys.readouterr().out == ""
