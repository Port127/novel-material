"""LLM API 调用客户端

所有脚本必须通过这个模块调用 LLM，不要在其他文件中直接调用 API。
"""
import json
import logging
import time
from dotenv import load_dotenv
import os

load_dotenv()

from .progress import get_pipeline_logger
logger = get_pipeline_logger()


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
) -> dict:
    """调用 LLM API，返回 JSON 结果。"""
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

        if usage:
            _api_stats["tokens_total"] += usage.total_tokens
            detail["input_tokens"] = usage.prompt_tokens
            detail["output_tokens"] = usage.completion_tokens
            detail["total_tokens"] = usage.total_tokens

            # INFO 级别日志：每次调用详情
            logger.info(
                f"API: {elapsed:.1f}s | "
                f"in={usage.prompt_tokens} out={usage.completion_tokens} "
                f"total={usage.total_tokens}"
            )
        else:
            # usage 为 None 时仍记录调用
            logger.warning(f"API: {elapsed:.1f}s | usage=None（无法获取 tokens）")

        _call_details.append(detail)
        return json.loads(response.choices[0].message.content)

    try:
        return _call()
    except Exception as e:
        _api_stats["errors"] += 1
        elapsed = time.monotonic() - _outer_start
        logger.error(f"API 失败 ({elapsed:.1f}s): {type(e).__name__}: {e}")
        raise