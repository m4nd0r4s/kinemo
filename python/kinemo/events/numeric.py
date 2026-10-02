"""Sampling-based numerics of the resolve phase: integrals and condition edges.

Conditions are sampled once per frame and each false → true edge is refined by bisection
to 1 ms, as the spec requires. Evaluation runs natively; only the loops live here."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .._core import Builder

EDGE_TOLERANCE = 1e-3


def grid(b: "Builder", expr_ir: dict[str, Any], t0: float, dt: float, n: int) -> list[float]:
    return b.eval_expr_grid(json.dumps(expr_ir), t0, dt, n)


def value_at(b: "Builder", expr_ir: dict[str, Any], t: float) -> float:
    return b.eval_expr_grid(json.dumps(expr_ir), t, 0.0, 1)[0]


def integrate(
    b: "Builder",
    rate_ir: dict[str, Any],
    by_ir: dict[str, Any],
    initial: float,
    clamp: tuple[float, float] | None,
    t0: float,
    dt: float,
    n: int,
) -> list[float]:
    """Trapezoidal integral of `rate` with respect to the variation of `by`, from `t0`."""
    rates = grid(b, rate_ir, t0, dt, n)
    bys = grid(b, by_ir, t0, dt, n)
    out = [initial]
    acc = initial
    for i in range(1, n):
        acc += 0.5 * (rates[i] + rates[i - 1]) * (bys[i] - bys[i - 1])
        if clamp is not None:
            acc = min(max(acc, clamp[0]), clamp[1])
        out.append(acc)
    return out


def edges(
    b: "Builder",
    cond_ir: dict[str, Any],
    t0: float,
    t1: float,
    dt: float,
    rearm_ir: dict[str, Any] | None = None,
    once: bool = False,
) -> list[float]:
    """Instants in [t0, t1] where `cond` goes from false to true.

    Without `rearm`, the condition must become false again before firing again; with it,
    `rearm` must become true (hysteresis)."""
    n = max(2, int((t1 - t0) / dt) + 2)
    values = grid(b, cond_ir, t0, dt, n)
    rearm = grid(b, rearm_ir, t0, dt, n) if rearm_ir is not None else None
    out: list[float] = []
    armed = values[0] < 0.5
    for i in range(1, n):
        if not armed:
            if rearm is not None:
                armed = rearm[i] >= 0.5 and values[i] < 0.5
            else:
                armed = values[i] < 0.5
            continue
        if values[i] >= 0.5 and values[i - 1] < 0.5:
            out.append(_bisect(b, cond_ir, t0 + (i - 1) * dt, t0 + i * dt))
            armed = False
            if once:
                break
    return [t for t in out if t <= t1 + 1e-12]


def _bisect(b: "Builder", cond_ir: dict[str, Any], lo: float, hi: float) -> float:
    while hi - lo > EDGE_TOLERANCE:
        mid = (lo + hi) / 2
        if value_at(b, cond_ir, mid) >= 0.5:
            hi = mid
        else:
            lo = mid
    return hi


def extreme(b: "Builder", expr_ir: dict[str, Any], t0: float, t1: float, dt: float) -> tuple[float, float]:
    """(max value, time) of an expression over [t0, t1] (for K0702 messages)."""
    n = max(2, int((t1 - t0) / dt) + 1)
    values = grid(b, expr_ir, t0, dt, n)
    i = max(range(n), key=lambda j: values[j])
    return values[i], t0 + i * dt
