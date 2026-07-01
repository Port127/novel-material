from novel_material.runtime.contracts import RunStatus
from novel_material.storage.sync_core import _sync_result


def test_sync_result_preserves_release_gate_summary() -> None:
    result = _sync_result(
        "nm_demo",
        RunStatus.SUCCESS,
        release_gate={
            "decision": "allow",
            "release_status": "degraded",
            "override": True,
        },
    )

    assert result.outputs["release_gate"]["decision"] == "allow"
    assert result.outputs["release_gate"]["override"] is True
