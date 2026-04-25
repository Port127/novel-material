#!/usr/bin/env python3
"""
validate_yaml.py — 通用 YAML 校验脚本（v2.0）

基于 Schema 定义校验事件文件和其他产出文件。

用法:
    python scripts/core/validate_yaml.py event <material_id>          # 校验全部事件
    python scripts/core/validate_yaml.py event <material_id> ev001   # 校验单个/匹配前缀
    python scripts/core/validate_yaml.py meta <material_id>           # 校验 meta.yaml
    python scripts/core/validate_yaml.py all <material_id>            # 校验全部产出

输出:
    校验报告（stdout），失败文件列表，exit code 0=全部通过, 1=有失败
"""

import argparse
import sys
import yaml
import re
from pathlib import Path
from dataclasses import dataclass
from typing import Callable, Any


# ====================================================================
# Schema Loader（从 schema YAML 提取字段定义）
# ====================================================================

@dataclass
class FieldSpec:
    """字段规格"""
    type_str: str
    type_checker: Callable[[Any], bool]
    required: bool
    value_domain: str | None
    min: int | float | None
    max: int | float | None
    min_length: int | None
    max_length: int | None
    length: int | None
    pattern: str | None
    default: Any
    description: str


class SchemaLoader:
    """从 schema YAML 文件加载字段定义"""

    TYPE_CHECKERS: dict[str, Callable[[Any], bool]] = {
        'str': lambda v: isinstance(v, str),
        'int': lambda v: isinstance(v, int) and not isinstance(v, bool),
        'bool': lambda v: isinstance(v, bool),
        'list[str]': lambda v: isinstance(v, list) and all(isinstance(x, str) for x in v),
        'list[int]': lambda v: isinstance(v, list) and all(isinstance(x, int) and not isinstance(x, bool) for x in v),
        'list[dict]': lambda v: isinstance(v, list) and all(isinstance(x, dict) for x in v),
        'dict': lambda v: isinstance(v, dict),
        'any': lambda v: True,  # 任意类型
    }

    def __init__(self, schema_path: Path):
        self.schema_path = schema_path
        self.schema = self._load_schema()
        self.field_defs = self._extract_definitions()
        self.schema_version = self.schema.get('schema_version', '1.0')

    def _load_schema(self) -> dict:
        """加载 schema YAML"""
        if not self.schema_path.exists():
            raise FileNotFoundError(f"Schema 文件不存在: {self.schema_path}")
        with open(self.schema_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def _extract_definitions(self) -> dict[str, FieldSpec]:
        """从 schema 提取字段定义字典"""
        defs = {}
        schema_def = self.schema.get('definitions', {})

        # 合并所有分组到单一字段字典
        for group_name, group_fields in schema_def.items():
            if not isinstance(group_fields, dict):
                continue
            for field_name, field_spec in group_fields.items():
                if field_name in defs:
                    # 字段已定义，跳过（优先保留 core 组的定义）
                    continue
                defs[field_name] = self._parse_field_spec(field_name, field_spec)

        return defs

    def _parse_field_spec(self, field_name: str, spec: dict) -> FieldSpec:
        """解析单个字段规格"""
        type_str = spec.get('type', 'str')
        type_checker = self.TYPE_CHECKERS.get(type_str, lambda v: True)
        value_domain_raw = spec.get('value_domain', '')

        # 解析值域引用： "tags.yaml → event_type" -> "event_type"
        value_domain = None
        if value_domain_raw and '→' in value_domain_raw:
            value_domain = value_domain_raw.split('→')[1].strip()
        elif value_domain_raw:
            value_domain = value_domain_raw

        return FieldSpec(
            type_str=type_str,
            type_checker=type_checker,
            required=spec.get('required', False),
            value_domain=value_domain,
            min=spec.get('min'),
            max=spec.get('max'),
            min_length=spec.get('min_length'),
            max_length=spec.get('max_length'),
            length=spec.get('length'),
            pattern=spec.get('pattern'),
            default=spec.get('default'),
            description=spec.get('description', ''),
        )

    def get_required_fields(self) -> list[str]:
        """获取所有必填字段名"""
        return [name for name, spec in self.field_defs.items() if spec.required]

    def get_field_spec(self, field_name: str) -> FieldSpec | None:
        """获取指定字段的规格"""
        return self.field_defs.get(field_name)


# ====================================================================
# Tags Domain Loader（解析 tags.yaml 分层结构）
# ====================================================================

class TagsDomainLoader:
    """加载 tags.yaml 并解析分层值域"""

    def __init__(self, tags_path: Path):
        self.tags_path = tags_path
        self.tags_data = self._load_tags()
        self.domains = self._extract_domains()

    def _load_tags(self) -> dict:
        if not self.tags_path.exists():
            return {}
        with open(self.tags_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    def _extract_domains(self) -> dict[str, set]:
        """提取每个维度的所有有效值

        Handles:
        - core + domains 结构（如 event_type, conflict）
        - 直接 values 结构（如 stakes, relationship）
        """
        result = {}

        for dimension, info in self.tags_data.items():
            if not isinstance(info, dict):
                continue

            values = set()

            # core + domains 结构
            if 'core' in info:
                core_values = info.get('core', [])
                if isinstance(core_values, list):
                    values.update(str(v) for v in core_values)

                domains = info.get('domains', {})
                if isinstance(domains, dict):
                    for domain_name, domain_info in domains.items():
                        if domain_name == 'custom':
                            # custom 区域动态扩展，不强制校验
                            continue
                        if isinstance(domain_info, dict) and 'values' in domain_info:
                            domain_values = domain_info.get('values', [])
                            if isinstance(domain_values, list):
                                values.update(str(v) for v in domain_values)

            # 直接 values 结构
            elif 'values' in info:
                vals = info.get('values', [])
                if isinstance(vals, list):
                    values.update(str(v) for v in vals)

            if values:
                result[dimension] = values

        return result

    def get_domain_values(self, dimension: str) -> set:
        """获取指定维度的所有有效值"""
        return self.domains.get(dimension, set())

    def has_domain(self, dimension: str) -> bool:
        """检查维度是否存在"""
        return dimension in self.domains


# ====================================================================
# Event Validator（基于 schema 校验事件文件）
# ====================================================================

class EventValidator:
    """基于 schema 的事件校验器"""

    def __init__(self, schema_loader: SchemaLoader, tags_loader: TagsDomainLoader,
                 chapter_titles: set | None, lenient: bool = False):
        self.schema_loader = schema_loader
        self.tags_loader = tags_loader
        self.chapter_titles = chapter_titles
        self.lenient = lenient

    def validate(self, event_path: Path) -> list[str]:
        """校验单个事件文件"""
        errors = []
        warnings = []

        # 1. 解析 YAML
        try:
            with open(event_path, 'r', encoding='utf-8') as f:
                raw = yaml.safe_load(f)
        except yaml.YAMLError as e:
            return [f"YAML 解析失败: {e}"]

        if raw is None:
            return ["文件为空"]

        if not isinstance(raw, dict):
            return [f"顶层不是字典，实际类型: {type(raw).__name__}"]

        # 2. Legacy 兼容：flatten 嵌套格式
        event = self._flatten_event(raw)

        # 3. 宽容模式：自动转换单值为列表
        if self.lenient:
            event = self._auto_coerce_types(event)

        # 4. 遍历 schema 定义的所有字段
        for field_name, field_spec in self.schema_loader.field_defs.items():
            value = event.get(field_name)

            # 必填检查
            if field_spec.required and value is None:
                # 宽容模式下部分字段可缺失
                if self.lenient and self._is_lenient_optional(field_name):
                    warnings.append(f"缺少字段: {field_name}（宽容模式：警告）")
                    continue
                errors.append(f"缺少必填字段: {field_name}")
                continue

            # 可选字段缺失时跳过
            if value is None:
                continue

            # 类型检查
            if not field_spec.type_checker(value):
                actual_type = type(value).__name__
                if isinstance(value, list):
                    actual_type = f"list[{type(value[0]).__name__ if value else 'empty'}]"
                # 宽容模式：单值自动转列表后重试
                if self.lenient and field_spec.type_str.startswith('list') and not isinstance(value, list):
                    coerced = [value]
                    if field_spec.type_checker(coerced):
                        warnings.append(f"字段 {field_name} 自动转换: {actual_type} → list")
                        value = coerced
                    else:
                        errors.append(f"字段 {field_name} 类型错误：期望 {field_spec.type_str}, 实际 {actual_type}")
                else:
                    errors.append(f"字段 {field_name} 类型错误：期望 {field_spec.type_str}, 实际 {actual_type}")

            # 值域检查
            if field_spec.value_domain and self.tags_loader.has_domain(field_spec.value_domain):
                allowed = self.tags_loader.get_domain_values(field_spec.value_domain)
                domain_errors = self._check_value_domain(field_name, value, allowed)
                if self.lenient:
                    # 宽容模式：值域越界是警告而非错误
                    for e in domain_errors:
                        warnings.append(e.replace("标签越界", "标签不在字典"))
                else:
                    errors.extend(domain_errors)

            # 范围检查（数值）
            if field_spec.min is not None or field_spec.max is not None:
                errors.extend(self._check_range(field_name, value, field_spec))

            # 长度检查（字符串）
            if field_spec.min_length is not None or field_spec.max_length is not None:
                str_errors = self._check_str_length(field_name, value, field_spec)
                if self.lenient:
                    for e in str_errors:
                        warnings.append(e)
                else:
                    errors.extend(str_errors)

            # 固定长度检查（列表）
            if field_spec.length is not None:
                errors.extend(self._check_list_length(field_name, value, field_spec))

            # 正则检查
            if field_spec.pattern:
                errors.extend(self._check_pattern(field_name, value, field_spec.pattern))

        # 5. 语义检查
        errors.extend(self._semantic_checks(event))

        # 返回错误和警告分开（宽容模式下只统计错误）
        return errors, warnings

    def _is_lenient_optional(self, field_name: str) -> bool:
        """宽容模式下可缺失的字段"""
        # 这些字段在宽容模式下可以缺失（主要针对 legacy 数据）
        lenient_optional = {
            'material_id', 'dialogue_type', 'info_delivery',
            'time_weather', 'conflict', 'stakes', 'hooks',
            'chapter_titles', 'text_range', 'lines', 'lines_approximate',
        }
        return field_name in lenient_optional

    def _auto_coerce_types(self, event: dict) -> dict:
        """自动转换单值为列表类型"""
        coerced = dict(event)
        for field_name, field_spec in self.schema_loader.field_defs.items():
            value = coerced.get(field_name)
            if value is None:
                continue
            # 如果字段期望列表但实际是单值，自动转换
            if field_spec.type_str.startswith('list') and not isinstance(value, list):
                coerced[field_name] = [value]
        return coerced

    def _flatten_event(self, raw: dict) -> dict:
        """将嵌套格式转为扁平格式（兼容 legacy 数据）

        处理旧的嵌套格式（content/people/emotion/structure/craft/setting 分组）
        """
        flat = dict(raw)

        # 仅当存在嵌套分组时才处理
        nested_groups = ['content', 'people', 'emotion', 'structure', 'craft', 'setting']

        for group_key in nested_groups:
            if group_key in flat and isinstance(flat[group_key], dict):
                group = flat.pop(group_key)
                for f, v in group.items():
                    if f not in flat:
                        flat[f] = v

        # 字段名映射（legacy 数据兼容）
        legacy_map = {
            'location': 'setting',
            'event_id': 'id',
            'tension_peak': 'tension',
        }
        for old_name, new_name in legacy_map.items():
            if old_name in flat and new_name not in flat:
                flat[new_name] = flat.pop(old_name)

        # moral_spectrum 可能是列表，取第一个
        if 'moral_spectrum' in flat and isinstance(flat['moral_spectrum'], list):
            flat['moral_spectrum'] = flat['moral_spectrum'][0] if flat['moral_spectrum'] else ''

        return flat

    def _check_value_domain(self, field: str, value: Any, allowed: set) -> list[str]:
        """检查值是否在允许的值域内"""
        errors = []
        if isinstance(value, list):
            for v in value:
                if str(v) not in allowed:
                    errors.append(f"标签越界: {field}='{v}'（不在 tags.yaml 中）")
        else:
            if str(value) not in allowed:
                errors.append(f"标签越界: {field}='{value}'（不在 tags.yaml 中）")
        return errors

    def _check_range(self, field: str, value: Any, spec: FieldSpec) -> list[str]:
        """检查数值范围"""
        errors = []
        if not isinstance(value, (int, float)):
            return errors
        if spec.min is not None and value < spec.min:
            errors.append(f"{field} 值过小: {value}（最小 {spec.min}）")
        if spec.max is not None and value > spec.max:
            errors.append(f"{field} 值过大: {value}（最大 {spec.max}）")
        return errors

    def _check_str_length(self, field: str, value: Any, spec: FieldSpec) -> list[str]:
        """检查字符串长度"""
        errors = []
        if not isinstance(value, str):
            return errors
        length = len(value)
        if spec.min_length is not None and length < spec.min_length:
            errors.append(f"{field} 过短: {length}字（最少 {spec.min_length}字）")
        if spec.max_length is not None and length > spec.max_length:
            errors.append(f"{field} 过长: {length}字（最多 {spec.max_length}字）")
        return errors

    def _check_list_length(self, field: str, value: Any, spec: FieldSpec) -> list[str]:
        """检查列表固定长度"""
        errors = []
        if not isinstance(value, list):
            return errors
        if len(value) != spec.length:
            errors.append(f"{field} 长度错误: {len(value)}（应为 {spec.length}）")
        return errors

    def _check_pattern(self, field: str, value: Any, pattern: str) -> list[str]:
        """检查正则匹配"""
        errors = []
        if not isinstance(value, str):
            return errors
        if not re.match(pattern, value):
            errors.append(f"{field} 格式错误: '{value}'（不匹配 {pattern}）")
        return errors

    def _semantic_checks(self, event: dict) -> list[str]:
        """语义检查"""
        errors = []

        # title 无语义检查
        if 'title' in event and isinstance(event['title'], str):
            title = event['title'].strip()
            if title.startswith('事件') and title[2:].isdigit():
                errors.append(f"title 无语义: '{title}'（禁止纯编号）")

        return errors


# ====================================================================
# 其他校验函数（保持原有逻辑）
# ====================================================================

META_REQUIRED_FIELDS = ['material_id', 'type', 'name', 'source', 'status']


def validate_outline(base_dir: Path) -> list[str]:
    """校验 outline/ 文件夹结构。"""
    errors = []
    outline_dir = base_dir / "outline"

    # 必选文件
    index_path = outline_dir / "_index.yaml"
    structure_path = outline_dir / "structure.yaml"

    for p in [index_path, structure_path]:
        if not p.exists():
            errors.append(f"缺少必选文件: {p.name}")
        else:
            errs = validate_yaml_parseable(p)
            errors.extend([f"{p.name}: {e}" for e in errs])

    # _index.yaml 必填字段
    if index_path.exists():
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            required = ['material_id', 'premise', 'theme', 'tone', 'modules_enabled']
            for field in required:
                if field not in data:
                    errors.append(f"_index.yaml 缺少: {field}")
            # structure_summary 检查
            if 'structure_summary' not in data:
                errors.append("_index.yaml 缺少: structure_summary")
            elif 'acts' not in data['structure_summary']:
                errors.append("_index.yaml structure_summary 缺少: acts")
        except yaml.YAMLError as e:
            errors.append(f"_index.yaml 解析失败: {e}")

    return errors


def validate_worldbuilding(base_dir: Path) -> list[str]:
    """校验 worldbuilding/ 文件夹结构。"""
    errors = []
    wb_dir = base_dir / "worldbuilding"

    if not wb_dir.exists():
        errors.append("worldbuilding/ 目录不存在")
        return errors

    index_path = wb_dir / "_index.yaml"
    if not index_path.exists():
        errors.append("缺少 _index.yaml")
    else:
        errs = validate_yaml_parseable(index_path)
        errors.extend([f"_index.yaml: {e}" for e in errs])

        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            required = ['material_id']
            for field in required:
                if field not in data:
                    errors.append(f"_index.yaml 缺少: {field}")
        except yaml.YAMLError as e:
            errors.append(f"_index.yaml 解析失败: {e}")

    return errors


def validate_characters(base_dir: Path) -> list[str]:
    """校验 characters/ 文件夹结构。"""
    errors = []
    chars_dir = base_dir / "characters"

    if not chars_dir.exists():
        errors.append("characters/ 目录不存在")
        return errors

    index_path = chars_dir / "_index.yaml"
    if not index_path.exists():
        errors.append("缺少 _index.yaml")
    else:
        errs = validate_yaml_parseable(index_path)
        errors.extend([f"_index.yaml: {e}" for e in errs])

        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}

            # roster 必填且 protagonists/antagonists 不为空
            if 'roster' not in data:
                errors.append("_index.yaml 缺少: roster")
            else:
                roster = data['roster']
                if 'protagonists' not in roster or not roster['protagonists']:
                    errors.append("roster.protagonists 为空")
                if 'antagonists' not in roster or not roster['antagonists']:
                    errors.append("roster.antagonists 为空")
        except yaml.YAMLError as e:
            errors.append(f"_index.yaml 解析失败: {e}")

    return errors


def validate_novel_tags(base_dir: Path) -> list[str]:
    """校验 tags.yaml。"""
    errors = []
    tags_path = base_dir / "tags.yaml"

    if not tags_path.exists():
        errors.append("tags.yaml 不存在")
        return errors

    errs = validate_yaml_parseable(tags_path)
    errors.extend(errs)

    try:
        with open(tags_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}

        required = ['material_id', 'genre', 'tone', 'themes']
        for field in required:
            if field not in data:
                errors.append(f"缺少: {field}")
    except yaml.YAMLError as e:
        errors.append(f"解析失败: {e}")

    return errors


def validate_yaml_parseable(path: Path) -> list[str]:
    """Check if a YAML file is parseable. Returns list of error strings."""
    if not path.exists():
        return [f"文件不存在: {path}"]
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if data is None:
            return ["文件为空"]
        return []
    except yaml.YAMLError as e:
        return [f"YAML 解析失败: {e}"]


def validate_meta(base_dir: Path) -> list[str]:
    """Validate meta.yaml required fields."""
    meta_path = base_dir / "meta.yaml"
    errors = validate_yaml_parseable(meta_path)
    if errors:
        return errors

    with open(meta_path, 'r', encoding='utf-8') as f:
        meta = yaml.safe_load(f)

    for field in META_REQUIRED_FIELDS:
        if field not in meta:
            errors.append(f"缺少必填字段: {field}")

    status = meta.get('status', '')
    valid_statuses = {'raw', 'outlined', 'tagged', 'complete', 'backfill-blocked', 'refined'}
    if status and status not in valid_statuses:
        errors.append(f"status 值无效: '{status}'（应为 {valid_statuses}）")

    return errors


def load_chapter_index(base_dir: Path) -> set | None:
    """Load chapter_index.yaml titles as a set."""
    ci_path = base_dir / "chapter_index.yaml"
    if not ci_path.exists():
        return None
    with open(ci_path, 'r', encoding='utf-8') as f:
        raw = yaml.safe_load(f)
    if not raw:
        return None
    titles = set()
    chapters = raw if isinstance(raw, list) else raw.get('chapters', [])
    for ch in chapters:
        if isinstance(ch, dict) and 'title' in ch:
            titles.add(ch['title'])
    return titles if titles else None


# ====================================================================
# 命令实现
# ====================================================================

def cmd_event(material_id: str, pattern: str = None, lenient: bool = False) -> int:
    """Validate event files.

    Args:
        lenient: If True, tag domain violations are warnings, not errors.
                 Also auto-converts single values to lists for list-type fields.
    """
    base_dir = Path(f"data/novels/{material_id}")
    events_dir = base_dir / "events"

    if not events_dir.exists():
        print(f"ERROR: 事件目录不存在: {events_dir}", file=sys.stderr)
        return 1

    # 加载 schema
    schema_path = Path("docs/schemas/event-unit.schema.yaml")
    try:
        schema_loader = SchemaLoader(schema_path)
    except FileNotFoundError:
        print(f"ERROR: Schema 文件不存在: {schema_path}", file=sys.stderr)
        return 1

    # 加载 tags 字典
    tags_path = Path("data/tags.yaml")
    tags_loader = TagsDomainLoader(tags_path)
    if not tags_loader.domains:
        print("WARNING: data/tags.yaml 无有效维度，跳过标签合法性检查", file=sys.stderr)

    # 加载章节索引
    chapter_titles = load_chapter_index(base_dir)

    # 创建校验器
    validator = EventValidator(schema_loader, tags_loader, chapter_titles, lenient=lenient)

    # 查找事件文件
    if pattern:
        event_files = sorted(events_dir.glob(f"{pattern}*.yaml"))
    else:
        event_files = sorted(events_dir.glob("ev*.yaml"))

    if not event_files:
        print(f"WARNING: 未找到匹配的事件文件")
        return 0

    total = len(event_files)
    failed_count = 0
    error_details = []
    warning_details = []

    for ef in event_files:
        errs, warns = validator.validate(ef)
        if errs:  # 只统计错误，警告不计入失败
            failed_count += 1
            error_details.append((ef.name, errs))
        if warns:
            warning_details.append((ef.name, warns))

    passed = total - failed_count

    print(f"📊 事件校验报告: {material_id}")
    print(f"   总文件数: {total}")
    print(f"   通过: {passed}")
    print(f"   失败: {failed_count}")
    if warning_details:
        print(f"   警告: {len(warning_details)} 个文件有警告")

    if not tags_loader.domains:
        print(f"   ⚠️ tags.yaml 无有效维度，标签合法性未校验")
    if chapter_titles is None:
        print(f"   ⚠️ chapter_index.yaml 缺失，章节名未校验")

    if error_details:
        print(f"\n❌ 失败文件详情:")
        for name, errs in error_details[:50]:
            print(f"\n  {name}:")
            for e in errs:
                print(f"    - {e}")
        if len(error_details) > 50:
            print(f"\n  ... 及其他 {len(error_details) - 50} 个文件")

    if warning_details and lenient:
        print(f"\n⚠️ 警告详情（宽容模式，不计入失败）:")
        for name, warns in warning_details[:20]:
            print(f"\n  {name}:")
            for w in warns[:10]:  # 每个文件最多显示10条警告
                print(f"    - {w}")
            if len(warns) > 10:
                print(f"    ... 及其他 {len(warns) - 10} 条警告")
        if len(warning_details) > 20:
            print(f"\n  ... 及其他 {len(warning_details) - 20} 个文件有警告")

    if failed_count == 0:
        print(f"\n✅ 全部通过（宽容模式下警告不计入失败）")

    return 1 if failed_count > 0 else 0


def cmd_meta(material_id: str) -> int:
    """Validate meta.yaml."""
    base_dir = Path(f"data/novels/{material_id}")
    errs = validate_meta(base_dir)
    if errs:
        print(f"❌ meta.yaml 校验失败:")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"✅ meta.yaml 校验通过")
    return 0


