"""Native building blocks (`k.sin`, `k.where`, `k.interp`, ...).

Every function is polymorphic: plain numbers give plain numbers (so the same function
can be used to plot with floats and traced as a signal), expressions give expressions,
and numpy arrays are handled elementwise. The overloads below spell that out for the
type checker: `float -> float`, `Expr[float] -> Expr[float]`, array -> array.
"""

from __future__ import annotations

import builtins
import math
from typing import TYPE_CHECKING, Any, Callable, Generic, Literal, Protocol, TypeVar, Union, cast, overload

from ..values.color import Color
from ..values.vec import Vec
from .expr import Const, Expr, Op, lift

if TYPE_CHECKING:
    from ..data.arrow import FloatColumn
    from ..theme.tokens import ThemeToken

pi = math.pi
tau = math.tau
e = math.e

T = TypeVar("T")
A = TypeVar("A")
R = TypeVar("R")


class SupportsArrayUfunc(Protocol):
    """A numpy-like array: native functions apply to it elementwise."""

    def __array_ufunc__(self, *args: Any, **kwargs: Any) -> Any: ...


ArrayT = TypeVar("ArrayT", bound=SupportsArrayUfunc)

#: A number or a numeric expression.
FloatExpr = Union[float, Expr[float]]
#: A color, a theme token, a hex string or a color expression (what `k.mix` blends).
ColorExpr = Union[Color, "ThemeToken", str, Expr[Color]]
#: A point or a vector expression.
VecExpr = Union[Vec, tuple[float, float], Expr[Vec]]


def _is_array(v: object) -> bool:
    return hasattr(v, "__array_ufunc__") and not isinstance(v, Expr)


class UnaryNative(Protocol):
    """`k.sin` & co.: `f(float) -> float`, `f(Expr) -> Expr`, `f(array) -> array`."""

    @overload
    def __call__(self, x: float, /) -> float: ...
    @overload
    def __call__(self, x: Expr[float], /) -> Expr[float]: ...
    @overload
    def __call__(self, x: ArrayT, /) -> ArrayT: ...


class BinaryNative(Protocol):
    """`k.atan2` & co.: two numbers, expressions or arrays."""

    @overload
    def __call__(self, a: float, b: float, /) -> float: ...  # pyright: ignore[reportOverlappingOverload] - floats stay floats
    @overload
    def __call__(self, a: FloatExpr, b: FloatExpr, /) -> Expr[float]: ...
    @overload
    def __call__(self, a: ArrayT, b: ArrayT | float, /) -> ArrayT: ...
    @overload
    def __call__(self, a: float, b: ArrayT, /) -> ArrayT: ...


def _unary(name: str, fn: Callable[[float], float], np_name: str | None = None) -> UnaryNative:
    def f(x: Any) -> Any:
        if isinstance(x, Expr):
            return Op("un", {"f": name, "a": x})
        if _is_array(x):
            import numpy as np

            return getattr(np, np_name or name)(x)
        return fn(x)

    f.__name__ = name
    f.__doc__ = f"{name}(x), native on signals."
    return cast(UnaryNative, f)


sin = _unary("sin", math.sin)
cos = _unary("cos", math.cos)
tan = _unary("tan", math.tan)
exp = _unary("exp", math.exp)
log = _unary("ln", math.log, "log")
sqrt = _unary("sqrt", math.sqrt)
floor = _unary("floor", math.floor)
ceil = _unary("ceil", math.ceil)


def _binary(name: str, fn: Callable[[float, float], float], np_name: str) -> BinaryNative:
    def f(a: Any, b: Any) -> Any:
        if isinstance(a, Expr) or isinstance(b, Expr):
            return Op("bin", {"f": name, "a": lift(a), "b": lift(b)})
        if _is_array(a) or _is_array(b):
            import numpy as np

            return getattr(np, np_name)(a, b)
        return fn(a, b)

    f.__name__ = name
    return cast(BinaryNative, f)


_min2 = _binary("min", builtins.min, "minimum")
_max2 = _binary("max", builtins.max, "maximum")
atan2 = _binary("atan2", math.atan2, "arctan2")


