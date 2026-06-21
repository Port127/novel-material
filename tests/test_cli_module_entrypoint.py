import subprocess
import sys


def test_module_entrypoint_does_not_preimport_main():
    completed = subprocess.run(
        [sys.executable, "-W", "error", "-m", "novel_material.cli.main", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "RuntimeWarning" not in completed.stderr
