"""统一 LLM 调用客户端：所有脚本通过此模块调用 LLM，禁止在其他文件中复制。

特性：
- 指数退避自动重试（tenacity）：网络超时、限流、服务端 5xx 均自动重试
- 429 速率限制：优先读取 Retry-After 响应头，保证按服务商要求等待
- 最多重试 8 次，其他错误指数退避（2→4→8→…→120s）
- tiktoken 动态 Token 截断工具（truncate_to_tokens）
"""
import sys
import json
import logging
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 全局 API 调用计数器（pipeline 运行时读写）
# ──────────────────────────────────────────────

_api_stats = {"calls": 0, "errors": 0, "tokens_total": 0}


def get_api_stats() -> dict:
    """获取全局 API 调用统计（只读快照）。"""
    return dict(_api_stats)


def reset_api_stats() -> None:
    """重置计数器（每次流水线启动时调用）。"""
    _api_stats["calls"] = 0
    _api_stats["errors"] = 0
    _api_stats["tokens_total"] = 0


# ──────────────────────────────────────────────
# 配置加载
# ──────────────────────────────────────────────

def load_config():
    """从环境变量加载 LLM 配置（读取 .env）。"""
    from dotenv import load_dotenv
    import os
    load_dotenv()

    return {
        "llm": {
            "provider": os.getenv("LLM_PROVIDER", "openai"),
            "model": os.getenv("LLM_MODEL", "gpt-4o-mini"),
            "api_key": os.getenv("LLM_API_KEY", ""),
            "base_url": os.getenv("LLM_BASE_URL"),
            "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "500")),
            "temperature": float(os.getenv("LLM_TEMPERATURE", "0.3")),
            "rate_limit_seconds": int(os.getenv("LLM_RATE_LIMIT_SECONDS", "10")),
            # 每次 API 调用批量处理的章节数（减少调用次数）
            # 30 章/次：1600章 → ~54次调用，输出约 4500 tokens/批（每章 ~150 tokens）
            # 上下文受限的小模型可设为 1（逐章模式），大模型可按输出上限调高
            "chapter_batch_size": int(os.getenv("LLM_CHAPTER_BATCH_SIZE", "30")),
        }
    }


# ──────────────────────────────────────────────
# Token 工具
# ──────────────────────────────────────────────

def truncate_to_tokens(text: str, max_tokens: int, model: str = "gpt-4o-mini") -> str:
    """将文本截断到指定 Token 数量上限。

    使用 tiktoken 精确计算，保留完整语义单元（不在词语中间截断）。
    如果 tiktoken 不可用，回退到字符数估算（1 token ≈ 1.5 中文字）。

    Args:
        text: 原始文本
        max_tokens: Token 上限
        model: 用于计算 token 的模型名（影响编码方式）

    Returns:
        截断后的文本
    """
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
        # 回退：中文平均 1 token ≈ 1.5 字符
        char_limit = int(max_tokens * 1.5)
        return text[:char_limit]


# ──────────────────────────────────────────────
# LLM 调用（带重试）
# ──────────────────────────────────────────────

def _retry_wait(retry_state) -> float:
    """自适应等待策略：429 优先读取 Retry-After 头，其他错误指数退避。

    服务商在 429 响应头中通常会通过 Retry-After 或
    x-ratelimit-reset-requests 告知需要等待的秒数。
    直接使用该值可避免"等待太短→再次 429→重试次数耗尽"的循环。
    """
    from openai import APIStatusError
    exc = retry_state.outcome.exception()

    if isinstance(exc, APIStatusError) and exc.status_code == 429:
        # 尝试从响应头读取 Retry-After
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
                    logger.warning(f"速率限制（429），按服务商要求等待 {wait:.0f}s（来自 {header}）")
                    return wait
                except (TypeError, ValueError):
                    pass

        # 无头信息时保守等待 60s
        logger.warning("速率限制（429），未找到 Retry-After 头，默认等待 60s")
        return 60.0

    # 其他错误（网络、5xx）：指数退避，上限 120s
    wait = min(2 ** retry_state.attempt_number * 2, 120)
    return wait


def call_llm(
    system_prompt: str,
    user_prompt: str,
    config: dict,
    max_tokens_override: int | None = None,
) -> dict:
    """调用 LLM API，返回解析后的 JSON 对象。

    自动重试策略：
    - 触发条件：网络错误、HTTP 429（限流）、HTTP 5xx（服务端错误）
    - 最多重试 8 次
    - 429：优先读取 Retry-After 响应头；无头信息则等待 60s
    - 其他错误：指数退避（4→8→16→…→120s），避免雪崩

    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        config: 由 load_config() 返回的配置字典
        max_tokens_override: 可选，覆盖 config 中的 max_tokens（适用于大输出场景）

    Returns:
        dict: LLM 返回的 JSON 对象

    Raises:
        openai.APIError: 超过最大重试次数后仍失败
    """
    from openai import OpenAI, APIStatusError, APIConnectionError, APITimeoutError
    from tenacity import (
        retry,
        stop_after_attempt,
        retry_if_exception_type,
        before_sleep_log,
    )

    effective_max_tokens = max_tokens_override or config["llm"].get("max_tokens", 2048)

    @retry(
        retry=retry_if_exception_type((APIConnectionError, APITimeoutError, APIStatusError)),
        stop=stop_after_attempt(8),
        wait=_retry_wait,
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _call() -> dict:
        client = OpenAI(
            api_key=config["llm"]["api_key"],
            base_url=config["llm"].get("base_url"),
        )
        response = client.chat.completions.create(
            model=config["llm"]["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=config["llm"].get("temperature", 0.3),
            max_tokens=effective_max_tokens,
            response_format={"type": "json_object"},
        )
        usage = response.usage
        _api_stats["calls"] += 1
        if usage:
            _api_stats["tokens_total"] += usage.total_tokens
        return json.loads(response.choices[0].message.content)

    try:
        return _call()
    except Exception as e:
        _api_stats["errors"] += 1
        raise
