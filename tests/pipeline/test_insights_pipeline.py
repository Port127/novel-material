"""chapter_insights 流水线辅助函数测试。"""

from pathlib import Path

from novel_material.runtime.contracts import RunStatus
from novel_material.pipeline.insights import (
    build_insight_batch_user_prompt,
    build_insight_user_prompt,
    get_insight_file,
    split_batches,
)
from novel_material.pipeline.progress import has_complete_insights


def test_get_insight_file_uses_zero_padded_chapter(tmp_path: Path):
    assert get_insight_file(tmp_path, 7) == tmp_path / "chapter_insights" / "0007.yaml"


def test_user_prompt_includes_chapter_summary_and_schema():
    ch = {
        "chapter": 1,
        "title": "第1章 开篇",
        "summary": "主角被逐出家族，发现戒指异常。",
        "key_event": "戒指出现异常",
    }
    prompt = build_insight_user_prompt(ch, "SCHEMA")
    assert "第1章 开篇" in prompt
    assert "主角被逐出家族" in prompt
    assert "SCHEMA" in prompt


def test_split_batches_respects_batch_size():
    chapters = [{"chapter": i} for i in range(1, 46)]
    batches = split_batches(chapters, 20)
    assert [len(batch) for batch in batches] == [20, 20, 5]


def test_batch_prompt_contains_multiple_chapters():
    chapters = [
        {"chapter": 1, "title": "第1章", "summary": "主角落难。"},
        {"chapter": 2, "title": "第2章", "summary": "主角获得线索。"},
    ]
    prompt = build_insight_batch_user_prompt(chapters, "SCHEMA")
    assert "第1章" in prompt
    assert "第2章" in prompt
    assert "JSON 数组" in prompt


def test_has_complete_insights_rejects_invalid_yaml_files(tmp_path: Path):
    novel_dir = tmp_path
    (novel_dir / "chapter_index.yaml").write_text(
        "- chapter: 1\n  title: A\n- chapter: 2\n  title: B\n",
        encoding="utf-8",
    )
    insights_dir = novel_dir / "chapter_insights"
    insights_dir.mkdir()
    (insights_dir / "0001.yaml").write_text("chapter: 1\n", encoding="utf-8")
    assert has_complete_insights(novel_dir) is False

    (insights_dir / "0002.yaml").write_text("chapter: 2\n", encoding="utf-8")
    assert has_complete_insights(novel_dir) is False


def test_missing_insight_is_failed_without_placeholder(tmp_path: Path, monkeypatch):
    material_id = "nm_demo"
    novel_dir = tmp_path / material_id
    novel_dir.mkdir()
    (novel_dir / "chapters.yaml").write_text(
        "- chapter: 1\n  title: 第一章\n  summary: 开篇\n",
        encoding="utf-8",
    )

    monkeypatch.setattr("novel_material.pipeline.insights.NOVELS_DIR", tmp_path)
    monkeypatch.setattr(
        "novel_material.pipeline.insights.resolve_profile_names",
        lambda *_args, **_kwargs: ["base"],
    )
    monkeypatch.setattr("novel_material.pipeline.insights.load_profiles", lambda _names: [])
    monkeypatch.setattr("novel_material.pipeline.insights.merge_profiles", lambda _profiles: object())
    monkeypatch.setattr("novel_material.pipeline.insights.build_insight_system_prompt", lambda _profile: "system")
    monkeypatch.setattr("novel_material.pipeline.insights.build_insight_schema_text", lambda _profile: "schema")
    monkeypatch.setattr(
        "novel_material.pipeline.insights.load_config",
        lambda _provider: {"llm": {"insight_batch_size": 20}},
    )
    monkeypatch.setattr(
        "novel_material.pipeline.insights.call_llm",
        lambda **_kwargs: {"items": []},
    )
    monkeypatch.setattr("novel_material.pipeline.insights.validate_insight", lambda *_args: [])

    result = __import__(
        "novel_material.pipeline.insights",
        fromlist=["generate_chapter_insights"],
    ).generate_chapter_insights(material_id)

    assert result.status is RunStatus.FAILED
    assert result.counts.failed == 1
    assert result.counts.remaining == 0
    assert not (novel_dir / "chapter_insights" / "0001.yaml").exists()
