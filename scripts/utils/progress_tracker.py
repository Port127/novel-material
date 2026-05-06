"""进度跟踪器：为流水线提供实时进度、计时和健康状态反馈。

功能：
- 阶段计时（阶段耗时、总耗时）
- 实时旋转指示器（LLM 调用时显示进度 + 已耗时）
- ETA 预估（基于已完成阶段的平均耗时）
- 健康状态监控（API 调用次数、错误率）
- 日志文件输出（供后续分析优化）
- 每部小说运行历史汇总（写入 novel_dir/run_history.yaml）
- 批量子进度跟踪（章节批次进度等）
"""
import sys
import yaml
import time
import threading
import logging
from pathlib import Path
from contextlib import contextmanager

_ROOT = Path(__file__).resolve().parent.parent.parent
_LOG_DIR = _ROOT / "logs"
_LOG_DIR.mkdir(exist_ok=True)

# 当前运行的日志文件路径（全局单例）
_CURRENT_LOG_FILE: Path | None = None


def get_pipeline_logger() -> logging.Logger:
    """获取 pipeline logger，供其他模块（如 llm_client）复用同一日志文件。"""
    return _setup_logger()


def _setup_logger() -> logging.Logger:
    """配置日志记录器，同时输出到控制台和日志文件。

    单例模式：一次运行只创建一个日志文件，后续调用返回同一个 logger。
    """
    global _CURRENT_LOG_FILE
    logger = logging.getLogger("pipeline")
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)  # 改为 DEBUG，捕获所有级别的日志

    # 文件处理器：一次运行只创建一个文件
    if _CURRENT_LOG_FILE is None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        _CURRENT_LOG_FILE = _LOG_DIR / f"pipeline_{timestamp}.log"

    file_handler = logging.FileHandler(_CURRENT_LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
    )
    file_handler.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)

    # 控制台处理器：只显示 INFO 及以上，简洁格式（不加级别前缀）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    return logger


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
    """将流水线运行记录追加到小说目录的 run_history.yaml。

    Args:
        novel_dir: 小说目录路径
        pipeline_name: 流水线名称（如 "完整流水线"）
        stage_times: 各阶段耗时列表，每项为 {"name": str, "elapsed_sec": float, "api_calls": int, "api_errors": int}
        total_elapsed: 总耗时（秒）
        status: "success" / "failed" / "partial"

    Returns:
        写入的文件路径
    """
    history_file = novel_dir / "run_history.yaml"

    # 加载已有记录
    if history_file.exists():
        with open(history_file, "r", encoding="utf-8") as f:
            history = yaml.safe_load(f) or {"runs": []}
    else:
        history = {"runs": []}

    # 构建本次记录
    run_record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pipeline": pipeline_name,
        "status": status,
        "total_elapsed_sec": round(total_elapsed, 1),
        "total_elapsed_human": _fmt(total_elapsed),
        "stages": [],
    }

    total_api = 0
    total_errors = 0
    for s in stage_times:
        total_api += s.get("api_calls", 0)
        total_errors += s.get("api_errors", 0)
        run_record["stages"].append({
            "name": s["name"],
            "elapsed_sec": round(s["elapsed_sec"], 1),
            "elapsed_human": _fmt(s["elapsed_sec"]),
            "pct": round(s["elapsed_sec"] / total_elapsed * 100, 1) if total_elapsed > 0 else 0,
            "api_calls": s.get("api_calls", 0),
            "api_errors": s.get("api_errors", 0),
        })

    run_record["api_total"] = total_api
    run_record["api_errors"] = total_errors
    run_record["api_error_rate"] = round(total_errors / total_api * 100, 1) if total_api > 0 else 0

    history["runs"].append(run_record)

    # 限制只保留最近 50 条记录，避免文件过大
    if len(history["runs"]) > 50:
        history["runs"] = history["runs"][-50:]

    with open(history_file, "w", encoding="utf-8") as f:
        yaml.dump(history, f, allow_unicode=True, default_flow_style=False)

    return history_file


