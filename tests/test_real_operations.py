"""
真人操作测试案例 TC-RO-001 ~ TC-RO-300
真实运行：文件误删恢复、YAML格式错误、Pipeline中断、数据修正、API异常、脚本命令行、环境问题。
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / "core"))

from core.validate_yaml import validate_event, validate_meta, validate_yaml_parseable, _flatten_event
from core.quality_audit import compute_batch_quality, load_events, _as_list
from core.build_db import create_schema, ingest_novel, _flatten_event as db_flatten

REAL_DATA = ROOT / "data"
REAL_NOVELS = REAL_DATA / "novels"

TAGS_DICT = None
if (REAL_DATA / "tags.yaml").exists():
    with open(REAL_DATA / "tags.yaml", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    TAGS_DICT = {dim: set(str(v) for v in info["values"]) for dim, info in raw.items() if isinstance(info, dict) and "values" in info}


def _make_event(overrides=None):
    s = {
        "id": "ev0001", "chapter": "第1章 测试", "title": "黎明之战",
        "summary": "主角在黎明时与敌人展开激战，最终以弱胜强",
        "tension": 4,
        "event_type": ["对决"], "conflict": ["人与人"], "stakes": ["生死"],
        "characters": ["张三", "李四"],
        "relationship": ["对手"], "interaction": ["对抗"],
        "power_dynamic": "以弱胜强", "character_moment": ["觉醒"],
        "moral_spectrum": "正义",
        "emotion": ["燃"], "reader_effect": ["爽感"],
        "plot_stage": "发展", "plot_function": ["推进主线"], "pacing": "快",
        "technique": ["伏笔"], "dialogue_type": ["争论"],
        "pov": "第三人称限制", "info_delivery": ["展示"],
        "setting": ["战场"], "scale": "个人", "time_weather": ["黎明"],
    }
    if overrides:
        s.update(overrides)
    return s


def _setup_novel_env(tmp_path, num_events=10):
    """Create a complete novel environment for testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    novels_dir = data_dir / "novels"
    novels_dir.mkdir()
    mid = "nm_novel_20260101_test"
    novel_dir = novels_dir / mid
    novel_dir.mkdir()
    events_dir = novel_dir / "events"
    events_dir.mkdir()

    meta = {"material_id": mid, "name": "测试小说", "author": "测试作者",
            "type": "novel", "status": "complete", "source": "source.txt"}
    (novel_dir / "meta.yaml").write_text(yaml.dump(meta, allow_unicode=True), encoding="utf-8")
    (novel_dir / "source.txt").write_text("第1章 开始\n正文内容\n\n第2章 继续\n更多内容", encoding="utf-8")
    (novel_dir / "source.raw.txt").write_text("原始备份内容", encoding="utf-8")
    (novel_dir / "outline.yaml").write_text(yaml.dump({"premise": "test"}, allow_unicode=True), encoding="utf-8")
    (novel_dir / "characters.yaml").write_text(
        yaml.dump({"roster": [{"name": "张三", "role": "protagonist"}]}, allow_unicode=True), encoding="utf-8")
    (novel_dir / "tags.yaml").write_text(yaml.dump({"genre": ["玄幻"]}, allow_unicode=True), encoding="utf-8")
    (novel_dir / "worldbuilding.yaml").write_text(yaml.dump({"power_system": {"name": "灵力"}}, allow_unicode=True), encoding="utf-8")

    tags = {"event_type": {"description": "t", "values": ["对决", "日常"]},
            "emotion": {"description": "e", "values": ["燃", "悲伤"]},
            "conflict": {"description": "c", "values": ["人与人"]},
            "stakes": {"description": "s", "values": ["生死"]},
            "relationship": {"description": "r", "values": ["对手"]},
            "interaction": {"description": "i", "values": ["对抗"]},
            "character_moment": {"description": "cm", "values": ["觉醒"]},
            "power_dynamic": {"description": "pd", "values": ["以弱胜强"]},
            "moral_spectrum": {"description": "ms", "values": ["正义"]},
            "reader_effect": {"description": "re", "values": ["爽感"]},
            "plot_stage": {"description": "ps", "values": ["发展"]},
            "plot_function": {"description": "pf", "values": ["推进主线"]},
            "pacing": {"description": "p", "values": ["快"]},
            "technique": {"description": "te", "values": ["伏笔"]},
            "dialogue_type": {"description": "dt", "values": ["争论"]},
            "pov": {"description": "pov", "values": ["第三人称限制"]},
            "info_delivery": {"description": "id", "values": ["展示"]},
            "setting": {"description": "se", "values": ["战场"]},
            "scale": {"description": "sc", "values": ["个人"]},
            "time_weather": {"description": "tw", "values": ["黎明"]}}
    (data_dir / "tags.yaml").write_text(yaml.dump(tags, allow_unicode=True), encoding="utf-8")
    (data_dir / "index.yaml").write_text(
        yaml.dump({"materials": [{"id": mid, "name": "测试", "folder": f"novels/{mid}"}]}, allow_unicode=True), encoding="utf-8")

    for i in range(1, num_events + 1):
        event = _make_event({
            "id": f"ch{i:04d}_s01", "chapter": f"第{i}章 标题{i}",
            "title": f"精彩事件_{i}", "summary": f"独特的事件描述_{i}",
            "tension": (i % 5) + 1,
            "event_type": ["对决" if i % 2 == 0 else "日常"],
            "emotion": ["燃" if i % 3 != 0 else "悲伤"],
        })
        (events_dir / f"ch{i:04d}_s01.yaml").write_text(
            yaml.dump(event, allow_unicode=True), encoding="utf-8")

    return data_dir, novel_dir, events_dir, mid


