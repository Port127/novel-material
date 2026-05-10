"""进度跟踪器：为流水线提供实时进度、计时和健康状态反馈。"""
import sys
import yaml
import time
import threading
from pathlib import Path
from contextlib import contextmanager

from .logging_config import (
    get_pipeline_logger,
    pause_console_logging,
    resume_console_logging,
)

# 重新导出，保持其他模块导入路径不变
__all__ = ["get_pipeline_logger", "pause_console_logging", "resume_console_logging", "silent_console"]


@contextmanager
def silent_console():
    """上下文管理器：暂停控制台日志，确保异常时也能恢复。

    用于进度条显示期间，防止日志输出干扰。
    """
    pause_console_logging()
    try:
        yield
    finally:
        resume_console_logging()


def _fmt(sec: float) -> str:
    """将秒数格式化为可读时长。"""
    if sec < 60:
        return f"{sec:.0f}s"
    elif sec < 3600:
        return f"{sec / 60:.1f}min"
    else:
        h = int(sec // 3600)
        m = int((sec % 3600) / 60)
        s = int(sec % 60)
        return f"{h}h{m:02d}m{s:02d}s"


def save_run_history(novel_dir: Path, pipeline_name: str, stage_times: list[dict], total_elapsed: float, status: str = "success") -> Path:
    """将流水线运行记录追加到小说目录的 run_history.yaml。"""
    history_file = novel_dir / "run_history.yaml"

    if history_file.exists():
        with open(history_file, "r", encoding="utf-8") as f:
            history = yaml.safe_load(f) or {"runs": []}
    else:
        history = {"runs": []}

    # 统计 tokens 和成本
    total_tokens_in = sum(s.get("tokens_in", 0) for s in stage_times)
    total_tokens_out = sum(s.get("tokens_out", 0) for s in stage_times)
    total_api = sum(s.get("api_calls", 0) for s in stage_times)
    total_errors = sum(s.get("api_errors", 0) for s in stage_times)

    # 成本估算（默认 qwen 价格）
    cost_in = total_tokens_in * 0.0004 / 1000
    cost_out = total_tokens_out * 0.0012 / 1000
    estimated_cost = cost_in + cost_out

    run_record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pipeline": pipeline_name,
        "status": status,
        "total_elapsed_sec": round(total_elapsed, 1),
        "total_elapsed_human": _fmt(total_elapsed),
        "tokens_in": total_tokens_in,
        "tokens_out": total_tokens_out,
        "estimated_cost": round(estimated_cost, 2),
        "api_total": total_api,
        "api_errors": total_errors,
        "api_error_rate": round(total_errors / total_api * 100, 1) if total_api > 0 else 0,
        "stages": [],
    }

    for s in stage_times:
        stage_record = {
            "name": s["name"],
            "elapsed_sec": round(s["elapsed_sec"], 1),
            "elapsed_human": _fmt(s["elapsed_sec"]),
            "pct": round(s["elapsed_sec"] / total_elapsed * 100, 1) if total_elapsed > 0 else 0,
            "api_calls": s.get("api_calls", 0),
            "api_errors": s.get("api_errors", 0),
            "tokens_in": s.get("tokens_in", 0),
            "tokens_out": s.get("tokens_out", 0),
        }
        if s.get("api_calls", 0) > 0:
            stage_record["avg_tokens_per_call"] = round(s.get("tokens_in", 0) / s.get("api_calls", 1), 0)
        run_record["stages"].append(stage_record)

    history["runs"].append(run_record)

    if len(history["runs"]) > 50:
        history["runs"] = history["runs"][-50:]

    with open(history_file, "w", encoding="utf-8") as f:
        yaml.dump(history, f, allow_unicode=True, default_flow_style=False)

    return history_file


