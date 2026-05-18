"""LLM API 调用客户端

所有脚本必须通过这个模块调用 LLM，不要在其他文件中直接调用 API。
"""
import json
import logging
import time
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()

from .progress import get_pipeline_logger
from .config import get_settings
from .yaml_io import load_yaml
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


def get_last_call_finish_reason() -> str:
    """获取最近一次调用的 finish_reason（供调试使用）。"""
    if _call_details:
        return _call_details[-1].get("finish_reason", "")
    return ""


def load_config(provider: str | None = None) -> dict:
    """加载 LLM 配置。

    配置优先级：
    1. 指定的 provider（providers.yaml 中的服务商）
    2. providers.yaml 中的 default_provider
    3. settings.yaml（向后兼容，无 providers.yaml 时）

    参数：
        provider：服务商名称（可选，对应 providers.yaml 中的 name 字段）

    返回：
        dict：LLM 配置字典

    异常：
        ValueError：指定了 provider 但在 providers.yaml 中找不到
    """
    from novel_material.infra.config_service import load_app_config
    app_config = load_app_config(provider)
    return {"llm": app_config["llm"]}


def _load_providers_yaml() -> dict | None:
    """加载 providers.yaml 配置文件，返回 None 表示文件不存在。"""
    if not PROVIDERS_CONFIG_FILE.exists():
        return None
    return load_yaml(PROVIDERS_CONFIG_FILE)


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


def _classify_error(exc: Exception) -> str:
    """将异常分类为简短标签，便于日志快速识别。"""
    from openai import APIStatusError, APIConnectionError, APITimeoutError, AuthenticationError

    if isinstance(exc, AuthenticationError):
        return "[AUTH]"
    if isinstance(exc, APIStatusError):
        if exc.status_code == 401:
            return "[AUTH]"
        if exc.status_code == 429:
            return "[RATE]"
        if exc.status_code >= 500:
            return "[SERVER]"
        return "[HTTP]"
    if isinstance(exc, APITimeoutError):
        return "[TIMEOUT]"
    if isinstance(exc, APIConnectionError):
        return "[CONN]"
    if isinstance(exc, json.JSONDecodeError):
        return "[JSON]"
    return "[OTHER]"


def _retry_log_callback(retry_state):
    """重试前的日志回调，打印重试状态。"""
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    if exc:
        error_tag = _classify_error(exc)
        attempt = retry_state.attempt_number
        max_attempts = 8
        wait_time = _retry_wait(retry_state)
        logger.warning(f"{error_tag} 重试 {attempt}/{max_attempts}，等待 {wait_time:.0f}s: {type(exc).__name__}")


def _retry_wait(retry_state):
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


def _format_prefix(context: str | None) -> str:
    """格式化日志前缀：[material_id] 批次部分"""
    if not context:
        return ""
    if " " in context:
        parts = context.split(" ", 1)
        return f"[{parts[0]}] {parts[1]} "
    return f"[{context}] "


def call_llm_with_args(args) -> dict:
    """调用 LLM API（参数对象版本），返回 JSON 结果。

    参数：
        args: LLMCallArgs 参数对象

    返回：
        dict: JSON 结果
    """
    return call_llm(
        system_prompt=args.system_prompt,
        user_prompt=args.user_prompt,
        config=args.config,
        max_tokens_override=args.max_tokens_override,
        timeout_override=args.timeout_override,
        context=args.context,
        thinking_budget=args.thinking_budget,
        temperature_override=args.temperature_override,
    )


