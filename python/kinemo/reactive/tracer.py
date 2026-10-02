"""Tracing: run a Python function once on symbolic values to compile it to the IR.

Traceable: arithmetic, comparisons, `& | ~`, `abs`, `round`, `k.*` math functions and
f-strings with format specs. `if`/`while`/`and`/`or` on symbolic values, `math.*` and
external libraries are not; tracing then fails with K0310 (never a silent fallback).
"""

from __future__ import annotations

import os
import re
import traceback
from contextvars import ContextVar
from typing import Any, Callable

from .._runtime.context import trace_mode
from .._runtime.spans import Span
from ..diagnostics import KinemoError
from .expr import Const, Expr, Op

_placeholders: ContextVar[list[Expr] | None] = ContextVar("kinemo_placeholders", default=None)
_TOKEN = re.compile("\x00K(\\d+)\x00")


def format_placeholder(e: Expr, spec: str) -> str:
    slots = _placeholders.get()
    if slots is None:
        slots = []
        _placeholders.set(slots)
    slots.append(Op("format", {"spec": spec, "a": e}, kind="str"))
    return f"\x00K{len(slots) - 1}\x00"


def _to_expr(result: Any, slots: list[Expr]) -> Expr:
    if isinstance(result, Expr):
        return result
    if isinstance(result, str):
        parts: list[Expr] = []
        pos = 0
        for m in _TOKEN.finditer(result):
            if m.start() > pos:
                parts.append(Const(result[pos : m.start()], "str"))
            parts.append(slots[int(m.group(1))])
            pos = m.end()
        if pos < len(result):
            parts.append(Const(result[pos:], "str"))
        if len(parts) == 1:
            return parts[0]
        return Op("concat", {"parts": parts or [Const("", "str")]}, kind="str")
    if isinstance(result, tuple) and len(result) == 2:
        return Op("vec2", {"x": _to_expr(result[0], slots), "y": _to_expr(result[1], slots)}, kind="vec2")
    if isinstance(result, bool):
        return Const(result, "bool")
    if isinstance(result, int | float):
        return Const(float(result), "float")
    return Const(result)


def _run(fn: Callable[..., Any], *args: Any) -> Expr:
    token = _placeholders.set([])
    try:
        with trace_mode():
            try:
                result = fn(*args)
            except KinemoError as e:
                if e.diagnostic.code in _HINTS:
                    raise _not_traceable(fn, e) from None
                raise
            except TypeError as e:
                raise _not_traceable(fn, e) from None
        return _to_expr(result, _placeholders.get() or [])
    finally:
        _placeholders.reset(token)


def trace(fn: Callable[[], Any]) -> Expr:
    """Compile a zero-argument function (a lambda in a prop) to an expression."""
    return _run(fn)


def trace_call(fn: Callable[[Any], Any], arg: Expr) -> Expr:
    """Compile `fn(arg)` (used by `.map`)."""
    from .native import PythonFn

    if isinstance(fn, PythonFn):
        return fn.apply(arg)
    return _run(fn, arg)


_HINTS = {
    "K0304": ("uses if/and/or or built-in min()/max() on a symbolic value", "k.where(cond, a, b), &, |, ~, k.min, k.max"),
    "K0305": ("uses math.* or int()/float() on a symbolic value", "k.sin, k.floor, k.min, k.max, ..."),
}


def _not_traceable(fn: Callable[..., Any], cause: Exception) -> KinemoError:
    name = getattr(fn, "__name__", "function")
    span = _span_in(fn, cause)
    why, native = ("it cannot be represented in the IR", "native k building blocks")
    if isinstance(cause, KinemoError) and cause.diagnostic.code in _HINTS:
        why, native = _HINTS[cause.diagnostic.code]
    elif isinstance(cause, TypeError):
        why = f"it failed with symbolic values ({cause})"
    return KinemoError.make(
        "K0310",
        f"'{name}' is not traceable: {why}",
        spans=[span] if span else (),
        fixes=[
            (f"replace it with {native} to run natively", None),
            ("accept the cost explicitly", f"x.map(k.python({name}))" if name != "<lambda>" else "move the lambda into a named function fn and use x.map(k.python(fn))"),
        ],
    )


def _span_in(fn: Callable[..., Any], cause: Exception) -> Span | None:
    code = getattr(fn, "__code__", None)
    if code is None:
        return None
    frames = traceback.extract_tb(cause.__traceback__)
    for fr in reversed(frames):
        if os.path.abspath(fr.filename) == os.path.abspath(code.co_filename):
            return Span(fr.filename, fr.lineno or 0)
    return Span(code.co_filename, code.co_firstlineno)
