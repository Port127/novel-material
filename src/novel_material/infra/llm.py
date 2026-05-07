"""LLM API 调用客户端

所有脚本必须通过这个模块调用 LLM，不要在其他文件中直接调用 API。
"""
import json
import logging
import time
from dotenv import load_dotenv
import os
from pathlib import Path
import yaml

load_dotenv()

from .progress import get_pipeline_logger
logger = get_pipeline_logger()

# 多服务商配置文件路径
PROVIDERS_CONFIG_FILE = Path(__file__).resolve().parent.parent.parent.parent / "config" / "providers.yaml"


# API 调用统计
_api_stats = {"calls": 0, "errors": 0, "tokens_total": 0}

# 单次调用详情列表（供 StageTracker 使用）
_call_details: list[dict] = []


def get_api_stats() -> dict:
    """获取当前 API 调用统计。"""
    return dict(_api_stats)


def reset_api_stats() -> None:
    """清零统计。"""
    _api_stats["calls"] = 0
    _api_stats["errors"] = 0
    _api_stats["tokens_total"] = 0


def get_call_details() -> list[dict]:
    """获取单次调用详情列表（供 StageTracker 使用）。"""
    return list(_call_details)


def clear_call_details() -> None:
    """清空单次调用详情（每个阶段开始时调用）。"""
    _call_details.clear()


def get_last_call_tokens() -> tuple[int, int]:
    """获取最近一次调用的 tokens（供实时更新使用）。"""
    if _call_details:
        last = _call_details[-1]
        return last.get("input_tokens", 0), last.get("output_tokens", 0)
    return 0, 0


def load_config():
    """从 .env 文件加载 LLM 配置。"""
    return {
        "llm": {
            "provider": os.getenv("LLM_PROVIDER", "openai"),
            "model": os.getenv("LLM_MODEL", "qwen3.6-plus"),
            "api_key": os.getenv("LLM_API_KEY", ""),
            "base_url": os.getenv("LLM_BASE_URL"),
            "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "2000")),
            "temperature": float(os.getenv("LLM_TEMPERATURE", "0.3")),
            "rate_limit_seconds": int(os.getenv("LLM_RATE_LIMIT_SECONDS", "60")),
            # 章级分析：原文输入，耗时长
            "analyze_timeout": int(os.getenv("LLM_ANALYZE_TIMEOUT", "180")),
            # 大纲生成：6000 tokens 摘要池
            "outline_timeout": int(os.getenv("LLM_OUTLINE_TIMEOUT", "300")),
            # 世界观提取：5000 tokens 摘要池
            "worldbuilding_timeout": int(os.getenv("LLM_WORLDBUILDING_TIMEOUT", "300")),
            # 人物提取：5000 tokens 摘要池，两轮调用
            "characters_timeout": int(os.getenv("LLM_CHARACTERS_TIMEOUT", "300")),
            # 其他小任务（默认兜底）
            "other_timeout": int(os.getenv("LLM_OTHER_TIMEOUT", "120")),
            # 摘要池 Token 上限（各阶段输入量）
            "outline_summary_tokens": int(os.getenv("LLM_OUTLINE_SUMMARY_TOKENS", "20000")),
            "outline_seq_summary_tokens": int(os.getenv("LLM_OUTLINE_SEQ_SUMMARY_TOKENS", "5000")),
            "worldbuilding_summary_tokens": int(os.getenv("LLM_WORLDBUILDING_SUMMARY_TOKENS", "15000")),
            "characters_summary_tokens": int(os.getenv("LLM_CHARACTERS_SUMMARY_TOKENS", "15000")),
            "chapter_batch_size": int(os.getenv("LLM_CHAPTER_BATCH_SIZE", "5")),
            # 定价配置（用于成本估算，默认 qwen 价格）
            "pricing": {
                "input_per_1k": float(os.getenv("LLM_PRICE_INPUT_1K", "0.0004")),
                "output_per_1k": float(os.getenv("LLM_PRICE_OUTPUT_1K", "0.0012")),
            },
        }
    }