class StageTracker:
    """阶段进度跟踪器。

    提供：
    - 阶段名称和序号（如 [2/6] 章级分析）
    - 阶段内子进度（如批次进度）
    - 计时（阶段耗时、总耗时）
    - ETA 预估（基于已完成阶段耗时）
    - 健康状态（API 调用次数、错误次数）

    用法：
        with StageTracker(6, "章级分析", 2) as tr:
            tr.start_spinner("LLM 分析中")
            do_work()
            tr.stop_spinner()
            tr.record_api_call()
    """

    def __init__(self, total_stages: int, stage_name: str, stage_num: int = 0):
        self.total_stages = total_stages
        self.stage_name = stage_name
        self.stage_num = stage_num
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
        self._logger = _setup_logger()

        # 用于 ETA 计算：记录已完成阶段的耗时
        self._completed_stage_times: list[float] = []

    def __enter__(self):
        self.print_header()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if not self._footer_printed and exc_type is None:
            self.print_footer()
        return False  # 不吞异常

    @property
    def elapsed_stage(self) -> float:
        """当前阶段耗时（秒）"""
        return time.monotonic() - self.stage_start

    @property
    def elapsed_total(self) -> float:
        """总耗时（秒）"""
        return time.monotonic() - self.wall_start

    def _format_duration(self, seconds: float) -> str:
        """将秒数格式化为可读时长。"""
        return _fmt(seconds)

    def set_sub_progress(self, done: int, total: int) -> None:
        """设置阶段内子进度（如章节批次进度）。

        调用后旋转指示器会显示子进度。
        """
        self._sub_progress_total = total
        self._sub_progress_done = done

    def _estimate_eta(self, progress_fraction: float) -> float:
        """基于当前进度和已耗时，预估剩余时间。"""
        if progress_fraction <= 0:
            return 0
        elapsed = self.elapsed_total
        total_estimated = elapsed / progress_fraction
        return total_estimated - elapsed

    def _spin(self, msg: str, done_event: threading.Event) -> None:
        """后台旋转指示器：显示 API 调用中 + 已耗时 + ETA + 子进度。"""
        chars = ["|", "/", "-", "\\"]
        idx = 0
        while not done_event.is_set():
            elapsed = time.monotonic() - self.wall_start

            parts = [msg]
            parts.append(f"已耗时 {_fmt(elapsed)}")

            # ETA 预估
            if self._sub_progress_total > 0 and self._sub_progress_done > 0:
                frac = self._sub_progress_done / self._sub_progress_total
                eta = self._estimate_eta(frac)
                if eta > 0:
                    parts.append(f"ETA {_fmt(eta)}")
                parts.append(f"{self._sub_progress_done}/{self._sub_progress_total}")

            spinner = chars[idx % len(chars)]
            sys.stdout.write(f"\r  {spinner} {' | '.join(parts)}")
            sys.stdout.flush()
            done_event.wait(0.25)
            idx += 1
        # 结束时清除旋转行
        sys.stdout.write("\r" + " " * 100 + "\r")
        sys.stdout.flush()

    def start_spinner(self, msg: str = "LLM 调用中") -> None:
        """启动后台旋转指示器。"""
        self._stop_spinner.clear()
        self._spinner_thread = threading.Thread(
            target=self._spin, args=(msg, self._stop_spinner), daemon=True
        )
        self._spinner_thread.start()

    def stop_spinner(self) -> None:
        """停止旋转指示器。"""
        self._stop_spinner.set()
        if self._spinner_thread:
            self._spinner_thread.join(timeout=1)
            self._spinner_thread = None

    def record_api_call(self, success: bool = True) -> None:
        """记录一次 API 调用。"""
        self.api_calls += 1
        if not success:
            self.api_errors += 1

    def print_header(self) -> None:
        """打印阶段开始头部。"""
        tag = ""
        if self.total_stages > 0 and self.stage_num > 0:
            tag = f"[{self.stage_num}/{self.total_stages}] "
        header = f"\n{'=' * 60}\n{tag}{self.stage_name}\n{'=' * 60}"
        print(header)
        self._logger.info(f"--- 阶段开始: {tag}{self.stage_name} ---")

    def print_footer(self) -> None:
        """打印阶段结束尾部，含健康状态。"""
        self._footer_printed = True
        elapsed = self.elapsed_stage
        footer = f"\n--- {self.stage_name} 完成 | 耗时: {_fmt(elapsed)} ---"
        print(footer)
        self._logger.info(f"--- 阶段完成: {self.stage_name} | 耗时: {_fmt(elapsed)} ---")

        if self.api_calls > 0:
            err_rate = self.api_errors / self.api_calls * 100
            status = "健康" if err_rate < 10 else "注意" if err_rate < 30 else "警告"
            health = f"    API: {self.api_calls} 次调用 | {self.api_errors} 错误 ({err_rate:.1f}%) | {status}"
            print(health)
            self._logger.info(f"    API 健康状态: {self.api_calls} 调用, {self.api_errors} 错误, {status}")

    def print_summary(self, stages: list[tuple[str, float]] = None) -> None:
        """打印总耗时摘要，含各阶段耗时明细。

        Args:
            stages: 可选，[(阶段名, 耗时秒), ...] 列表，用于打印各阶段耗时明细
        """
        total = self.elapsed_total
        lines = [
            f"\n{'=' * 60}",
            f"总耗时: {_fmt(total)}",
            f"API 总调用: {self.api_calls} 次",
            f"API 总错误: {self.api_errors} 次",
        ]
        if self.api_calls > 0:
            avg = total / self.api_calls
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
        self._logger.info(f"--- 流水线完成 | 总耗时: {_fmt(total)} | API: {self.api_calls} 调用, {self.api_errors} 错误 ---")


