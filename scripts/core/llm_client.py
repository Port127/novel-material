"""LLM API 调用客户端

所有脚本必须通过这个模块调用 LLM，不要在其他文件中直接调用 API。

核心功能：
1. 自动重试：网络超时、速率限制、服务器错误都会自动重试
2. 总超时控制：限制从请求开始到失败的总时间（包括所有重试）
3. 智能等待：遇到速率限制时，按服务商要求等待，避免被反复拒绝
4. Token 截断：把过长的文本截断到指定 Token 数量
"""
import sys
import json
import logging
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 使用统一的日志记录器
from scripts.utils.progress_tracker import get_pipeline_logger
logger = get_pipeline_logger()


# ============================================================
# API 调用统计（用于监控运行状态）
# ============================================================

_api_stats = {"calls": 0, "errors": 0, "tokens_total": 0}


def get_api_stats() -> dict:
    """获取当前 API 调用统计（调用次数、错误次数、总 Token 数）。"""
    return dict(_api_stats)


def reset_api_stats() -> None:
    """清零统计（每次流水线开始时调用）。"""
    _api_stats["calls"] = 0
    _api_stats["errors"] = 0
    _api_stats["tokens_total"] = 0


# ============================================================
# 配置加载
# ============================================================

def load_config():
    """从 .env 文件加载 LLM 配置。"""
    from dotenv import load_dotenv
    import os
    load_dotenv()

    return {
        "llm": {
            "provider": os.getenv("LLM_PROVIDER", "openai"),
            "model": os.getenv("LLM_MODEL", "qwen3.6-plus"),
            "api_key": os.getenv("LLM_API_KEY", ""),
            "base_url": os.getenv("LLM_BASE_URL"),
            "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "2000")),
            "temperature": float(os.getenv("LLM_TEMPERATURE", "0.3")),
            # 批次间隔时间（秒）
            "rate_limit_seconds": int(os.getenv("LLM_RATE_LIMIT_SECONDS", "60")),
            # 总超时时间（秒）- 包括所有重试等待
            "timeout_seconds": int(os.getenv("LLM_TIMEOUT_SECONDS", "120")),
            # 章级分析专用：批量分析的总超时
            "chapter_batch_timeout_seconds": int(
                os.getenv("LLM_CHAPTER_BATCH_TIMEOUT_SECONDS", "180")
            ),
            # 每批处理章节数
            "chapter_batch_size": int(os.getenv("LLM_CHAPTER_BATCH_SIZE", "5")),
        }
    }


# ============================================================
# Token 截断工具
# ============================================================

def truncate_to_tokens(text: str, max_tokens: int, model: str = "qwen3.6-plus") -> str:
    """把文本截断到指定 Token 数量。

    使用 tiktoken 精确计算 Token 数，保证截断后的文本不超过限制。
    如果 tiktoken 不可用，则用字符数估算（1 Token ≈ 1.5 中文字）。

    参数：
        text: 原始文本
        max_tokens: Token 上限
        model: 模型名称（影响 Token 计算方式）

    返回：
        截断后的文本
    """
    try:
        import tiktoken
        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            # 未知模型，使用通用编码
            enc = tiktoken.get_encoding("cl100k_base")

        tokens = enc.encode(text)
        if len(tokens) <= max_tokens:
            return text
        truncated_tokens = tokens[:max_tokens]
        return enc.decode(truncated_tokens)
    except ImportError:
        # 没有 tiktoken，用字符数估算
        char_limit = int(max_tokens * 1.5)
        return text[:char_limit]


# ============================================================
# 重试等待策略
# ============================================================

