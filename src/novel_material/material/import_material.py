"""导入外部已分析好的素材目录，重新生成 material_id 并注册。"""
import sys
import yaml
import shutil
import time
from pathlib import Path

from novel_material.infra.config import NOVELS_DIR, INDEX_FILE
from novel_material.infra.common import generate_material_id
from novel_material.tags.validate import validate_tag, validate_tags_batch


def validate_tags_with_db(tags):
    """校验标签合法性（使用数据库）。"""
    invalid = []
    if isinstance(tags, dict):
        elements = tags.get("elements") or []
        if isinstance(elements, list):
            _, inv = validate_tags_batch("element", elements)
            for v in inv:
                invalid.append(f"element={v}")

        style = tags.get("style") or []
        if isinstance(style, str):
            style = [style]
        if isinstance(style, list):
            _, inv = validate_tags_batch("style", style)
            for v in inv:
                invalid.append(f"style={v}")

        structure = tags.get("structure")
        if structure:
            if not validate_tag("structure", structure):
                invalid.append(f"structure={structure}")

        setting = tags.get("setting")
        if setting:
            if not validate_tag("setting", setting):
                invalid.append(f"setting={setting}")

    return invalid


def import_material(source_path):
    """导入外部素材目录。"""
    source_path = Path(source_path).resolve()
    if not source_path.exists():
        print(f"错误: 源目录不存在: {source_path}")
        return

    new_id = generate_material_id()
    target_dir = NOVELS_DIR / new_id

    print(f"正在导入: {source_path}")
    print(f"新 material_id: {new_id}")

    shutil.copytree(source_path, target_dir, dirs_exist_ok=True)

    meta_file = target_dir / "meta.yaml"
    meta = {}
    if meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = yaml.safe_load(f) or {}

        meta["material_id"] = new_id
        meta["imported_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        meta["imported_from"] = str(source_path)

        with open(meta_file, "w", encoding="utf-8") as f:
            yaml.dump(meta, f, allow_unicode=True, default_flow_style=False)

    tags_file = target_dir / "tags.yaml"
    if tags_file.exists():
        with open(tags_file, "r", encoding="utf-8") as f:
            tags = yaml.safe_load(f) or {}

        invalid = validate_tags_with_db(tags)
        if invalid:
            print(f"警告: 发现 {len(invalid)} 个非法标签:")
            for inv in invalid:
                print(f"  {inv}")
            print("请手动修复后再同步到数据库")
        else:
            print("标签校验通过")

    index_file = INDEX_FILE
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            index = yaml.safe_load(f) or {}
    else:
        index = {}

    index[new_id] = {
        "name": meta.get("name", source_path.name),
        "status": meta.get("status", "raw"),
        "path": f"data/novels/{new_id}",
        "imported_at": meta.get("imported_at")
    }

    with open(index_file, "w", encoding="utf-8") as f:
        yaml.dump(index, f, allow_unicode=True, default_flow_style=False)

    print(f"\n导入完成: {new_id}")
    print("请运行以下命令同步到数据库:")
    print(f"  nm storage sync {new_id}")

    return new_id


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python import.py <素材目录路径>")
        sys.exit(1)

    import_material(sys.argv[1])