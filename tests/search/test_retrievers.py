from contextlib import contextmanager
import importlib

import pytest

from novel_material.search.models import SearchRequest
from novel_material.search.detail import retrieve_details_semantic
from tests.search.fakes import FakeConnection


LEXICAL_CASES = [
    ("chapter", "retrieve_chapters_lexical"),
    ("event", "retrieve_events_lexical"),
    ("outline", "retrieve_outlines_lexical"),
    ("character", "retrieve_characters_lexical"),
    ("world", "retrieve_worldbuilding_lexical"),
    ("detail", "retrieve_details_lexical"),
]


@pytest.mark.parametrize(("module_name", "function_name"), LEXICAL_CASES)
def test_lexical_retrievers_use_search_document(
    monkeypatch,
    module_name,
    function_name,
):
    module = importlib.import_module(f"novel_material.search.{module_name}")
    fake = FakeConnection()

    @contextmanager
    def fake_readonly_connection(*_args, **_kwargs):
        yield fake

    monkeypatch.setattr(module, "readonly_connection", fake_readonly_connection)

    retriever = getattr(module, function_name)
    retriever(SearchRequest(query="雨中告别", document_types=[module_name]))

    sql, params = fake.cursor_instance.executions[0]
    assert "search_document" in sql
    assert "plainto_tsquery('simple', %s)" in sql
    assert "雨中告别" in " ".join(str(param) for param in params)


STRUCTURED_CASES = [
    ("chapter", "retrieve_chapters_structured"),
    ("event", "retrieve_events_structured"),
    ("outline", "retrieve_outlines_structured"),
    ("character", "retrieve_characters_structured"),
    ("world", "retrieve_worldbuilding_structured"),
    ("detail", "retrieve_details_structured"),
]


@pytest.mark.parametrize(("module_name", "function_name"), STRUCTURED_CASES)
def test_structured_retrievers_skip_database_without_filters(
    module_name,
    function_name,
):
    module = importlib.import_module(f"novel_material.search.{module_name}")
    retriever = getattr(module, function_name)

    assert retriever(SearchRequest(query="雨中告别")) == []


@pytest.mark.parametrize(("module_name", "function_name"), STRUCTURED_CASES)
def test_structured_retrievers_apply_material_filter(
    monkeypatch,
    module_name,
    function_name,
):
    module = importlib.import_module(f"novel_material.search.{module_name}")
    fake = FakeConnection()

    @contextmanager
    def fake_readonly_connection(*_args, **_kwargs):
        yield fake

    monkeypatch.setattr(module, "readonly_connection", fake_readonly_connection)

    retriever = getattr(module, function_name)
    retriever(SearchRequest(query="雨中告别", filters={"material_id": "nm_demo"}))

    sql, params = fake.cursor_instance.executions[0]
    assert "material_id = %s" in sql
    assert "nm_demo" in params


def test_detail_semantic_retriever_uses_full_description_embedding(
    monkeypatch,
):
    module = importlib.import_module("novel_material.search.detail")
    fake = FakeConnection(rows=[{
        "material_id": "nm_demo",
        "act": 2,
        "sequence": 4,
        "beat": 1,
        "title": "揭露",
        "chapter": 35,
        "description": "关键证据出现，骗局被识破。",
        "tension": 4,
        "novel_name": "示例小说",
        "novel_genre": ["玄幻"],
        "distance": 0.1,
    }])

    @contextmanager
    def fake_readonly_connection(*_args, **_kwargs):
        yield fake

    monkeypatch.setattr(module, "readonly_connection", fake_readonly_connection)
    monkeypatch.setattr(module, "load_embedding_config", lambda: object())
    monkeypatch.setattr(module, "get_embedding", lambda *_args: [0.1, 0.2])

    results = retrieve_details_semantic(SearchRequest(query="识破骗局"))

    sql, _params = fake.cursor_instance.executions[0]
    assert "description_embedding <=> %s::vector" in sql
    assert results[0].result_id == "detail:nm_demo:2:4:1"
    assert results[0].scores["semantic"] == pytest.approx(0.9)
