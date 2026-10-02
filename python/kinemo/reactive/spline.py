"""`k.spline`: natural cubic spline through a table, native on signals."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, overload

from .expr import Expr, Op

if TYPE_CHECKING:
    from ..data.arrow import FloatColumn
    from .native import ArrayT


def _second_derivatives(xs: list[float], ys: list[float]) -> list[float]:
    """Natural spline (zero curvature at the ends), by the tridiagonal algorithm."""
    n = len(xs)
    if n < 3:
        return [0.0] * n
    m = [0.0] * n
    u = [0.0] * n
    for i in range(1, n - 1):
        sig = (xs[i] - xs[i - 1]) / (xs[i + 1] - xs[i - 1])
        p = sig * m[i - 1] + 2.0
        m[i] = (sig - 1.0) / p
        slope = (ys[i + 1] - ys[i]) / (xs[i + 1] - xs[i]) - (ys[i] - ys[i - 1]) / (xs[i] - xs[i - 1])
        u[i] = (6.0 * slope / (xs[i + 1] - xs[i - 1]) - sig * u[i - 1]) / p
    for k in range(n - 2, -1, -1):
        m[k] = m[k] * m[k + 1] + u[k]
    m[-1] = 0.0
    return m


def _evaluate(x: float, xs: list[float], ys: list[float], m: list[float]) -> float:
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    i = next(j for j in range(1, len(xs)) if xs[j] >= x)
    h = xs[i] - xs[i - 1]
    a, b = (xs[i] - x) / h, (x - xs[i - 1]) / h
    return a * ys[i - 1] + b * ys[i] + ((a**3 - a) * m[i - 1] + (b**3 - b) * m[i]) * h * h / 6.0


@overload
def spline(x: float, xs: FloatColumn, ys: FloatColumn) -> float: ...
@overload
def spline(x: Expr[float], xs: FloatColumn, ys: FloatColumn) -> Expr[float]: ...
@overload
def spline(x: ArrayT, xs: FloatColumn, ys: FloatColumn) -> ArrayT: ...
def spline(x: Any, xs: FloatColumn, ys: FloatColumn) -> Any:
    """Smooth interpolation through `(xs, ys)` (Arrow columns, numpy, lists); clamped outside."""
    from ..data.arrow import to_float_list

    pairs = sorted(zip(to_float_list(xs), to_float_list(ys)))
    if not pairs:
        raise ValueError("spline: empty table")
    px, py = [p[0] for p in pairs], [p[1] for p in pairs]
    m = _second_derivatives(px, py)
    if isinstance(x, Expr):
        return Op("spline", {"x": x, "xs": px, "ys": py, "m": m})
    if hasattr(x, "__array_ufunc__"):
        import numpy as np

        return np.array([_evaluate(float(v), px, py, m) for v in np.ravel(x)]).reshape(np.shape(x))
    return _evaluate(float(x), px, py, m)
