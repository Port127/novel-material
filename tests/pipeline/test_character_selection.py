"""自适应人物小传目标选择测试。"""

from novel_material.pipeline.characters_selection import (
    CharacterSignals,
    build_character_signals,
    select_biography_targets,
)
from novel_material.pipeline.evaluation_models import (
    CoreCharacterCandidate,
    EvaluationNavigation,
)


def test_selects_between_five_and_twelve_when_enough_candidates():
    appearance = {f"角色{i}": 100 - i for i in range(1, 20)}
    navigation = EvaluationNavigation(
        core_character_candidates=(
            CoreCharacterCandidate(
                name="角色15",
                reasons=("导航候选",),
                confidence=0.99,
            ),
        )
    )
    signals = CharacterSignals(
        appearance_counts=appearance,
        chapter_span={name: (1, 100) for name in appearance},
        key_event_counts={name: 3 for name in appearance},
        relationship_degree={name: 1 for name in appearance},
        navigation=navigation,
    )

    result = select_biography_targets(signals)

    assert 5 <= len(result.targets) <= 12
    assert "角色15" in [item.name for item in result.targets]
    assert result.selection_reason == "enough_candidates"


def test_selects_all_qualified_when_less_than_five():
    signals = CharacterSignals(
        appearance_counts={"甲": 20, "乙": 12, "丙": 6},
        chapter_span={"甲": (1, 20), "乙": (3, 18), "丙": (8, 14)},
        key_event_counts={"甲": 2, "乙": 1, "丙": 1},
        relationship_degree={"甲": 1, "乙": 1, "丙": 0},
        navigation=EvaluationNavigation(),
    )

    result = select_biography_targets(signals)

    assert [item.name for item in result.targets] == ["甲", "乙", "丙"]
    assert result.selection_reason == "fewer_than_minimum"


def test_build_character_signals_derives_span_events_and_relationships():
    chapters = [
        {
            "chapter": 1,
            "characters_appear": ["甲", "乙"],
            "key_event": "甲救下乙",
        },
        {
            "chapter": 3,
            "characters_appear": ["甲", "丙"],
            "key_event": "丙背叛甲",
        },
        {
            "chapter": 4,
            "characters_appear": ["甲"],
            "key_event": "甲独自离开",
        },
    ]

    signals = build_character_signals(chapters, EvaluationNavigation())

    assert signals.appearance_counts == {"甲": 3, "乙": 1, "丙": 1}
    assert signals.chapter_span["甲"] == (1, 4)
    assert signals.chapter_span["乙"] == (1, 1)
    assert signals.key_event_counts == {"甲": 3, "乙": 1, "丙": 1}
    assert signals.relationship_degree == {"甲": 2, "乙": 1, "丙": 1}
