#!/usr/bin/env python
"""导入外部已分析好的素材目录，重新生成 material_id 并注册。"""
import os
import sys
import yaml
import shutil
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

def generate_material_id():
    """生成唯一的 material_id: nm_novel_YYYYMMDD_xxxx"""
    import random
    import string
    date_str = datetime.now().strftime("%Y%m%d")
    random_str = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return f"nm_novel_{date_str}_{random_str}"

def load_tags_dict():
    """加载标签字典。"""
    tags_file = Path("data/tags.yaml")
    if tags_file.exists():
        with open(tags_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

def validate_tags(tags, tags_dict):
    """校验标签合法性。"""
    invalid = []
    if isinstance(tags, dict):
        for key, value in tags.items():
            if key in ["channel", "genre_primary", "style", "structure", "setting"]:
                valid_set = set()
                if key == "channel":
                    valid_set = set(tags_dict.get("channel", []))
                elif key == "genre_primary":
                    for g in tags_dict.get("genre", {}).values():
                        if isinstance(g, list):
                            valid_set.update(g)
                elif key == "style":
                    valid_set = set(tags_dict.get("style", []))
                elif key == "structure":
                    valid_set = set(tags_dict.get("structure", []))
                elif key == "setting":
                    valid_set = set(tags_dict.get("setting", []))

                if value and value not in valid_set:
                    invalid.append(f"{key}={value}")

            elif key == "elements":
                valid_elements = set(tags_dict.get("element", []))
                if isinstance(value, list):
                    for v in value:
                        if v not in valid_elements:
                            invalid.append(f"element={v}")

    return invalid

def import_material(source_path):
    """导入外部素材目录。"""
    source_path = Path(source_path).resolve()
    if not source_path.exists():
        print(f"错误: 源目录不存在: {source_path}")
        return

    # 生成新的 material_id
    new_id = generate_material_id()
    target_dir = Path("data/novels") / new_id

    print(f"正在导入: {source_path}")
    print(f"新 material_id: {new_id}")

    # 复制目录
    shutil.copytree(source_path, target_dir, dirs_exist_ok=True)

    # 更新 meta.yaml
    meta_file = target_dir / "meta.yaml"
    if meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = yaml.safe_load(f) or {}

        meta["material_id"] = new_id
        meta["imported_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        meta["imported_from"] = str(source_path)

        with open(meta_file, "w", encoding="utf-8") as f:
            yaml.dump(meta, f, allow_unicode=True, default_flow_style=False)

    # 校验标签
    tags_dict = load_tags_dict()
    tags_file = target_dir / "tags.yaml"
    if tags_file.exists() and tags_dict:
        with open(tags_file, "r", encoding="utf-8") as f:
            tags = yaml.safe_load(f) or {}

        invalid = validate_tags(tags, tags_dict)
        if invalid:
            print(f"警告: 发现 {len(invalid)} 个非法标签:")
            for inv in invalid:
                print(f"  {inv}")
            print("请手动修复后再同步到数据库")
        else:
            print("标签校验通过")

    # 更新全局索引
    index_file = Path("data/index.yaml")
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            index = yaml.safe_load(f) or {}
    else:
        index = {}

    index[new_id] = {
        "name": meta.get("name", source_path.name),
        "status": meta.get("status", "imported"),
        "path": f"data/novels/{new_id}",
        "imported_at": meta.get("imported_at")
    }

    with open(index_file, "w", encoding="utf-8") as f:
        yaml.dump(index, f, allow_unicode=True, default_flow_style=False)

    print(f"\n导入完成: {new_id}")
    print("请运行以下命令同步到数据库:")
    print(f"  python scripts/core/sync_db.py {new_id}")

    return new_id

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python material_import.py <素材目录路径>")
        sys.exit(1)

    import_material(sys.argv[1])
