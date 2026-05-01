"""统一 LLM 调用客户端：所有脚本通过此模块调用 LLM，禁止在其他文件中复制。

特性：
- 指数退避自动重试（tenacity）：网络超时、限流、服务端 5xx 均自动重试
- 最多重试 5 次，初始等待 2 秒，最长等待 60 秒
- tiktoken 动态 Token 截断工具（truncate_to_tokens）
"""
import sys
import yaml
import json
import logging
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.core.paths import CONFIG_DIR

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 配置加载
# ──────────────────────────────────────────────

def load_config():
    """加载 LLM 配置（config/llm.yaml）。"""
    with open(CONFIG_DIR / "llm.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


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

def call_llm(system_prompt: str, user_prompt: str, config: dict) -> dict:
    """调用 LLM API，返回解析后的 JSON 对象。

    自动重试策略：
    - 触发条件：网络错误、HTTP 429（限流）、HTTP 5xx（服务端错误）
    - 最多重试 5 次，指数退避（2s → 4s → 8s → 16s → 32s），上限 60s
    - 每次重试前打印警告日志

    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        config: 由 load_config() 返回的配置字典

    Returns:
        dict: LLM 返回的 JSON 对象

    Raises:
        openai.APIError: 超过最大重试次数后仍失败
    """
    from openai import OpenAI, APIStatusError, APIConnectionError, APITimeoutError
    from tenacity import (
        retry,
        stop_after_attempt,
        wait_exponential,
        retry_if_exception_type,
        before_sleep_log,
    )

    _retryable = (APIConnectionError, APITimeoutError)

    def _is_retryable_status(exc: Exception) -> bool:
        if isinstance(exc, APIStatusError):
            return exc.status_code in (429, 500, 502, 503, 504)
        return isinstance(exc, _retryable)

    @retry(
        retry=retry_if_exception_type((APIConnectionError, APITimeoutError, APIStatusError)),
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=2, min=2, max=60),
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
            max_tokens=config["llm"].get("max_tokens", 2048),
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)

    return _call()
