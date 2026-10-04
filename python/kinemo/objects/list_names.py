"""Names for objects created as the elements of a list assigned to a variable:
`squares = [k.Square.on(side) for side in tri.sides]` names them `squares[0]`, `squares[1]`, ...,
and `dots = [k.Dot(), k.Dot(x=1)]` names `dots[0]` and `dots[1]`.

The scene file is parsed once (per modification time) to find, for each list element that is
a call, the variable it is assigned to and its index; elements built by a comprehension are
numbered in the order they are made."""

from __future__ import annotations

import ast
import functools
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .._runtime.spans import Span
    from ..scene.scene import Scene

#: (line, char column) of an element call → (variable, index; None inside a comprehension, callee)
Elements = dict[tuple[int, int], tuple[str, "int | None", str]]


def list_element_name(span: "Span", callees: set[str], scene: "Scene") -> str | None:
    """`name[i]` when the call at `span` is an element of a list assigned to `name` and
    calls one of `callees` (the class being built, or the factory)."""
    try:
        elements = _elements(span.file, os.stat(span.file).st_mtime)
    except OSError:
        return None
    found = elements.get((span.line, span.col))
    if found is None or found[2] not in callees:
        return None
    variable, index, _ = found
    if index is None:
        counts: dict[tuple[int, int], int] = scene.__dict__.setdefault("_list_element_counts", {})
        index = counts.get((span.line, span.col), 0)
        counts[(span.line, span.col)] = index + 1
    return f"{variable}[{index}]"


@functools.lru_cache(maxsize=64)
def _elements(path: str, mtime: float) -> Elements:
    try:
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
        tree = ast.parse(source)
    except (OSError, SyntaxError, ValueError):
        return {}
    lines = source.splitlines()
    out: Elements = {}

    def record(call: ast.expr, variable: str, index: int | None) -> None:
        if not isinstance(call, ast.Call):
            return
        callee = call.func.attr if isinstance(call.func, ast.Attribute) else call.func.id if isinstance(call.func, ast.Name) else None
        if callee is None or call.lineno > len(lines):
            return
        # ast columns count UTF-8 bytes; spans count characters.
        column = len(lines[call.lineno - 1].encode("utf-8")[: call.col_offset].decode("utf-8", errors="replace"))
        out[(call.lineno, column)] = (variable, index, callee)

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            variable, value = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            variable, value = node.target.id, node.value
        else:
            continue
        if isinstance(value, ast.List):
            for index, element in enumerate(value.elts):
                record(element, variable, index)
        elif isinstance(value, ast.ListComp):
            record(value.elt, variable, None)
    return out
