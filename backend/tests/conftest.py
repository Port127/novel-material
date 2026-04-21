import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEST_MATERIAL_ID = "nm_novel_20260101_test"

TAGS_YAML = {
    "event_type": {"description": "事件类型", "values": ["对决", "日常", "回忆", "追逐", "密谋"]},
    "conflict": {"description": "冲突类型", "values": ["人与人", "人与命运", "人与自然"]},
    "stakes": {"description": "赌注", "values": ["生死", "情感", "尊严"]},
    "relationship": {"description": "关系", "values": ["师徒", "对手", "恋人"]},
    "interaction": {"description": "互动", "values": ["对抗", "合作", "试探"]},
    "character_moment": {"description": "人物高光", "values": ["觉醒", "牺牲", "蜕变"]},
    "emotion": {"description": "情绪", "values": ["燃", "悲伤", "温暖", "紧张"]},
    "reader_effect": {"description": "读者效果", "values": ["催泪", "爽感", "悬念"]},
    "plot_function": {"description": "情节功能", "values": ["推进主线", "铺垫", "高潮"]},
    "plot_stage": {"description": "情节阶段", "values": ["开端", "发展", "高潮", "结局"]},
    "technique": {"description": "技巧", "values": ["伏笔", "反转", "蒙太奇"]},
    "dialogue_type": {"description": "对白类型", "values": ["争论", "独白", "潜台词"]},
    "info_delivery": {"description": "信息传达", "values": ["展示", "叙述", "对话"]},
    "setting": {"description": "空间类型", "values": ["战场", "城市", "荒野"]},
    "time_weather": {"description": "时间天气", "values": ["黎明", "暴雨", "深夜"]},
    "pacing": {"description": "节奏", "values": ["快", "中", "慢"]},
    "pov": {"description": "视角", "values": ["第一人称", "第三人称限制", "全知"]},
    "power_dynamic": {"description": "力量对比", "values": ["以弱胜强", "势均力敌", "碾压"]},
    "moral_spectrum": {"description": "道德光谱", "values": ["正义", "灰色", "黑暗"]},
    "scale": {"description": "规模", "values": ["个人", "群体", "国家"]},
}


