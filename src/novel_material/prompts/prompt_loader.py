"""提示词加载器：从 prompts/*.yaml 读取提示词模板，支持模板变量替换。"""

import yaml
import re
from pathlib import Path
from dataclasses import dataclass, field

# 提示词目录
_PROMPTS_DIR = Path(__file__).parent

# 模板变量替换模式：{{variable_name}}
_TEMPLATE_PATTERN = re.compile(r"\{\{(\w+)\}\}")


@dataclass
class Prompt:
    """提示词模板。"""
    name: str
    system_prompt: str
    chapter_schema: str | None = None
    chapter_schema_with_window: str | None = None
    batch_schema: str | None = None
    evaluation_schema: str | None = None
    # 子提示词（如 characters.yaml 的 core_prompt/supporting_prompt/minor_prompt）
    sub_prompts: dict[str, "Prompt"] = field(default_factory=dict)

    @classmethod
    def load(cls, prompt_name: str) -> "Prompt":
        """加载单个提示词模板。

        Args:
            prompt_name: 提示词名称（如 "analyze"、"outline"）

        Returns:
            Prompt 实例，system_prompt 已完成模板变量替换

        Raises:
            FileNotFoundError: 提示词文件不存在
        """
        prompt_file = _PROMPTS_DIR / f"{prompt_name}.yaml"
        if not prompt_file.exists():
            raise FileNotFoundError(f"提示词文件不存在: {prompt_file}")

        with open(prompt_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        # 处理子提示词（如 characters.yaml）
        sub_prompts = {}
        for key in ["core_prompt", "supporting_prompt", "minor_prompt", "premise_prompt", "beats_prompt"]:
            if key in data and data[key]:
                sub_data = data[key]
                sub_prompts[key] = cls(
                    name=f"{prompt_name}.{key}",
                    system_prompt=_replace_template_vars(sub_data.get("system_prompt", "")),
                )

        return cls(
            name=prompt_name,
            system_prompt=_replace_template_vars(data.get("system_prompt", "")),
            chapter_schema=_replace_template_vars(data.get("chapter_schema")),
            chapter_schema_with_window=_replace_template_vars(data.get("chapter_schema_with_window")),
            batch_schema=_replace_template_vars(data.get("batch_schema")),
            evaluation_schema=_replace_template_vars(data.get("evaluation_schema")),
            sub_prompts=sub_prompts,
        )

    def get_sub_prompt(self, sub_name: str) -> "Prompt | None":
        """获取子提示词。

        Args:
            sub_name: 子提示词名称（如 "core_prompt"）

        Returns:
            Prompt 实例或 None
        """
        return self.sub_prompts.get(sub_name)


def load_prompt(prompt_name: str) -> Prompt:
    """加载单个提示词模板（便捷函数）。"""
    return Prompt.load(prompt_name)


def _replace_template_vars(text: str | None) -> str | None:
    """替换模板变量。

    将 {{summary_min}} 替换为从 FieldSchema.load("summary").min_length 获取的值。

    Args:
        text: 包含模板变量的文本

    Returns:
        替换后的文本，如果输入为 None 则返回 None
    """
    if text is None:
        return None

    def replacer(match: re.Match) -> str:
        var_name = match.group(1)

        # 解析变量名：field_attribute 格式
        # 如 summary_min → field="summary", attribute="min_length"
        # 如 character_description_core_max → field="character_description_core", attribute="max_length"
        if "_" in var_name:
            # 找到最后一个属性后缀
            for attr_suffix in ["_min", "_max"]:
                if var_name.endswith(attr_suffix):
                    field_name = var_name[:-len(attr_suffix)]
                    attribute = "min_length" if attr_suffix == "_min" else "max_length"
                    break
            else:
                # 无法解析，返回原文本
                return match.group(0)
        else:
            # 无法解析，返回原文本
            return match.group(0)

        # 从 FieldSchema 加载值
        try:
            from novel_material.schema import FieldSchema
            field = FieldSchema.load(field_name)
            value = getattr(field, attribute, None)
            if value is not None:
                return str(value)
        except KeyError:
            pass  # 字段不存在，返回原文本

        return match.group(0)

    return _TEMPLATE_PATTERN.sub(replacer, text)