"""产物可疑项的受限 LLM 复审协议与实现。"""

from __future__ import annotations

import json
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from .models import ArtifactIssue


class ReviewDecision(BaseModel):
    """reviewer 对一个可疑项的结构化判断。"""

    model_config = ConfigDict(frozen=True)

    code: str = Field(min_length=1)
    confirmed: bool
    rationale: str = Field(min_length=1, max_length=500)


class ArtifactReviewer(Protocol):
    """审计服务依赖的最小复审接口。"""

    def review(
        self,
        issue: ArtifactIssue,
        evidence_excerpt: str,
    ) -> ReviewDecision: ...


class LLMArtifactReviewer:
    """只发送受限证据且不暴露任何写入能力的 LLM reviewer。"""

    def __init__(
        self,
        *,
        provider: str | None = None,
        evidence_chars: int | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        if evidence_chars is None or timeout_seconds is None:
            from novel_material.infra.config import get_settings

            settings = get_settings()
            if evidence_chars is None:
                evidence_chars = int(settings["ARTIFACT_REVIEW_EVIDENCE_CHARS"])
            if timeout_seconds is None:
                timeout_seconds = int(settings["LLM_OTHER_TIMEOUT"])
        if evidence_chars < 0:
            raise ValueError("evidence_chars 不能小于 0")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds 必须大于 0")
        self.provider = provider
        self.evidence_chars = evidence_chars
        self.timeout_seconds = timeout_seconds

    def review(
        self,
        issue: ArtifactIssue,
        evidence_excerpt: str,
    ) -> ReviewDecision:
        """请求严格 JSON 判断，解析或 code 不匹配时抛出异常。"""
        from novel_material.infra.llm import call_llm, load_config

        payload = {
            "code": issue.code,
            "message": issue.message,
            "evidence": issue.evidence,
            "evidence_excerpt": evidence_excerpt[: self.evidence_chars],
        }
        result = call_llm(
            system_prompt=(
                "你是小说分析产物审计员。只判断给定问题是否被证据确认，"
                "不得提出或执行文件修改。严格返回 code、confirmed、rationale JSON。"
            ),
            user_prompt=json.dumps(payload, ensure_ascii=False, sort_keys=True),
            config=load_config(self.provider),
            timeout_override=self.timeout_seconds,
            context=f"artifact review {issue.code}",
        )
        decision = ReviewDecision.model_validate(result)
        if decision.code != issue.code:
            raise ValueError("review decision code 与问题不一致")
        return decision


__all__ = ["ArtifactReviewer", "LLMArtifactReviewer", "ReviewDecision"]