def cmd_outline(material_id: str) -> int:
    """Validate outline/ folder."""
    base_dir = Path(f"data/novels/{material_id}")
    errs = validate_outline(base_dir)
    if errs:
        print(f"❌ outline 校验失败:")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"✅ outline 校验通过")
    return 0


def cmd_worldbuilding(material_id: str) -> int:
    """Validate worldbuilding/ folder."""
    base_dir = Path(f"data/novels/{material_id}")
    errs = validate_worldbuilding(base_dir)
    if errs:
        print(f"❌ worldbuilding 校验失败:")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"✅ worldbuilding 校验通过")
    return 0


def cmd_characters(material_id: str) -> int:
    """Validate characters/ folder."""
    base_dir = Path(f"data/novels/{material_id}")
    errs = validate_characters(base_dir)
    if errs:
        print(f"❌ characters 校验失败:")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"✅ characters 校验通过")
    return 0


def cmd_novel_tags(material_id: str) -> int:
    """Validate tags.yaml."""
    base_dir = Path(f"data/novels/{material_id}")
    errs = validate_novel_tags(base_dir)
    if errs:
        print(f"❌ novel-tags 校验失败:")
        for e in errs:
            print(f"  - {e}")
        return 1
    print(f"✅ novel-tags 校验通过")
    return 0


