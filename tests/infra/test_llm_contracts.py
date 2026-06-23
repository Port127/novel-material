import pytest

from novel_material.infra.llm_contracts import (
    LLMResponseContractError,
    require_integer,
    require_mapping,
    require_mapping_list,
    require_number,
    require_string,
    require_string_list,
)


def test_require_mapping_reports_field_path_and_actual_type():
    with pytest.raises(LLMResponseContractError, match=r"worldbuilding\.power_system.*对象.*list"):
        require_mapping([], "worldbuilding.power_system")


def test_require_mapping_list_rejects_non_mapping_item():
    with pytest.raises(LLMResponseContractError, match=r"characters\[1\].*对象"):
        require_mapping_list([{"name": "甲"}, "乙"], "characters")


@pytest.mark.parametrize("value", [True, False])
def test_numeric_contracts_reject_bool(value):
    with pytest.raises(LLMResponseContractError):
        require_number(value, "score")
    with pytest.raises(LLMResponseContractError):
        require_integer(value, "chapter")


def test_string_and_string_list_return_valid_values():
    assert require_string("文本", "summary") == "文本"
    assert require_string_list(["甲", "乙"], "characters") == ["甲", "乙"]