@overload
def min(*args: float) -> float: ...  # noqa: A001  # pyright: ignore[reportOverlappingOverload] - floats stay floats
@overload
def min(*args: FloatExpr) -> Expr[float]: ...
@overload
def min(*args: ArrayT | float) -> ArrayT: ...
def min(*args: Any) -> Any:  # noqa: A001
    out = args[0]
    for a in args[1:]:
        out = _min2(out, a)
    return out


@overload
def max(*args: float) -> float: ...  # noqa: A001  # pyright: ignore[reportOverlappingOverload] - floats stay floats
@overload
def max(*args: FloatExpr) -> Expr[float]: ...
@overload
def max(*args: ArrayT | float) -> ArrayT: ...
def max(*args: Any) -> Any:  # noqa: A001
    out = args[0]
    for a in args[1:]:
        out = _max2(out, a)
    return out


@overload
def clamp(x: float, lo: float, hi: float) -> float: ...  # pyright: ignore[reportOverlappingOverload] - floats stay floats
@overload
def clamp(x: FloatExpr, lo: FloatExpr, hi: FloatExpr) -> Expr[float]: ...
@overload
def clamp(x: ArrayT, lo: float, hi: float) -> ArrayT: ...
def clamp(x: Any, lo: Any, hi: Any) -> Any:
    if any(isinstance(v, Expr) for v in (x, lo, hi)):
        return Op("clamp", {"a": lift(x), "lo": lift(lo), "hi": lift(hi)})
    if _is_array(x):
        import numpy as np

        return np.clip(x, lo, hi)
    return lo if x < lo else hi if x > hi else x


@overload
def where(cond: bool, a: T, b: T) -> T: ...  # pyright: ignore[reportOverlappingOverload] - plain values stay plain
@overload
def where(cond: bool | Expr[bool], a: T | Expr[T], b: T | Expr[T]) -> Expr[T]: ...
@overload
def where(cond: ArrayT, a: ArrayT | float, b: ArrayT | float) -> ArrayT: ...
def where(cond: Any, a: Any, b: Any) -> Any:
    """`a` where `cond` holds, else `b` (the traceable `if`)."""
    if any(isinstance(v, Expr) for v in (cond, a, b)):
        kind = lift(a).kind
        return Op("where", {"c": lift(cond), "a": lift(a), "b": lift(b)}, kind=kind)
    if _is_array(cond):
        import numpy as np

        return np.where(cond, a, b)
    return a if cond else b


@overload
def piecewise(*cases: tuple[bool, T], default: T) -> T: ...  # pyright: ignore[reportOverlappingOverload] - plain values stay plain
@overload
def piecewise(*cases: tuple[bool | Expr[bool], T | Expr[T]], default: T | Expr[T]) -> Expr[T]: ...
@overload
def piecewise(*cases: tuple[bool | Expr[bool], float | Expr[float]]) -> Expr[float]: ...
def piecewise(*cases: tuple[Any, Any], default: Any = 0.0) -> Any:
    """`piecewise((cond1, v1), (cond2, v2), default=v)`: first matching condition wins."""
    out = default
    for cond, value in reversed(cases):
        out = where(cond, value, out)
    return out


@overload
def mix(a: float, b: float, t: float) -> float: ...  # pyright: ignore[reportOverlappingOverload] - floats stay floats
@overload
def mix(a: FloatExpr, b: FloatExpr, t: FloatExpr) -> Expr[float]: ...
@overload
def mix(a: ColorExpr, b: ColorExpr, t: FloatExpr) -> Expr[Color]: ...
@overload
def mix(a: VecExpr, b: VecExpr, t: FloatExpr) -> Expr[Vec]: ...
def mix(a: Any, b: Any, t: Any) -> Any:
    """Linear mix of numbers, vectors or colors (colors in OKLab)."""
    if any(isinstance(v, Expr) for v in (a, b, t)) or not isinstance(a, int | float):
        la = lift(a)
        return Op("mix", {"a": la, "b": lift(b), "t": lift(t)}, kind=la.kind)
    return a + (b - a) * t


