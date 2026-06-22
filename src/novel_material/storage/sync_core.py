"""数据库同步入口：预检、自动修复、执行同步。

此模块包含 sync_novel、sync_all 等入口函数，
调用各子模块完成同步任务。
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from novel_material.infra.config import NOVELS_DIR
from novel_material.infra.progress import get_pipeline_logger
from novel_material.runtime.context import current_context, new_id
from novel_material.runtime.contracts import (
    Diagnostic,
    ProgressCounts,
    RunEvent,
    RunStatus,
    StageResult,
)
from novel_material.runtime.dispatcher import NullDispatcher, RuntimeDispatcher
from novel_material.validation.schema import validate_material, get_schema_error_chapters
from novel_material.validation.quality import get_short_summary_chapters, get_missing_chapters
from novel_material.storage.repair import repair_short_summaries

from novel_material.storage.sync_utils import (
    logger,
    get_db_connection,
    DatabaseConfigError,
    QualityCheckError,
    SchemaValidationError,
)
from novel_material.storage.sync_meta import sync_meta
from novel_material.storage.sync_chapters import sync_chapters
from novel_material.storage.sync_outline import sync_outline
from novel_material.storage.sync_characters import sync_characters
from novel_material.storage.sync_worldbuilding import sync_worldbuilding


class SyncSummary(BaseModel):
    """批量同步的稳定结果汇总。"""

    model_config = ConfigDict(frozen=True)

    total: int
    succeeded: int
    failed: int
    skipped: int
    results: tuple[StageResult, ...] = ()

    @property
    def status(self) -> RunStatus:
        if self.failed == 0:
            return RunStatus.SUCCESS
        if self.succeeded > 0:
            return RunStatus.DEGRADED
        return RunStatus.FAILED


def _sync_result(
    material_id: str,
    status: RunStatus,
    *,
    diagnostic: Diagnostic | None = None,
) -> StageResult:
    success = status is RunStatus.SUCCESS
    return StageResult(
        stage_id=new_id("stage"),
        name="sync",
        status=status,
        counts=ProgressCounts(
            expected=1,
            processed=1,
            succeeded=1 if success else 0,
            failed=0 if success else 1,
            remaining=0,
        ),
        diagnostics=(diagnostic,) if diagnostic else (),
        outputs={"material_id": material_id},
    )


def _precheck_schema(material_id: str, verbose: bool = True) -> None:
    """同步前检查数据格式（纯校验，不修复）。

    参数：
        material_id: 素材 ID
        verbose: 是否输出详细信息

    Raises:
        QualityCheckError: 检查失败，包含可修复的章节列表
        SchemaValidationError: 检查失败且无法修复（非 summary/schema 问题）
    """
    if validate_material(material_id, verbose=verbose, skip_tags=True):
        logger.info(f"Schema 预检通过: {material_id}")
        return

    # 检查是否是 summary 长度问题、缺失章节问题或 schema 错误问题
    short_chapters = get_short_summary_chapters(material_id)
    missing_chapters = get_missing_chapters(material_id, strict=False)
    schema_error_chapters = get_schema_error_chapters(material_id)

    if short_chapters or missing_chapters or schema_error_chapters:
        # 是可修复问题（summary长度不足、章节缺失或 schema 错误）
        if short_chapters:
            logger.warning(f"Schema 预检失败: {material_id}，{len(short_chapters)} 章 summary 长度不足")
        if missing_chapters:
            logger.warning(f"Schema 预检失败: {material_id}，{len(missing_chapters)} 章缺失")
        if schema_error_chapters:
            logger.warning(f"Schema 预检失败: {material_id}，{len(schema_error_chapters)} 章 schema 错误")
        raise QualityCheckError(
            material_id,
            short_chapters=short_chapters,
            missing_chapters=missing_chapters,
            schema_error_chapters=schema_error_chapters
        )
    else:
        # 不是可修复问题，无法自动修复
        logger.error(f"Schema 预检失败（非 summary/缺失/schema 错误问题），无法自动修复: {material_id}")
        raise SchemaValidationError(f"Schema 预检失败（非可修复问题），中止同步: {material_id}")


def _execute_sync(conn, novel_dir, material_id) -> bool:
    """执行同步操作（内部函数，消除重复代码）。

    参数：
        conn: 数据库连接
        novel_dir: 小说目录
        material_id: 素材 ID

    返回：
        True 表示成功，False 表示失败
    """
    try:
        sync_meta(conn, novel_dir, material_id)
        sync_chapters(conn, novel_dir, material_id)
        sync_outline(conn, novel_dir, material_id)
        sync_characters(conn, novel_dir, material_id)
        sync_worldbuilding(conn, novel_dir, material_id)
        conn.commit()
        logger.info(f"同步完成: {material_id}")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"同步失败，已回滚: {e}")
        return False


def _do_sync_with_connection(novel_dir, material_id) -> bool:
    """获取连接并执行同步（内部函数）。

    返回：
        True 表示成功，False 表示失败
    """
    try:
        conn = get_db_connection()
    except DatabaseConfigError as e:
        logger.error(str(e))
        return False

    try:
        return _execute_sync(conn, novel_dir, material_id)
    finally:
        conn.close()


def _sync_novel_impl(
    material_id: str,
    provider: str | None = None,
    use_window: bool = False,
    *,
    repair_allowed: bool = False,
) -> StageResult:
    """同步单本小说到数据库。

    参数：
        material_id: 素材 ID
        provider: LLM 服务商（用于修复时的参数传递）
        use_window: 是否使用滑动窗口（用于修复时的参数传递）

    返回：
        StageResult 同步终态。
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        logger.warning(f"跳过: 目录不存在 {novel_dir}")
        return _sync_result(
            material_id,
            RunStatus.FAILED,
            diagnostic=Diagnostic(
                code="material_not_found",
                message=f"素材目录不存在: {material_id}",
                severity="error",
            ),
        )

    # 预检
    try:
        _precheck_schema(material_id, verbose=True)
    except QualityCheckError as e:
        if not repair_allowed:
            return _sync_result(
                material_id,
                RunStatus.FAILED,
                diagnostic=Diagnostic(
                    code="sync_precheck_failed",
                    message=str(e),
                    severity="error",
                    retryable=True,
                    next_action="使用 --repair 明确授权修复后重试",
                ),
            )
        # 合并短摘要、缺失章节和 schema 错误章节
        chapters_to_fix = sorted(set(e.short_chapters) | set(e.missing_chapters) | set(e.schema_error_chapters))
        logger.info(f"[{material_id}] 自动修复 {len(chapters_to_fix)} 章...")
        success, repaired, total = repair_short_summaries(
            material_id,
            short_chapters=chapters_to_fix,  # 传入合并后的章节列表
            provider=provider,
            use_window=use_window,
        )
        if not success:
            logger.warning(f"[{material_id}] 修复失败（成功率 < 80%），需人工干预")
            return _sync_result(
                material_id,
                RunStatus.FAILED,
                diagnostic=Diagnostic(
                    code="sync_repair_failed",
                    message="自动修复未达到成功阈值",
                    severity="error",
                    retryable=True,
                ),
            )

        # 修复成功，再次预检
        logger.info(f"[{material_id}] 修复成功: {repaired}/{total} 章")
        try:
            _precheck_schema(material_id, verbose=True)
        except QualityCheckError:
            # 修复后仍有问题
            remaining_short = get_short_summary_chapters(material_id)
            remaining_missing = get_missing_chapters(material_id, strict=False)
            remaining_schema_error = get_schema_error_chapters(material_id)
            total_remaining = len(remaining_short) + len(remaining_missing) + len(remaining_schema_error)
            logger.warning(
                f"[{material_id}] 修复后仍有 {total_remaining} 章问题"
                f"（{len(remaining_short)} 章短摘要，{len(remaining_missing)} 章缺失，{len(remaining_schema_error)} 章 schema 错误），需人工干预"
            )
            return _sync_result(
                material_id,
                RunStatus.FAILED,
                diagnostic=Diagnostic(
                    code="sync_precheck_failed",
                    message="修复后预检仍未通过",
                    severity="error",
                    retryable=True,
                ),
            )
        except SchemaValidationError:
            return _sync_result(
                material_id,
                RunStatus.FAILED,
                diagnostic=Diagnostic(
                    code="sync_precheck_failed",
                    message="修复后 schema 预检仍未通过",
                    severity="error",
                ),
            )

    except SchemaValidationError as exc:
        return _sync_result(
            material_id,
            RunStatus.FAILED,
            diagnostic=Diagnostic(
                code="sync_precheck_failed",
                message=str(exc),
                severity="error",
            ),
        )

    # 预检通过，执行同步
    if _do_sync_with_connection(novel_dir, material_id):
        return _sync_result(material_id, RunStatus.SUCCESS)
    return _sync_result(
        material_id,
        RunStatus.FAILED,
        diagnostic=Diagnostic(
            code="sync_failed",
            message=f"数据库同步失败: {material_id}",
            severity="error",
            retryable=True,
        ),
    )


