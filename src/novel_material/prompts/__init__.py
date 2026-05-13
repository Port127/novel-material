"""Prompts 契约层：提示词模板加载与模板变量替换。

导出：
- Prompt: 提示词类
- load_prompt: 加载单个提示词
"""

from novel_material.prompts.prompt_loader import Prompt, load_prompt

__all__ = [
    "Prompt",
    "load_prompt",
]