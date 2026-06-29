from pathlib import Path

import yaml

from novel_material.pipeline.evaluation_models import (
    EvaluationNavigation,
    load_evaluation_navigation,
    normalize_evaluation_navigation,
)


def write_yaml(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True), encoding="utf-8")


def test_v3_navigation_keeps_stage_map_candidates_and_sample_coverage() -> None:
    navigation = normalize_evaluation_navigation(
        {
            "schema_version": "3.0.0",
            "novel_type": ["都市"],
            "premise": "重生者在商业与情感之间重新选择。",
            "main_thread_summary": "主角重回青春时期，通过商业机会和关系重建改变命运。",
            "stage_map": [
                {
                    "stage": "opening",
                    "chapter_ranges": [[1, 20]],
                    "central_conflict": "主角决定改变过去。",
                    "turning_points": [{"chapter": 8, "event": "第一次主动破局"}],
                }
            ],
            "core_character_candidates": [
                {
                    "name": "陈汉升",
                    "reasons": ["贯穿全书", "推动主线"],
                    "confidence": 0.96,
                }
            ],
            "worldbuilding_dimensions": ["商业环境", "校园关系"],
            "analysis_focus": ["人物选择代价", "创业节奏"],
            "sample_coverage": {
                "sampled_chapters": [1, 8, 20],
                "covered_ranges": [[1, 20]],
                "limitations": ["仅基于采样章节推断"],
            },
        }
    )

    assert isinstance(navigation, EvaluationNavigation)
    assert navigation.schema_version == "3.0.0"
    assert navigation.core_character_candidates[0].name == "陈汉升"
    assert navigation.sample_coverage.sampled_chapters == (1, 8, 20)


def test_legacy_v201_is_adapted_without_rewriting_file(tmp_path: Path) -> None:
    novel_dir = tmp_path / "nm_demo"
    evaluation_path = novel_dir / "evaluation.yaml"
    write_yaml(
        evaluation_path,
        {
            "schema_version": "2.0.1",
            "novel_type": ["都市"],
            "main_thread_summary": "旧版主线概要。",
            "total_chapters": 100,
            "core_characters_hint": ["陈汉升"],
            "stage_summaries": {
                1: "开篇",
                2: "发展",
                3: "转折",
                4: "高潮",
                5: "收束",
            },
        },
    )

    before = evaluation_path.read_text(encoding="utf-8")
    navigation = load_evaluation_navigation(novel_dir)
    after = evaluation_path.read_text(encoding="utf-8")

    assert navigation.schema_version == "3.0.0"
    assert navigation.source_schema_version == "2.0.1"
    assert navigation.core_character_candidates[0].confidence == 0.5
    assert before == after
