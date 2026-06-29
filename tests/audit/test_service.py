import subprocess
import sys
from pathlib import Path

import yaml

from novel_material.audit.models import ArtifactAudit, ArtifactIssue, AuditSeverity
from novel_material.audit.service import audit_material, audit_to_stage_result
from novel_material.pipeline import stages as stage_entries
from novel_material.runtime.contracts import RunStatus


def issue(
    code: str,
    severity: AuditSeverity,
    *,
    artifact: str = "tags.yaml",
) -> ArtifactIssue:
    return ArtifactIssue(
        code=code,
        severity=severity,
        artifact=artifact,
        message=f"{code} 问题",
    )


def write_yaml(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, allow_unicode=True), encoding="utf-8")


def test_importing_audit_package_does_not_load_config() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; import novel_material.audit; "
                "print('novel_material.infra.config' in sys.modules)"
            ),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "False"


def test_audit_service_deduplicates_and_sorts_issues(
    tmp_path: Path,
    monkeypatch,
) -> None:
    duplicate = issue("same", AuditSeverity.WARNING)
    blocker = issue("missing", AuditSeverity.BLOCKER, artifact="meta.yaml")
    error = issue("fallback", AuditSeverity.ERROR)
    monkeypatch.setattr(
        "novel_material.audit.service.RULES",
        (
            ("one", lambda _context: (duplicate, error)),
            ("two", lambda _context: (duplicate, blocker)),
        ),
    )

    audit = audit_material("nm_demo", novels_dir=tmp_path)

    assert audit.checks == ("one", "two")
    assert audit.issues == (blocker, error, duplicate)


def test_audit_service_resolves_default_novels_dir_at_call_time(
    tmp_path: Path,
    monkeypatch,
) -> None:
    observed_dirs = []
    monkeypatch.setattr(
        "novel_material.audit.service.RULES",
        (("path", lambda context: observed_dirs.append(context.novel_dir) or ()),),
    )
    monkeypatch.setattr("novel_material.infra.config.NOVELS_DIR", tmp_path)

    audit_material("nm_demo")

    assert observed_dirs == [tmp_path / "nm_demo"]


def test_audit_service_summarizes_character_biography_quality(
    tmp_path: Path,
    monkeypatch,
) -> None:
    novel = tmp_path / "nm_demo"
    write_yaml(
        novel / "characters/_index.yaml",
        {
            "biography_target_count": 3,
            "biography_completed_count": 2,
            "biography_failed_count": 1,
            "biography_targets": [
                {"name": "角色一"},
                {"name": "角色二"},
                {"name": "角色三"},
            ],
        },
    )
    for name, complete in (("角色一", True), ("角色二", True), ("角色三", False)):
        write_yaml(
            novel / f"characters/profiles/{name}.yaml",
            {
                "name": name,
                "profile_level": "full",
                "biography_complete": complete,
            },
        )
    write_yaml(
        novel / "characters/profiles/路人.yaml",
        {
            "name": "路人",
            "profile_level": "brief",
        },
    )
    monkeypatch.setattr("novel_material.audit.service.RULES", ())

    audit = audit_material("nm_demo", novels_dir=tmp_path)
    payload = audit.model_dump(mode="json")

    assert payload["character_quality"] == {
        "biography_target_count": 3,
        "biography_completed_count": 2,
        "brief_profile_count": 1,
        "biography_failed_count": 1,
    }


def test_audit_error_maps_to_degraded_stage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    problem = issue(
        "fallback",
        AuditSeverity.ERROR,
        artifact="characters/profiles/主角.yaml",
    )
    monkeypatch.setattr(
        "novel_material.audit.service.RULES",
        (("characters", lambda _context: (problem,)),),
    )

    stage = audit_to_stage_result(audit_material("nm_demo", novels_dir=tmp_path))

    assert stage.name == "audit"
    assert stage.status is RunStatus.DEGRADED
    assert stage.counts.expected == stage.counts.processed == 1
    assert stage.diagnostics[0].code == "fallback"
    assert stage.outputs["audit"]["summary"]["error"] == 1


def test_artifact_audit_stage_entry_returns_stage_result(monkeypatch) -> None:
    audit = ArtifactAudit(material_id="nm_demo")
    monkeypatch.setattr(stage_entries, "audit_material", lambda *_args, **_kwargs: audit)

    stage = stage_entries.run_artifact_audit_stage("nm_demo")

    assert stage.name == "audit"
    assert stage.status is RunStatus.SUCCESS
    assert stage.outputs["audit"]["material_id"] == "nm_demo"
