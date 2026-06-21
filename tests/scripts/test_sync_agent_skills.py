from pathlib import Path

import pytest

from scripts.sync_agent_skills import check_skills, sync_skills


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_check_reports_drift_and_sync_repairs_it(tmp_path):
    source = tmp_path / ".agents" / "skills"
    target = tmp_path / ".claude" / "skills"
    write(source / "demo" / "SKILL.md", "source\n")
    write(target / "demo" / "SKILL.md", "stale\n")

    assert check_skills(source, target) == ["内容不同: demo/SKILL.md"]

    sync_skills(source, target)

    assert check_skills(source, target) == []
    assert (target / "demo" / "SKILL.md").read_text(encoding="utf-8") == "source\n"


def test_hidden_files_are_not_managed(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    write(source / "demo" / "SKILL.md", "same\n")
    write(target / "demo" / "SKILL.md", "same\n")
    write(target / ".DS_Store", "local")

    assert check_skills(source, target) == []


def test_sync_removes_target_file_missing_from_source(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    write(source / "demo" / "SKILL.md", "same\n")
    write(target / "demo" / "SKILL.md", "same\n")
    write(target / "obsolete" / "SKILL.md", "old\n")

    sync_skills(source, target)

    assert not (target / "obsolete" / "SKILL.md").exists()
    assert check_skills(source, target) == []


def test_sync_rejects_missing_source(tmp_path):
    with pytest.raises(FileNotFoundError, match="源目录不存在"):
        sync_skills(tmp_path / "missing", tmp_path / "target")
