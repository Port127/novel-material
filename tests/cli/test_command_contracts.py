"""CLI 参数、错误流和入口契约。"""

from __future__ import annotations

from pathlib import Path
import tomllib

from typer.testing import CliRunner

from novel_material.cli.main import app
from novel_material.search.models import SearchResponse, SearchTrace
from novel_material.runtime.contracts import RunStatus, StageResult
from novel_material.storage.sync_core import SyncSummary


runner = CliRunner()


class RecordingSearchService:
    def __init__(self):
        self.requests = []

    def search(self, request):
        self.requests.append(request)
        return SearchResponse(query=request.query, results=[], trace=SearchTrace())


def test_invalid_search_limit_is_usage_error():
    result = runner.invoke(app, ["search", "chapter", "雨", "--limit", "0"])

    assert result.exit_code == 2
    assert "limit" in result.stderr.lower()
    assert "Traceback" not in result.stderr


def test_event_keyword_option_is_rejected():
    result = runner.invoke(app, ["search", "event", "雨", "--keyword"])

    assert result.exit_code == 2
    assert "No such option" in result.stderr


def test_semantic_alias_warns_and_maps_to_exact(monkeypatch):
    service = RecordingSearchService()
    monkeypatch.setattr(
        "novel_material.cli.search.create_default_search_service",
        lambda: service,
    )

    result = runner.invoke(app, ["search", "chapter", "雨", "--semantic"])

    assert result.exit_code == 0
    assert "--semantic 已弃用" in result.stderr
    assert service.requests[0].mode == "exact"


def test_semantic_alias_conflicts_with_explicit_quality_mode():
    result = runner.invoke(
        app,
        ["search", "chapter", "雨", "--mode", "quality", "--semantic"],
    )

    assert result.exit_code == 2
    assert "不能同时使用" in result.stderr


def test_pyproject_exposes_non_conflicting_entrypoint():
    root = Path(__file__).resolve().parents[2]
    scripts = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]["scripts"]

    assert scripts["nm"] == "novel_material.cli:main"
    assert scripts["novel-material"] == "novel_material.cli:main"


def test_root_help_exposes_terminal_control_options():
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--quiet" in result.stdout
    assert "--no-progress" in result.stdout
    assert "--no-color" in result.stdout


def test_standalone_insights_keeps_explicit_chapter_range(tmp_path, monkeypatch):
    material_id = "nm_demo"
    novel_dir = tmp_path / material_id
    novel_dir.mkdir()
    (novel_dir / "chapter_index.yaml").write_text(
        "- chapter: 1\n  title: 第一章\n"
        "- chapter: 2\n  title: 第二章\n"
        "- chapter: 3\n  title: 第三章\n",
        encoding="utf-8",
    )
    recorded = {}

    def fake_generate(material_id_arg, **kwargs):
        recorded.update(material_id=material_id_arg, **kwargs)
        return StageResult(
            stage_id="stage-insights",
            name="insights",
            status=RunStatus.SUCCESS,
        )

    monkeypatch.setattr("novel_material.cli.pipeline.NOVELS_DIR", tmp_path)
    monkeypatch.setattr(
        "novel_material.cli.pipeline.generate_chapter_insights",
        fake_generate,
    )

    result = runner.invoke(
        app,
        ["pipeline", "insights", material_id, "--start", "2", "--end", "3"],
    )

    assert result.exit_code == 0
    assert recorded["material_id"] == material_id
    assert recorded["start_ch"] == 2
    assert recorded["end_ch"] == 3


def test_validate_all_exits_one_when_any_material_fails(tmp_path, monkeypatch):
    for material_id in ("nm_ok", "nm_bad"):
        (tmp_path / material_id).mkdir()
    monkeypatch.setattr("novel_material.infra.config.NOVELS_DIR", tmp_path)
    monkeypatch.setattr(
        "novel_material.cli.validate.validate_material",
        lambda material_id, **_kwargs: material_id == "nm_ok",
    )

    result = runner.invoke(app, ["validate", "validate", "--all"])

    assert result.exit_code == 1
    assert "nm_bad" in result.stdout + result.stderr


def test_validate_single_failure_exits_one(monkeypatch):
    monkeypatch.setattr(
        "novel_material.cli.validate.validate_material",
        lambda *_args, **_kwargs: False,
    )

    result = runner.invoke(app, ["validate", "validate", "nm_bad"])

    assert result.exit_code == 1
    assert "校验失败" in result.stderr


