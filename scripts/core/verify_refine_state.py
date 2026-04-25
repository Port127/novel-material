#!/usr/bin/env python
"""
verify_refine_state.py — 验证 refine 状态证据一致性

检查 meta.yaml 中 pipeline.refine_batches 的状态标记与实际证据列表是否一致。
防止 Agent 无证据标记完成。

检查规则：
  - stats_merged=true 但 batch_1.stats_updated 为空 → 警告
  - hooks_verified=true 但 batch_2.hooks_verified_list 为空 → 警告
  - characters_refined=true 但 batch_3.profiles_updated 为空 → 警告
  - relations_verified=true 但 batch_4.relations_verified_list 为空 → 警告
  - worldbuilding_refined=true 但 batch_5.worldbuilding_updated 为空 → 警告
  - cleanup_done=true 但 batch_6.cleanup_items 为空 → 警告
  - 任一 batch completed_at 为 null 但对应状态为 true → 警告

用法:
    python scripts/core/verify_refine_state.py <material_id>
    python scripts/core/verify_refine_state.py <material_id> --fix
"""

import argparse
import sys
from pathlib import Path

import yaml


def _load_refine_batches(meta: dict) -> tuple[dict, bool]:
    """优先读取 pipeline.refine_batches；兼容 legacy 顶层 refine_batches。"""
    pipeline = meta.get("pipeline")
    if isinstance(pipeline, dict) and isinstance(pipeline.get("refine_batches"), dict):
        return pipeline["refine_batches"], False
    legacy = meta.get("refine_batches")
    if isinstance(legacy, dict):
        return legacy, True
    return {}, False


def _save_refine_batches(meta: dict, refine_batches: dict):
    """统一写回到 pipeline.refine_batches，并清理 legacy 顶层路径。"""
    pipeline = meta.get("pipeline")
    if not isinstance(pipeline, dict):
        pipeline = {}
        meta["pipeline"] = pipeline
    pipeline["refine_batches"] = refine_batches
    if "refine_batches" in meta:
        del meta["refine_batches"]


