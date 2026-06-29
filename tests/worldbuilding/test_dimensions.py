from novel_material.worldbuilding.dimensions import resolve_worldbuilding_dimensions


def test_urban_dimension_router_marks_cultivation_not_applicable() -> None:
    result = resolve_worldbuilding_dimensions(
        meta={"genre": ["都市", "重生"]},
        navigation_dimensions=["商业环境", "校园关系"],
        chapter_signals={"locations": {"江陵大学": 3}, "organizations": {"学生会": 2}},
    )

    by_id = {item.id: item for item in result.dimensions}
    assert by_id["business_rules"].applicability == "applicable"
    assert by_id["cultivation_levels"].applicability == "not_applicable"
    assert "超自然" in by_id["cultivation_levels"].reason


def test_xianxia_dimension_router_keeps_power_and_resources() -> None:
    result = resolve_worldbuilding_dimensions(
        meta={"genre": ["仙侠"]},
        navigation_dimensions=["宗门", "修炼体系"],
        chapter_signals={"locations": {"青云宗": 5}, "organizations": {"青云宗": 5}},
    )

    by_id = {item.id: item for item in result.dimensions}
    assert by_id["cultivation_levels"].applicability == "applicable"
    assert by_id["resources"].applicability == "applicable"


def test_navigation_keywords_can_enable_power_dimension_for_urban() -> None:
    result = resolve_worldbuilding_dimensions(
        meta={"genre": ["都市"]},
        navigation_dimensions=["灵气复苏", "境界"],
        chapter_signals={},
    )

    by_id = {item.id: item for item in result.dimensions}
    assert by_id["cultivation_levels"].applicability == "applicable"
    assert "导航" in by_id["cultivation_levels"].reason