def sync_novel(
    material_id: str,
    provider: str | None = None,
    use_window: bool = False,
    *,
    repair_allowed: bool = False,
    dispatcher: RuntimeDispatcher | None = None,
) -> StageResult:
    """同步单本素材并发布最小审计事件。"""
    event_dispatcher = dispatcher or NullDispatcher()
    _emit_sync_audit(event_dispatcher, material_id, phase="started")
    result = _sync_novel_impl(
        material_id,
        provider=provider,
        use_window=use_window,
        repair_allowed=repair_allowed,
    )
    _emit_sync_audit(
        event_dispatcher,
        material_id,
        phase="completed" if result.status is RunStatus.SUCCESS else "failed",
        status=result.status,
    )
    return result


def _emit_sync_audit(
    dispatcher: RuntimeDispatcher,
    material_id: str,
    *,
    phase: str,
    status: RunStatus | None = None,
) -> None:
    context = current_context()
    if context is None:
        return
    now = datetime.now(timezone.utc)
    dispatcher.emit(
        RunEvent(
            event_name="AuditRecorded",
            event_id=new_id("event"),
            occurred_at=now,
            observed_at=now,
            run_id=context.run_id,
            stage_id=context.stage_id,
            command=context.command,
            component="storage",
            operation="storage.sync",
            material_id=material_id,
            status=status,
            attributes={
                "phase": phase,
                "object_type": "material",
                "object_id": material_id,
            },
        )
    )


