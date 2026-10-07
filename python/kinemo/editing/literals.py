"""Classify argument expressions: plain literals are offered for editing whole; inside a
computed expression only its numbers are, so a tool never overwrites what the author
computed."""

from __future__ import annotations

import ast
from typing import Literal, TypeGuard

LiteralKind = Literal["number", "string", "bool", "none", "vector", "color", "ease"]


def literal_kind(node: ast.expr, module_aliases: frozenset[str]) -> LiteralKind | None:
    """Kind of a literal argument, or `None` when it is computed (a name, a call, ...).

    `module_aliases` are the names kinemo is imported as (`k` in `import kinemo as k`), so
    `k.RED` and `k.theme.accent` count as colors and `k.ease.smooth` as an easing.
    """
    if _is_number(node):
        return "number"
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return "bool"
        if isinstance(node.value, str):
            return "string"
        if node.value is None:
            return "none"
        return None
    if isinstance(node, (ast.Tuple, ast.List)) and 2 <= len(node.elts) <= 3 and all(_is_number(e) for e in node.elts):
        return "vector"
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in module_aliases
        and node.attr.isupper()
    ):
        return "color"
    if (
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Attribute)
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id in module_aliases
        and not node.attr.startswith("_")
    ):
        return {"ease": "ease", "theme": "color"}.get(node.value.attr)  # type: ignore[return-value]
    return None


def literal_value(node: ast.expr) -> object:
    """Python value of a literal argument, JSON-friendly: `k.RED` → `"RED"`,
    `k.theme.accent` → `"theme.accent"`, `k.ease.smooth` → `"ease.smooth"`."""
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Attribute):
            return f"{node.value.attr}.{node.attr}"
        return node.attr
    value = ast.literal_eval(node)
    if isinstance(value, tuple):
        return list(value)  # pyright: ignore[reportUnknownArgumentType]
    return value


def numbers_inside(node: ast.expr) -> list[ast.expr]:
    """The numbers written inside a computed expression, in source order: `1.2` in
    `title.x + 1.2`, `3` and `0.75` in `lambda x: 3 * x - 0.75 * x**2`. A sign written
    against a number belongs to it (`-2` in `(a, -2)`); booleans and complex numbers are left
    out."""
    found: list[ast.expr] = []
    signed: set[int] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.UnaryOp) and isinstance(child.op, (ast.USub, ast.UAdd)) and _is_plain_number(child.operand):
            found.append(child)
            signed.add(id(child.operand))
        elif _is_plain_number(child) and id(child) not in signed:
            found.append(child)
    return sorted(found, key=lambda n: (n.lineno, n.col_offset))


def _is_plain_number(node: ast.AST) -> TypeGuard[ast.Constant]:
    return isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool)


def is_number(node: ast.expr) -> bool:
    """Whether `node` is a number literal, signed or not (what a number edit may write)."""
    return _is_number(node)


def _is_number(node: ast.expr) -> bool:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        node = node.operand
    return isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool)


def is_valid_expression(text: str) -> bool:
    """Whether `text` parses as one Python expression (what an edit may write)."""
    try:
        ast.parse(text, mode="eval")
    except SyntaxError:
        return False
    return True