class StageTracker:
    """阶段进度跟踪器。"""

    def __init__(
        self,
        total_stages: int,
        stage_name: str,
        stage_num: int = 0,
        material_id: str = None,
        novel_info: dict = None,
    ):
        self.total_stages = total_stages
        self.stage_name = stage_name
        self.stage_num = stage_num
        self.material_id = material_id
        self.novel_info = novel_info or {}
        self.stage_start = time.monotonic()
        self.wall_start = time.monotonic()
        self.api_calls = 0
        self.api_errors = 0
        self._spinner_thread = None
        self._stop_spinner = threading.Event()
        self._footer_printed = False
        self._sub_progress_total = 0
        self._sub_progress_done = 0
        self._prev_completed = 0
        self._prev_time = time.monotonic()
        self._eta_seconds = 0
        self._logger = get_pipeline_logger()
        self._completed_stage_times: list[float] = []
        # Token 统计
        self._tokens_in = 0
        self._tokens_out = 0
        self._call_count = 0

    def __enter__(self):
        self.print_header()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._footer_printed and exc_type is None:
            self.print_footer()
        return False

    @property
    def elapsed_stage(self) -> float:
        return time.monotonic() - self.stage_start

    @property
    def elapsed_total(self) -> float:
        return time.monotonic() - self.wall_start

    def record_tokens(self, in_tokens: int, out_tokens: int):
        """记录 token 消耗（每次 API 调用后调用）。"""
        self._tokens_in += in_tokens
        self._tokens_out += out_tokens
        self._call_count += 1

    def set_sub_progress(self, done: int, total: int) -> None:
        self._sub_progress_total = total
        self._sub_progress_done = done

    def _estimate_eta(self, progress_fraction: float) -> float:
        if progress_fraction <= 0:
            return 0
        elapsed = self.elapsed_total
        total_estimated = elapsed / progress_fraction
        return total_estimated - elapsed

    def _spin(self, msg: str, done_event: threading.Event) -> None:
        chars = ["|", "/", "-", "\\"]
        idx = 0
        while not done_event.is_set():
            elapsed = time.monotonic() - self.wall_start

            parts = [msg]
            parts.append(f"已耗时 {_fmt(elapsed)}")

            # 显示 tokens 消耗
            if self._tokens_in > 0:
                parts.append(f"tokens {self._tokens_in:,}/{self._tokens_out:,}")

            if self._sub_progress_total > 0 and self._sub_progress_done > 0:
                frac = self._sub_progress_done / self._sub_progress_total
                eta = self._estimate_eta(frac)
                if eta > 60:
                    parts.append(f"ETA {_fmt(eta)}")
                parts.append(f"{self._sub_progress_done}/{self._sub_progress_total}")

            spinner = chars[idx % len(chars)]
            sys.stdout.write(f"\r  {spinner} {' | '.join(parts)}")
            sys.stdout.flush()
            done_event.wait(0.25)
            idx += 1
        sys.stdout.write("\r" + " " * 100 + "\r")
        sys.stdout.flush()

    def start_spinner(self, msg: str = "LLM 调用中") -> None:
        pause_console_logging()
        self._stop_spinner.clear()
        self._spinner_thread = threading.Thread(
            target=self._spin, args=(msg, self._stop_spinner), daemon=True
        )
        self._spinner_thread.start()

    def stop_spinner(self) -> None:
        self._stop_spinner.set()
        if self._spinner_thread:
            self._spinner_thread.join(timeout=1)
            self._spinner_thread = None
        resume_console_logging()

    def record_api_call(self, success: bool = True) -> None:
        self.api_calls += 1
        if not success:
            self.api_errors += 1

    def print_header(self) -> None:
        # 显示小说基本信息
        if self.novel_info:
            title = self.novel_info.get("name", self.material_id or "未知")
            chapters = self.novel_info.get("chapter_count", "?")
            words = self.novel_info.get("word_count", "?")
            status = self.novel_info.get("status", "?")
            info_line = f"  小说: {title} | {chapters} 章 | {words} 字 | 状态: {status}"
            print(info_line)
            self._logger.info(info_line)

        tag = ""
        if self.total_stages > 0 and self.stage_num > 0:
            tag = f"[{self.stage_num}/{self.total_stages}] "
        header = f"\n{'=' * 60}\n{tag}{self.stage_name}\n{'=' * 60}"
        print(header)
        self._logger.info(f"=== 阶段开始: {tag}{self.stage_name} ===")

    def print_footer(self) -> None:
        self._footer_printed = True
        elapsed = self.elapsed_stage

        footer = f"\n--- {self.stage_name} 完成 | 耗时: {_fmt(elapsed)}"
        if self._tokens_in > 0:
            footer += f" | tokens: in={self._tokens_in:,} out={self._tokens_out:,}"
        footer += " ---"
        print(footer)

        # 详细日志
        log_msg = (
            f"阶段完成: {self.stage_name} | elapsed={elapsed:.1f}s | "
            f"tokens_in={self._tokens_in} tokens_out={self._tokens_out} | "
            f"api_calls={self._call_count}"
        )
        if self.api_errors > 0:
            log_msg += f" | errors={self.api_errors}"
        self._logger.info(log_msg)

        if self.api_calls > 0:
            err_rate = self.api_errors / self.api_calls * 100
            status = "健康" if err_rate < 10 else "注意" if err_rate < 30 else "警告"
            health = f"    API: {self.api_calls} 次调用 | {self.api_errors} 错误 ({err_rate:.1f}%) | {status}"
            print(health)
            self._logger.info(f"    API 健康状态: {self.api_calls} 调用, {self.api_errors} 错误, {status}")

    def print_summary(self, stages: list[tuple[str, float]] = None) -> None:
        total = self.elapsed_total
        lines = [
            f"\n{'=' * 60}",
            f"总耗时: {_fmt(total)}",
            f"API 总调用: {self._call_count} 次",
        ]

        if self._tokens_in > 0:
            lines.append(f"tokens 输入: {self._tokens_in:,} 输出: {self._tokens_out:,}")

        # 成本估算（使用默认 qwen 价格）
        if self._tokens_in > 0 and self._tokens_out > 0:
            cost_in = self._tokens_in * 0.0004 / 1000
            cost_out = self._tokens_out * 0.0012 / 1000
            estimated_cost = cost_in + cost_out
            lines.append(f"预估成本: ¥{estimated_cost:.2f}")

        if self._call_count > 0:
            avg = total / self._call_count
            lines.append(f"平均每次 API 耗时: {_fmt(avg)}")

        if stages:
            lines.append("")
            lines.append("各阶段耗时:")
            for name, sec in stages:
                pct = sec / total * 100 if total > 0 else 0
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                lines.append(f"  {name:20s} {_fmt(sec):>8s}  {pct:5.1f}%  {bar}")

        lines.append(f"{'=' * 60}")
        print("\n".join(lines))
        self._logger.info(f"--- 流水线完成 | 总耗时: {_fmt(total)} | API: {self._call_count} 调用, tokens: {self._tokens_in}/{self._tokens_out} ---")