def _retry_wait(retry_state) -> float:
    """计算重试前需要等待多久。

    策略：
    - 遇到速率限制（HTTP 429）：按服务商响应头的要求等待
    - 其他错误：指数退避（2→4→8→...→最多 120 秒）

    这样可以避免"等待太短→再次被拒绝→重试次数耗尽"的问题。
    """
    from openai import APIStatusError

    # 检查是否有异常信息
    if not hasattr(retry_state, 'outcome') or retry_state.outcome is None:
        return 2.0
    exc = retry_state.outcome.exception()
    if exc is None:
        return 2.0

    # 处理速率限制（HTTP 429）
    if isinstance(exc, APIStatusError) and exc.status_code == 429:
        # 尝试从响应头读取服务商要求的等待时间
        headers = {}
        try:
            headers = dict(exc.response.headers) if exc.response else {}
        except Exception:
            pass

        # 常见的等待时间响应头
        for header in ("retry-after", "x-ratelimit-reset-requests", "ratelimit-reset"):
            val = headers.get(header) or headers.get(header.lower())
            if val:
                try:
                    wait = float(val)
                    logger.warning(f"速率限制（429），按服务商要求等待 {wait:.0f}s")
                    return wait
                except (TypeError, ValueError):
                    pass

        # 没有响应头信息，默认等待 60 秒
        logger.warning("速率限制（429），默认等待 60s")
        return 60.0

    # 其他错误：指数退避，上限 120 秒
    # 第 1 次重试等 4 秒，第 2 次等 8 秒，第 3 次等 16 秒...
    wait = min(2 ** retry_state.attempt_number * 2, 120)
    return wait


# ============================================================
# 主函数：调用 LLM
# ============================================================

def call_llm(
    system_prompt: str,
    user_prompt: str,
    config: dict,
    max_tokens_override: int | None = None,
    timeout_override: int | None = None,
) -> dict:
    """调用 LLM API，返回 JSON 结果。

    重试机制：
    - 会自动重试的错误：网络超时、速率限制（429）、服务器错误（5xx）
    - 不重试的错误：参数错误（如 prompt 太长）
    - 最多重试 8 次
    - 总超时限制：超过指定秒数（包括所有重试等待）后放弃

    参数：
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        config: 配置字典（由 load_config() 返回）
        max_tokens_override: 输出 Token 上限（可选，覆盖配置）
        timeout_override: 总超时秒数（可选，覆盖配置）

    返回：
        dict: LLM 返回的 JSON 对象

    可能抛出的异常：
        - APITimeoutError: 超时
        - APIStatusError: API 返回错误（如速率限制）
        - BadRequestError: 参数错误（不重试）
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
    # 总超时：从请求开始到放弃的总时间（包括所有重试等待）
    total_timeout = timeout_override or config["llm"].get("timeout_seconds", 6000)

    def _should_retry(retry_state) -> bool:
        """判断是否应该重试。"""
        # 检查异常信息
        if not hasattr(retry_state, 'outcome') or retry_state.outcome is None:
            return False
        exc = retry_state.outcome.exception()
        if exc is None:
            return False
        # 参数错误不重试（如 prompt 太长）
        if isinstance(exc, BadRequestError):
            return False
        # 网络错误、超时、速率限制、服务器错误：重试
        return isinstance(exc, (APIConnectionError, APITimeoutError, APIStatusError))

    @retry(
        retry=retry_if_exception(_should_retry),
        # 两个停止条件：重试 8 次或超过总超时
        stop=(stop_after_attempt(8) | stop_after_delay(total_timeout)),
        wait=_retry_wait,
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def _call() -> dict:
        # 创建客户端，禁用 SDK 内置重试（让 tenacity 控制）
        client = OpenAI(
            api_key=config["llm"]["api_key"],
            base_url=config["llm"].get("base_url"),
            max_retries=0,
        )
        # SDK 单次调用的超时设为总超时的 80%，留时间给重试
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
        # 记录统计
        usage = response.usage
        _api_stats["calls"] += 1
        if usage:
            _api_stats["tokens_total"] += usage.total_tokens
        return json.loads(response.choices[0].message.content)

    try:
        return _call()
    except Exception:
        _api_stats["errors"] += 1
        raise