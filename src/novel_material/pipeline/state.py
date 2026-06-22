"""Pipeline 新运行的原子 sidecar 状态存储。"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Callable, Iterator

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from novel_material.runtime.contracts import RunStatus, StageResult


class PipelineStateError(RuntimeError):
    """Pipeline sidecar 基础异常。"""


class PipelineStateCorruptError(PipelineStateError):
    """sidecar 或索引缺失、损坏或互相矛盾。"""


class ConcurrentRunError(PipelineStateError):
    """同一素材已有活跃写运行。"""


class PersistedRunState(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    run_id: str = Field(min_length=1)
    command: str = Field(min_length=1)
    status: RunStatus
    generation: int = Field(ge=1)
    created_at: datetime
    updated_at: datetime
    stages: tuple[StageResult, ...] = ()

    @field_validator("created_at", "updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("sidecar 时间必须包含时区")
        return value


class LatestRunIndex(BaseModel):
    model_config = ConfigDict(frozen=True)

    schema_version: int = 1
    run_id: str = Field(min_length=1)
    generation: int = Field(ge=1)
    updated_at: datetime

    @field_validator("updated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("索引时间必须包含时区")
        return value


class PipelineStateStore:
    def __init__(
        self,
        novel_dir: Path,
        process_probe: Callable[[int], bool] | None = None,
    ) -> None:
        self.runs_dir = novel_dir / "runs"
        self._process_probe = process_probe or _process_is_alive

    def write(self, state: PersistedRunState) -> Path:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        target = self.runs_dir / f"{state.run_id}.json"
        _write_json_fsynced(target, state.model_dump_json(indent=2))
        index = LatestRunIndex(
            run_id=state.run_id,
            generation=state.generation,
            updated_at=state.updated_at,
        )
        _write_json_fsynced(
            self.runs_dir / "latest.json",
            index.model_dump_json(indent=2),
        )
        return target

    def read(self, run_id: str) -> PersistedRunState:
        try:
            return PersistedRunState.model_validate_json(
                (self.runs_dir / f"{run_id}.json").read_text(encoding="utf-8")
            )
        except (OSError, ValidationError) as exc:
            raise PipelineStateCorruptError(f"运行 sidecar 无效：{run_id}") from exc

    def read_latest(self) -> PersistedRunState:
        try:
            index = LatestRunIndex.model_validate_json(
                (self.runs_dir / "latest.json").read_text(encoding="utf-8")
            )
        except (OSError, ValidationError) as exc:
            raise PipelineStateCorruptError("latest 索引无效") from exc
        state = self.read(index.run_id)
        if state.generation != index.generation:
            raise PipelineStateCorruptError("latest 索引与运行状态不一致")
        return state

    @contextmanager
    def acquire_lease(self, run_id: str) -> Iterator[None]:
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        lease = self.runs_dir / "active.lock"
        payload = json.dumps({"run_id": run_id, "pid": os.getpid()})
        try:
            descriptor = os.open(lease, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError as exc:
            owner = _read_lease(lease)
            if owner and self._process_probe(owner.get("pid", -1)):
                raise ConcurrentRunError("pipeline_run_already_active") from exc
            lease.unlink(missing_ok=True)
            descriptor = os.open(lease, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as target:
                target.write(payload)
                target.flush()
                os.fsync(target.fileno())
            yield
        finally:
            owner = _read_lease(lease)
            if owner and owner.get("run_id") == run_id:
                lease.unlink(missing_ok=True)


def _write_json_fsynced(target: Path, content: str) -> None:
    temp = target.with_name(f"{target.name}.tmp")
    with temp.open("w", encoding="utf-8") as output:
        output.write(content)
        output.flush()
        os.fsync(output.fileno())
    os.replace(temp, target)


def _read_lease(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _process_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


__all__ = [
    "ConcurrentRunError",
    "LatestRunIndex",
    "PersistedRunState",
    "PipelineStateCorruptError",
    "PipelineStateStore",
]
