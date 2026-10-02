"""W0312: a signal used as a clock (`d=` of `k.integrate`) is animated with easing.

    clock = k.signal(0)
    energy = k.integrate(power, d=clock)
    s.play(clock.to(10, duration=10))          # default easing: the clock speeds up and slows down

An integral over `d=clock` accumulates `power × d(clock)`; an eased clock makes the
integral run fast in the middle and stall at the ends. Fix: animate the clock with
`ease=k.ease.linear` (or integrate over `k.time` / `k.time.map(...)`).

Best effort: every `NAME.to(...)` call in the function, where `NAME` is passed as `d=`
to some `*.integrate(...)` call, must carry `ease=<...>.ease.linear` (or `"linear"`).
"""

from __future__ import annotations

import ast

from ..._runtime.spans import Span
from ...diagnostics import Fix
from ..source_edits import char_column, line_fix, with_keyword_in_call
from .scope import CodeFinding
from .source import FunctionSource

CODE = "W0312"


def _is_integrate(call: ast.Call) -> bool:
    f = call.func
    return (isinstance(f, ast.Attribute) and f.attr == "integrate") or (isinstance(f, ast.Name) and f.id == "integrate")


def _clock_names(fn: ast.AST) -> set[str]:
    out: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and _is_integrate(node):
            for kw in node.keywords:
                if kw.arg == "d" and isinstance(kw.value, ast.Name):
                    out.add(kw.value.id)
    return out


def _is_linear(value: ast.AST) -> bool:
    if isinstance(value, ast.Attribute):
        return value.attr == "linear"
    if isinstance(value, ast.Name):
        return value.id == "linear"
    return isinstance(value, ast.Constant) and value.value == "linear"


def find(source: FunctionSource) -> list[CodeFinding]:
    fn = source.node
    module = source.module
    clocks = _clock_names(fn)
    out: list[CodeFinding] = []
    if not clocks:
        return out
    linear = f"{module.kinemo_alias}.ease.linear"
    for node in ast.walk(fn):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "to"):
            continue
        owner = node.func.value
        if not (isinstance(owner, ast.Name) and owner.id in clocks):
            continue
        ease = next((kw.value for kw in node.keywords if kw.arg == "ease"), None)
        if ease is not None and _is_linear(ease):
            continue
        name = owner.id
        message = (
            f"'{name}' is used as a clock (d= of integrate) and is animated with non-linear easing: "
            "the integral speeds up and slows down along with it"
        )
        line = module.line(node.lineno)
        span = Span(module.file, node.lineno, char_column(line, node.col_offset))
        description = f"animate the clock linearly (or use {module.kinemo_alias}.time.map(...))"
        new_line = with_keyword_in_call(line, "to", "ease", linear) if node.lineno == node.end_lineno else None
        fix = line_fix(description, module.file, node.lineno, new_line) if new_line else Fix(description, f"{name}.to(..., ease={linear})")
        out.append(CodeFinding(CODE, message, [span], [fix]))
    return out
