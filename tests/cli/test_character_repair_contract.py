"""人物定向修复 CLI 契约测试。"""

from types import SimpleNamespace

from typer.testing import CliRunner

from novel_material.cli.main import app


def test_characters_repair_character_option_is_repeatable(monkeypatch):
    runner = CliRunner()
    captured = {}

    def fake_stage(material_id, **kwargs):
        captured.update(material_id=material_id, **kwargs)
        return SimpleNamespace(status=SimpleNamespace(value="success"))

    monkeypatch.setattr("novel_material.cli.pipeline.run_characters_stage", fake_stage)

    result = runner.invoke(
        app,
        [
            "pipeline",
            "characters",
            "nm_demo",
            "--repair-character",
            "陈汉升",
            "--repair-character",
            "沈幼楚",
        ],
    )

    assert result.exit_code == 0
    assert captured["repair_characters"] == ("陈汉升", "沈幼楚")
