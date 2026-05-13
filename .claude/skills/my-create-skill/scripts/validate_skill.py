#!/usr/bin/env python3
"""validate_skill.py — 校验 SKILL.md 是否符合团队约定。

用法: python scripts/validate_skill.py <path-to-SKILL.md>
说明: 此脚本位于 skill 目录的 scripts/ 下，相对于 SKILL.md 执行。

返回 0 表示通过，1 表示有错误。
"""

import re
import sys
from pathlib import Path


def load_frontmatter(text: str) -> tuple[dict, str]:
    """解析 YAML frontmatter，返回 (fields, body)。"""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    body = parts[2].strip()
    fm_text = parts[1].strip()
    fields = {}
    current_key = None
    current_value_lines = []

    def flush():
        nonlocal current_key, current_value_lines
        if current_key:
            value = "\n".join(current_value_lines).strip().strip("'\"")
            fields[current_key] = value
        current_key = None
        current_value_lines = []

    for line in fm_text.splitlines():
        if line.strip().startswith("#"):
            continue
        # 新 key-value 行（不以空白开头）
        if line and not line[0].isspace() and ":" in line:
            flush()
            key, _, value = line.partition(":")
            current_key = key.strip()
            stripped = value.strip()
            if stripped.startswith(">-") or stripped.startswith(">") or stripped.startswith("|"):
                current_value_lines = [stripped[1:].lstrip()]  # 去掉 > 或 >-
            elif stripped:
                current_value_lines = [stripped.strip("'\"")]
            else:
                current_value_lines = []
        elif current_key and line.strip():
            # 多行 value 的延续
            current_value_lines.append(line.strip())

    flush()
    return fields, body


def validate(skill_path: str) -> list[str]:
    """校验 SKILL.md，返回错误列表。"""
    path = Path(skill_path)
    if not path.exists():
        return [f"文件不存在: {skill_path}"]

    text = path.read_text(encoding="utf-8")
    errors = []

    # 1. Frontmatter
    fields, body = load_frontmatter(text)

    # name
    name = fields.get("name", "")
    if not name:
        errors.append("缺少 name 字段")
    else:
        if len(name) > 64:
            errors.append(f"name 超长: {len(name)} > 64")
        if not re.match(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$", name):
            errors.append(f"name 格式错误: {name}（应为 kebab-case）")
        if name != path.parent.name and path.parent.name != "scripts":
            pass  # 校验目录名一致性（非致命）

    # description
    desc = fields.get("description", "")
    if not desc:
        errors.append("缺少 description 字段")
    elif len(desc) > 1024:
        errors.append(f"description 超长: {len(desc)} > 1024")

    if desc and "手动触发" not in desc and "仅当用户明确" not in desc:
        errors.append("description 缺少手动触发声明")

    # 非标准字段
    forbidden_fields = {"when_to_use", "argument-hint", "arguments"}
    for f in forbidden_fields:
        if f in fields:
            errors.append(f"存在非标准 frontmatter 字段: {f}")

    # 2. 触发约束段落
    if "## 触发约束" not in body:
        errors.append("body 缺少 '## 触发约束' 段落")
    if "### ⛔ 不触发的场景" not in body:
        errors.append("body 缺少 '### ⛔ 不触发的场景'")
    if "### ✅ 触发条件" not in body:
        errors.append("body 缺少 '### ✅ 触发条件'")

    # 3. 第二人称检查 — 只检测明显的第二人称命令式用法
    # 排除中文场景中的惯用表达（"在你的流水线中"、"你的项目"等）
    second_person_en = re.findall(r"(?:You should|You must|You need to|you'll need|you can|You can)", body)
    if second_person_en:
        errors.append(f"body 中疑似使用第二人称: {second_person_en[:3]}")

    # 4. 行数检查
    lines = body.splitlines()
    if len(lines) > 500:
        errors.append(f"body 超长: {len(lines)} > 500 行")

    return errors


def main():
    if len(sys.argv) < 2:
        print("用法: python validate_skill.py <path-to-SKILL.md>")
        sys.exit(1)

    skill_path = sys.argv[1]
    errors = validate(skill_path)

    if not errors:
        print("✅ 校验通过")
        sys.exit(0)
    else:
        print(f"❌ 发现 {len(errors)} 个问题:")
        for i, err in enumerate(errors, 1):
            print(f"  {i}. {err}")
        sys.exit(1)


if __name__ == "__main__":
    main()
