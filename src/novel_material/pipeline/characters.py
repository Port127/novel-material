"""人物提取：统计驱动的分层人物提取。

分层策略：
1. 统计章节出场人物频率，筛选候选人（>=5章）
2. 分三层处理：
   - 核心层（>=50章）：完整档案（心理分析、弧线、关键事件）
   - 配角层（>=10章）：标准档案（基础信息 + 关系）
   - 次要层（>=5章）：精简档案（仅基础信息）

注意：此脚本在 analyze 完成后运行，需要 chapters.yaml 作为全书视角输入。

模块拆分：
- characters_stats.py：出场频率统计
- characters_selector.py：分层筛选
- characters_profile.py：档案生成 + 增量写入
- characters_layer.py：分批提取
- characters_core.py：入口函数
- characters.py：统一入口
"""
import sys

# 从子模块导入所有函数，向后兼容
from novel_material.pipeline.characters_core import generate_characters
from novel_material.pipeline.characters_stats import (
    CHARACTER_THRESHOLDS,
    CHARACTER_BATCH_SIZE,
    VALID_ROLES,
    _extract_appearance_stats,
)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python characters.py <material_id>")
        sys.exit(1)

    generate_characters(sys.argv[1])