"""Adaptive sampling of functions for plots, with discontinuity detection."""

from __future__ import annotations

import math
from typing import Any, Callable

Segment = list[tuple[float, float]]


def _value(fn: Callable[[float], Any], x: float) -> float | None:
    try:
        y = float(fn(x))
    except (ZeroDivisionError, ValueError, OverflowError, TypeError):
        return None
    return y if math.isfinite(y) else None


def sample(
    fn: Callable[[float], Any],
    x0: float,
    x1: float,
    y_span: float,
    samples: int = 160,
    max_depth: int = 6,
) -> list[Segment]:
    """Points of `fn` on [x0, x1], denser where it bends, split at discontinuities.

    A jump larger than the visible y span between neighbours (e.g. the asymptote of 1/x)
    starts a new segment instead of drawing a vertical line."""
    if x1 <= x0:
        return []
    jump = max(y_span, 1e-9)
    xs = [x0 + (x1 - x0) * i / samples for i in range(samples + 1)]
    pts: list[tuple[float, float | None]] = [(x, _value(fn, x)) for x in xs]

    def refine(a: tuple[float, float | None], b: tuple[float, float | None], depth: int) -> list[tuple[float, float | None]]:
        if depth >= max_depth or a[1] is None or b[1] is None:
            return []
        xm = (a[0] + b[0]) / 2
        m = (xm, _value(fn, xm))
        if m[1] is None:
            return [m]
        linear = (a[1] + b[1]) / 2
        if abs(m[1] - linear) < 1e-3 * jump:
            return []
        return refine(a, m, depth + 1) + [m] + refine(m, b, depth + 1)

    dense: list[tuple[float, float | None]] = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        dense += refine(a, b, 0)
        dense.append(b)

    segments: list[Segment] = []
    current: Segment = []
    prev: float | None = None
    for x, y in dense:
        if y is None or (prev is not None and abs(y - prev) > jump):
            if len(current) > 1:
                segments.append(current)
            current = []
        if y is not None:
            current.append((x, y))
        prev = y
    if len(current) > 1:
        segments.append(current)
    return segments


def ticks(lo: float, hi: float, step: float | None) -> list[float]:
    """Tick positions; without a step, a 'nice' one giving about 5 ticks."""
    if hi <= lo:
        return []
    spacing = step if step is not None and step > 0 else _nice_step(lo, hi)
    first = math.ceil(lo / spacing - 1e-9) * spacing
    out: list[float] = []
    v = first
    while v <= hi + 1e-9:
        out.append(round(v, 10))
        v += spacing
    return out


def _nice_step(lo: float, hi: float) -> float:
    """A 1-2-2.5-5 step giving about 5 ticks on [lo, hi]."""
    raw = (hi - lo) / 5
    mag: float = 10 ** math.floor(math.log10(raw))
    return min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=raw)
