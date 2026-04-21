import sqlite3
import sys
from pathlib import Path

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

TEST_MATERIAL_ID = "nm_novel_20260101_test"

TAGS_YAML = {
    "event_type": {"description": "事件类型", "values": ["对决", "日常", "回忆"]},
    "conflict": {"description": "冲突", "values": ["人与人", "人与命运"]},
    "stakes": {"description": "赌注", "values": ["生死", "情感"]},
    "relationship": {"description": "关系", "values": ["师徒", "对手"]},
    "interaction": {"description": "互动", "values": ["对抗", "合作"]},
    "character_moment": {"description": "高光", "values": ["觉醒", "牺牲"]},
    "emotion": {"description": "情绪", "values": ["燃", "悲伤", "温暖"]},
    "reader_effect": {"description": "效果", "values": ["催泪", "爽感"]},
    "plot_function": {"description": "功能", "values": ["推进主线", "铺垫"]},
    "plot_stage": {"description": "阶段", "values": ["开端", "发展", "高潮"]},
    "technique": {"description": "技巧", "values": ["伏笔", "反转"]},
    "dialogue_type": {"description": "对白", "values": ["争论", "独白"]},
    "info_delivery": {"description": "信息", "values": ["展示", "叙述"]},
    "setting": {"description": "空间类型", "values": ["战场", "城市"]},
    "time_weather": {"description": "天气", "values": ["黎明", "暴雨"]},
    "pacing": {"description": "节奏", "values": ["快", "中", "慢"]},
    "pov": {"description": "视角", "values": ["第一人称", "第三人称限制"]},
    "power_dynamic": {"description": "力量", "values": ["以弱胜强", "势均力敌"]},
    "moral_spectrum": {"description": "道德", "values": ["正义", "灰色", "黑暗"]},
    "scale": {"description": "规模", "values": ["个人", "群体", "国家"]},
}


@pytest.fixture()
def novel_env(tmp_path, monkeypatch):
    """Set up a tmp novel directory tree matching data/ layout expected by scripts."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    novels_dir = data_dir / "novels"
    novels_dir.mkdir()

    with open(data_dir / "tags.yaml", "w", encoding="utf-8") as f:
        yaml.dump(TAGS_YAML, f, allow_unicode=True)

    mid = TEST_MATERIAL_ID
    novel_dir = novels_dir / mid
    novel_dir.mkdir()
    events_dir = novel_dir / "events"
    events_dir.mkdir()

    meta = {"material_id": mid, "name": "测试小说", "author": "测试作者",
            "type": "novel", "status": "complete", "source": "source.txt"}
    with open(novel_dir / "meta.yaml", "w", encoding="utf-8") as f:
        yaml.dump(meta, f, allow_unicode=True)

    characters = {
        "material_id": mid,
        "roster": [
            {"name": "张三", "role": "protagonist", "archetype": "英雄",
             "moral_spectrum": "正义", "arc_summary": "成长", "narrative_function": "主线",
             "psychology": {"fatal_flaw": "冲动", "obsession": "力量"}},
            {"name": "李四", "role": "antagonist", "archetype": "暗影",
             "moral_spectrum": "黑暗", "arc_summary": "堕落", "narrative_function": "冲突"},
        ],
    }
    with open(novel_dir / "characters.yaml", "w", encoding="utf-8") as f:
        yaml.dump(characters, f, allow_unicode=True)

    index = {"materials": [{"id": mid, "type": "novel", "name": "测试小说", "author": "测试作者"}]}
    with open(data_dir / "index.yaml", "w", encoding="utf-8") as f:
        yaml.dump(index, f, allow_unicode=True)

    for i in range(1, 11):
        event = {
            "id": f"{mid}_ev{i:04d}", "chapter": f"第{i}章 标题{i}",
            "title": f"事件标题_{i}", "summary": f"第{i}章的精彩事件描述，各不相同_{i}",
            "tension": (i % 5) + 1,
            "event_type": ["对决" if i % 2 == 0 else "日常"],
            "conflict": ["人与人"], "stakes": ["生死"],
            "relationship": ["对手"], "interaction": ["对抗"],
            "character_moment": ["觉醒"], "power_dynamic": "以弱胜强",
            "moral_spectrum": "正义", "plot_stage": "发展",
            "plot_function": ["推进主线"], "pacing": "快",
            "technique": ["伏笔"], "dialogue_type": ["争论"],
            "pov": "第三人称限制", "info_delivery": ["展示"],
            "setting": ["战场"], "scale": "个人",
            "time_weather": ["黎明"], "reader_effect": ["爽感"],
            "emotion": ["燃" if i % 3 != 0 else "悲伤"],
            "characters": ["张三", "李四"],
        }
        with open(events_dir / f"ev{i:04d}.yaml", "w", encoding="utf-8") as f:
            yaml.dump(event, f, allow_unicode=True)

    monkeypatch.chdir(tmp_path)
    return tmp_path, data_dir, novel_dir, mid
