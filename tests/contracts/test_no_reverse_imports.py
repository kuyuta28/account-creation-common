from __future__ import annotations

import ast
from pathlib import Path

COMMON_SRC = Path(__file__).resolve().parents[2] / "src" / "common"
FORBIDDEN_IMPORT_PREFIXES = (
    "aa_proxy",
    "web_ui",
    "mail_service",
    "registrar",
    "tts_proxy",
)


def _imported_modules(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.append(node.module)
    return modules


def test_common_does_not_import_service_packages():
    violations = []
    for path in COMMON_SRC.rglob("*.py"):
        for module in _imported_modules(path):
            if module.startswith(FORBIDDEN_IMPORT_PREFIXES):
                violations.append(f"{path.relative_to(COMMON_SRC)} imports {module}")

    assert violations == []