def sync_all(
    provider: str | None = None,
    use_window: bool = False,
    *,
    repair_allowed: bool = False,
    novels_dir: Path = NOVELS_DIR,
) -> SyncSummary:
    """同步所有小说到数据库。

    参数：
        provider: LLM 服务商（用于修复时的参数传递）
        use_window: 是否使用滑动窗口（用于修复时的参数传递）

    返回：
        SyncSummary 批次结果。
    """
    if not novels_dir.exists():
        logger.warning("没有小说目录")
        return SyncSummary(total=0, succeeded=0, failed=0, skipped=0)

    results = []
    for novel_dir in sorted(novels_dir.iterdir()):
        if novel_dir.is_dir() and novel_dir.name.startswith("nm_"):
            results.append(
                sync_novel(
                    novel_dir.name,
                    provider=provider,
                    use_window=use_window,
                    repair_allowed=repair_allowed,
                )
            )

    return SyncSummary(
        total=len(results),
        succeeded=sum(result.status is RunStatus.SUCCESS for result in results),
        failed=sum(result.status is RunStatus.FAILED for result in results),
        skipped=sum(
            result.status not in {RunStatus.SUCCESS, RunStatus.FAILED}
            for result in results
        ),
        results=tuple(results),
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python sync_core.py <material_id> 或 python sync_core.py all")
        sys.exit(1)

    if sys.argv[1] == "all":
        summary = sync_all()
        print(f"已同步 {summary.succeeded}/{summary.total} 个素材")
        if summary.status is not RunStatus.SUCCESS:
            sys.exit(3 if summary.status is RunStatus.DEGRADED else 1)
    else:
        result = sync_novel(sys.argv[1])
        if result.status is RunStatus.SUCCESS:
            print(f"同步完成: {sys.argv[1]}")
        else:
            print(f"同步失败: {sys.argv[1]}")
            sys.exit(1)