def call_llm(
    system_prompt: str,
    user_prompt: str,
    config: dict,
    max_tokens_override: int | None = None,
    timeout_override: int | None = None,
    context: str | None = None,
    thinking_budget: int | None = None,
    temperature_override: float | None = None,
) -> dict:
    """调用 LLM API，返回 JSON 结果。

    参数：
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        config: LLM 配置字典
        max_tokens_override: 最大 tokens 覆盖
        timeout_override: 超时时间覆盖
        context: 上下文标签（如 "章节分析#批次53"），用于日志区分
        thinking_budget: 思考模式预算 tokens（可选，设为 0 表示启用思考模式）
        temperature_override: 温度覆盖（可选，用于动态调整输出多样性）
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
        before_sleep=_retry_log_callback,
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

        # 构建 create 参数
        # thinking 控制：DashScope OpenAI 兼容接口通过 extra_body 传递 thinking_budget
        model_name = config["llm"]["model"]
        create_kwargs: dict = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": effective_max_tokens,
            "timeout": sdk_timeout,
            "response_format": {"type": "json_object"},
        }

        if thinking_budget is not None:
            thinking_format = config["llm"].get("thinking_format", "openai")
            if thinking_format == "dashscope":
                # 阿里云 DashScope 格式
                create_kwargs["extra_body"] = {"enable_thinking": True, "thinking_budget": thinking_budget}
            else:
                # 标准 OpenAI 格式
                create_kwargs["thinking"] = {"type": "enabled", "budget_tokens": thinking_budget}
        else:
            # 温度处理：优先使用 override，否则使用配置默认值
            if temperature_override is not None:
                effective_temp = temperature_override
            else:
                effective_temp = config["llm"].get("temperature", 0.3)
            # 确保 temperature_max 上限（仅在 override 时应用）
            temp_max = config["llm"].get("temperature_max", 1.0)
            if temperature_override is not None:
                effective_temp = min(effective_temp, temp_max)
            create_kwargs["temperature"] = effective_temp

        response = client.chat.completions.create(**create_kwargs)
        elapsed = time.monotonic() - call_start

        # 获取 request_id（用于服务商后台追踪）
        request_id = getattr(response, "id", "")
        if not request_id:
            # 尝试从 headers 获取
            try:
                request_id = response._request_id if hasattr(response, "_request_id") else ""
            except Exception:
                request_id = ""

        usage = response.usage
        finish_reason = response.choices[0].finish_reason if response.choices else None
        _api_stats["calls"] += 1

        # 记录调用详情（无论 usage 是否存在）
        detail = {
            "elapsed_sec": elapsed,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "thinking_tokens": 0,
            "model": model_name,
            "timestamp": time.strftime("%H:%M:%S"),
            "finish_reason": finish_reason,
            "request_id": request_id,
        }

        prefix = _format_prefix(context)
        if usage:
            _api_stats["tokens_total"] += usage.total_tokens
            detail["input_tokens"] = usage.prompt_tokens
            detail["output_tokens"] = usage.completion_tokens
            detail["total_tokens"] = usage.total_tokens
            # thinking tokens（如果 API 返回）
            comp_details = getattr(usage, "completion_tokens_details", None)
            if comp_details:
                thinking = getattr(comp_details, "reasoning_tokens", 0)
                if thinking:
                    detail["thinking_tokens"] = thinking
                    # 阈值检查：thinking tokens 异常低时发出警告
                    threshold = int(get_settings().get("LLM_THINKING_TOKENS_MIN_THRESHOLD", 1000))
                    if thinking < threshold:
                        logger.warning(
                            f"{prefix}thinking tokens 异常低: {thinking} < {threshold}，可能导致输出质量下降"
                        )

            # INFO 级别日志：每次调用详情（含请求参数 + 行业标准字段）
            thinking_mode = "enabled" if thinking_budget is not None else "disabled"
            temp_str = f"{effective_temp:.2f}" if "effective_temp" in dir() else "None"
            log_parts = [
                f"{prefix}API: {elapsed:.1f}s",
                f"model={model_name}",
                f"max_tokens={effective_max_tokens}",
                f"thinking={thinking_mode} budget={thinking_budget if thinking_budget is not None else 'None'}",
                f"temp={temp_str}",
                f"in={usage.prompt_tokens} out={usage.completion_tokens} total={usage.total_tokens}",
            ]
            if detail["thinking_tokens"]:
                log_parts.append(f"thinking_tokens={detail['thinking_tokens']}")
            log_parts.append(f"finish={finish_reason}")
            if context:
                log_parts.append(f"context={context}")
            if request_id:
                log_parts.append(f"req={request_id[:12]}...")

            logger.info(" | ".join(log_parts))
        else:
            # usage 为 None 时仍记录调用
            logger.warning(f"{prefix}API: {elapsed:.1f}s | usage=None（无法获取 tokens） | finish={finish_reason}")

        # 存储原始内容供异常处理使用
        raw_content = response.choices[0].message.content
        detail["_raw_content"] = raw_content

        _call_details.append(detail)
        # 限制列表长度，防止无界增长（只需最后一条供 get_last_call_* 使用）
        if len(_call_details) > 100:
            _call_details.pop(0)
        return json.loads(raw_content)

    # JSON 解析失败时自动加大 max_tokens 重试（最多 2 次）
    max_json_retries = 2
    for attempt in range(max_json_retries + 1):
        try:
            return _call()
        except json.JSONDecodeError as e:
            # 从最后一次调用获取详细信息
            last_detail = _call_details[-1] if _call_details else {}
            raw_snippet = last_detail.get("_raw_content", "")[:200] if last_detail.get("_raw_content") else "(无内容)"
            last_req_id = last_detail.get("request_id", "N/A")[:12]
            last_elapsed = last_detail.get("elapsed_sec", 0)

            if attempt < max_json_retries:
                new_max = min(effective_max_tokens * 2, 65536)
                prefix = _format_prefix(context)
                logger.warning(
                    f"{prefix}[JSON] 解析失败 | model={config['llm']['model']} | "
                    f"max_tokens={effective_max_tokens} | attempt={last_elapsed:.1f}s | "
                    f"req={last_req_id}... | snippet: {raw_snippet} | "
                    f"加大到 {new_max}，重试 {attempt+1}/{max_json_retries}"
                )
                effective_max_tokens = new_max
            else:
                _api_stats["errors"] += 1
                elapsed = time.monotonic() - _outer_start
                prefix = _format_prefix(context)
                logger.error(
                    f"{prefix}[JSON] 解析最终失败 | model={config['llm']['model']} | "
                    f"total={elapsed:.1f}s | req={last_req_id}... | error: {e}"
                )
                raise
        except Exception as e:
            _api_stats["errors"] += 1
            elapsed = time.monotonic() - _outer_start
            error_tag = _classify_error(e)
            prefix = _format_prefix(context)
            # 从最后一次调用获取详细信息（如果有）
            last_detail = _call_details[-1] if _call_details else {}
            last_req_id = last_detail.get("request_id", "N/A")[:12]
            last_elapsed = last_detail.get("elapsed_sec", 0)
            logger.error(
                f"{prefix}{error_tag} API 失败 | model={config['llm']['model']} | "
                f"context={context or 'N/A'} | attempt={last_elapsed:.1f}s | total={elapsed:.1f}s | "
                f"req={last_req_id}... | error: {type(e).__name__}: {e}"
            )
            raise