@overload
def smoothstep(e0: float, e1: float, x: float) -> float: ...  # pyright: ignore[reportOverlappingOverload] - floats stay floats
@overload
def smoothstep(e0: FloatExpr, e1: FloatExpr, x: FloatExpr) -> Expr[float]: ...
def smoothstep(e0: Any, e1: Any, x: Any) -> Any:
    t = clamp((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


@overload
def interp(x: float, xs: FloatColumn, ys: FloatColumn) -> float: ...
@overload
def interp(x: Expr[float], xs: FloatColumn, ys: FloatColumn) -> Expr[float]: ...
@overload
def interp(x: ArrayT, xs: FloatColumn, ys: FloatColumn) -> ArrayT: ...
def interp(x: Any, xs: FloatColumn, ys: FloatColumn) -> Any:
    """Piecewise-linear interpolation over a table (Arrow columns, numpy, lists)."""
    xs_l, ys_l = _floats(xs), _floats(ys)
    if len(xs_l) != len(ys_l) or not xs_l:
        raise ValueError("interp: xs and ys must have the same non-zero length")
    pairs = sorted(zip(xs_l, ys_l))
    xs_l, ys_l = [p[0] for p in pairs], [p[1] for p in pairs]
    if isinstance(x, Expr):
        return Op("interp", {"x": x, "xs": xs_l, "ys": ys_l})
    if _is_array(x):
        import numpy as np

        return np.interp(x, xs_l, ys_l)
    if x <= xs_l[0]:
        return ys_l[0]
    if x >= xs_l[-1]:
        return ys_l[-1]
    for i in range(1, len(xs_l)):
        if x <= xs_l[i]:
            t = (x - xs_l[i - 1]) / (xs_l[i] - xs_l[i - 1])
            return ys_l[i - 1] + (ys_l[i] - ys_l[i - 1]) * t
    return ys_l[-1]


def _floats(col: FloatColumn) -> list[float]:
    from ..data.arrow import to_float_list

    return to_float_list(col)


def noise(x: FloatExpr, seed: int = 0) -> Expr[float]:
    """Smooth deterministic value noise in [-1, 1]."""
    return Op("noise", {"a": lift(x), "seed": int(seed)})


@overload
def vec(x: float, y: float) -> Vec: ...  # pyright: ignore[reportOverlappingOverload] - floats give a plain Vec
@overload
def vec(x: FloatExpr, y: FloatExpr) -> Expr[Vec]: ...
def vec(x: Any, y: Any) -> Any:
    if isinstance(x, Expr) or isinstance(y, Expr):
        return Op("vec2", {"x": lift(x), "y": lift(y)}, kind="vec2")
    return Vec(float(x), float(y))


class PythonFn(Generic[A, R]):
    """`k.python(fn)`: an opaque Python function, precomputed per frame in the resolve phase."""

    def __init__(self, fn: Callable[[A], R], vectorized: bool = False) -> None:
        from .._runtime.spans import user_span

        self.fn = fn
        self.vectorized = vectorized
        self.__name__ = getattr(fn, "__name__", "python")
        self.span = user_span()

    def apply(self, arg: Expr[A]) -> Expr[R]:
        from .._runtime.context import current_scene

        return current_scene()._precompute(self, arg)

    @overload
    def __call__(self, arg: Expr[A]) -> Expr[R]: ...
    @overload
    def __call__(self, arg: A) -> R: ...
    def __call__(self, arg: Any) -> Any:
        if isinstance(arg, Expr):
            return self.apply(arg)
        return self.fn(arg)


@overload
def python(fn: Callable[[A], R], vectorized: Literal[False] = False) -> PythonFn[A, R]: ...
@overload
def python(fn: Callable[..., object], vectorized: Literal[True]) -> PythonFn[float, float]: ...
def python(fn: Callable[[Any], Any], vectorized: bool = False) -> PythonFn[Any, Any]:
    """Mark `fn` as opaque Python: it is called once per frame during resolve, never at render."""
    return PythonFn(fn, vectorized)


__all__ = [
    "Const",
    "atan2",
    "ceil",
    "clamp",
    "cos",
    "e",
    "exp",
    "floor",
    "interp",
    "log",
    "max",
    "min",
    "mix",
    "noise",
    "pi",
    "piecewise",
    "python",
    "sin",
    "smoothstep",
    "sqrt",
    "tan",
    "tau",
    "vec",
    "where",
]
