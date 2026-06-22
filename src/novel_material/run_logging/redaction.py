"""结构化日志字段和值脱敏。"""

from __future__ import annotations

import re
from typing import Any


SENSITIVE_KEYS = {
    "authorization", "api_key", "password", "connection_string",
    "database_url", "prompt", "raw_content", "source_text",
}
VALUE_PATTERNS = (
    (re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)\b(?:sk|key)-[A-Za-z0-9._-]+"), "[REDACTED]"),
    (
        re.compile(r"(?i)\b(postgresql(?:\+\w+)?://)[^\s/@:]+:[^\s/@]+@"),
        r"\1[REDACTED]@",
    ),
    (re.compile(r"(?i)\bpassword\s*=\s*[^\s;,]+"), "password=[REDACTED]"),
)


def redact_sensitive_patterns(value: str) -> str:
    for pattern, replacement in VALUE_PATTERNS:
        value = pattern.sub(replacement, value)
    return value


def sanitize_value(key: str, value: Any) -> Any:
    normalized = key.lower()
    if normalized in SENSITIVE_KEYS or normalized.endswith("_secret"):
        return "[REDACTED]"
    if isinstance(value, str):
        cleaned = " ".join(value.replace("\x1b", "").splitlines())
        return redact_sensitive_patterns(cleaned)[:2000]
    if isinstance(value, dict):
        return {
            str(child_key): sanitize_value(str(child_key), child_value)
            for child_key, child_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_value(key, item) for item in value[:100]]
    return value


__all__ = ["redact_sensitive_patterns", "sanitize_value"]
