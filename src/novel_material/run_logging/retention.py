"""仅管理新 JSONL 文件的保留策略。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path


class RetentionPolicy:
    def __init__(self, *, retention_days: int, max_files: int, today: date | None = None):
        self.retention_days = max(0, retention_days)
        self.max_files = max(1, max_files)
        self.today = today or date.today()

    def apply(
        self,
        log_dir: Path,
        *,
        active_paths: set[Path] | None = None,
    ) -> tuple[Path, ...]:
        active = {path.resolve() for path in (active_paths or set())}
        candidates: list[tuple[date, Path]] = []
        if not log_dir.exists():
            return ()
        for directory in log_dir.iterdir():
            if not directory.is_dir():
                continue
            try:
                directory_date = datetime.strptime(directory.name, "%Y-%m-%d").date()
            except ValueError:
                continue
            candidates.extend(
                (directory_date, path)
                for path in directory.glob("*.jsonl")
                if path.is_file()
            )

        removed: list[Path] = []
        cutoff = self.today - timedelta(days=self.retention_days)
        for directory_date, path in candidates:
            if directory_date < cutoff and path.resolve() not in active:
                path.unlink()
                removed.append(path)

        remaining = [
            path for _date, path in candidates
            if path.exists() and path.resolve() not in active
        ]
        remaining.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        for path in remaining[self.max_files:]:
            path.unlink()
            removed.append(path)
        return tuple(sorted(removed, key=lambda path: path.as_posix()))


__all__ = ["RetentionPolicy"]
