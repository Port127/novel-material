"""工作区零数据变更护栏测试。"""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
GUARD_SCRIPT = ROOT / "scripts" / "check_runtime_workspace.py"


def run_guard(
    action: str,
    root: Path,
    baseline: Path,
    *extra_args: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(GUARD_SCRIPT),
            action,
            "--root",
            str(root),
            "--baseline",
            str(baseline),
            *extra_args,
        ],
        capture_output=True,
        check=False,
        text=True,
    )


def test_workspace_guard_detects_untracked_data_change(tmp_path: Path):
    novel = tmp_path / "data" / "novels" / "nm_demo" / "meta.yaml"
    novel.parent.mkdir(parents=True)
    novel.write_text("status: clean\n", encoding="utf-8")
    baseline = tmp_path / "baseline.json"

    recorded = run_guard("record", tmp_path, baseline)
    assert recorded.returncode == 0, recorded.stderr

    new_file = novel.parent / "new.yaml"
    new_file.write_text("new: true\n", encoding="utf-8")

    verified = run_guard("verify", tmp_path, baseline)
    assert verified.returncode == 1
    assert "data/novels/nm_demo/new.yaml" in verified.stderr


def test_workspace_guard_includes_nested_legacy_logs(tmp_path: Path):
    legacy = tmp_path / "logs" / "2025" / "pipeline.log"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("before", encoding="utf-8")
    baseline = tmp_path / "baseline.json"

    recorded = run_guard("record", tmp_path, baseline)
    assert recorded.returncode == 0, recorded.stderr

    legacy.write_text("after", encoding="utf-8")

    verified = run_guard("verify", tmp_path, baseline)
    assert verified.returncode == 1
    assert "logs/2025/pipeline.log" in verified.stderr


def test_workspace_guard_ignores_new_jsonl_logs(tmp_path: Path):
    legacy = tmp_path / "logs" / "pipeline.log"
    legacy.parent.mkdir(parents=True)
    legacy.write_text("legacy", encoding="utf-8")
    baseline = tmp_path / "baseline.json"

    recorded = run_guard("record", tmp_path, baseline)
    assert recorded.returncode == 0, recorded.stderr

    jsonl = tmp_path / "logs" / "2026-06-22" / "pipeline_run-1.jsonl"
    jsonl.parent.mkdir(parents=True)
    jsonl.write_text('{"event_name":"RunStarted"}\n', encoding="utf-8")

    verified = run_guard("verify", tmp_path, baseline)
    assert verified.returncode == 0, verified.stderr


def test_workspace_guard_allows_append_to_explicit_active_log(tmp_path: Path):
    active_log = tmp_path / "logs" / "pipeline_active.log"
    active_log.parent.mkdir(parents=True)
    active_log.write_text("before\n", encoding="utf-8")
    baseline = tmp_path / "baseline.json"

    recorded = run_guard(
        "record",
        tmp_path,
        baseline,
        "--allow-appending-log",
        "logs/pipeline_active.log",
    )
    assert recorded.returncode == 0, recorded.stderr

    with active_log.open("a", encoding="utf-8") as target:
        target.write("after\n")

    verified = run_guard("verify", tmp_path, baseline)
    assert verified.returncode == 0, verified.stderr


def test_workspace_guard_rejects_rewritten_active_log_prefix(tmp_path: Path):
    active_log = tmp_path / "logs" / "pipeline_active.log"
    active_log.parent.mkdir(parents=True)
    active_log.write_text("before\n", encoding="utf-8")
    baseline = tmp_path / "baseline.json"

    recorded = run_guard(
        "record",
        tmp_path,
        baseline,
        "--allow-appending-log",
        "logs/pipeline_active.log",
    )
    assert recorded.returncode == 0, recorded.stderr

    active_log.write_text("changed\nafter\n", encoding="utf-8")

    verified = run_guard("verify", tmp_path, baseline)
    assert verified.returncode == 1
    assert "logs/pipeline_active.log" in verified.stderr
