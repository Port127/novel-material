from contextlib import contextmanager

from novel_material.search.context import (
    enrich_chapter_result,
    enrich_results_from_storage,
)
from novel_material.search.models import SearchResult, SearchTrace
from tests.search.fakes import FakeConnection


def result(document_type: str = "chapter", chapter: int | None = 2) -> SearchResult:
    return SearchResult(
        result_id=f"{document_type}:nm_demo:{chapter}",
        document_type=document_type,
        material_id="nm_demo",
        chapter=chapter,
    )


def test_enrich_chapter_result_adds_neighbors_and_line_range(tmp_path):
    novel_dir = tmp_path / "nm_demo"
    novel_dir.mkdir()
    (novel_dir / "chapter_index.yaml").write_text(
        "- chapter: 2\n  title: 第二章\n  start_line: 21\n  end_line: 40\n",
        encoding="utf-8",
    )

    enriched = enrich_chapter_result(
        result(),
        summaries={1: "前章", 2: "本章", 3: "后章"},
        novels_dir=tmp_path,
    )

    assert enriched.neighbors.previous_summary == "前章"
    assert enriched.neighbors.next_summary == "后章"
    assert enriched.source.chapter == 2
    assert enriched.source.start_line == 21
    assert enriched.source.end_line == 40


def test_enrich_chapter_result_allows_missing_boundary_neighbor(tmp_path):
    novel_dir = tmp_path / "nm_demo"
    novel_dir.mkdir()
    (novel_dir / "chapter_index.yaml").write_text(
        "- chapter: 1\n  start_line: 1\n  end_line: 20\n",
        encoding="utf-8",
    )

    enriched = enrich_chapter_result(
        result(chapter=1),
        summaries={1: "本章", 2: "后章"},
        novels_dir=tmp_path,
    )

    assert enriched.neighbors.previous_summary is None
    assert enriched.neighbors.next_summary == "后章"


def test_enrich_chapter_result_ignores_types_without_chapter_context(tmp_path):
    original = result(document_type="world")

    enriched = enrich_chapter_result(
        original,
        summaries={1: "前章", 3: "后章"},
        novels_dir=tmp_path,
    )

    assert enriched == original
    assert enriched is not original


def test_enrich_results_loads_neighbor_summaries_in_one_query(monkeypatch, tmp_path):
    module = __import__("novel_material.search.context", fromlist=["context"])
    fake = FakeConnection(rows=[
        {"material_id": "nm_demo", "chapter": 1, "summary": "前章"},
        {"material_id": "nm_demo", "chapter": 2, "summary": "本章"},
        {"material_id": "nm_demo", "chapter": 3, "summary": "后章"},
    ])
    novel_dir = tmp_path / "nm_demo"
    novel_dir.mkdir()
    (novel_dir / "chapter_index.yaml").write_text(
        "- chapter: 2\n  start_line: 21\n  end_line: 40\n",
        encoding="utf-8",
    )

    @contextmanager
    def fake_readonly_connection(*_args, **_kwargs):
        yield fake

    monkeypatch.setattr(module, "readonly_connection", fake_readonly_connection)

    enriched = enrich_results_from_storage(
        [result()],
        trace=SearchTrace(),
        novels_dir=tmp_path,
    )

    assert len(fake.cursor_instance.executions) == 1
    assert enriched[0].neighbors.previous_summary == "前章"
    assert enriched[0].neighbors.next_summary == "后章"