def _create_test_db(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS novels (
            material_id TEXT PRIMARY KEY, name TEXT, author TEXT,
            status TEXT, total_events INTEGER DEFAULT 0, built_at TEXT
        );
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT NOT NULL, material_id TEXT NOT NULL,
            chapter TEXT, title TEXT, summary TEXT, tension INTEGER DEFAULT 0,
            pacing TEXT, pov TEXT, power_dynamic TEXT, moral_spectrum TEXT,
            plot_stage TEXT, scale TEXT,
            PRIMARY KEY (event_id, material_id)
        );
        CREATE TABLE IF NOT EXISTS event_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL, material_id TEXT NOT NULL,
            dimension TEXT NOT NULL, value TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS characters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            material_id TEXT NOT NULL, name TEXT NOT NULL,
            role TEXT, archetype TEXT, moral_spectrum TEXT,
            arc_summary TEXT, narrative_function TEXT,
            fatal_flaw TEXT, obsession TEXT, soft_spot TEXT, misbelief TEXT
        );
        CREATE TABLE IF NOT EXISTS event_characters (
            event_id TEXT NOT NULL, material_id TEXT NOT NULL,
            character_name TEXT NOT NULL,
            PRIMARY KEY (event_id, material_id, character_name)
        );
        CREATE INDEX IF NOT EXISTS idx_et_dv ON event_tags(dimension, value);
        CREATE INDEX IF NOT EXISTS idx_events_mat ON events(material_id);
        CREATE INDEX IF NOT EXISTS idx_chars_mat ON characters(material_id);
        CREATE INDEX IF NOT EXISTS idx_ec_name ON event_characters(character_name);
    """)

    mid = TEST_MATERIAL_ID
    conn.execute(
        "INSERT INTO novels VALUES (?,?,?,?,?,?)",
        (mid, "测试小说", "测试作者", "complete", 3, "2026-01-01T00:00:00"),
    )

    events = [
        (f"{mid}_ch001_s1", mid, "第1章 起始", "黎明之战", "主角在黎明时分与宿敌展开决战", 4, "快", "第三人称限制", "以弱胜强", "正义", "发展", "个人"),
        (f"{mid}_ch002_s1", mid, "第2章 转折", "温暖的回忆", "主角回忆起师父的教诲", 2, "慢", "第一人称", "势均力敌", "灰色", "发展", "个人"),
        (f"{mid}_ch003_s1", mid, "第3章 高潮", "最终对决", "正邪大战一触即发", 5, "快", "全知", "以弱胜强", "正义", "高潮", "国家"),
    ]
    conn.executemany("INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", events)

    tag_rows = [
        (f"{mid}_ch001_s1", mid, "event_type", "对决"),
        (f"{mid}_ch001_s1", mid, "emotion", "燃"),
        (f"{mid}_ch001_s1", mid, "conflict", "人与人"),
        (f"{mid}_ch002_s1", mid, "event_type", "回忆"),
        (f"{mid}_ch002_s1", mid, "emotion", "温暖"),
        (f"{mid}_ch003_s1", mid, "event_type", "对决"),
        (f"{mid}_ch003_s1", mid, "emotion", "燃"),
        (f"{mid}_ch003_s1", mid, "emotion", "紧张"),
        (f"{mid}_ch003_s1", mid, "conflict", "人与命运"),
    ]
    conn.executemany(
        "INSERT INTO event_tags (event_id, material_id, dimension, value) VALUES (?,?,?,?)",
        tag_rows,
    )

    chars = [
        (mid, "张三", "protagonist", "英雄", "正义", "从新手到大师", "推动主线", "冲动", "力量", "妹妹", "只有力量才能保护一切"),
        (mid, "李四", "antagonist", "暗影", "黑暗", "从同门到宿敌", "制造冲突", "傲慢", "权力", None, "弱者不配活着"),
    ]
    conn.executemany(
        "INSERT INTO characters (material_id,name,role,archetype,moral_spectrum,arc_summary,narrative_function,fatal_flaw,obsession,soft_spot,misbelief) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        chars,
    )

    ec_rows = [
        (f"{mid}_ch001_s1", mid, "张三"), (f"{mid}_ch001_s1", mid, "李四"),
        (f"{mid}_ch002_s1", mid, "张三"),
        (f"{mid}_ch003_s1", mid, "张三"), (f"{mid}_ch003_s1", mid, "李四"),
    ]
    conn.executemany("INSERT INTO event_characters VALUES (?,?,?)", ec_rows)

    conn.commit()
    conn.close()


def _create_novel_dir(novels_dir: Path):
    mid = TEST_MATERIAL_ID
    novel_dir = novels_dir / mid
    novel_dir.mkdir(parents=True, exist_ok=True)

    meta = {
        "material_id": mid,
        "name": "测试小说",
        "author": "测试作者",
        "type": "novel",
        "status": "complete",
        "source": "source.txt",
        "formatted": True,
    }
    with open(novel_dir / "meta.yaml", "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True)

    outline = {
        "material_id": mid,
        "premise": "少年张三的成长之路",
        "theme": ["成长", "牺牲"],
        "structure": [{"act": "第一幕", "title": "起始", "chapters": ["第1章", "第2章"]}],
    }
    with open(novel_dir / "outline.yaml", "w", encoding="utf-8") as f:
        yaml.dump(outline, f, allow_unicode=True)

    worldbuilding = {
        "material_id": mid,
        "power_system": {"name": "灵力体系", "levels": ["入门", "大师"]},
    }
    with open(novel_dir / "worldbuilding.yaml", "w", encoding="utf-8") as f:
        yaml.dump(worldbuilding, f, allow_unicode=True)

    characters = {
        "material_id": mid,
        "roster": [
            {"name": "张三", "role": "protagonist", "traits": ["勇敢", "冲动"]},
            {"name": "李四", "role": "antagonist", "traits": ["狡诈", "强大"]},
        ],
    }
    with open(novel_dir / "characters.yaml", "w", encoding="utf-8") as f:
        yaml.dump(characters, f, allow_unicode=True)

    tags = {"material_id": mid, "genre": ["玄幻"], "theme": ["成长"]}
    with open(novel_dir / "tags.yaml", "w", encoding="utf-8") as f:
        yaml.dump(tags, f, allow_unicode=True)

    stats = {"material_id": mid, "total_events": 3, "avg_tension": 3.67}
    with open(novel_dir / "stats.yaml", "w", encoding="utf-8") as f:
        yaml.dump(stats, f, allow_unicode=True)

    (novel_dir / "stats.html").write_text("<html><body>Stats</body></html>", encoding="utf-8")
    (novel_dir / "source.txt").write_text("第1章 起始\n这是正文内容。\n\n第2章 转折\n继续。", encoding="utf-8")

    events_dir = novel_dir / "events"
    events_dir.mkdir(exist_ok=True)
    for i, (sid, ch, title, summary) in enumerate([
        (f"{mid}_ch001_s1", "第1章 起始", "黎明之战", "主角在黎明时分与宿敌展开决战"),
        (f"{mid}_ch002_s1", "第2章 转折", "温暖的回忆", "主角回忆起师父的教诲"),
        (f"{mid}_ch003_s1", "第3章 高潮", "最终对决", "正邪大战一触即发"),
    ], 1):
        event = {
            "id": sid, "chapter": ch, "title": title, "summary": summary,
            "tension": i + 2, "event_type": ["对决"], "emotion": ["燃"],
            "conflict": ["人与人"], "stakes": ["生死"],
            "relationship": ["对手"], "interaction": ["对抗"],
            "character_moment": ["觉醒"], "power_dynamic": "以弱胜强",
            "moral_spectrum": "正义", "plot_stage": "发展",
            "plot_function": ["推进主线"], "pacing": "快",
            "technique": ["伏笔"], "dialogue_type": ["争论"],
            "pov": "第三人称限制", "info_delivery": ["展示"],
            "setting": ["战场"], "scale": "个人",
            "time_weather": ["黎明"], "reader_effect": ["爽感"],
            "characters": ["张三", "李四"],
        }
        with open(events_dir / f"ev{i:04d}.yaml", "w", encoding="utf-8") as f:
            yaml.dump(event, f, allow_unicode=True)


@pytest.fixture()
def data_env(tmp_path):
    """Set up a complete temporary data environment and patch data_service paths."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    novels_dir = data_dir / "novels"
    novels_dir.mkdir()
    config_dir = data_dir / ".config"
    config_dir.mkdir()

    with open(data_dir / "tags.yaml", "w", encoding="utf-8") as f:
        yaml.dump(TAGS_YAML, f, allow_unicode=True)

    index = {
        "materials": [{
            "id": TEST_MATERIAL_ID, "type": "novel", "name": "测试小说",
            "author": "测试作者", "folder": f"novels/{TEST_MATERIAL_ID}",
            "status": "complete", "added": "2026-01-01",
        }]
    }
    with open(data_dir / "index.yaml", "w", encoding="utf-8") as f:
        yaml.dump(index, f, allow_unicode=True)

    db_path = data_dir / "material.db"
    _create_test_db(db_path)
    _create_novel_dir(novels_dir)

    _write_json(config_dir / "pipeline_status.json", {})
    _write_json(config_dir / "llm_config.json", {})

    return data_dir, db_path, novels_dir, tmp_path