def test_validate_artifacts_uses_audit_status(monkeypatch):
    from novel_material.audit.models import (
        ArtifactAudit,
        ArtifactIssue,
        AuditSeverity,
    )

    monkeypatch.setattr(
        "novel_material.cli.validate.audit_material",
        lambda *_args, **_kwargs: ArtifactAudit(
            material_id="nm_demo",
            issues=(
                ArtifactIssue(
                    code="fallback",
                    severity=AuditSeverity.ERROR,
                    artifact="characters/profiles/主角.yaml",
                    message="主要人物为空壳",
                ),
            ),
        ),
    )

    result = runner.invoke(app, ["validate", "artifacts", "nm_demo"])

    assert result.exit_code == 3
    assert "fallback" in result.stderr
    assert "规则审计" in result.stderr


def test_validate_artifacts_default_does_not_enable_review(monkeypatch):
    from novel_material.audit.models import ArtifactAudit

    calls = []

    def fake_audit(material_id, **kwargs):
        calls.append((material_id, kwargs))
        return ArtifactAudit(material_id=material_id)

    monkeypatch.setattr("novel_material.cli.validate.audit_material", fake_audit)

    result = runner.invoke(app, ["validate", "artifacts", "nm_demo"])

    assert result.exit_code == 0
    assert calls == [("nm_demo", {})]


def test_validate_artifacts_review_builds_reviewer_and_budget(monkeypatch):
    from novel_material.audit.models import ArtifactAudit

    reviewer = object()
    budget = object()
    calls = []
    monkeypatch.setattr(
        "novel_material.cli.validate.get_settings",
        lambda: {
            "ARTIFACT_REVIEW_MAX_CALLS_STANDARD": 3,
            "ARTIFACT_REVIEW_ESTIMATED_CALL_SECONDS": 120,
        },
    )
    monkeypatch.setattr(
        "novel_material.cli.validate.LLMArtifactReviewer",
        lambda: reviewer,
    )
    monkeypatch.setattr(
        "novel_material.cli.validate.ReviewBudget",
        lambda **kwargs: calls.append(("budget", kwargs)) or budget,
    )
    monkeypatch.setattr(
        "novel_material.cli.validate.audit_material",
        lambda material_id, **kwargs: (
            calls.append((material_id, kwargs))
            or ArtifactAudit(material_id=material_id)
        ),
    )

    result = runner.invoke(app, ["validate", "artifacts", "nm_demo", "--review"])

    assert result.exit_code == 0
    assert calls == [
        ("budget", {"max_seconds": 360, "max_calls": 3}),
        (
            "nm_demo",
            {
                "reviewer": reviewer,
                "budget": budget,
                "estimated_call_seconds": 120,
            },
        ),
    ]


def test_material_delete_requires_id_as_usage_error():
    result = runner.invoke(app, ["material", "delete"])

    assert result.exit_code == 2
    assert "--id" in result.stderr


def test_material_delete_failure_exits_one(monkeypatch):
    monkeypatch.setattr(
        "novel_material.cli.material.delete_material",
        lambda *_args, **_kwargs: False,
    )

    result = runner.invoke(
        app,
        ["material", "delete", "--id", "nm_demo", "--force"],
    )

    assert result.exit_code == 1
    assert "删除失败" in result.stderr


def test_storage_sync_repair_requires_confirmation(monkeypatch):
    sync = []
    monkeypatch.setattr(
        "novel_material.cli.storage.sync_novel",
        lambda *_args, **kwargs: sync.append(kwargs),
    )

    result = runner.invoke(
        app,
        ["storage", "sync", "nm_demo", "--repair"],
        input="n\n",
    )

    assert result.exit_code == 0
    assert "修改 YAML" in result.stdout
    assert "调用 LLM" in result.stdout
    assert "产生费用" in result.stdout
    assert "未执行同步" in result.stdout
    assert sync == []


def test_storage_sync_defaults_to_no_repair(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "novel_material.cli.storage.sync_novel",
        lambda *_args, **kwargs: (
            calls.append(kwargs)
            or StageResult(
                stage_id="stage-sync",
                name="sync",
                status=RunStatus.SUCCESS,
            )
        ),
    )

    result = runner.invoke(app, ["storage", "sync", "nm_demo"])

    assert result.exit_code == 0
    assert calls[0]["repair_allowed"] is False


def test_storage_sync_all_empty_is_success(monkeypatch):
    monkeypatch.setattr(
        "novel_material.cli.storage.sync_all",
        lambda **_kwargs: SyncSummary(
            total=0,
            succeeded=0,
            failed=0,
            skipped=0,
        ),
    )

    result = runner.invoke(app, ["storage", "sync"])

    assert result.exit_code == 0
    assert "没有可同步素材" in result.stdout


def test_storage_sync_all_partial_failure_exits_three(monkeypatch):
    monkeypatch.setattr(
        "novel_material.cli.storage.sync_all",
        lambda **_kwargs: SyncSummary(
            total=2,
            succeeded=1,
            failed=1,
            skipped=0,
        ),
    )

    result = runner.invoke(app, ["storage", "sync"])

    assert result.exit_code == 3
    assert "成功 1" in result.stderr
    assert "失败 1" in result.stderr
