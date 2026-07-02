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


def test_build_llm_config_exposes_quality_budget_keys() -> None:
    config = _build_llm_config(
        {
            "LLM_CONTEXT_WINDOW_TOKENS": 1000000,
            "LLM_WORLDBUILDING_MAX_TOKENS": 64000,
            "LLM_CHARACTERS_MAX_TOKENS": 64000,
            "LLM_PROFILE_MAX_TOKENS": 64000,
            "LLM_INSIGHTS_MAX_TOKENS": 32000,
            "LLM_CHARACTERS_SUMMARY_TOKENS": 120000,
            "LLM_PROFILE_CONTEXT_TOKENS": 120000,
            "LLM_LENGTH_RETRY_MULTIPLIER": 2,
            "LLM_LENGTH_RETRY_MAX_TOKENS": 128000,
        },
        providers_yaml=None,
        provider=None,
    )

    assert config["context_window_tokens"] == 1000000
    assert config["worldbuilding_max_tokens"] == 64000
    assert config["characters_max_tokens"] == 64000
    assert config["profile_max_tokens"] == 64000
    assert config["insights_max_tokens"] == 32000
    assert config["characters_summary_tokens"] == 120000
    assert config["profile_context_tokens"] == 120000
    assert config["length_retry_multiplier"] == 2
    assert config["length_retry_max_tokens"] == 128000


def test_build_llm_config_exposes_resilient_enrichment_keys() -> None:
    config = _build_llm_config(
        {
            "LLM_SDK_TIMEOUT_CAP": 1200,
            "LLM_PROFILE_TIMEOUT": 1800,
            "LLM_INSIGHTS_TIMEOUT": 1200,
            "LLM_CORE_CHARACTER_BATCH_SIZE": 2,
            "LLM_SUPPORTING_CHARACTER_BATCH_SIZE": 12,
            "LLM_MINOR_CHARACTER_BATCH_SIZE": 20,
            "LLM_CHARACTER_REPAIR_MAX_ATTEMPTS": 1,
        },
        providers_yaml=None,
        provider=None,
    )

    assert config["sdk_timeout_cap"] == 1200
    assert config["profile_timeout"] == 1800
    assert config["insights_timeout"] == 1200
    assert config["core_character_batch_size"] == 2
    assert config["supporting_character_batch_size"] == 12
    assert config["minor_character_batch_size"] == 20
    assert config["character_repair_max_attempts"] == 1
