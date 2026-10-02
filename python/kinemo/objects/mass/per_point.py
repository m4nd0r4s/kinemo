"""Per-point prop values and the base class of mass objects.

A per-point prop accepts:

- a plain value or a signal — the same for every point;
- a function of the symbolic point (`lambda p:` / `lambda t, p:`) — traced to a
  per-point expression, evaluated natively for every point at every frame;
- a sequence or numpy array with one value per point — stored as a list;
- `k.python(fn, vectorized=True)` — `fn` is called once at build time with a point
  whose attributes are numpy arrays, and must return one value per point.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Sequence, Union

from ...diagnostics import KinemoError
from ...reactive.expr import Expr
from ...reactive.native import PythonFn
from ...theme.tokens import ThemeToken
from ...values.color import Color
from ...values.encode import encode
from ..node import Node
from ..props import PropSignal, PropSpec
from .symbolic_point import SymbolicPoint, trace_per_point

if TYPE_CHECKING:
    from ...data.arrow import ArrowArrayExportable, ArrowStreamExportable, FloatColumn, SupportsArray, SupportsBuffer
    from ...reactive.native import ColorExpr, FloatExpr
    from ...values.aliases import ColorLike, ColorVal, FloatVal, VecLike

#: A per-point number: a value or signal for every point, one value per point, a
#: function of the symbolic point (`lambda p:` / `lambda t, p:`) or
#: `k.python(fn, vectorized=True)`.
PerPointFloat = Union[
    "FloatVal",
    "FloatColumn",
    Callable[[SymbolicPoint], "FloatExpr"],
    Callable[["Expr[float]", SymbolicPoint], "FloatExpr"],
    "PythonFn[Any, Any]",
]
#: A per-point color, with the same forms as `PerPointFloat`.
PerPointColor = Union[
    "ColorVal",
    "Sequence[ColorLike]",
    Callable[[SymbolicPoint], "ColorExpr"],
    Callable[["Expr[float]", SymbolicPoint], "ColorExpr"],
    "PythonFn[Any, Any]",
]
#: Point coordinates: an `(n, 2)` array, a list of points, or a pair of columns.
PointsInput = Union[
    "Sequence[VecLike]",
    "tuple[FloatColumn, FloatColumn]",
    "SupportsBuffer",
    "SupportsArray",
    "ArrowArrayExportable",
    "ArrowStreamExportable",
]


class PerPointValues:
    """One value per point, already encoded as an IR list."""

    __slots__ = ("ir",)

    def __init__(self, values: list[Any], kind: str) -> None:
        self.ir = {"List": [encode(v, kind) for v in values]}


class NumpyPoint:
    """The point given to `k.python(fn, vectorized=True)`: attributes are numpy arrays."""

    def __init__(self, xs: list[float], ys: list[float]) -> None:
        import numpy as np

        n = len(xs)
        self.x = np.asarray(xs, dtype=float)
        self.y = np.asarray(ys, dtype=float)
        self.index = np.arange(n, dtype=float)
        self.count = n
        self.t = self.index / (n - 1) if n > 1 else np.zeros(n)


def _is_function(value: Any) -> bool:
    return callable(value) and not isinstance(value, Expr | Color | ThemeToken | type | PythonFn)


def _is_sequence(value: Any) -> bool:
    return hasattr(value, "__array__") or isinstance(value, list | tuple)


def _vectorized(fn: PythonFn[Any, Any], xs: list[float], ys: list[float], kind: str) -> PerPointValues:
    out = fn.fn(NumpyPoint(xs, ys))
    values = out.tolist() if hasattr(out, "tolist") else list(out)
    if len(values) != len(xs):
        raise KinemoError.make(
            "K0310",
            f"'{fn.__name__}' returned {len(values)} values for {len(xs)} points",
            fixes=[("return an array with one value per point", None)],
        )
    if kind == "color":
        values = [Color(*v) if isinstance(v, list | tuple) else v for v in values]
    return PerPointValues(values, kind)


def per_point_value(value: Any, kind: str, xs: list[float] | None = None, ys: list[float] | None = None) -> Any:
    """Normalizes a per-point prop value (see the module docs); `xs`/`ys` are the points
    for `k.python(..., vectorized=True)` (unknown for grids sampled by the core)."""
    if value is None or isinstance(value, Expr | ThemeToken | Color | str):
        return value
    if isinstance(value, PythonFn):
        if value.vectorized and xs is not None and ys is not None:
            return _vectorized(value, xs, ys, kind)
        raise KinemoError.make(
            "K0310",
            f"'{value.__name__}' cannot run per point: per-point functions are traced and vectorized in Rust",
            fixes=[
                ("use native k functions on the symbolic point", "lambda p: k.sin(p.x)"),
                ("or receive numpy arrays once, at build time", f"k.python({value.__name__}, vectorized=True)"),
            ],
        )
    if _is_function(value):
        return trace_per_point(value)
    if _is_sequence(value) and not (kind == "vec2" and len(value) == 2 and not _is_sequence(value[0])):
        items = value.tolist() if hasattr(value, "tolist") else list(value)
        if kind == "color":
            items = [Color(*v) if isinstance(v, list | tuple) else v for v in items]
        return PerPointValues(items, kind)
    return value


class MassNode(Node):
    """Base of mass objects: props may hold one value per point (`PerPointValues`)."""

    PROPS: ClassVar[dict[str, PropSpec]] = {}

    def _create_signal(self, name: str, value: Any, explicit: bool = False) -> PropSignal[Any]:
        if not isinstance(value, PerPointValues):
            return super()._create_signal(name, value, explicit)
        spec = self._spec(name)
        assert spec is not None
        s = self._scene
        sid = s._b.add_signal(json.dumps(value.ir), "step_end", (self._id, name), json.dumps(self._span.ir()))
        s._b.set_prop(self._id, name, sid)
        sig = PropSignal(s, sid, spec.kind, "step_end", self, name)
        self._sigs[name] = sig
        return sig

    def _color_props(self) -> tuple[str, ...]:
        return ("color",)
