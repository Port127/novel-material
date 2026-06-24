"""不可变 run 报告与原子 latest 报告写入器。"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tempfile

from pydantic import ValidationError
import yaml

from .markdown import render_markdown
from .models import PipelineRunReport


class ReportWriteError(RuntimeError):
    """报告持久化错误。"""


class ReportConflictError(ReportWriteError):
    """同一 run_id 已存在内容不同的不可变报告。"""


class ReportHistoryError(ReportWriteError):
    """历史报告缺失、损坏或不符合模型契约。"""


@dataclass(frozen=True)
class ReportPaths:
    """一次写入产生的稳定文件路径。"""

    run_yaml: Path
    latest_yaml: Path
    latest_markdown: Path


class ReportWriter:
    """在单部素材目录下持久化运行报告。"""

    def __init__(self, novel_dir: Path) -> None:
        self.novel_dir = Path(novel_dir)
        self.reports_dir = self.novel_dir / "reports"
        self.runs_dir = self.reports_dir / "runs"

    def write(self, report: PipelineRunReport) -> ReportPaths:
        """排他创建 run YAML，并原子替换两个 latest 文件。"""
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        paths = ReportPaths(
            run_yaml=self.runs_dir / f"{report.run_id}.yaml",
            latest_yaml=self.reports_dir / "latest.yaml",
            latest_markdown=self.reports_dir / "latest.md",
        )
        yaml_text = yaml.safe_dump(
            report.model_dump(mode="json"),
            allow_unicode=True,
            sort_keys=False,
        )
        markdown_text = render_markdown(report)

        _write_immutable(paths.run_yaml, yaml_text, report.run_id)
        _write_atomic(paths.latest_yaml, yaml_text)
        _write_atomic(paths.latest_markdown, markdown_text)
        return paths

    def load_history(self) -> tuple[PipelineRunReport, ...]:
        """读取并校验全部不可变 run 报告，按完成时间升序返回。"""
        if not self.runs_dir.exists():
            return ()
        reports: list[PipelineRunReport] = []
        for path in sorted(self.runs_dir.glob("*.yaml")):
            try:
                payload = yaml.safe_load(path.read_text(encoding="utf-8"))
                reports.append(PipelineRunReport.model_validate(payload))
            except (OSError, UnicodeError, yaml.YAMLError, ValidationError) as exc:
                raise ReportHistoryError(f"历史报告无效：{path.name}") from exc
        reports.sort(key=lambda item: (item.completed_at, item.run_id))
        return tuple(reports)


def _write_immutable(target: Path, content: str, run_id: str) -> None:
    try:
        with target.open("x", encoding="utf-8") as output:
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
    except FileExistsError as exc:
        try:
            existing = target.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as read_exc:
            raise ReportConflictError(f"无法校验已有报告：{run_id}") from read_exc
        if existing != content:
            raise ReportConflictError(f"run 报告内容冲突：{run_id}") from exc


def _write_atomic(target: Path, content: str) -> None:
    temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
            delete=False,
        ) as output:
            temp = Path(output.name)
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, target)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


__all__ = [
    "ReportConflictError",
    "ReportHistoryError",
    "ReportPaths",
    "ReportWriteError",
    "ReportWriter",
]
