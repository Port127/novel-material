from novel_material.pipeline.evaluate import (
    build_sample_coverage,
    normalize_evaluation_response,
    run_evaluation,
)
from novel_material.infra.yaml_io import load_yaml, save_yaml


def test_normalize_evaluation_response_requires_v3_navigation_fields() -> None:
    result = normalize_evaluation_response(
        {
            "novel_type": ["都市"],
            "premise": "重生者重新选择人生。",
            "main_thread_summary": "主角围绕事业与关系重建展开主线。",
            "stage_map": [
                {
                    "stage": "opening",
                    "chapter_ranges": [[1, 10]],
                    "central_conflict": "主角重新面对旧关系。",
                    "turning_points": [{"chapter": 3, "event": "首次主动改变"}],
                }
            ],
            "core_character_candidates": [
                {"name": "陈汉升", "reasons": ["贯穿主线"], "confidence": 0.9}
            ],
            "worldbuilding_dimensions": ["校园", "商业"],
            "analysis_focus": ["人物选择", "创业节奏"],
        }
    )

    assert result["schema_version"] == "3.0.0"
    assert result["core_character_candidates"][0]["confidence"] == 0.9


def test_build_sample_coverage_records_sampled_chapters_and_limitations() -> None:
    batches = {
        1: [{"chapter": 1}, {"chapter": 10}],
        2: [{"chapter": 30}],
    }
    coverage = build_sample_coverage(batches, total_chapters=100)

    assert coverage["sampled_chapters"] == [1, 10, 30]
    assert coverage["covered_ranges"] == [[1, 30]]
    assert coverage["limitations"]


def test_run_evaluation_writes_v3_navigation(tmp_path, monkeypatch) -> None:
    material_id = "nm_demo"
    novel_dir = tmp_path / material_id
    novel_dir.mkdir()
    save_yaml(
        novel_dir / "meta.yaml",
        {"material_id": material_id, "name": "测试小说", "status": "clean"},
    )
    save_yaml(
        novel_dir / "chapter_index.yaml",
        [
            {
                "chapter": chapter,
                "title": f"第{chapter}章",
                "start_line": chapter,
                "end_line": chapter,
            }
            for chapter in range(1, 16)
        ],
    )
    (novel_dir / "source.txt").write_text(
        "\n".join(f"第{chapter}章内容" for chapter in range(1, 16)),
        encoding="utf-8",
    )

    max_token_overrides = []

    def fake_call_llm(*_args, **kwargs):
        max_token_overrides.append(kwargs.get("max_tokens_override"))
        return {
            "novel_type": ["都市"],
            "premise": "重生者重新选择人生。",
            "main_thread_summary": "主角围绕事业与关系重建展开主线。",
            "stage_map": [
                {
                    "stage": "opening",
                    "chapter_ranges": [[1, 3]],
                    "central_conflict": "主角重新面对旧关系。",
                    "turning_points": [{"chapter": 1, "event": "首次主动改变"}],
                }
            ],
            "core_character_candidates": [
                {"name": "陈汉升", "reasons": ["贯穿主线"], "confidence": 0.9}
            ],
            "worldbuilding_dimensions": ["校园", "商业"],
            "analysis_focus": ["人物选择", "创业节奏"],
        }

    monkeypatch.setattr("novel_material.pipeline.evaluate.NOVELS_DIR", tmp_path)
    monkeypatch.setattr("novel_material.infra.config.NOVELS_DIR", tmp_path)
    monkeypatch.setattr(
        "novel_material.pipeline.evaluate.load_config",
        lambda _provider=None: {
            "llm": {
                "model": "fake-model",
                "other_timeout": 1,
                "rate_limit_seconds": 0,
            }
        },
    )
    monkeypatch.setattr("novel_material.pipeline.evaluate.call_llm", fake_call_llm)
    monkeypatch.setattr("novel_material.pipeline.evaluate.time.sleep", lambda _seconds: None)

    assert run_evaluation(material_id, silent=True) is True

    evaluation = load_yaml(novel_dir / "evaluation.yaml")
    assert evaluation["schema_version"] == "3.0.0"
    assert evaluation["sample_coverage"]["sampled_chapters"] == list(range(1, 16))
    assert evaluation["core_character_candidates"][0]["name"] == "陈汉升"
    assert max_token_overrides == [3000] * 5
