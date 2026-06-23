from pathlib import Path

from novel_material.audit.budget import ReviewBudget
from novel_material.audit.models import (
    ArtifactIssue,
    AuditSeverity,
    ReviewState,
)
from novel_material.audit.reviewer import LLMArtifactReviewer, ReviewDecision
from novel_material.audit.service import audit_material


def reviewable_issue(code: str, artifact: str) -> ArtifactIssue:
    return ArtifactIssue(
        code=code,
        severity=AuditSeverity.WARNING,
        artifact=artifact,
        message="证据覆盖不足",
        evidence={"count": 0},
        reviewable=True,
        review_state=ReviewState.PENDING,
    )


class FakeReviewer:
    evidence_chars = 4000

    def __init__(self, *, confirmed: bool = True) -> None:
        self.confirmed = confirmed
        self.calls = []

    def review(self, issue, evidence_excerpt):
        self.calls.append((issue.code, evidence_excerpt))
        return ReviewDecision(
            code=issue.code,
            confirmed=self.confirmed,
            rationale="证据不足，保留警告" if self.confirmed else "规则误报",
        )


def test_llm_reviewer_limits_evidence_and_requests_structured_decision(
    monkeypatch,
) -> None:
    captured = {}

    def fake_call_llm(**kwargs):
        captured.update(kwargs)
        return {"code": "legacy", "confirmed": True, "rationale": "确认缺少证据"}

    monkeypatch.setattr("novel_material.infra.llm.call_llm", fake_call_llm)
    monkeypatch.setattr(
        "novel_material.infra.llm.load_config",
        lambda _provider=None: {"llm": {"model": "fake"}},
    )
    reviewer = LLMArtifactReviewer(evidence_chars=10, timeout_seconds=77)

    decision = reviewer.review(
        reviewable_issue("legacy", "worldbuilding/_index.yaml"),
        "0123456789不得发送",
    )

    assert decision.confirmed is True
    assert "0123456789" in captured["user_prompt"]
    assert "不得发送" not in captured["user_prompt"]
    assert captured["timeout_override"] == 77


def test_service_reviews_only_reviewable_issues_and_never_writes_yaml(
    tmp_path: Path,
    monkeypatch,
) -> None:
    novel = tmp_path / "nm_demo"
    source = novel / "worldbuilding/_index.yaml"
    source.parent.mkdir(parents=True)
    source.write_text("llm_success: true\n", encoding="utf-8")
    before = source.read_bytes()
    reviewer = FakeReviewer()
    reviewable = reviewable_issue("legacy", "worldbuilding/_index.yaml")
    fixed = ArtifactIssue(
        code="fixed",
        severity=AuditSeverity.INFO,
        artifact="meta.yaml",
        message="无需复审",
    )
    monkeypatch.setattr(
        "novel_material.audit.service.RULES",
        (("test", lambda _context: (reviewable, fixed)),),
    )

    audit = audit_material(
        "nm_demo",
        novels_dir=tmp_path,
        reviewer=reviewer,
        budget=ReviewBudget(max_seconds=100, max_calls=1, clock=lambda: 0),
        estimated_call_seconds=10,
    )

    assert reviewer.calls == [("legacy", "llm_success: true\n")]
    assert source.read_bytes() == before
    assert {item.code: item.review_state for item in audit.issues} == {
        "fixed": ReviewState.NOT_REQUIRED,
        "legacy": ReviewState.CONFIRMED,
    }
    assert audit.review_budget.calls_used == 1


def test_service_marks_remaining_reviews_when_budget_is_exhausted(
    tmp_path: Path,
    monkeypatch,
) -> None:
    reviewer = FakeReviewer()
    first = reviewable_issue("first", "first.yaml")
    second = reviewable_issue("second", "second.yaml")
    monkeypatch.setattr(
        "novel_material.audit.service.RULES",
        (("test", lambda _context: (first, second)),),
    )

    audit = audit_material(
        "nm_demo",
        novels_dir=tmp_path,
        reviewer=reviewer,
        budget=ReviewBudget(max_seconds=100, max_calls=1, clock=lambda: 0),
        estimated_call_seconds=10,
    )
    states = {item.code: item.review_state for item in audit.issues}

    assert states == {
        "first": ReviewState.CONFIRMED,
        "second": ReviewState.NOT_REVIEWED_DUE_TO_BUDGET,
    }
    assert audit.review_budget.stop_reason == "call_budget_exhausted"


def test_dismissed_review_is_retained_as_information(
    tmp_path: Path,
    monkeypatch,
) -> None:
    reviewer = FakeReviewer(confirmed=False)
    candidate = reviewable_issue("legacy", "worldbuilding/_index.yaml")
    monkeypatch.setattr(
        "novel_material.audit.service.RULES",
        (("test", lambda _context: (candidate,)),),
    )

    audit = audit_material(
        "nm_demo",
        novels_dir=tmp_path,
        reviewer=reviewer,
        budget=ReviewBudget(max_seconds=100, max_calls=1, clock=lambda: 0),
        estimated_call_seconds=10,
    )

    assert audit.issues[0].severity is AuditSeverity.INFO
    assert audit.issues[0].review_state is ReviewState.DISMISSED
    assert audit.issues[0].evidence["review_rationale"] == "规则误报"


def test_review_failure_adds_warning_without_changing_original_severity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class BrokenReviewer:
        evidence_chars = 4000

        def review(self, _issue, _evidence_excerpt):
            raise ValueError("invalid response")

    candidate = reviewable_issue("legacy", "worldbuilding/_index.yaml")
    monkeypatch.setattr(
        "novel_material.audit.service.RULES",
        (("test", lambda _context: (candidate,)),),
    )

    audit = audit_material(
        "nm_demo",
        novels_dir=tmp_path,
        reviewer=BrokenReviewer(),
        budget=ReviewBudget(max_seconds=100, max_calls=1, clock=lambda: 0),
        estimated_call_seconds=10,
    )
    by_code = {item.code: item for item in audit.issues}

    assert by_code["legacy"].severity is AuditSeverity.WARNING
    assert by_code["review_failed"].severity is AuditSeverity.WARNING
    assert by_code["review_failed"].evidence == {"error_type": "ValueError"}
