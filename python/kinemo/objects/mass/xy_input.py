"""Point coordinates from numpy arrays, Arrow-like columns or plain sequences."""

from __future__ import annotations

from typing import Any

from ...diagnostics import KinemoError


def _columns(xs: Any, ys: Any) -> tuple[list[float], list[float]]:
    from ...data.arrow import to_float_list

    x, y = to_float_list(xs), to_float_list(ys)
    if len(x) != len(y):
        raise KinemoError.make("K1201", f"x and y columns have different lengths ({len(x)} and {len(y)})")
    return x, y


def _is_column(v: Any) -> bool:
    """A 1-D column object (numpy vector, polars/pandas series, Arrow array). Plain
    Python sequences are never columns: `((1, 2), (3, 4))` is two points."""
    shape = getattr(v, "shape", None)
    if shape is not None:
        return len(shape) == 1
    return any(hasattr(v, a) for a in ("to_pylist", "to_list", "__arrow_c_array__"))


def to_xy(xy: Any = None, x: Any = None, y: Any = None) -> tuple[list[float], list[float]]:
    """`(n, 2)` numpy array, list of `(x, y)` / `k.Vec`, a pair of column objects
    `(xs, ys)`, or `x=` and `y=` columns → two lists of floats."""
    if x is not None or y is not None:
        if x is None or y is None or xy is not None:
            raise KinemoError.make("K1201", "pass xy=, or x= and y= together", fixes=[("columns", "k.Points(x=df['a'], y=df['b'])")])
        return _columns(x, y)
    if xy is None:
        return [], []
    shape = getattr(xy, "shape", None)
    if shape is not None and len(shape) == 2:
        if shape[1] != 2:
            raise KinemoError.make("K1201", f"xy must have shape (n, 2), not {tuple(shape)}", fixes=[("stack the columns", "np.column_stack([xs, ys])")])
        rows = xy.tolist()
        return [float(r[0]) for r in rows], [float(r[1]) for r in rows]
    if isinstance(xy, tuple) and len(xy) == 2 and all(_is_column(c) for c in xy):
        return _columns(xy[0], xy[1])
    xs: list[float] = []
    ys: list[float] = []
    to_list = getattr(xy, "tolist", None)
    rows: Any = to_list() if callable(to_list) else xy
    for p in rows:
        px, py = (p.x, p.y) if hasattr(p, "x") and hasattr(p, "y") else (p[0], p[1])
        xs.append(float(px))
        ys.append(float(py))
    return xs, ys
