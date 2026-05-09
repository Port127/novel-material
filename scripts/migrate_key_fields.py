"""迁移脚本：将旧 key_plot_point 移到 key_event，并重新推断结构角色。

执行时机：在实现新逻辑后，批量处理已有小说。

前置条件：
    1. 数据库需先执行 ALTER TABLE 添加字段（见 schema.sql 迁移部分）
    2. 确保 analyze.py 已完成章级分析

用法：
    python scripts/migrate_key_fields.py <material_id>
    python scripts/migrate_key_fields.py --all  # 批量处理所有小说
    python scripts/migrate_key_fields.py --all --dry-run  # 仅打印计划
"""
import sys
import yaml
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from novel_material.infra.config import NOVELS_DIR
from novel_material.pipeline.infer import infer_key_plot_points


def migrate_material(material_id: str, dry_run: bool = False) -> bool:
    """迁移单个小说的 key_plot_point 字段。

    流程：
    1. 备份 chapters.yaml
    2. 遍历 chapters/*.yaml，将 key_plot_point 移到 key_event
    3. 清空 key_plot_point
    4. 调用 infer_key_plot_points 重新推断

    参数：
        material_id: 素材 ID
        dry_run: 仅打印迁移计划，不实际修改

    返回：
        True 表示成功
    """
    novel_dir = NOVELS_DIR / material_id
    if not novel_dir.exists():
        print(f"[错误] 小说目录不存在: {novel_dir}")
        return False

    chapters_dir = novel_dir / "chapters"
    chapters_file = novel_dir / "chapters.yaml"

    if not chapters_dir.exists() and not chapters_file.exists():
        print(f"[错误] 无章节数据: {material_id}")
        return False

    # 统计需要迁移的章节数
    migrate_count = 0

    # 处理分散文件
    if chapters_dir.exists():
        for chapter_file in sorted(chapters_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(chapter_file.read_text(encoding="utf-8"))
            except yaml.YAMLError as e:
                print(f"[警告] 跳过异常文件: {chapter_file.name} - {e}")
                continue

            if not isinstance(data, dict):
                continue

            old_kpp = data.get("key_plot_point")
            if old_kpp and not data.get("key_event"):
                migrate_count += 1
                if dry_run:
                    print(f"  第{data.get('chapter', '?')}章: '{old_kpp[:30]}...' → key_event")
                else:
                    # 迁移
                    data["key_event"] = old_kpp
                    data["key_plot_point"] = None
                    chapter_file.write_text(
                        yaml.dump(data, allow_unicode=True, default_flow_style=False),
                        encoding="utf-8"
                    )

    # 处理合并文件（如果存在且无分散文件）
    if not chapters_dir.exists() and chapters_file.exists():
        with open(chapters_file, "r", encoding="utf-8") as f:
            chapters = yaml.safe_load(f) or []

        for ch in chapters:
            if not isinstance(ch, dict):
                continue
            old_kpp = ch.get("key_plot_point")
            if old_kpp and not ch.get("key_event"):
                migrate_count += 1
                if dry_run:
                    print(f"  第{ch.get('chapter', '?')}章: '{old_kpp[:30]}...' → key_event")
                else:
                    ch["key_event"] = old_kpp
                    ch["key_plot_point"] = None

        if not dry_run:
            # 备份
            backup_file = chapters_file.with_suffix(".yaml.bak")
            chapters_file.rename(backup_file)
            print(f"[备份] {backup_file}")

            # 写入迁移后的数据
            with open(chapters_file, "w", encoding="utf-8") as f:
                yaml.dump(chapters, f, allow_unicode=True, default_flow_style=False)

    if migrate_count == 0:
        print(f"[跳过] {material_id}: 无需迁移（key_event 已存在或 key_plot_point 为空）")
        return True

    print(f"[迁移] {material_id}: {migrate_count} 章")

    if dry_run:
        print("[dry-run] 未实际修改文件")
        return True

    # 重新推断结构角色
    print(f"[推断] {material_id}: 开始推断 key_plot_point...")
    if not infer_key_plot_points(material_id):
        print(f"[错误] {material_id}: 结构角色推断失败")
        return False

    print(f"[完成] {material_id}")
    return True


def migrate_all(dry_run: bool = False):
    """批量迁移所有小说。"""
    if not NOVELS_DIR.exists():
        print(f"[错误] 小说目录不存在: {NOVELS_DIR}")
        return

    material_ids = sorted(
        d.name for d in NOVELS_DIR.iterdir()
        if d.is_dir() and d.name.startswith("nm_")
    )

    if not material_ids:
        print("[信息] 无小说数据")
        return

    print(f"[批量] 发现 {len(material_ids)} 本小说")
    if dry_run:
        print("[dry-run] 仅打印迁移计划，不实际修改")

    success_count = 0
    for material_id in material_ids:
        if migrate_material(material_id, dry_run=dry_run):
            success_count += 1

    print(f"\n[统计] 成功: {success_count}/{len(material_ids)}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="迁移 key_plot_point → key_event")
    parser.add_argument("material_id", nargs="?", help="素材 ID（不指定则批量处理）")
    parser.add_argument("--all", action="store_true", help="批量处理所有小说")
    parser.add_argument("--dry-run", action="store_true", help="仅打印计划，不实际修改")

    args = parser.parse_args()

    if args.all:
        migrate_all(dry_run=args.dry_run)
    elif args.material_id:
        if not migrate_material(args.material_id, dry_run=args.dry_run):
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)