"""进度管理器：统一管理流水线进度阶段。

核心功能：
- register_stage: 注册阶段
- update: 更新进度

用于 ExecutionContext 统一携带进度信息。
"""

from dataclasses import dataclass, field
from typing import Callable


@dataclass
class ProgressStage:
    """进度阶段定义。"""
    name: str
    total: int | None = None
    done: int = 0
    index: int = 0


class ProgressManager:
    """进度管理器，统一管理流水线进度阶段。"""

    def __init__(self, update_callback: Callable[[int, int, int, str], None] | None = None):
        """初始化进度管理器。

        Args:
            update_callback: 进度更新回调函数 (stage_idx, done, total, desc)
        """
        self._stages: list[ProgressStage] = []
        self._current_stage: int = 0
        self._update_callback = update_callback

    def register_stage(self, name: str, total: int | None = None) -> int:
        """注册进度阶段。

        Args:
            name: 阶段名称
            total: 阶段总数（可选）

        Returns:
            int: 阶段索引
        """
        stage = ProgressStage(
            name=name,
            total=total,
            done=0,
            index=len(self._stages),
        )
        self._stages.append(stage)
        return stage.index

    def update(self, stage_idx: int, done: int, desc: str = "") -> None:
        """更新进度。

        Args:
            stage_idx: 阶段索引
            done: 已完成数量
            desc: 描述信息
        """
        if stage_idx < 0 or stage_idx >= len(self._stages):
            return

        stage = self._stages[stage_idx]
        stage.done = done

        if self._update_callback:
            total = stage.total or 0
            self._update_callback(stage_idx, done, total, desc)

    def get_stage(self, stage_idx: int) -> ProgressStage | None:
        """获取阶段信息。

        Args:
            stage_idx: 阶段索引

        Returns:
            ProgressStage | None: 阶段信息
        """
        if stage_idx < 0 or stage_idx >= len(self._stages):
            return None
        return self._stages[stage_idx]

    def total_stages(self) -> int:
        """获取总阶段数。"""
        return len(self._stages)

    def current_stage_name(self) -> str:
        """获取当前阶段名称。"""
        if self._current_stage < len(self._stages):
            return self._stages[self._current_stage].name
        return ""


__all__ = ["ProgressManager", "ProgressStage"]