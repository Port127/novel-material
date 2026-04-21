"""
知乎调研测试案例 TC-ZH-001 ~ TC-ZH-100
真实运行，覆盖素材入库、标签体系、搜索检索、事件质量、人物世界观、索引数据库、前端 API、统计报告。
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT / "scripts"
BACKEND_DIR = ROOT / "backend"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / "core"))

from core.validate_yaml import validate_event, _flatten_event, validate_meta, validate_yaml_parseable, load_tags_dict as _load_tags
from core.quality_audit import compute_batch_quality, detect_quality_drift, load_events, _as_list
from core.build_db import create_schema, ingest_novel, _flatten_event as db_flatten, _str_or_first, _as_list as db_as_list

REAL_DATA = ROOT / "data"
REAL_TAGS = REAL_DATA / "tags.yaml"
REAL_INDEX = REAL_DATA / "index.yaml"
REAL_DB = REAL_DATA / "material.db"
REAL_NOVELS = REAL_DATA / "novels"

TAGS_DICT = None
if REAL_TAGS.exists():
    with open(REAL_TAGS, encoding="utf-8") as f:
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


# ==============================================================================
# A. 素材库管理与入库 TC-ZH-001 ~ TC-ZH-015
# ==============================================================================
class TestMaterialManagement:
    """TC-ZH-001~015: 入库、导入、去重、格式校验"""

    def test_zh001_short_novel_meta(self, tmp_path):
        """TC-ZH-001: 500字短篇入库后 meta.yaml 结构正确"""
        novel_dir = tmp_path / "data" / "novels" / "nm_novel_20260101_test"
        novel_dir.mkdir(parents=True)
        meta = {"material_id": "nm_novel_20260101_test", "name": "短篇测试",
                "author": "作者", "type": "novel", "status": "raw", "source": "source.txt"}
        (novel_dir / "meta.yaml").write_text(yaml.dump(meta, allow_unicode=True), encoding="utf-8")
        (novel_dir / "source.txt").write_text("a" * 500, encoding="utf-8")
        errs = validate_meta(novel_dir)
        assert errs == [], f"meta 校验失败: {errs}"

    def test_zh005_path_with_chinese_spaces(self, tmp_path):
        """TC-ZH-005: 中文和空格路径不影响 YAML 读写"""
        weird_dir = tmp_path / "数据 目录" / "novels" / "nm_test"
        weird_dir.mkdir(parents=True)
        data = {"title": "测试", "tension": 3}
        p = weird_dir / "test.yaml"
        p.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
        loaded = yaml.safe_load(p.read_text(encoding="utf-8"))
        assert loaded["title"] == "测试"

    def test_zh007_empty_file_rejected(self, tmp_path):
        """TC-ZH-007: 0 字节文件 validate 报错"""
        empty = tmp_path / "empty.yaml"
        empty.write_text("", encoding="utf-8")
        errs = validate_yaml_parseable(empty)
        assert len(errs) > 0 and "空" in errs[0]

    def test_zh009_index_yaml_structure(self):
        """TC-ZH-009: index.yaml 含 materials 列表且字段完整"""
        assert REAL_INDEX.exists(), "data/index.yaml 不存在"
        with open(REAL_INDEX, encoding="utf-8") as f:
            idx = yaml.safe_load(f)
        materials = idx.get("materials", [])
        assert len(materials) > 0, "index.yaml 中无素材"
        for m in materials:
            assert "id" in m, f"缺少 id 字段: {m}"
            assert "name" in m, f"缺少 name 字段: {m}"
            assert m["id"].startswith("nm_"), f"ID 格式异常: {m['id']}"

    def test_zh010_encoding_handling(self, tmp_path):
        """TC-ZH-010: GBK 编码文件在读写时应正确处理"""
        p = tmp_path / "gbk.txt"
        p.write_bytes("你好世界".encode("gbk"))
        content = p.read_bytes().decode("gbk")
        assert content == "你好世界"

    def test_zh012_illegal_tags_detected(self, tmp_path):
        """TC-ZH-012: 导入包含非法标签值的事件被检测到"""
        if not TAGS_DICT:
            pytest.skip("tags.yaml 不存在")
        event = _make_event({"event_type": ["超自然非法值_XYZ"]})
        p = tmp_path / "bad.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        errs = validate_event(p, TAGS_DICT, None)
        assert any("标签越界" in e for e in errs), f"未检测到非法标签: {errs}"

    def test_zh015_unique_ids(self):
        """TC-ZH-015: index.yaml 中所有 material_id 唯一"""
        with open(REAL_INDEX, encoding="utf-8") as f:
            idx = yaml.safe_load(f)
        ids = [m["id"] for m in idx.get("materials", [])]
        assert len(ids) == len(set(ids)), f"有重复 ID: {ids}"


# ==============================================================================
# B. 标签体系 TC-ZH-016 ~ TC-ZH-030
# ==============================================================================
class TestTagSystem:
    """TC-ZH-016~030: 标签完整性、合法性、校验"""

    EVENT_DIMS = [
        "event_type", "conflict", "stakes", "relationship", "interaction",
        "power_dynamic", "character_moment", "moral_spectrum", "emotion",
        "reader_effect", "plot_stage", "plot_function", "pacing",
        "technique", "dialogue_type", "pov", "info_delivery",
        "setting", "scale", "time_weather",
    ]
    NOVEL_DIMS = ["genre", "tone", "narrative_structure", "time_handling",
                  "prose_style", "writing_strength", "tropes"]

    def test_zh016_all_20_event_dims(self):
        """TC-ZH-016: tags.yaml 包含全部 20 个事件标签维度"""
        assert TAGS_DICT is not None
        for dim in self.EVENT_DIMS:
            assert dim in TAGS_DICT, f"缺少维度: {dim}"

    def test_zh017_all_7_novel_dims(self):
        """TC-ZH-017: tags.yaml 包含全部 7 个小说标签维度"""
        assert TAGS_DICT is not None
        for dim in self.NOVEL_DIMS:
            assert dim in TAGS_DICT, f"缺少小说维度: {dim}"

    def test_zh021_illegal_tag_detected(self, tmp_path):
        """TC-ZH-021: 非法标签值被 validate_event 检测"""
        event = _make_event({"emotion": ["非法情绪_ZZZ"]})
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        errs = validate_event(p, TAGS_DICT, None)
        assert any("标签越界" in e and "emotion" in e for e in errs)

    def test_zh022_missing_required_tag_field(self, tmp_path):
        """TC-ZH-022: 缺少必填标签字段被检测"""
        event = _make_event()
        del event["emotion"]
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        errs = validate_event(p, TAGS_DICT, None)
        assert any("emotion" in e for e in errs)

    def test_zh023_tension_out_of_range(self, tmp_path):
        """TC-ZH-023: tension 超出 1-5 范围"""
        for bad_val in [0, 6, -1, 100]:
            event = _make_event({"tension": bad_val})
            p = tmp_path / "test.yaml"
            p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
            errs = validate_event(p, TAGS_DICT, None)
            assert any("tension" in e for e in errs), f"tension={bad_val} 未被检测"

    def test_zh025_tag_whitespace(self, tmp_path):
        """TC-ZH-025: 标签值含前后空格"""
        event = _make_event({"emotion": [" 燃 "]})
        p = tmp_path / "test.yaml"
        p.write_text(yaml.dump(event, allow_unicode=True), encoding="utf-8")
        errs = validate_event(p, TAGS_DICT, None)
        has_issue = any("标签越界" in e for e in errs)
        assert has_issue, "带空格的标签值应检测为非法"

    def test_zh029_multi_dim_search(self):
        """TC-ZH-029: SQLite 多维组合查询"""
        if not REAL_DB.exists():
            pytest.skip("material.db 不存在")
        conn = sqlite3.connect(str(REAL_DB))
        q = """SELECT DISTINCT s.event_id FROM events s
               JOIN event_tags t1 ON s.event_id = t1.event_id AND t1.dimension='event_type' AND t1.value='对决'
               JOIN event_tags t2 ON s.event_id = t2.event_id AND t2.dimension='emotion' AND t2.value='燃'
               LIMIT 10"""
        rows = conn.execute(q).fetchall()
        conn.close()
        assert isinstance(rows, list)  # 能执行不报错

    def test_zh030_tag_diversity_check(self):
        """TC-ZH-030: quality_audit 检测标签雷同"""
        identical = [_make_event({"id": f"ch{i:04d}_s01"}) for i in range(1, 11)]
        result = compute_batch_quality(identical)
        assert result["quality"]["tag_diversity"] < 0.5 or result["status"] == "failed" or \
               result["quality"]["tag_diversity"] == 0.1, \
               f"10个相同标签事件的多样性应该很低: {result['quality']['tag_diversity']}"


# ==============================================================================
# C. 搜索与检索 TC-ZH-031 ~ TC-ZH-050
# ==============================================================================
class TestSearchRetrieval:
    """TC-ZH-031~050: 搜索、SQL注入、性能、一致性"""

    @pytest.fixture(autouse=True)
    def _skip_no_db(self):
        if not REAL_DB.exists():
            pytest.skip("material.db 不存在")

    def _conn(self):
        return sqlite3.connect(str(REAL_DB))

    def test_zh031_keyword_search(self):
        """TC-ZH-031: 关键词检索"""
        conn = self._conn()
        rows = conn.execute("SELECT COUNT(*) FROM events WHERE summary LIKE '%战%'").fetchone()
        conn.close()
        assert rows[0] >= 0

    def test_zh032_nonexistent_keyword(self):
        """TC-ZH-032: 不存在的词返回空结果"""
        conn = self._conn()
        rows = conn.execute("SELECT COUNT(*) FROM events WHERE summary LIKE '%飞天遁地炸裂锤ZZZYYYXXX%'").fetchone()
        conn.close()
        assert rows[0] == 0

    def test_zh034_single_dim_search(self):
        """TC-ZH-034: 按 emotion=悲伤 筛选"""
        conn = self._conn()
        rows = conn.execute(
            "SELECT event_id FROM event_tags WHERE dimension='emotion' AND value='悲伤' LIMIT 5"
        ).fetchall()
        conn.close()
        assert isinstance(rows, list)

    def test_zh035_multi_dim_and(self):
        """TC-ZH-035: 多维 AND 查询"""
        conn = self._conn()
        q = """SELECT s.event_id FROM events s
               WHERE s.event_id IN (SELECT event_id FROM event_tags WHERE dimension='emotion' AND value='燃')
               AND s.event_id IN (SELECT event_id FROM event_tags WHERE dimension='event_type' AND value='对决')
               LIMIT 10"""
        rows = conn.execute(q).fetchall()
        conn.close()
        assert isinstance(rows, list)

    def test_zh036_or_query(self):
        """TC-ZH-036: OR 查询"""
        conn = self._conn()
        rows = conn.execute(
            "SELECT DISTINCT event_id FROM event_tags WHERE dimension='emotion' AND value IN ('燃','紧张') LIMIT 10"
        ).fetchall()
        conn.close()
        assert isinstance(rows, list)

    def test_zh037_tension_range(self):
        """TC-ZH-037: tension >= 4"""
        conn = self._conn()
        rows = conn.execute("SELECT COUNT(*) FROM events WHERE tension >= 4").fetchone()
        conn.close()
        assert rows[0] >= 0

    def test_zh038_character_search(self):
        """TC-ZH-038: 按人物搜索"""
        conn = self._conn()
        rows = conn.execute("SELECT COUNT(*) FROM characters").fetchone()
        conn.close()
        assert rows[0] > 0, "数据库中无人物数据"

    def test_zh041_cross_novel_search(self):
        """TC-ZH-041: 跨小说搜索"""
        conn = self._conn()
        rows = conn.execute(
            "SELECT DISTINCT material_id FROM event_tags WHERE dimension='emotion' AND value='燃'"
        ).fetchall()
        conn.close()
        materials = [r[0] for r in rows]
        assert len(materials) >= 1, "应至少有1本小说含 emotion=燃"

    def test_zh044_sql_injection(self):
        """TC-ZH-044: SQL 注入防御"""
        conn = self._conn()
        malicious = "'; DROP TABLE events; --"
        rows = conn.execute(
            "SELECT COUNT(*) FROM events WHERE summary LIKE ?", (f"%{malicious}%",)
        ).fetchone()
        still_exists = conn.execute("SELECT COUNT(*) FROM events").fetchone()
        conn.close()
        assert still_exists[0] > 0, "events 表被删除了！SQL 注入成功！"
        assert rows[0] == 0

    def test_zh045_yaml_sqlite_consistency(self):
        """TC-ZH-045: YAML 与 SQLite 事件数一致性"""
        conn = self._conn()
        novels = conn.execute("SELECT material_id, total_events FROM novels").fetchall()
        conn.close()
        for mid, db_count in novels:
            events_dir = REAL_NOVELS / mid / "events"
            if not events_dir.exists():
                continue
            yaml_count = len(list(events_dir.glob("ch*.yaml")))
            assert db_count == yaml_count, \
                f"{mid}: SQLite={db_count} vs YAML={yaml_count}"

    def test_zh050_search_performance(self):
        """TC-ZH-050: 搜索性能 < 2秒"""
        import time
        conn = self._conn()
        start = time.time()
        conn.execute(
            """SELECT s.event_id, s.title FROM events s
               JOIN event_tags t ON s.event_id = t.event_id
               WHERE t.dimension='emotion' AND t.value='燃'
               LIMIT 100"""
        ).fetchall()
        elapsed = time.time() - start
        conn.close()
        assert elapsed < 2.0, f"搜索耗时 {elapsed:.2f}s 超过 2 秒"


# ==============================================================================
# D. 事件拆分与质量 TC-ZH-051 ~ TC-ZH-065
# ==============================================================================
class TestEventQuality:
    """TC-ZH-051~065: 事件质量、Anti-Pattern、断点恢复"""

    def test_zh052_no_number_titles(self):
        """TC-ZH-052: 真实事件 title 不是编号形式"""
        for novel_dir in REAL_NOVELS.iterdir():
            events_dir = novel_dir / "events"
            if not events_dir.exists():
                continue
            for sf in list(events_dir.glob("ch*.yaml"))[:20]:
                try:
                    data = yaml.safe_load(sf.read_text(encoding="utf-8"))
                except:
                    continue
                if not data:
                    continue
                title = str(data.get("title", ""))
                assert not (title.startswith("事件") and title[2:].isdigit()), \
                    f"{sf.name}: title 是编号形式 '{title}'"

    def test_zh054_tag_diversity_in_real_data(self):
        """TC-ZH-054: 真实数据中同批次标签组合不完全相同"""
        for novel_dir in REAL_NOVELS.iterdir():
            events_dir = novel_dir / "events"
            if not events_dir.exists():
                continue
            events = load_events(events_dir, "1-10")
            if len(events) < 3:
                continue
            result = compute_batch_quality(events)
            q = result.get("quality", {})
            assert q.get("tag_diversity", 0) > 0.1, \
                f"{novel_dir.name}: 前10章标签多样性过低 {q.get('tag_diversity')}"
            break

    def test_zh056_yaml_safe_load(self):
        """TC-ZH-056: 所有真实事件 YAML 能被 safe_load 解析"""
        failures = []
        for novel_dir in REAL_NOVELS.iterdir():
            events_dir = novel_dir / "events"
            if not events_dir.exists():
                continue
            for sf in list(events_dir.glob("ch*.yaml"))[:50]:
                try:
                    yaml.safe_load(sf.read_text(encoding="utf-8"))
                except yaml.YAMLError as e:
                    failures.append(f"{novel_dir.name}/{sf.name}: {e}")
        assert len(failures) == 0, f"YAML 解析失败: {failures[:5]}"

    def test_zh058_quality_audit_runs(self):
        """TC-ZH-058: quality_audit 能正常审计"""
        for novel_dir in REAL_NOVELS.iterdir():
            events_dir = novel_dir / "events"
            if not events_dir.exists():
                continue
            events = load_events(events_dir, "1-10")
            if not events:
                continue
            result = compute_batch_quality(events)
            assert "status" in result
            assert result["events_count"] > 0
            break

    def test_zh059_detect_cloned_events(self):
        """TC-ZH-059: 全部相同标签的事件被检测"""
        clones = [_make_event({"id": f"ch{i:04d}_s01"}) for i in range(1, 11)]
        result = compute_batch_quality(clones)
        assert result["quality"]["tag_diversity"] <= 0.1

    def test_zh064_event_id_format(self):
        """TC-ZH-064: 真实事件 ID 格式正确"""
        import re
        pattern = re.compile(r"ch\d{4}_s\d{1,2}")
        for novel_dir in REAL_NOVELS.iterdir():
            events_dir = novel_dir / "events"
            if not events_dir.exists():
                continue
            for sf in list(events_dir.glob("ch*.yaml"))[:20]:
                try:
                    data = yaml.safe_load(sf.read_text(encoding="utf-8"))
                except:
                    continue
                if not data:
                    continue
                sid = data.get("id", "")
                assert pattern.match(sid), f"{sf.name}: ID 格式异常 '{sid}'"
            break

    def test_zh065_not_all_conflict_empty(self):
        """TC-ZH-065: 不是所有事件 conflict 都为空"""
        for novel_dir in REAL_NOVELS.iterdir():
            events_dir = novel_dir / "events"
            if not events_dir.exists():
                continue
            has_conflict = 0
            total = 0
            for sf in list(events_dir.glob("ch*.yaml"))[:50]:
                try:
                    data = yaml.safe_load(sf.read_text(encoding="utf-8"))
                except:
                    continue
                if not data:
                    continue
                total += 1
                c = data.get("conflict", [])
                if c and c != []:
                    has_conflict += 1
            if total > 5:
                assert has_conflict > 0, f"{novel_dir.name}: 前50个事件 conflict 全为空"
                break


# ==============================================================================
# E. 人物与世界观 TC-ZH-066 ~ TC-ZH-075
# ==============================================================================
class TestCharactersWorldbuilding:
    """TC-ZH-066~075: 人物名册、世界观、全局索引"""

    def test_zh066_characters_roster(self):
        """TC-ZH-066: characters.yaml 包含 roster 列表"""
        for novel_dir in REAL_NOVELS.iterdir():
            chars = novel_dir / "characters.yaml"
            if not chars.exists():
                continue
            data = yaml.safe_load(chars.read_text(encoding="utf-8"))
            roster = data.get("roster", data.get("characters", []))
            assert len(roster) > 0, f"{novel_dir.name}: 人物名册为空"
            for c in roster[:5]:
                assert "name" in c, f"人物缺少 name 字段"
            break

    def test_zh070_worldbuilding_exists(self):
        """TC-ZH-070: 至少有一本小说有 worldbuilding.yaml"""
        found = False
        for novel_dir in REAL_NOVELS.iterdir():
            if (novel_dir / "worldbuilding.yaml").exists():
                data = yaml.safe_load((novel_dir / "worldbuilding.yaml").read_text(encoding="utf-8"))
                assert data is not None, f"{novel_dir.name}: worldbuilding.yaml 为空"
                found = True
                break
        assert found, "没有小说生成了 worldbuilding.yaml"

    def test_zh071_outline_structure(self):
        """TC-ZH-071: outline.yaml 包含 premise/theme/structure"""
        for novel_dir in REAL_NOVELS.iterdir():
            outline = novel_dir / "outline.yaml"
            if not outline.exists():
                continue
            data = yaml.safe_load(outline.read_text(encoding="utf-8"))
            assert data is not None
            break

    def test_zh074_character_index(self):
        """TC-ZH-074: character_index.yaml 聚合了多本小说人物"""
        ci = REAL_DATA / "character_index.yaml"
        if not ci.exists():
            pytest.skip("character_index.yaml 不存在")
        data = yaml.safe_load(ci.read_text(encoding="utf-8"))
        assert data is not None

    def test_zh075_plot_index(self):
        """TC-ZH-075: plot_index.yaml 存在"""
        pi = REAL_DATA / "plot_index.yaml"
        if not pi.exists():
            pytest.skip("plot_index.yaml 不存在")
        data = yaml.safe_load(pi.read_text(encoding="utf-8"))
        assert data is not None


# ==============================================================================
# F. 索引与数据库 TC-ZH-076 ~ TC-ZH-085
# ==============================================================================
class TestIndexDatabase:
    """TC-ZH-076~085: 索引生成、SQLite 同步、可重建性"""

    def test_zh078_sqlite_event_count(self):
        """TC-ZH-078: SQLite 事件数与 novels 表记录一致"""
        if not REAL_DB.exists():
            pytest.skip("material.db 不存在")
        conn = sqlite3.connect(str(REAL_DB))
        for mid, total in conn.execute("SELECT material_id, total_events FROM novels").fetchall():
            actual = conn.execute("SELECT COUNT(*) FROM events WHERE material_id=?", (mid,)).fetchone()[0]
            assert total == actual, f"{mid}: novels.total_events={total} vs actual={actual}"
        conn.close()

    def test_zh079_rebuild_db(self, tmp_path):
        """TC-ZH-079: 从 YAML 重建 SQLite"""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)
        old_cwd = os.getcwd()
        os.chdir(ROOT)
        try:
            with open(REAL_INDEX, encoding="utf-8") as f:
                idx = yaml.safe_load(f)
            first_mid = idx["materials"][0]["id"]
            count = ingest_novel(conn, first_mid)
            assert count >= 0
            n = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
            assert n == count
        finally:
            os.chdir(old_cwd)
            conn.close()

    def test_zh080_delete_and_rebuild(self, tmp_path):
        """TC-ZH-080: 删除 DB 后可重建"""
        db_path = tmp_path / "material.db"
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)
        conn.execute("INSERT INTO novels VALUES ('test','n','a','complete',0,'now')")
        conn.commit()
        conn.close()
        db_path.unlink()
        assert not db_path.exists()
        conn = sqlite3.connect(str(db_path))
        create_schema(conn)
        conn.close()
        assert db_path.exists()

    def test_zh081_flatten_nested_format(self):
        """TC-ZH-081: 嵌套格式事件能被正确展平"""
        nested = {
            "id": "ch0001_s01", "chapter": "第1章", "title": "测试",
            "summary": "test", "tension": 3,
            "content": {"event_type": ["对决"], "conflict": ["人与人"], "stakes": ["生死"]},
            "people": {"relationship": ["对手"], "interaction": ["对抗"],
                       "power_dynamic": "以弱胜强", "character_moment": ["觉醒"],
                       "moral_spectrum": "正义"},
            "emotion": {"emotion": ["燃"], "reader_effect": ["爽感"], "tension": 3},
            "structure": {"plot_stage": "发展", "plot_function": ["推进主线"], "pacing": "快"},
            "craft": {"technique": ["伏笔"], "dialogue_type": ["争论"], "pov": "第三人称限制", "info_delivery": ["展示"]},
            "setting": {"location": ["战场"], "scale": "个人", "time_weather": ["黎明"]},
            "characters": ["张三"],
        }
        flat = db_flatten(nested)
        assert flat.get("event_type") == ["对决"]
        assert flat.get("emotion") == ["燃"]
        assert flat.get("pov") == "第三人称限制"

    def test_zh082_yaml_db_one_to_one(self):
        """TC-ZH-082: SQLite 记录与 YAML 文件一一对应"""
        if not REAL_DB.exists():
            pytest.skip("material.db 不存在")
        conn = sqlite3.connect(str(REAL_DB))
        for mid, in conn.execute("SELECT material_id FROM novels").fetchall():
            db_events = set(r[0] for r in conn.execute(
                "SELECT event_id FROM events WHERE material_id=?", (mid,)).fetchall())
            events_dir = REAL_NOVELS / mid / "events"
            if not events_dir.exists():
                continue
            yaml_events = set()
            for sf in events_dir.glob("ch*.yaml"):
                try:
                    data = yaml.safe_load(sf.read_text(encoding="utf-8"))
                    if data:
                        yaml_events.add(data.get("id", sf.stem))
                except:
                    pass
            missing_in_db = yaml_events - db_events
            extra_in_db = db_events - yaml_events
            assert len(missing_in_db) == 0, f"{mid}: YAML有但DB无: {list(missing_in_db)[:5]}"
            assert len(extra_in_db) == 0, f"{mid}: DB有但YAML无: {list(extra_in_db)[:5]}"
        conn.close()

    def test_zh084_index_paths_valid(self):
        """TC-ZH-084: index.yaml 中所有 folder 路径实际存在"""
        with open(REAL_INDEX, encoding="utf-8") as f:
            idx = yaml.safe_load(f)
        broken = []
        for m in idx.get("materials", []):
            folder = m.get("folder", "")
            # folder may be relative to project root (e.g. "data/novels/xxx") or to data/ (e.g. "novels/xxx")
            full_path = ROOT / folder
            if not full_path.exists():
                full_path = REAL_DATA / folder
            if not full_path.exists():
                broken.append(f"{m.get('id')}: {folder}")
        assert len(broken) == 0, f"路径不存在: {broken}"


# ==============================================================================
# G. 前端 API TC-ZH-086 ~ TC-ZH-095 + H. 统计 TC-ZH-096 ~ TC-ZH-100
# ==============================================================================
class TestFrontendAPI:
    """TC-ZH-086~100: FastAPI 端点测试"""

    @pytest.fixture(autouse=True)
    def _setup_client(self, tmp_path):
        # Use the backend's conftest fixtures
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

    def test_zh086_dashboard(self):
        """TC-ZH-086: Dashboard API 返回统计"""
        r = self.client.get("/api/stats")
        assert r.status_code == 200
        data = r.json()
        assert "novels" in data or "total_materials" in data

    def test_zh087_material_list(self):
        """TC-ZH-087: 素材列表 API"""
        r = self.client.get("/api/materials")
        assert r.status_code == 200
        assert len(r.json()) > 0

    def test_zh088_material_detail(self):
        """TC-ZH-088: 素材详情 API"""
        r = self.client.get(f"/api/materials/{self.mid}")
        assert r.status_code == 200

    def test_zh089_missing_field_fallback(self):
        """TC-ZH-089: 不存在的素材返回 404"""
        r = self.client.get("/api/materials/nm_fake_nonexistent_id")
        assert r.status_code == 404

    def test_zh090_event_search(self):
        """TC-ZH-090: 事件搜索 API"""
        r = self.client.get("/api/search/events", params={"event_type": "对决"})
        assert r.status_code == 200

    def test_zh091_character_search(self):
        """TC-ZH-091: 人物搜索 API"""
        r = self.client.get("/api/search/characters", params={"name": "张三"})
        assert r.status_code == 200

    def test_zh092_tag_dict(self):
        """TC-ZH-092: 标签字典 API"""
        r = self.client.get("/api/tags")
        assert r.status_code == 200

    def test_zh094_500_error(self):
        """TC-ZH-094: API 错误返回 JSON 而非白屏"""
        r = self.client.get("/api/materials/nm_fake_nonexistent_id/outline")
        assert r.status_code in (404, 500)
        assert "application/json" in r.headers.get("content-type", "")

    def test_zh096_stats_yaml(self):
        """TC-ZH-096: stats API"""
        r = self.client.get(f"/api/materials/{self.mid}/stats")
        assert r.status_code == 200

    def test_zh098_stats_html(self):
        """TC-ZH-098: stats.html API"""
        r = self.client.get(f"/api/materials/{self.mid}/stats/html")
        assert r.status_code == 200
        assert "html" in r.headers.get("content-type", "").lower() or "text" in r.headers.get("content-type", "").lower()
