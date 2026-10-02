"""The symbolic point `p` of per-point functions, and the tracing of those functions."""

from __future__ import annotations

import inspect
from typing import Any, Callable

from ...reactive.expr import Expr, Op, Time
from ...values.vec import Vec


def point_attr(attr: str, kind: str = "float") -> Op:
    """IR read of one attribute of the point being evaluated."""
    return Op("point", {"attr": attr}, kind=kind)


class SymbolicPoint:
    """`p` in `lambda p: ...` / `lambda t, p: ...`: the point a per-point function runs on.

    `p.x`, `p.y` — coordinates; `p.index` — position in the set; `p.count` — number of
    points; `p.t` — `index / (count - 1)` in [0, 1]; `p.xy` — the point as a vector.
    """

    __slots__ = ()

    @property
    def x(self) -> Expr[float]:
        return point_attr("x")

    @property
    def y(self) -> Expr[float]:
        return point_attr("y")

    @property
    def index(self) -> Expr[float]:
        return point_attr("index")

    @property
    def count(self) -> Expr[float]:
        return point_attr("count")

    @property
    def t(self) -> Expr[float]:
        return point_attr("t")

    @property
    def xy(self) -> Expr[Vec]:
        return point_attr("xy", "vec2")

    def __repr__(self) -> str:
        return "p"


def required_arity(fn: Callable[..., Any]) -> int:
    """Positional parameters without defaults (`lambda p, i=i:` has arity 1)."""
    try:
        params = inspect.signature(fn).parameters.values()
    except (TypeError, ValueError):
        return 1
    kinds = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    return sum(1 for p in params if p.kind in kinds and p.default is inspect.Parameter.empty)


def trace_per_point(fn: Callable[..., Any]) -> Expr[Any]:
    """`lambda p:` or `lambda t, p:` (t is `k.time`) → a per-point expression."""
    from ...reactive.tracer import _run

    p = SymbolicPoint()
    if required_arity(fn) >= 2:
        return _run(fn, Time(), p)
    return _run(fn, p)


def trace_field(fn: Callable[..., Any]) -> Expr[Vec]:
    """A field `lambda x, y: (vx, vy)`, `lambda p: ...` or `lambda t, x, y: ...` → vec2 expression."""
    from ...reactive.tracer import _run

    p = SymbolicPoint()
    arity = required_arity(fn)
    if arity >= 3:
        out = _run(fn, Time(), p.x, p.y)
    elif arity == 2:
        out = _run(fn, p.x, p.y)
    else:
        out = _run(fn, p)
    if out.kind != "vec2":
        out = Op("vec2", {"x": out.x, "y": out.y}, kind="vec2")
    return out
