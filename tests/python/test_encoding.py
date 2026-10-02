"""Text files are read and written as UTF-8 explicitly.

Without `encoding=`, Python uses the locale's code page, which on Windows cannot decode the
docs and scenes ("—", "×", "→"). This scans the library, the scripts and the website export.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCES = sorted([*(ROOT / "python" / "kinemo").rglob("*.py"), *(ROOT / "scripts").glob("*.py"), *(ROOT / "website").rglob("siteexport/*.py")])


def _text_io_without_encoding(path: Path) -> list[int]:
    lines: list[int] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call) or any(k.arg == "encoding" for k in node.keywords):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in ("read_text", "write_text"):
            lines.append(node.lineno)
        elif isinstance(func, ast.Name) and func.id == "open":
            mode = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == "mode"), None)
            if not (isinstance(mode, ast.Constant) and "b" in str(mode.value)):
                lines.append(node.lineno)
        elif any(k.arg == "text" and isinstance(k.value, ast.Constant) and k.value.value is True for k in node.keywords):
            lines.append(node.lineno)  # subprocess output decoded with the locale
    return lines


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(ROOT)))
def test_text_io_names_its_encoding(path: Path) -> None:
    assert _text_io_without_encoding(path) == [], f"add encoding=\"utf-8\" at these lines of {path.relative_to(ROOT)}"