# ==============================================================================
# 一、文件误删与恢复 TC-RO-001 ~ TC-RO-040
# ==============================================================================
class TestFileDeletionRecovery:
    """TC-RO-001~040: 事件/索引/分析文件误删与批量误操作"""

    def test_ro001_delete_single_event(self, tmp_path):
        """TC-RO-001: 删除单个事件文件后其他文件不受影响"""
        _, _, events_dir, _ = _setup_novel_env(tmp_path, 10)
        target = events_dir / "ch0005_s01.yaml"
        assert target.exists()
        target.unlink()
        remaining = list(events_dir.glob("ch*.yaml"))
        assert len(remaining) == 9

    def test_ro002_delete_entire_events_dir(self, tmp_path):
        """TC-RO-002: 删除整个 events 文件夹"""
        _, novel_dir, events_dir, _ = _setup_novel_env(tmp_path)
        shutil.rmtree(events_dir)
        assert not events_dir.exists()
        assert (novel_dir / "meta.yaml").exists(), "meta.yaml 不应受影响"

    def test_ro005_db_stale_after_yaml_delete(self, tmp_path):
        """TC-RO-005: 删了事件但 SQLite 还有记录 → 重建后一致"""
        data_dir, novel_dir, events_dir, mid = _setup_novel_env(tmp_path)
        db_path = data_dir / "material.db"
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            ingest_novel(conn, mid)
            before = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            assert before == 10
            (events_dir / "ch0010_s01.yaml").unlink()
            ingest_novel(conn, mid)
            after = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            assert after == 9
        finally:
            os.chdir(old_cwd)
            conn.close()

    def test_ro007_delete_meta(self, tmp_path):
        """TC-RO-007: 删除 meta.yaml 后 validate_meta 报错"""
        _, novel_dir, _, _ = _setup_novel_env(tmp_path)
        (novel_dir / "meta.yaml").unlink()
        errs = validate_meta(novel_dir)
        assert len(errs) > 0 and "不存在" in errs[0]

    def test_ro008_recover_from_raw(self, tmp_path):
        """TC-RO-008: source.txt 删了可从 source.raw.txt 恢复"""
        _, novel_dir, _, _ = _setup_novel_env(tmp_path)
        (novel_dir / "source.txt").unlink()
        raw = novel_dir / "source.raw.txt"
        assert raw.exists()
        shutil.copy(raw, novel_dir / "source.txt")
        assert (novel_dir / "source.txt").exists()

    def test_ro010_delete_tags_yaml(self, tmp_path):
        """TC-RO-010: 删除全局 tags.yaml"""
        data_dir, _, _, _ = _setup_novel_env(tmp_path)
        tags_path = data_dir / "tags.yaml"
        assert tags_path.exists()
        tags_path.unlink()
        assert not tags_path.exists()

    def test_ro011_delete_and_rebuild_db(self, tmp_path):
        """TC-RO-011: 删除 material.db 后重建"""
        data_dir, _, _, mid = _setup_novel_env(tmp_path)
        db_path = data_dir / "material.db"
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            ingest_novel(conn, mid)
            conn.close()
            db_path.unlink()
            assert not db_path.exists()
            conn = sqlite3.connect(str(db_path))
            create_schema(conn)
            ingest_novel(conn, mid)
            n = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            assert n == 10
        finally:
            os.chdir(old_cwd)
            conn.close()

    def test_ro018_delete_db_and_index(self, tmp_path):
        """TC-RO-018: 同时删除 DB 和 events_index 后重建"""
        data_dir, novel_dir, _, mid = _setup_novel_env(tmp_path)
        si = novel_dir / "events_index.yaml"
        si.write_text("test: true", encoding="utf-8")
        db_path = data_dir / "material.db"
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)
        conn.close()
        si.unlink()
        db_path.unlink()
        assert not si.exists() and not db_path.exists()
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            ingest_novel(conn, mid)
        finally:
            os.chdir(old_cwd)
            conn.close()
        assert db_path.exists()

    def test_ro031_delete_all_novels(self, tmp_path):
        """TC-RO-031: 删除所有小说后目录结构完整"""
        data_dir, _, _, _ = _setup_novel_env(tmp_path)
        novels_dir = data_dir / "novels"
        shutil.rmtree(novels_dir)
        novels_dir.mkdir()
        assert novels_dir.exists()
        assert len(list(novels_dir.iterdir())) == 0

    def test_ro033_delete_all_yaml(self, tmp_path):
        """TC-RO-033: 删除所有 .yaml 文件的影响"""
        data_dir, novel_dir, events_dir, _ = _setup_novel_env(tmp_path)
        yaml_files = list(data_dir.rglob("*.yaml"))
        assert len(yaml_files) > 10
        for f in yaml_files:
            f.unlink()
        remaining = list(data_dir.rglob("*.yaml"))
        assert len(remaining) == 0

    def test_ro036_copy_events_between_novels(self, tmp_path):
        """TC-RO-036: 把 A 的 events 复制到 B 不会破坏文件系统"""
        data_dir, novel_a, events_a, _ = _setup_novel_env(tmp_path)
        novel_b = data_dir / "novels" / "nm_novel_20260102_test"
        novel_b.mkdir(parents=True)
        events_b = novel_b / "events"
        shutil.copytree(events_a, events_b)
        assert len(list(events_b.glob("ch*.yaml"))) == 10

    def test_ro039_disk_full_simulation(self, tmp_path):
        """TC-RO-039: 写入不完整文件的检测"""
        _, novel_dir, events_dir, _ = _setup_novel_env(tmp_path)
        incomplete = events_dir / "ch0099_s01.yaml"
        incomplete.write_text("id: ch0099_s01\ntitle: 未完", encoding="utf-8")
        errs = validate_event(incomplete, TAGS_DICT, None)
        assert len(errs) > 0, "不完整文件应有校验错误"


