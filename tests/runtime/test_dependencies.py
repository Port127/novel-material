"""Runtime、结构化日志与终端模块的依赖边界测试。"""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_logging_and_terminal_do_not_import_each_other():
    forbidden = {
        "run_logging": "novel_material.terminal",
        "terminal": "novel_material.run_logging",
    }
    for package, target in forbidden.items():
        package_root = ROOT / "src" / "novel_material" / package
        assert package_root.is_dir(), f"缺少 package：{package_root}"
        for path in package_root.glob("*.py"):
            imports = imported_modules(path)
            assert not any(
                module == target or module.startswith(f"{target}.")
                for module in imports
            ), f"{path} 不得依赖 {target}"


def test_runtime_package_exists_as_shared_dependency():
    package_root = ROOT / "src" / "novel_material" / "runtime"
    assert package_root.is_dir(), f"缺少 package：{package_root}"


def test_business_code_does_not_call_legacy_llm_state_accessors():
    forbidden = {
        "get_call_details",
        "get_last_call_tokens",
        "get_last_call_finish_reason",
        "clear_call_details",
        "get_api_stats",
        "reset_api_stats",
    }
    violations = []
    source_root = ROOT / "src" / "novel_material"
    compatibility_module = source_root / "infra" / "llm.py"
    for path in source_root.rglob("*.py"):
        if path == compatibility_module:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else None
            if name in forbidden:
                violations.append(f"{path.relative_to(ROOT)}:{node.lineno}:{name}")

    assert violations == [], "发现旧 LLM 调用状态读取：\n" + "\n".join(violations)