@contextmanager
def stage_context(total_stages: int, stage_num: int, stage_name: str):
    """上下文管理器：自动打印阶段头部/尾部 + 计时。

    用法：
        with stage_context(6, 2, "章级分析阶段") as tracker:
            tracker.start_spinner()
            do_work()
            tracker.stop_spinner()
            tracker.record_api_call()
    """
    tracker = StageTracker(total_stages, stage_name, stage_num)
    tracker.print_header()
    try:
        yield tracker
    finally:
        tracker.print_footer()


class PipelineRunner:
    """流水线运行器：管理多个阶段的进度跟踪、ETA 和日志。

    用法：
        runner = PipelineRunner("完整流水线", 6, novel_dir=path)
        with runner.stage(1, "入库") as tr:
            do_ingest()
            tr.record_api_call()
        with runner.stage(2, "章级分析") as tr:
            tr.start_spinner()
            do_analysis()
            tr.stop_spinner()
            tr.record_api_call()
        runner.print_final_summary()
        runner.save_history()
    """

    def __init__(self, name: str, total_stages: int, novel_dir: Path = None):
        self.name = name
        self.total_stages = total_stages
        self.wall_start = time.monotonic()
        self._tracker = StageTracker(total_stages, name)
        self._stage_times: list[tuple[str, float]] = []
        self._stage_details: list[dict] = []
        self._novel_dir = novel_dir
        self._logger = _setup_logger()
        self._logger.info(f"=== 流水线启动: {name} ({total_stages} 个阶段) ===")

    def stage(self, stage_num: int, stage_name: str) -> StageTracker:
        """创建一个阶段跟踪器。

        Args:
            stage_num: 阶段序号（1-based）
            stage_name: 阶段名称
        """
        tr = StageTracker(self.total_stages, stage_name, stage_num)
        tr.wall_start = self.wall_start  # 共享全局起始时间
        return tr

    def record_stage_complete(self, stage_name: str, elapsed: float, api_calls: int = 0, api_errors: int = 0) -> None:
        """记录一个阶段的完成，用于后续 ETA、摘要和运行历史。"""
        self._stage_times.append((stage_name, elapsed))
        self._stage_details.append({
            "name": stage_name,
            "elapsed_sec": elapsed,
            "api_calls": api_calls,
            "api_errors": api_errors,
        })

    def print_final_summary(self) -> None:
        """打印最终总摘要。"""
        self._tracker.print_summary(self._stage_times)
        self._logger.info(f"=== 流水线完成: {self.name} ===")

    def save_history(self, status: str = "success") -> Path | None:
        """保存运行历史到小说目录的 run_history.yaml。

        Args:
            status: "success" / "failed" / "partial"
        """
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