def cmd_all(material_id: str) -> int:
    """Validate all output files."""
    base_dir = Path(f"data/novels/{material_id}")
    if not base_dir.exists():
        print(f"ERROR: 目录不存在: {base_dir}", file=sys.stderr)
        return 1

    exit_code = 0
    results = []

    yaml_files = [
        ('meta.yaml', True),
        ('outline.yaml', False),
        ('worldbuilding.yaml', False),
        ('characters.yaml', False),
        ('tags.yaml', False),
        ('events_index.yaml', False),
        ('events_manifest.yaml', False),
        ('stats.yaml', False),
    ]

    print(f"📊 全量校验报告: {material_id}\n")

    for filename, required in yaml_files:
        filepath = base_dir / filename
        if not filepath.exists():
            if required:
                print(f"  ❌ {filename}: 不存在（必需）")
                exit_code = 1
            else:
                print(f"  ⏭️  {filename}: 不存在（跳过）")
            continue

        if filename == 'meta.yaml':
            errs = validate_meta(base_dir)
        else:
            errs = validate_yaml_parseable(filepath)

        if errs:
            print(f"  ❌ {filename}: {'; '.join(errs)}")
            exit_code = 1
        else:
            print(f"  ✅ {filename}")

    events_dir = base_dir / "events"
    if events_dir.exists():
        print()
        event_exit = cmd_event(material_id)
        if event_exit != 0:
            exit_code = 1
    else:
        print(f"\n  ⏭️  events/: 不存在（跳过）")

    return exit_code