@pytest.fixture()
def patched_ds(data_env):
    """Patch data_service module-level paths."""
    data_dir, db_path, novels_dir, tmp_path = data_env
    import services.data_service as ds
    orig = (ds.PROJECT_ROOT, ds.DATA_DIR, ds.DB_PATH, ds.NOVELS_DIR)
    ds.PROJECT_ROOT = tmp_path
    ds.DATA_DIR = data_dir
    ds.DB_PATH = db_path
    ds.NOVELS_DIR = novels_dir
    yield ds
    ds.PROJECT_ROOT, ds.DATA_DIR, ds.DB_PATH, ds.NOVELS_DIR = orig


@pytest.fixture()
def patched_ps(data_env, patched_ds):
    """Patch pipeline_service paths."""
    data_dir, db_path, novels_dir, tmp_path = data_env
    import services.pipeline_service as ps
    orig = (ps.CONFIG_DIR, ps.STATUS_FILE, ps.LLM_CONFIG_FILE, ps.SCRIPTS_DIR)
    ps.CONFIG_DIR = data_dir / ".config"
    ps.STATUS_FILE = data_dir / ".config" / "pipeline_status.json"
    ps.LLM_CONFIG_FILE = data_dir / ".config" / "llm_config.json"
    ps.SCRIPTS_DIR = tmp_path / "scripts"
    yield ps
    ps.CONFIG_DIR, ps.STATUS_FILE, ps.LLM_CONFIG_FILE, ps.SCRIPTS_DIR = orig


@pytest.fixture()
def client(patched_ds, patched_ps):
    """Create a FastAPI TestClient with patched services."""
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


def _write_json(path: Path, data: dict):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