@contextmanager
def stage_context(total_stages: int, stage_num: int, stage_name: str):
    """上下文管理器。"""
    tracker = StageTracker(total_stages, stage_name, stage_num)
    tracker.print_header()
    try:
        yield tracker
    finally:
        tracker.print_footer()


class PipelineRunner:
    """流水线运行器。"""

    def __init__(self, name: str, total_stages: int, novel_dir: Path = None, material_id: str = None, novel_info: dict = None):
        # 延迟导入避免循环依赖（llm.py 已导入 progress.get_pipeline_logger）
        from novel_material.infra.llm import clear_call_details
        clear_call_details()  # 每次流水线启动时清理历史调用记录

        self.name = name
        self.total_stages = total_stages
        self.wall_start = time.monotonic()
        self.material_id = material_id
        self.novel_info = novel_info or {}
        self._tracker = StageTracker(total_stages, name, material_id=material_id, novel_info=novel_info)
        self._stage_times: list[tuple[str, float]] = []
        self._stage_details: list[dict] = []
        self._novel_dir = novel_dir
        self._logger = get_pipeline_logger()
        self._logger.info(f"=== 流水线启动: {name} ({total_stages} 个阶段) ===")

        if novel_info:
            title = novel_info.get("name", material_id or "未知")
            chapters = novel_info.get("chapter_count", "?")
            words = novel_info.get("word_count", "?")
            self._logger.info(f"  小说: {title} | {chapters} 章 | {words} 字")

    def stage(self, stage_num: int, stage_name: str) -> StageTracker:
        tr = StageTracker(self.total_stages, stage_name, stage_num, material_id=self.material_id, novel_info=self.novel_info)
        tr.wall_start = self.wall_start
        return tr

    def record_stage_complete(self, stage_name: str, elapsed: float, api_calls: int = 0, api_errors: int = 0, tokens_in: int = 0, tokens_out: int = 0) -> None:
        self._stage_times.append((stage_name, elapsed))
        self._stage_details.append({
            "name": stage_name,
            "elapsed_sec": elapsed,
            "api_calls": api_calls,
            "api_errors": api_errors,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        })

    def print_final_summary(self) -> None:
        self._tracker.print_summary(self._stage_times)
        self._logger.info(f"=== 流水线完成: {self.name} ===")

    def save_history(self, status: str = "success") -> Path | None:
        if not self._novel_dir:
            return None
        path = save_run_history(
            novel_dir=self._novel_dir,
            pipeline_name=self.name,
            stage_times=self._stage_details,
            total_elapsed=self._tracker.elapsed_total,
            status=status,
        )
        print(f"\n运行历史已写入: {path}")
        self._logger.info(f"运行历史已写入: {path}")
        return path