# ====================================================================
# Main
# ====================================================================

def main():
    parser = argparse.ArgumentParser(description='通用 YAML 校验脚本（v2.0）')
    subparsers = parser.add_subparsers(dest='command', required=True)

    event_parser = subparsers.add_parser('event', help='校验事件文件')
    event_parser.add_argument('material_id', help='素材 ID')
    event_parser.add_argument('pattern', nargs='?', help='事件 ID 前缀（如 ev001）')
    event_parser.add_argument('--lenient', '-l', action='store_true',
                              help='宽容模式：标签越界为警告，自动转换类型，部分字段可选')

    meta_parser = subparsers.add_parser('meta', help='校验 meta.yaml')
    meta_parser.add_argument('material_id', help='素材 ID')

    all_parser = subparsers.add_parser('all', help='校验全部产出')
    all_parser.add_argument('material_id', help='素材 ID')

    # 其他命令
    outline_parser = subparsers.add_parser('outline', help='校验 outline/ 文件夹')
    outline_parser.add_argument('material_id', help='素材 ID')

    worldbuilding_parser = subparsers.add_parser('worldbuilding', help='校验 worldbuilding/ 文件夹')
    worldbuilding_parser.add_argument('material_id', help='素材 ID')

    characters_parser = subparsers.add_parser('characters', help='校验 characters/ 文件夹')
    characters_parser.add_argument('material_id', help='素材 ID')

    novel_tags_parser = subparsers.add_parser('novel-tags', help='校验 tags.yaml')
    novel_tags_parser.add_argument('material_id', help='素材 ID')

    args = parser.parse_args()

    # 命令路由
    if args.command == 'event':
        sys.exit(cmd_event(args.material_id, args.pattern, args.lenient))
    elif args.command == 'meta':
        sys.exit(cmd_meta(args.material_id))
    elif args.command == 'all':
        sys.exit(cmd_all(args.material_id))
    elif args.command == 'outline':
        sys.exit(cmd_outline(args.material_id))
    elif args.command == 'worldbuilding':
        sys.exit(cmd_worldbuilding(args.material_id))
    elif args.command == 'characters':
        sys.exit(cmd_characters(args.material_id))
    elif args.command == 'novel-tags':
        sys.exit(cmd_novel_tags(args.material_id))


if __name__ == '__main__':
    main()
