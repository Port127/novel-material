from novel_material.infra.config_service import _build_llm_config


def test_build_llm_config_exposes_evaluation_max_tokens() -> None:
    config = _build_llm_config(
        {"LLM_EVALUATION_MAX_TOKENS": 4200},
        providers_yaml=None,
        provider=None,
    )

    assert config["evaluation_max_tokens"] == 4200


def test_build_llm_config_defaults_evaluation_max_tokens_to_3000() -> None:
    config = _build_llm_config({}, providers_yaml=None, provider=None)

    assert config["evaluation_max_tokens"] == 3000
