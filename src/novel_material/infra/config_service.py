"""应用配置服务：统一 settings.yaml 和 providers.yaml 加载。

此模块提供单一配置入口 load_app_config()，
合并 settings.yaml（通用配置）和 providers.yaml（LLM服务商配置）。

向后兼容：
- get_settings() 仍可使用，返回通用配置
- load_config() 返回 LLM 配置（调用 load_app_config 内部逻辑）
"""
from pathlib import Path
from novel_material.infra.config import get_settings, CONFIG_DIR
from novel_material.infra.yaml_io import load_yaml


def load_app_config(provider: str | None = None) -> dict:
    """加载应用配置：合并 settings.yaml + providers.yaml。

    配置优先级：
    1. 指定的 provider（providers.yaml 中的服务商）
    2. providers.yaml 中的 default_provider
    3. settings.yaml（向后兼容，无 providers.yaml 时）

    参数：
        provider：服务商名称（可选，对应 providers.yaml 中的 name 字段）

    返回：
        dict：完整配置字典，结构为：
        {
            "settings": {...},  # settings.yaml 内容
            "llm": {...}        # LLM 配置（已合并 provider）
        }

    异常：
        ValueError：指定了 provider 但在 providers.yaml 中找不到
    """
    s = get_settings()

    providers_yaml_path = CONFIG_DIR / "providers.yaml"
    providers_yaml = None
    if providers_yaml_path.exists():
        providers_yaml = load_yaml(providers_yaml_path)

    llm_config = _build_llm_config(s, providers_yaml, provider)

    return {
        "settings": s,
        "llm": llm_config,
    }


def _build_llm_config(settings: dict, providers_yaml: dict | None, provider: str | None) -> dict:
    """构建 LLM 配置。

    参数：
        settings：settings.yaml 配置
        providers_yaml：providers.yaml 配置（可选）
        provider：指定服务商名称（可选）

    返回：
        dict：LLM 配置字典
    """
    import os

    base_config = {
        "provider": settings.get("LLM_PROVIDER", "openai"),
        "model": settings.get("LLM_MODEL", "qwen3.6-plus"),
        "api_key": settings.get("LLM_API_KEY", ""),
        "base_url": settings.get("LLM_BASE_URL"),
        "max_tokens": int(settings.get("LLM_MAX_TOKENS", 8000)),
        "evaluation_max_tokens": int(settings.get("LLM_EVALUATION_MAX_TOKENS", 3000)),
        "temperature": float(settings.get("LLM_TEMPERATURE", 0.3)),
        "rate_limit_seconds": int(settings.get("LLM_RATE_LIMIT_SECONDS", 60)),
        "analyze_timeout": int(settings.get("LLM_ANALYZE_TIMEOUT", 180)),
        "outline_timeout": int(settings.get("LLM_OUTLINE_TIMEOUT", 300)),
        "worldbuilding_timeout": int(settings.get("LLM_WORLDBUILDING_TIMEOUT", 300)),
        "characters_timeout": int(settings.get("LLM_CHARACTERS_TIMEOUT", 300)),
        "other_timeout": int(settings.get("LLM_OTHER_TIMEOUT", 120)),
        "outline_summary_tokens": int(settings.get("LLM_OUTLINE_SUMMARY_TOKENS", 20000)),
        "outline_seq_summary_tokens": int(settings.get("LLM_OUTLINE_SEQ_SUMMARY_TOKENS", 5000)),
        "worldbuilding_summary_tokens": int(settings.get("LLM_WORLDBUILDING_SUMMARY_TOKENS", 15000)),
        "characters_summary_tokens": int(settings.get("LLM_CHAPTERS_SUMMARY_TOKENS", 15000)),
        "chapter_batch_size": int(settings.get("LLM_CHAPTER_BATCH_SIZE", 5)),
        "insight_batch_size": int(settings.get("LLM_INSIGHT_BATCH_SIZE", 20)),
        "pricing": {
            "input_per_1k": float(settings.get("LLM_PRICE_INPUT_1K", 0.0004)),
            "output_per_1k": float(settings.get("LLM_PRICE_OUTPUT_1K", 0.0012)),
        },
        "dynamic_prompt_enabled": settings.get("LLM_DYNAMIC_PROMPT_ENABLED", True),
        "diversity_reminder_interval": int(settings.get("LLM_DIVERSITY_REMINDER_INTERVAL", 10)),
        "late_chapter_threshold": float(settings.get("LLM_LATE_CHAPTER_THRESHOLD", 0.6)),
        "late_temperature_boost": float(settings.get("LLM_LATE_TEMPERATURE_BOOST", 0.15)),
        "temperature_max": float(settings.get("LLM_TEMPERATURE_MAX", 0.6)),
        "dynamic_temperature_enabled": settings.get("LLM_DYNAMIC_TEMPERATURE_ENABLED", True),
        "similarity_window": int(settings.get("LLM_SIMILARITY_WINDOW", 10)),
        "similarity_threshold": float(settings.get("LLM_SIMILARITY_WARNING_THRESHOLD", 0.7)),
    }

    if not providers_yaml:
        return base_config

    providers = providers_yaml.get("providers", [])
    target_name = provider or providers_yaml.get("default_provider")

    if not target_name:
        return base_config

    provider_config = None
    for p in providers:
        if p.get("name") == target_name:
            provider_config = p
            break

    if not provider_config:
        available = [p.get("name", "") for p in providers if p.get("name")]
        raise ValueError(f"服务商 '{target_name}' 不存在。可用服务商: {available}")

    api_key_env = provider_config.get("api_key_env", "")
    api_key = os.getenv(api_key_env, "")

    return {
        **base_config,
        "provider": target_name,
        "model": provider_config.get("model", base_config["model"]),
        "api_key": api_key,
        "base_url": provider_config.get("base_url", base_config["base_url"]),
        "thinking_format": provider_config.get("thinking_format", "openai"),
    }


__all__ = ["load_app_config"]