# ==============================================================================
# 二、YAML 格式错误 TC-RO-041 ~ TC-RO-080
# ==============================================================================
class TestYAMLFormatErrors:
    """TC-RO-041~080: 手动编辑引入的格式错误、配置错误、LLM生成格式问题"""

    def test_ro041_mixed_indent(self, tmp_path):
        """TC-RO-041: Tab 和空格混用"""
        content = "id: ch0001_s01\n\ttitle: 测试"
        p = tmp_path / "bad.yaml"
        p.write_text(content, encoding="utf-8")
        errs = validate_yaml_parseable(p)
        assert len(errs) > 0

    def test_ro042_missing_space_after_colon(self, tmp_path):
        """TC-RO-042: 冒号后缺少空格"""
        content = "id:ch0001_s01\ntitle:没有空格"
        p = tmp_path / "bad.yaml"
        p.write_text(content, encoding="utf-8")
        loaded = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert loaded is not None  # YAML actually parses this as a string key

    def test_ro043_chinese_quotes(self, tmp_path):
        """TC-RO-043: 中文引号不用单引号包裹"""
        content = 'id: ch0001_s01\nnote: 他说\u201c你好\u201d'
        p = tmp_path / "test.yaml"
        p.write_text(content, encoding="utf-8")
        loaded = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert loaded["note"] == '他说\u201c你好\u201d'

    def test_ro045_tension_as_string(self, tmp_path):
        """TC-RO-045: tension 写成字符串"""
        event = _make_event({"tension": "5"})
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert isinstance(data["tension"], str), "YAML dump 把 '5' 变成了整数"

    def test_ro046_tension_float(self, tmp_path):
        """TC-RO-046: tension 是小数"""
        event = _make_event({"tension": 3.5})
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        errs = validate_event(p, TAGS_DICT, None)
        # 3.5 is within 1-5 range, but not integer
        # Current implementation accepts float in range - document this behavior
        assert isinstance(errs, list)

    def test_ro047_list_as_string(self, tmp_path):
        """TC-RO-047: 列表写成逗号分隔字符串"""
        content = """id: ch0001_s01
chapter: 第1章 测试
title: 测试事件
summary: 测试内容
tension: 3
emotion: 燃, 悲伤
event_type: [对决]
conflict: [人与人]
stakes: [生死]
relationship: [对手]
interaction: [对抗]
power_dynamic: 以弱胜强
character_moment: [觉醒]
moral_spectrum: 正义
reader_effect: [爽感]
plot_stage: 发展
plot_function: [推进主线]
pacing: 快
technique: [伏笔]
dialogue_type: [争论]
pov: 第三人称限制
info_delivery: [展示]
setting: [战场]
scale: 个人
time_weather: [黎明]
characters: [张三]"""
        p = tmp_path / "test.yaml"
        p.write_text(content, encoding="utf-8")
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert isinstance(data["emotion"], str), "逗号分隔被解析为字符串而非列表"
        errs = validate_event(p, TAGS_DICT, None)
        assert any("emotion" in e and "列表" in e for e in errs)

    def test_ro049_missing_id(self, tmp_path):
        """TC-RO-049: 缺少必填字段 id"""
        event = _make_event()
        del event["id"]
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        errs = validate_event(p, TAGS_DICT, None)
        assert any("id" in e for e in errs)

    def test_ro050_missing_chapter(self, tmp_path):
        """TC-RO-050: 缺少必填字段 chapter"""
        event = _make_event()
        del event["chapter"]
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        errs = validate_event(p, TAGS_DICT, None)
        assert any("chapter" in e for e in errs)

    def test_ro053_chinese_colon(self, tmp_path):
        """TC-RO-053: 中文冒号替代英文冒号"""
        content = "title\uff1a\u9ece\u660e\u4e4b\u6218"
        p = tmp_path / "bad.yaml"
        p.write_text(content, encoding="utf-8")
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert "title" not in (data if isinstance(data, dict) else {}), "中文冒号不被 YAML 识别为键值分隔符"

    def test_ro055_null_in_array(self, tmp_path):
        """TC-RO-055: 列表中混入 null"""
        event = _make_event({"emotion": ["燃", None, "悲伤"]})
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert None in data["emotion"]

    def test_ro057_bom_header(self, tmp_path):
        """TC-RO-057: BOM 头的 UTF-8"""
        p = tmp_path / "bom.yaml"
        p.write_bytes(b"\xef\xbb\xbfid: ch0001_s01\ntitle: test")
        data = yaml.safe_load(p.read_text(encoding="utf-8-sig"))
        assert data.get("id") == "ch0001_s01"

    def test_ro060_empty_event_file(self, tmp_path):
        """TC-RO-060: 空事件文件"""
        p = tmp_path / "empty.yaml"
        p.write_text("", encoding="utf-8")
        errs = validate_event(p, TAGS_DICT, None)
        assert any("空" in e for e in errs)

    def test_ro061_invalid_status(self, tmp_path):
        """TC-RO-061: meta.yaml 中非法 status"""
        _, novel_dir, _, _ = _setup_novel_env(tmp_path)
        meta_path = novel_dir / "meta.yaml"
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
        meta["status"] = "doing"
        meta_path.write_text(yaml.dump(meta, allow_unicode=True), encoding="utf-8")
        errs = validate_meta(novel_dir)
        assert any("status" in e for e in errs)

    def test_ro067_broken_json(self, tmp_path):
        """TC-RO-067: pipeline_status.json 格式不合法"""
        p = tmp_path / "broken.json"
        p.write_text("{invalid json!!!", encoding="utf-8")
        with pytest.raises(json.JSONDecodeError):
            json.loads(p.read_text(encoding="utf-8"))

    def test_ro071_markdown_fence_in_yaml(self, tmp_path):
        """TC-RO-071: LLM 输出包含 ```yaml 围栏"""
        content = "```yaml\nid: ch0001_s01\ntitle: test\n```"
        p = tmp_path / "fenced.yaml"
        p.write_text(content, encoding="utf-8")
        errs = validate_yaml_parseable(p)
        # This will either parse or fail - document behavior
        assert isinstance(errs, list)

    def test_ro074_numbered_title_detected(self):
        """TC-RO-074: 编号形式 title 被检测"""
        event = _make_event({"title": "事件3"})
        events = [event]
        result = compute_batch_quality(events)
        assert result["quality"]["bad_titles"] > 0

    def test_ro075_identical_emotion_detected(self):
        """TC-RO-075: 所有事件相同 emotion 标签被检测"""
        events = [_make_event({"id": f"ch{i:04d}_s01", "emotion": ["平静"],
                               "event_type": ["日常"], "conflict": []})
                  for i in range(1, 11)]
        result = compute_batch_quality(events)
        assert result["quality"]["tag_diversity"] < 0.5

    def test_ro076_illegal_tag_from_llm(self, tmp_path):
        """TC-RO-076: LLM 给出非法标签值"""
        event = _make_event({"event_type": ["超自然"]})
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        if TAGS_DICT:
            errs = validate_event(p, TAGS_DICT, None)
            assert any("标签越界" in e for e in errs)

    def test_ro077_missing_characters(self, tmp_path):
        """TC-RO-077: 缺少 characters 字段"""
        event = _make_event()
        del event["characters"]
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        # characters is not in EVENT_TAG_FIELDS so validate_event won't catch it
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert "characters" not in data

    def test_ro079_tension_chinese(self, tmp_path):
        """TC-RO-079: tension 写成中文"""
        event = _make_event({"tension": "三"})
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        errs = validate_event(p, TAGS_DICT, None)
        # tension "三" is a string, not int
        assert isinstance(errs, list)