def verify_refine_state(material_id: str, fix: bool = False) -> dict:
    """验证 refine 状态证据一致性。"""
    base_dir = Path(f"data/novels/{material_id}")
    meta_path = base_dir / "meta.yaml"

    if not meta_path.exists():
        print(f"ERROR: meta.yaml 不存在: {meta_path}", file=sys.stderr)
        sys.exit(1)

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = yaml.safe_load(f) or {}

    refine_batches, using_legacy_path = _load_refine_batches(meta)
    batch_outputs = refine_batches.get("batch_outputs", {})

    issues = []

    # Batch-1: stats_merged
    stats_merged = refine_batches.get("stats_merged", False)
    batch_1 = batch_outputs.get("batch_1", {})
    stats_updated = batch_1.get("stats_updated", [])
    batch_1_completed = batch_1.get("completed_at")

    if stats_merged:
        if not stats_updated:
            issues.append({
                "batch": "batch_1",
                "status_field": "stats_merged",
                "status_value": True,
                "evidence_field": "stats_updated",
                "evidence_value": stats_updated,
                "issue": "状态为 true 但证据列表为空",
            })
        if not batch_1_completed:
            issues.append({
                "batch": "batch_1",
                "status_field": "stats_merged",
                "status_value": True,
                "evidence_field": "completed_at",
                "evidence_value": None,
                "issue": "状态为 true 但 completed_at 为 null",
            })

    # Batch-2: hooks_verified
    hooks_verified = refine_batches.get("hooks_verified", False)
    batch_2 = batch_outputs.get("batch_2", {})
    hooks_verified_list = batch_2.get("hooks_verified_list", [])
    batch_2_completed = batch_2.get("completed_at")

    if hooks_verified:
        if not hooks_verified_list:
            issues.append({
                "batch": "batch_2",
                "status_field": "hooks_verified",
                "status_value": True,
                "evidence_field": "hooks_verified_list",
                "evidence_value": hooks_verified_list,
                "issue": "状态为 true 但证据列表为空",
            })
        if not batch_2_completed:
            issues.append({
                "batch": "batch_2",
                "status_field": "hooks_verified",
                "status_value": True,
                "evidence_field": "completed_at",
                "evidence_value": None,
                "issue": "状态为 true 但 completed_at 为 null",
            })

    # Batch-3: characters_refined
    characters_refined = refine_batches.get("characters_refined", False)
    batch_3 = batch_outputs.get("batch_3", {})
    profiles_updated = batch_3.get("profiles_updated", [])
    batch_3_completed = batch_3.get("completed_at")

    if characters_refined:
        if not profiles_updated:
            issues.append({
                "batch": "batch_3",
                "status_field": "characters_refined",
                "status_value": True,
                "evidence_field": "profiles_updated",
                "evidence_value": profiles_updated,
                "issue": "状态为 true 但证据列表为空",
            })
        if not batch_3_completed:
            issues.append({
                "batch": "batch_3",
                "status_field": "characters_refined",
                "status_value": True,
                "evidence_field": "completed_at",
                "evidence_value": None,
                "issue": "状态为 true 但 completed_at 为 null",
            })

    # Batch-4: relations_verified
    relations_verified = refine_batches.get("relations_verified", False)
    batch_4 = batch_outputs.get("batch_4", {})
    relations_verified_list = batch_4.get("relations_verified_list", [])
    batch_4_completed = batch_4.get("completed_at")

    if relations_verified:
        if not relations_verified_list:
            issues.append({
                "batch": "batch_4",
                "status_field": "relations_verified",
                "status_value": True,
                "evidence_field": "relations_verified_list",
                "evidence_value": relations_verified_list,
                "issue": "状态为 true 但证据列表为空",
            })
        if not batch_4_completed:
            issues.append({
                "batch": "batch_4",
                "status_field": "relations_verified",
                "status_value": True,
                "evidence_field": "completed_at",
                "evidence_value": None,
                "issue": "状态为 true 但 completed_at 为 null",
            })

    # Batch-5: worldbuilding_refined
    worldbuilding_refined = refine_batches.get("worldbuilding_refined", False)
    batch_5 = batch_outputs.get("batch_5", {})
    worldbuilding_updated = batch_5.get("worldbuilding_updated", [])
    batch_5_completed = batch_5.get("completed_at")

    if worldbuilding_refined:
        if not worldbuilding_updated:
            issues.append({
                "batch": "batch_5",
                "status_field": "worldbuilding_refined",
                "status_value": True,
                "evidence_field": "worldbuilding_updated",
                "evidence_value": worldbuilding_updated,
                "issue": "状态为 true 但证据列表为空",
            })
        if not batch_5_completed:
            issues.append({
                "batch": "batch_5",
                "status_field": "worldbuilding_refined",
                "status_value": True,
                "evidence_field": "completed_at",
                "evidence_value": None,
                "issue": "状态为 true 但 completed_at 为 null",
            })

    # Batch-6: cleanup_done
    cleanup_done = refine_batches.get("cleanup_done", False)
    batch_6 = batch_outputs.get("batch_6", {})
    cleanup_items = batch_6.get("cleanup_items", [])
    batch_6_completed = batch_6.get("completed_at")

    if cleanup_done:
        if not cleanup_items:
            issues.append({
                "batch": "batch_6",
                "status_field": "cleanup_done",
                "status_value": True,
                "evidence_field": "cleanup_items",
                "evidence_value": cleanup_items,
                "issue": "状态为 true 但证据列表为空",
            })
        if not batch_6_completed:
            issues.append({
                "batch": "batch_6",
                "status_field": "cleanup_done",
                "status_value": True,
                "evidence_field": "completed_at",
                "evidence_value": None,
                "issue": "状态为 true 但 completed_at 为 null",
            })

    # 输出报告
    print(f"📊 refine 状态证据验证 — {material_id}")
    print(f"  批次状态:")
    print(f"    stats_merged: {stats_merged}")
    print(f"    hooks_verified: {hooks_verified}")
    print(f"    characters_refined: {characters_refined}")
    print(f"    relations_verified: {relations_verified}")
    print(f"    worldbuilding_refined: {worldbuilding_refined}")
    print(f"    cleanup_done: {cleanup_done}")
    if using_legacy_path:
        print("  ⚠️ 检测到 legacy 路径: meta.refine_batches（建议迁移到 pipeline.refine_batches）")

    if issues:
        print(f"\n🚫 发现 {len(issues)} 个证据不一致问题:")
        for i in issues:
            print(f"  ❌ {i['batch']}: {i['status_field']}={i['status_value']} 但 {i['evidence_field']}={i['evidence_value']}")
            print(f"     问题: {i['issue']}")

        if fix:
            print("\n🔧 修复模式：将状态标记重置为 false...")
            # 重置不一致的状态标记
            for i in issues:
                refine_batches[i["status_field"]] = False

            _save_refine_batches(meta, refine_batches)
            with open(meta_path, "w", encoding="utf-8") as f:
                yaml.dump(meta, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            print("✅ 已修复状态标记")

            sys.exit(1)
        else:
            print("\n💡 建议: 使用 --fix 参数自动修复状态标记")
            sys.exit(1)
    else:
        if using_legacy_path and fix:
            _save_refine_batches(meta, refine_batches)
            with open(meta_path, "w", encoding="utf-8") as f:
                yaml.dump(meta, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            print("✅ 已将 legacy refine_batches 迁移到 pipeline.refine_batches")
        print(f"\n✅ 所有状态标记与证据一致")

    return {"material_id": material_id, "issues": issues, "valid": len(issues) == 0}


def main():
    parser = argparse.ArgumentParser(description="验证 refine 状态证据一致性")
    parser.add_argument("material_id", help="素材 ID")
    parser.add_argument("--fix", action="store_true", help="自动修复不一致的状态标记")

    args = parser.parse_args()
    verify_refine_state(args.material_id, args.fix)


if __name__ == "__main__":
    main()