def _load_providers_yaml() -> dict | None:
    """加载 providers.yaml 配置文件，返回 None 表示文件不存在。"""
    if not PROVIDERS_CONFIG_FILE.exists():
        return None
    with open(PROVIDERS_CONFIG_FILE, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def list_available_providers() -> list[str]:
    """列出所有可用的服务商名称。

    返回：
        list：服务商名称列表，若 providers.yaml 不存在则返回空列表
    """
    config = _load_providers_yaml()
    if not config:
        return []
    providers = config.get("providers", [])
    return [p.get("name", "") for p in providers if p.get("name")]


def load_provider_config(provider_name: str | None = None) -> dict:
    """加载指定服务商的配置。

    配置优先级：
    1. 指定的 provider_name
    2. providers.yaml 中的 default_provider
    3. .env 文件配置（向后兼容）

    参数：
        provider_name：服务商名称（可选，对应 providers.yaml 中的 name 字段）

    返回：
        dict：与 load_config() 格式一致的配置字典

    异常：
        ValueError：指定了 provider_name 但在 providers.yaml 中找不到
    """
    providers_yaml = _load_providers_yaml()

    # 若 providers.yaml 不存在，使用 .env 配置
    if not providers_yaml:
        return load_config()

    providers = providers_yaml.get("providers", [])

    # 确定要使用的服务商
    target_name = provider_name or providers_yaml.get("default_provider")

    # 若未指定且无 default_provider，使用 .env 配置
    if not target_name:
        return load_config()

    # 查找指定的服务商
    provider_config = None
    for p in providers:
        if p.get("name") == target_name:
            provider_config = p
            break

    if not provider_config:
        available = list_available_providers()
        raise ValueError(
            f"服务商 '{target_name}' 不存在。可用服务商: {available}"
        )

    # 从环境变量获取 api_key
    api_key_env = provider_config.get("api_key_env", "")
    api_key = os.getenv(api_key_env, "")

    if not api_key:
        logger.warning(f"服务商 '{target_name}' 的 API Key 未配置（环境变量 {api_key_env}）")

    # 从 .env 获取基础配置（公共参数）
    base_config = load_config()

    # 只覆盖服务商差异化参数
    return {
        "llm": {
            **base_config["llm"],  # 复制 .env 的所有配置
            "provider": target_name,
            "model": provider_config.get("model", base_config["llm"]["model"]),
            "api_key": api_key,
            "base_url": provider_config.get("base_url", base_config["llm"]["base_url"]),
        }
    }


def truncate_to_tokens(text: str, max_tokens: int, model: str = "qwen3.6-plus") -> str:
    """把文本截断到指定 Token 数量。"""
    try:
        import tiktoken
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")

        tokens = enc.encode(text)
        if len(tokens) <= max_tokens:
            return text
        truncated_tokens = tokens[:max_tokens]
        return enc.decode(truncated_tokens)
    except ImportError:
        char_limit = int(max_tokens * 1.5)
        return text[:char_limit]


def _retry_wait(retry_state) -> float:
    """计算重试前需要等待多久。"""
    from openai import APIStatusError

    if not hasattr(retry_state, 'outcome') or retry_state.outcome is None:
        return 2.0
    exc = retry_state.outcome.exception()
    if exc is None:
        return 2.0

    if isinstance(exc, APIStatusError) and exc.status_code == 429:
        headers = {}
        try:
            headers = dict(exc.response.headers) if exc.response else {}
        except Exception:
            pass

        for header in ("retry-after", "x-ratelimit-reset-requests", "ratelimit-reset"):
            val = headers.get(header) or headers.get(header.lower())
            if val:
                try:
                    wait = float(val)
                    logger.warning(f"速率限制（429），按服务商要求等待 {wait:.0f}s")
                    return wait
                except (TypeError, ValueError):
                    pass

        logger.warning("速率限制（429），默认等待 60s")
        return 60.0

    wait = min(2 ** retry_state.attempt_number * 2, 120)
    return wait


def call_llm(
    system_prompt: str,
    user_prompt: str,
    config: dict,
    max_tokens_override: int | None = None,
    timeout_override: int | None = None,
    context: str | None = None,
) -> dict:
    """调用 LLM API，返回 JSON 结果。

    参数：
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        config: LLM 配置字典
        max_tokens_override: 最大 tokens 覆盖
        timeout_override: 超时时间覆盖
        context: 上下文标签（如 "章节分析#批次53"），用于日志区分
    """
    from openai import OpenAI, APIStatusError, APIConnectionError, APITimeoutError, BadRequestError
    from tenacity import (
        retry,
        stop_after_attempt,
        stop_after_delay,
        retry_if_exception,
        before_sleep_log,
    )

    effective_max_tokens = max_tokens_override or config["llm"].get("max_tokens", 2048)
    total_timeout = timeout_override or config["llm"].get("other_timeout", 120)

    # 外部计时起点（用于错误日志）
    _outer_start = time.monotonic()

    def _should_retry(retry_state) -> bool:
        if not hasattr(retry_state, 'outcome') or retry_state.outcome is None:
            return False
        exc = retry_state.outcome.exception()
        if exc is None:
            return False
        if isinstance(exc, BadRequestError):
            return False
        return isinstance(exc, (APIConnectionError, APITimeoutError, APIStatusError))

    @retry(
        retry=retry_if_exception(_should_retry),
        stop=(stop_after_attempt(8) | stop_after_delay(total_timeout)),
        wait=_retry_wait,
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _call() -> dict:
        call_start = time.monotonic()
        client = OpenAI(
            api_key=config["llm"]["api_key"],
            base_url=config["llm"].get("base_url"),
            max_retries=0,
        )
        sdk_timeout = min(total_timeout * 0.8, 300)
        response = client.chat.completions.create(
            model=config["llm"]["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=config["llm"].get("temperature", 0.3),
            max_tokens=effective_max_tokens,
            timeout=sdk_timeout,
            response_format={"type": "json_object"},
        )
        elapsed = time.monotonic() - call_start

        usage = response.usage
        _api_stats["calls"] += 1

        # 记录调用详情（无论 usage 是否存在）
        detail = {
            "elapsed_sec": elapsed,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "model": config["llm"]["model"],
            "timestamp": time.strftime("%H:%M:%S"),
        }

        prefix = f"[{context}] " if context else ""
        if usage:
            _api_stats["tokens_total"] += usage.total_tokens
            detail["input_tokens"] = usage.prompt_tokens
            detail["output_tokens"] = usage.completion_tokens
            detail["total_tokens"] = usage.total_tokens

            # INFO 级别日志：每次调用详情
            logger.info(
                f"{prefix}API: {elapsed:.1f}s | "
                f"in={usage.prompt_tokens} out={usage.completion_tokens} "
                f"total={usage.total_tokens}"
            )
        else:
            # usage 为 None 时仍记录调用
            logger.warning(f"{prefix}API: {elapsed:.1f}s | usage=None（无法获取 tokens）")

        _call_details.append(detail)
        return json.loads(response.choices[0].message.content)

    try:
        return _call()
    except Exception as e:
        _api_stats["errors"] += 1
        elapsed = time.monotonic() - _outer_start
        prefix = f"[{context}] " if context else ""
        logger.error(f"{prefix}API 失败 ({elapsed:.1f}s): {type(e).__name__}: {e}")
        raise