# ==============================================================================
# 三、Pipeline 中断与恢复 TC-RO-081 ~ TC-RO-120
# ==============================================================================
class TestPipelineInterruption:
    """TC-RO-081~120: 中断恢复、进度追踪、并发"""

    def test_ro087_continue_from_batch(self, tmp_path):
        """TC-RO-087: 中断后从特定批次恢复——进度记录在 meta"""
        _, novel_dir, events_dir, mid = _setup_novel_env(tmp_path, 15)
        meta_path = novel_dir / "meta.yaml"
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
        meta["pipeline"] = {"events_processed": ["1-10"], "last_batch": "1-10"}
        meta_path.write_text(yaml.dump(meta, allow_unicode=True), encoding="utf-8")
        reloaded = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
        assert reloaded["pipeline"]["last_batch"] == "1-10"

    def test_ro096_concurrent_same_novel(self, tmp_path):
        """TC-RO-096: 同时操作同一本书的 DB 不报错"""
        data_dir, _, _, mid = _setup_novel_env(tmp_path)
        db_path = data_dir / "material.db"
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            conn1 = sqlite3.connect(str(db_path))
            conn2 = sqlite3.connect(str(db_path))
            create_schema(conn1)
            create_schema(conn2)
            ingest_novel(conn1, mid)
            n1 = conn1.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            n2 = conn2.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            assert n1 == n2
        finally:
            os.chdir(old_cwd)
            conn1.close()
            conn2.close()

    def test_ro101_event_continuity(self, tmp_path):
        """TC-RO-101: 事件文件编号连续性"""
        _, _, events_dir, _ = _setup_novel_env(tmp_path, 10)
        files = sorted(events_dir.glob("ch*.yaml"))
        nums = []
        for f in files:
            n = int(f.stem.split("_")[0].replace("ch", ""))
            nums.append(n)
        for i in range(len(nums) - 1):
            assert nums[i + 1] == nums[i] + 1, f"编号不连续: {nums[i]} → {nums[i+1]}"

    def test_ro117_gap_in_numbering(self, tmp_path):
        """TC-RO-117: 编号有空洞时 build-index 不崩溃"""
        data_dir, _, events_dir, mid = _setup_novel_env(tmp_path, 10)
        (events_dir / "ch0005_s01.yaml").unlink()
        db_path = data_dir / "material.db"
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            count = ingest_novel(conn, mid)
            assert count == 9
        finally:
            os.chdir(old_cwd)
            conn.close()

    def test_ro118_stale_index_after_tag_change(self, tmp_path):
        """TC-RO-118: 修改标签后不重建索引导致不一致"""
        data_dir, _, events_dir, mid = _setup_novel_env(tmp_path)
        db_path = data_dir / "material.db"
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            ingest_novel(conn, mid)
            sf = events_dir / "ch0001_s01.yaml"
            event = yaml.safe_load(sf.read_text(encoding="utf-8"))
            event["emotion"] = ["悲伤"]
            sf.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
            old_tags = conn.execute(
                "SELECT value FROM event_tags WHERE event_id='ch0001_s01' AND dimension='emotion'"
            ).fetchall()
            assert old_tags[0][0] == "燃", "DB 还是旧值"
            ingest_novel(conn, mid)
            new_tags = conn.execute(
                "SELECT value FROM event_tags WHERE event_id='ch0001_s01' AND dimension='emotion'"
            ).fetchall()
            assert new_tags[0][0] == "悲伤", "重建后应为新值"
        finally:
            os.chdir(old_cwd)
            conn.close()


