"""Shared pieces of the data charts: the `chart.to(data=...)` animation and value scales."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Callable, Sequence

from ..._runtime.spans import Span
from ...anim.animation import Animation
from ...anim.ease import Ease
from ...anim.prop import PropTo, Target
from ...data.arrow import number_text

if TYPE_CHECKING:
    from ...scene.scene import Scene

#: `apply(scene, start, duration, ease, span)`: schedules the change of data.
__all__ = ["Apply", "DataTransition", "animate", "nice_scale", "number_text", "set_at", "tick_values"]

Apply = Callable[["Scene", float, float, Ease, Span], None]


class DataTransition(Animation):
    """`chart.to(data=...)`: the chart diffs the new data against its state when the
    animation is scheduled (so consecutive transitions chain), then animates the change."""

    def __init__(self, owner: Any, apply: Apply, span: Span) -> None:
        super().__init__(0.0, None, 0.0, span)
        self.owner = owner
        self.apply = apply

    def describe(self) -> str:
        return f"{self.owner._label()}.to(data)"

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        self.apply(s, start, duration, ease, self.span)


def animate(s: "Scene", targets: Sequence[Target], start: float, duration: float, ease: Ease, span: Span) -> None:
    """Schedule `targets` (signal, value) from `start` over `duration`."""
    if targets:
        PropTo(targets, span=span)._emit(s, start, duration, ease)


def set_at(s: "Scene", targets: Sequence[Target], t: float, span: Span) -> None:
    """Instant change of `targets` at `t`."""
    if targets:
        PropTo(targets, span=span)._emit(s, t, 0.0, _linear())


def _linear() -> Ease:
    from ...anim.ease import ease

    return ease.linear


def nice_scale(top: float, target_ticks: int = 5) -> tuple[float, float]:
    """(nice upper bound, tick step) for values in [0, top]: 1, 2, 2.5 or 5 × 10^k."""
    if not math.isfinite(top) or top <= 0:
        return 1.0, 0.2
    raw = top / target_ticks
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw - 1e-12), default=raw)
    return math.ceil(top / step - 1e-9) * step, step


def tick_values(top: float, step: float) -> list[float]:
    count = int(round(top / step))
    return [round(i * step, 10) for i in range(count + 1)]
