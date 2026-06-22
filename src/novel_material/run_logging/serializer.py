"""RunEvent 到稳定单行 JSON 的序列化。"""

from __future__ import annotations

from datetime import datetime, timezone
import json

from novel_material.runtime.contracts import RunEvent

from .redaction import sanitize_value


ALLOWED_TOP_LEVEL = (
    "schema_version", "event_name", "event_id", "occurred_at",
    "observed_at", "severity_text", "severity_number", "run_id",
    "stage_id", "request_id", "provider_request_id", "command",
    "component", "operation", "material_id", "status", "duration_ms",
    "attributes",
)


def _to_rfc3339(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def serialize_event(event: RunEvent) -> str:
    source = event.model_dump(mode="json", exclude_none=True)
    payload = {key: source[key] for key in ALLOWED_TOP_LEVEL if key in source}
    payload["occurred_at"] = _to_rfc3339(payload["occurred_at"])
    payload["observed_at"] = _to_rfc3339(payload["observed_at"])
    payload["attributes"] = sanitize_value(
        "attributes",
        payload.get("attributes", {}),
    )
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


__all__ = ["serialize_event"]