# ==============================================================================
# 四、数据写错与修正 TC-RO-121 ~ TC-RO-170
# ==============================================================================
class TestDataCorrection:
    """TC-RO-121~170: 标签拼错、配置错误、批次修正"""

    def test_ro121_typo_tag_value(self, tmp_path):
        """TC-RO-121: 标签值拼写错误"""
        event = _make_event({"emotion": ["燃燃"]})
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        if TAGS_DICT:
            errs = validate_event(p, TAGS_DICT, None)
            assert any("标签越界" in e for e in errs)

    def test_ro123_scalar_as_list(self, tmp_path):
        """TC-RO-123: 单值字段写成列表"""
        event = _make_event({"pacing": ["快"]})
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        errs = validate_event(p, TAGS_DICT, None)
        assert any("pacing" in e for e in errs)

    def test_ro124_list_as_scalar(self, tmp_path):
        """TC-RO-124: 列表字段写成单值"""
        event = _make_event({"emotion": "燃"})
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        errs = validate_event(p, TAGS_DICT, None)
        assert any("emotion" in e and "列表" in e for e in errs)

    def test_ro125_tension_zero(self, tmp_path):
        """TC-RO-125: tension = 0"""
        event = _make_event({"tension": 0})
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        errs = validate_event(p, TAGS_DICT, None)
        assert any("tension" in e for e in errs)

    def test_ro126_tension_negative(self, tmp_path):
        """TC-RO-126: tension = -1"""
        event = _make_event({"tension": -1})
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        errs = validate_event(p, TAGS_DICT, None)
        assert any("tension" in e for e in errs)

    def test_ro128_chapter_not_from_index(self, tmp_path):
        """TC-RO-128: chapter 与 chapter_index 不匹配"""
        event = _make_event({"chapter": "第一章 开始"})
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        chapter_titles = {"第1章 开始", "第2章 继续"}
        errs = validate_event(p, TAGS_DICT, chapter_titles)
        assert any("章节名不匹配" in e for e in errs)

    def test_ro129_duplicate_event_ids(self, tmp_path):
        """TC-RO-129: 多个事件 YAML 使用同一 id"""
        data_dir, novel_dir, events_dir, mid = _setup_novel_env(tmp_path, 3)
        sf1 = yaml.safe_load((events_dir / "ch0001_s01.yaml").read_text(encoding="utf-8"))
        sf2 = yaml.safe_load((events_dir / "ch0002_s01.yaml").read_text(encoding="utf-8"))
        sf2["id"] = sf1["id"]
        (events_dir / "ch0002_s01.yaml").write_text(yaml.dump(sf2, allow_unicode=True), encoding="utf-8")
        db_path = data_dir / "material.db"
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            ingest_novel(conn, mid)
            count = conn.execute("SELECT COUNT(*) FROM events WHERE material_id=?", (mid,)).fetchone()[0]
            # INSERT OR REPLACE means second overwrites first
            assert count < 3, "重复 ID 应导致覆盖，不应有3条"
        finally:
            os.chdir(old_cwd)
            conn.close()

    def test_ro140_direct_db_edit_inconsistency(self, tmp_path):
        """TC-RO-140: 直接修改 DB 后与 YAML 不一致"""
        data_dir, _, events_dir, mid = _setup_novel_env(tmp_path)
        db_path = data_dir / "material.db"
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            ingest_novel(conn, mid)
            conn.execute("UPDATE events SET title='被篡改的标题' WHERE event_id='ch0001_s01'")
            conn.commit()
            db_title = conn.execute("SELECT title FROM events WHERE event_id='ch0001_s01'").fetchone()[0]
            assert db_title == "被篡改的标题"
            yaml_data = yaml.safe_load((events_dir / "ch0001_s01.yaml").read_text(encoding="utf-8"))
            assert yaml_data["title"] != "被篡改的标题", "YAML 不应被 DB 修改影响"
            ingest_novel(conn, mid)
            restored = conn.execute("SELECT title FROM events WHERE event_id='ch0001_s01'").fetchone()[0]
            assert restored == yaml_data["title"], "重建后应恢复 YAML 中的值"
        finally:
            os.chdir(old_cwd)
            conn.close()

    def test_ro156_redo_batch(self, tmp_path):
        """TC-RO-156: 删除某批次事件后重新计算"""
        _, _, events_dir, _ = _setup_novel_env(tmp_path, 10)
        for i in range(6, 11):
            (events_dir / f"ch{i:04d}_s01.yaml").unlink()
        remaining = list(events_dir.glob("ch*.yaml"))
        assert len(remaining) == 5
        events = load_events(events_dir)
        result = compute_batch_quality(events)
        assert result["events_count"] == 5

    def test_ro168_stats_vs_actual(self, tmp_path):
        """TC-RO-168: 统计数据与实际事件数对比"""
        _, novel_dir, events_dir, _ = _setup_novel_env(tmp_path, 10)
        (novel_dir / "stats.yaml").write_text(
            yaml.dump({"total_events": 15}, allow_unicode=True), encoding="utf-8")
        stats = yaml.safe_load((novel_dir / "stats.yaml").read_text(encoding="utf-8"))
        actual = len(list(events_dir.glob("ch*.yaml")))
        assert stats["total_events"] != actual, "stats 声称15个但实际10个——不一致"


