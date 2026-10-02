"""Registry of codemods. Each one is exact and idempotent: it rewrites a deprecated
call into its replacement, preserving everything else byte for byte."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Callable

Rewrite = tuple[int, int, int, int, str]  # (line, col, end_line, end_col, replacement)


@dataclass(frozen=True)
class Codemod:
    name: str
    since: str  # version where the old form became deprecated
    description: str
    find: Callable[[ast.AST, str], list[Rewrite]]


def _is_kinemo_call(node: ast.AST, name: str) -> bool:
    if not isinstance(node, ast.Call):
        return False
    f = node.func
    return (isinstance(f, ast.Attribute) and f.attr == name) or (isinstance(f, ast.Name) and f.id == name)


def _line_width_to_length(tree: ast.AST, source: str) -> list[Rewrite]:
    """`k.Line(width=10)` → `k.Line(length=10)` (width is a derived, read-only prop)."""
    out: list[Rewrite] = []
    for node in ast.walk(tree):
        if _is_kinemo_call(node, "Line"):
            for kw in node.keywords:  # type: ignore[attr-defined]
                if kw.arg == "width":
                    line, col = kw.lineno, kw.col_offset
                    out.append((line, col, line, col + len("width"), "length"))
    return out


def _param_text_to_str(tree: ast.AST, source: str) -> list[Rewrite]:
    """`k.Text(...)` used as a scene parameter type → `k.Str(...)` (one name per concept)."""
    out: list[Rewrite] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.keyword) and node.arg == "params" and isinstance(node.value, ast.Dict):
            for value in node.value.values:
                if _is_kinemo_call(value, "Text"):
                    f = value.func  # type: ignore[attr-defined]
                    if isinstance(f, ast.Attribute):
                        end = f.end_col_offset or 0
                        out.append((f.end_lineno or f.lineno, end - len("Text"), f.end_lineno or f.lineno, end, "Str"))
    return out


CODEMODS: list[Codemod] = [
    Codemod("line-length", "0.1", "k.Line(width=) → k.Line(length=)", _line_width_to_length),
    Codemod("param-str", "0.1", "parameter k.Text(...) → k.Str(...)", _param_text_to_str),
]


def _apply(source: str, rewrites: list[Rewrite]) -> str:
    lines = source.splitlines(keepends=True)
    for line, col, end_line, end_col, text in sorted(rewrites, reverse=True):
        if line != end_line:
            continue
        row = lines[line - 1]
        lines[line - 1] = row[:col] + text + row[end_col:]
    return "".join(lines)


def upgrade_source(source: str) -> tuple[str, list[str]]:
    """New source and the names of the codemods that changed something."""
    applied: list[str] = []
    for mod in CODEMODS:
        tree = ast.parse(source)
        rewrites = mod.find(tree, source)
        if rewrites:
            source = _apply(source, rewrites)
            applied.append(mod.name)
    return source, applied