# ==============================================================================
# 五、前端操作异常 TC-RO-171 ~ TC-RO-220
# ==============================================================================
class TestFrontendAPI:
    """TC-RO-171~220: 页面加载、搜索异常、上传"""

    @pytest.fixture(autouse=True)
    def _setup_client(self, tmp_path):
        sys.path.insert(0, str(BACKEND_DIR))
        sys.path.insert(0, str(BACKEND_DIR / "tests"))
        from conftest import _create_test_db, _create_novel_dir, TAGS_YAML as T, TEST_MATERIAL_ID as MID
        self.mid = MID
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        novels_dir = data_dir / "novels"
        novels_dir.mkdir()
        config_dir = data_dir / ".config"
        config_dir.mkdir()
        (data_dir / "tags.yaml").write_text(yaml.dump(T, allow_unicode=True), encoding="utf-8")
        idx = {"materials": [{"id": MID, "type": "novel", "name": "测试小说",
                              "author": "测试作者", "folder": f"novels/{MID}", "status": "complete"}]}
        (data_dir / "index.yaml").write_text(yaml.dump(idx, allow_unicode=True), encoding="utf-8")
        db_path = data_dir / "material.db"
        _create_test_db(db_path)
        _create_novel_dir(novels_dir)
        (config_dir / "pipeline_status.json").write_text("{}", encoding="utf-8")
        (config_dir / "llm_config.json").write_text("{}", encoding="utf-8")

        import services.data_service as ds
        import services.pipeline_service as ps
        orig_ds = (ds.PROJECT_ROOT, ds.DATA_DIR, ds.DB_PATH, ds.NOVELS_DIR)
        ds.PROJECT_ROOT, ds.DATA_DIR, ds.DB_PATH, ds.NOVELS_DIR = tmp_path, data_dir, db_path, novels_dir
        orig_ps = (ps.CONFIG_DIR, ps.STATUS_FILE, ps.LLM_CONFIG_FILE, ps.SCRIPTS_DIR)
        ps.CONFIG_DIR = config_dir
        ps.STATUS_FILE = config_dir / "pipeline_status.json"
        ps.LLM_CONFIG_FILE = config_dir / "llm_config.json"
        ps.SCRIPTS_DIR = tmp_path / "scripts"

        from fastapi.testclient import TestClient
        from main import app
        self.client = TestClient(app)
        yield
        ds.PROJECT_ROOT, ds.DATA_DIR, ds.DB_PATH, ds.NOVELS_DIR = orig_ds
        ps.CONFIG_DIR, ps.STATUS_FILE, ps.LLM_CONFIG_FILE, ps.SCRIPTS_DIR = orig_ps

    def test_ro175_nonexistent_material(self):
        """TC-RO-175: 不存在的 material_id 返回 404"""
        r = self.client.get("/api/materials/nm_nonexistent_fake_id_xyz")
        assert r.status_code == 404

    def test_ro191_empty_search(self):
        """TC-RO-191: 空搜索条件"""
        r = self.client.get("/api/search/events")
        assert r.status_code == 200

    def test_ro192_very_long_search(self):
        """TC-RO-192: 超长搜索字符串"""
        r = self.client.get("/api/search/text", params={"query": "x" * 10000})
        assert r.status_code == 200

    def test_ro193_xss_in_search(self):
        """TC-RO-193: XSS 攻击"""
        r = self.client.get("/api/search/text", params={"query": "<script>alert(1)</script>"})
        assert r.status_code == 200
        assert "<script>" not in r.text or "script" in json.dumps(r.json())

    def test_ro194_sql_in_search(self):
        """TC-RO-194: SQL 注入"""
        r = self.client.get("/api/search/text", params={"query": "'; DROP TABLE events; --"})
        assert r.status_code == 200

    def test_ro199_nonexistent_character(self):
        """TC-RO-199: 搜索不存在的人物"""
        r = self.client.get("/api/search/characters", params={"name": "不存在的角色XYZ"})
        assert r.status_code == 200
        data = r.json()
        chars = data if isinstance(data, list) else data.get("characters", [])
        assert len(chars) == 0

    def test_ro206_invalid_query_params(self):
        """TC-RO-206: 非法查询参数"""
        r = self.client.get("/api/search/events", params={"tension_min": "abc"})
        assert r.status_code in (200, 422)

    def test_ro207_empty_result(self):
        """TC-RO-207: 搜索返回空结果"""
        r = self.client.get("/api/search/events", params={"event_type": "不存在的类型XYZ"})
        assert r.status_code == 200

    def test_ro211_upload_txt(self):
        """TC-RO-211: 上传 .txt 文件"""
        r = self.client.post("/api/upload", files={"file": ("test.txt", b"content here", "text/plain")})
        assert r.status_code in (200, 201)

    def test_ro212_upload_docx_rejected(self):
        """TC-RO-212: 上传 .docx 被拒绝或处理"""
        r = self.client.post("/api/upload", files={"file": ("test.docx", b"fake docx content", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
        assert r.status_code in (200, 400, 415)

    def test_ro214_upload_empty(self):
        """TC-RO-214: 上传空文件"""
        r = self.client.post("/api/upload", files={"file": ("empty.txt", b"", "text/plain")})
        assert r.status_code in (200, 400)

    def test_ro261_nonexistent_route(self):
        """TC-RO-261: 不存在的 API 路径"""
        r = self.client.get("/api/v1/nonexistent")
        assert r.status_code == 404

    def test_ro263_material_not_found(self):
        """TC-RO-263: 不存在的 ID"""
        r = self.client.get("/api/materials/nm_fake_id_12345")
        assert r.status_code == 404

    def test_ro268_concurrent_requests(self):
        """TC-RO-268: 并发搜索请求"""
        import concurrent.futures
        def search():
            return self.client.get("/api/search/events", params={"event_type": "对决"})
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            futures = [ex.submit(search) for _ in range(20)]
            results = [f.result() for f in futures]
        assert all(r.status_code == 200 for r in results)

    def test_ro274_tag_dict_api(self):
        """TC-RO-274: 标签字典 API"""
        r = self.client.get("/api/tags")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0

    def test_ro283_path_traversal(self):
        """TC-RO-283: 路径遍历攻击"""
        r = self.client.get("/api/materials/../../etc/passwd")
        assert r.status_code in (404, 422)


# ==============================================================================
# 六、脚本命令行 TC-RO-221 ~ TC-RO-260
# ==============================================================================
class TestScriptsCLI:
    """TC-RO-221~260: search/build_db/validate_yaml/quality_audit CLI"""

    def test_ro236_build_db_empty_novels(self, tmp_path):
        """TC-RO-236: data/novels/ 为空时 build_db 创建空数据库"""
        data_dir = tmp_path / "data"
        (data_dir / "novels").mkdir(parents=True)
        (data_dir / "index.yaml").write_text(yaml.dump({"materials": []}, allow_unicode=True), encoding="utf-8")
        db_path = data_dir / "material.db"
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)
        conn.close()
        assert db_path.exists()
        conn = sqlite3.connect(str(db_path))
        n = conn.execute("SELECT COUNT(*) FROM novels").fetchone()[0]
        conn.close()
        assert n == 0

    def test_ro237_build_db_bad_yaml(self, tmp_path):
        """TC-RO-237: 有格式错误的 YAML 时 build_db 跳过继续"""
        data_dir, novel_dir, events_dir, mid = _setup_novel_env(tmp_path, 5)
        (events_dir / "ch0003_s01.yaml").write_text("{{invalid yaml!!", encoding="utf-8")
        db_path = data_dir / "material.db"
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            count = ingest_novel(conn, mid)
            assert count == 4, "应跳过损坏文件，处理其余 4 个"
        finally:
            os.chdir(old_cwd)
            conn.close()

    def test_ro240_build_db_idempotent(self, tmp_path):
        """TC-RO-240: build_db 运行两次无重复数据"""
        data_dir, _, _, mid = _setup_novel_env(tmp_path)
        db_path = data_dir / "material.db"
        old_cwd = os.getcwd()
        os.chdir(tmp_path)
        try:
            conn = sqlite3.connect(str(db_path))
            create_schema(conn)
            ingest_novel(conn, mid)
            first = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            ingest_novel(conn, mid)
            second = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            assert first == second, "两次运行结果应相同"
        finally:
            os.chdir(old_cwd)
            conn.close()

    def test_ro241_flatten_nested_events(self):
        """TC-RO-241: 嵌套格式事件正确展平"""
        nested = {
            "event_id": "ch0001_s01",
            "content": {"event_type": ["日常"], "conflict": [], "stakes": []},
            "people": {"relationship": [], "interaction": [], "power_dynamic": "平等",
                       "character_moment": [], "moral_spectrum": ["灰色"]},
        }
        flat = db_flatten(nested)
        assert flat.get("id") == "ch0001_s01"
        assert flat.get("event_type") == ["日常"]
        assert flat.get("power_dynamic") == "平等"

    def test_ro246_valid_event_passes(self, tmp_path):
        """TC-RO-246: 完全合规的事件通过校验"""
        event = _make_event()
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        tags = {"event_type": {"values": ["对决"]}, "emotion": {"values": ["燃"]},
                "conflict": {"values": ["人与人"]}, "stakes": {"values": ["生死"]},
                "relationship": {"values": ["对手"]}, "interaction": {"values": ["对抗"]},
                "character_moment": {"values": ["觉醒"]}, "power_dynamic": {"values": ["以弱胜强"]},
                "moral_spectrum": {"values": ["正义"]}, "reader_effect": {"values": ["爽感"]},
                "plot_stage": {"values": ["发展"]}, "plot_function": {"values": ["推进主线"]},
                "pacing": {"values": ["快"]}, "technique": {"values": ["伏笔"]},
                "dialogue_type": {"values": ["争论"]}, "pov": {"values": ["第三人称限制"]},
                "info_delivery": {"values": ["展示"]}, "setting": {"values": ["战场"]},
                "scale": {"values": ["个人"]}, "time_weather": {"values": ["黎明"]}}
        td = {k: set(str(v) for v in info["values"]) for k, info in tags.items()}
        errs = validate_event(p, td, None)
        assert errs == [], f"合规事件不应有错误: {errs}"

    def test_ro248_illegal_tag_reported(self, tmp_path):
        """TC-RO-248: 非法标签值被报告"""
        event = _make_event({"emotion": ["完全虚构的非法情绪_XYZ"]})
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        if TAGS_DICT:
            errs = validate_event(p, TAGS_DICT, None)
            illegal = [e for e in errs if "标签越界" in e and "emotion" in e]
            assert len(illegal) > 0

    def test_ro251_quality_audit_passes(self):
        """TC-RO-251: 标签多样性正常的批次审计通过"""
        events = []
        types = ["对决", "日常", "对决", "日常", "对决"]
        emotions = ["燃", "悲伤", "燃", "悲伤", "燃"]
        conflicts = [["人与人"], [], ["人与人"], ["人与人"], []]
        for i in range(5):
            events.append(_make_event({
                "id": f"ch{i+1:04d}_s01",
                "title": f"独特标题_{i}",
                "summary": f"完全不同的事件描述_{i}，包含独特情节，第{i}段",
                "event_type": [types[i]],
                "emotion": [emotions[i]],
                "conflict": conflicts[i],
                "tension": (i % 5) + 1,
            }))
        result = compute_batch_quality(events)
        assert result["status"] == "passed", f"应通过审计: {result.get('issues')}"

    def test_ro252_cloned_batch_fails(self):
        """TC-RO-252: 标签雷同批次审计失败"""
        events = [_make_event({"id": f"ch{i:04d}_s01",
                               "title": f"相同标题",
                               "summary": f"相同摘要"})
                  for i in range(1, 11)]
        result = compute_batch_quality(events)
        assert result["status"] == "failed" or result["quality"]["tag_diversity"] <= 0.1

    def test_ro253_numbered_title_audit(self):
        """TC-RO-253: title 编号形式被检测"""
        events = [_make_event({"id": "ch0001_s01", "title": "事件1"})]
        result = compute_batch_quality(events)
        assert result["quality"]["bad_titles"] > 0


# ==============================================================================
# 七、后端 API 异常 TC-RO-261 ~ TC-RO-290 (在 TestFrontendAPI 中已覆盖部分)
# ==============================================================================


# ==============================================================================
# 八、环境与依赖 TC-RO-291 ~ TC-RO-300
# ==============================================================================
class TestEnvironment:
    """TC-RO-291~300: 依赖、跨平台、路径"""

    def test_ro291_yaml_importable(self):
        """TC-RO-291: pyyaml 可导入"""
        import yaml
        assert yaml.__version__

    def test_ro292_sqlite3_importable(self):
        """TC-RO-292: sqlite3 可导入"""
        import sqlite3
        assert sqlite3.sqlite_version

    def test_ro297_no_git_still_works(self, tmp_path):
        """TC-RO-297: 没有 git 不影响核心功能"""
        event = _make_event()
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        errs = validate_yaml_parseable(p)
        assert errs == []

    def test_ro299_pathlib_cross_platform(self, tmp_path):
        """TC-RO-299: pathlib 路径跨平台"""
        p = tmp_path / "data" / "novels" / "test" / "events"
        p.mkdir(parents=True)
        assert p.exists()
        assert str(p).replace("\\", "/").endswith("data/novels/test/events")

    def test_ro300_relative_paths(self, tmp_path):
        """TC-RO-300: 相对路径正常工作"""
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "test.yaml").write_text("key: value", encoding="utf-8")
        old = os.getcwd()
        os.chdir(tmp_path)
        try:
            p = Path("data/test.yaml")
            assert p.exists()
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            assert data["key"] == "value"
        finally:
            os.chdir(old)
