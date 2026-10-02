"""Function plots drawn natively inside an axes (`ax.plot`, `ax.area`)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Unpack, overload

from ...reactive.expr import Expr, lift
from ...reactive.native import sqrt, vec
from ...reactive.tracer import trace_call
from ..props import STYLE, PropSpec
from ..shapes import Line, Shape

if TYPE_CHECKING:
    from ...reactive.native import FloatExpr
    from ...values.aliases import FloatVal
    from ...values.vec import Vec
    from ..keywords import StyleKeywords, UnplacedStyleKeywords
    from ..props import PropAccessor
    from ..text import Text
    from .axes import Axes, PlotFunction

FAR = 1e300

PLOT_PROPS = {
    "points": PropSpec("segments", [], "step_end"),
    "x_range": PropSpec("vec2", (0.0, 1.0)),
    "y_range": PropSpec("vec2", (0.0, 1.0)),
    "size": PropSpec("vec2", (1.0, 1.0)),
    "clip": PropSpec("vec2", (-FAR, FAR)),
}


@overload
def _apply(fn: PlotFunction, x: float) -> float: ...
@overload
def _apply(fn: PlotFunction, x: Expr[float]) -> Expr[float]: ...
def _apply(fn: PlotFunction, x: FloatExpr) -> FloatExpr:
    return trace_call(fn, x) if isinstance(x, Expr) else fn(x)


class Plot(Shape):
    """A curve `y = fn(x)` of an axes. Grows with `until=`; follows the axes when it zooms."""

    kind = "plot"
    PROPS = dict(PLOT_PROPS)

    if TYPE_CHECKING:
        points: PropAccessor[list[list[Vec]]]
        x_range: PropAccessor[Vec]
        y_range: PropAccessor[Vec]
        size: PropAccessor[Vec]
        clip: PropAccessor[Vec]
        axes: Axes
        fn: PlotFunction
        _step: float
        #: The curve's label (only with `ax.plot(..., label=...)`).
        label: Text

    def __init__(self, axes: "Axes", fn: PlotFunction, segments: list[list[tuple[float, float]]], clip: Vec | Expr[Vec], **props: Unpack[StyleKeywords]) -> None:
        object.__setattr__(self, "axes", axes)
        object.__setattr__(self, "fn", fn)
        xs = [x for seg in segments for x, _ in seg]
        object.__setattr__(self, "_step", (max(xs) - min(xs)) * 1e-4 if xs else 1e-4)
        super().__init__(points=segments, x_range=axes.x_range, y_range=axes.y_range, size=axes.size, clip=clip, **props)

    def point_at(self, x: FloatExpr) -> Expr[Vec]:
        """World position of the curve at `x` (reactive when `x` is a signal)."""
        return self.axes.point(x, _apply(self.fn, x))

    @overload
    def value_at(self, x: float) -> float: ...
    @overload
    def value_at(self, x: Expr[float]) -> Expr[float]: ...
    def value_at(self, x: FloatExpr) -> FloatExpr:
        """Function value at `x` (an expression when `x` is a signal)."""
        return _apply(self.fn, x)

    def slope_at(self, x: FloatExpr) -> Expr[float]:
        h = self._step
        at: Expr[float] = lift(x)
        return (_apply(self.fn, at + h) - _apply(self.fn, at - h)) / (2 * h)

    def tangent_at(self, x: FloatExpr, length: float = 2.0, *, enter_with_axes: bool = True, **style: Unpack[UnplacedStyleKeywords]) -> Line:
        """Tangent segment of `length` units centered on the curve at `x`. It belongs to the
        axes and enters with it; `enter_with_axes=False` keeps it hidden until you bring it in
        with a verb (`k.fade_in(tan)`, `k.draw(tan)`) or `s.add(tan)`."""
        ax = self.axes
        p = ax.local_point(x, _apply(self.fn, x))
        sx = ax.size.x / (ax.x_range.y - ax.x_range.x)
        sy = ax.size.y / (ax.y_range.y - ax.y_range.x)
        dx, dy = sx * 1.0, sy * self.slope_at(x)
        norm = sqrt(dx * dx + dy * dy)
        ux, uy = dx / norm * (length / 2), dy / norm * (length / 2)
        style.setdefault("stroke", self._sig("stroke"))
        line = Line(start=vec(p.x - ux, p.y - uy), end=vec(p.x + ux, p.y + uy), **style)
        ax._append(line, enter_with_axes)
        from .axes import _name_from_call

        _name_from_call(line, "tangent_at")
        return line


class Area(Shape):
    """Region between a curve and another curve (or the x axis)."""

    kind = "plot_area"
    PROPS = {**PLOT_PROPS, "base": PropSpec("segments", [], "step_end"), "fill_opacity": PropSpec("float", 0.25), "stroke_width": PropSpec("float", 0.0)}

    if TYPE_CHECKING:
        points: PropAccessor[list[list[Vec]]]
        base: PropAccessor[list[list[Vec]]]
        x_range: PropAccessor[Vec]
        y_range: PropAccessor[Vec]
        size: PropAccessor[Vec]
        clip: PropAccessor[Vec]

    def __init__(self, axes: "Axes", top: list[tuple[float, float]], base: list[tuple[float, float]] | None, clip: Vec | Expr[Vec], **props: Unpack[StyleKeywords]) -> None:
        super().__init__(
            points=[top],
            base=[base] if base else [],
            x_range=axes.x_range,
            y_range=axes.y_range,
            size=axes.size,
            clip=clip,
            **props,
        )


__all__ = ["Area", "Plot", "STYLE"]


class ParametricPlot(Plot):
    """Curve `(fx(t), fy(t))` of an axes; `point_at(t)` follows the parameter."""

    if TYPE_CHECKING:
        fx: PlotFunction
        fy: PlotFunction

    def __init__(self, axes: "Axes", fx: PlotFunction, fy: PlotFunction, segments: list[list[tuple[float, float]]], **props: Unpack[StyleKeywords]) -> None:
        object.__setattr__(self, "fx", fx)
        object.__setattr__(self, "fy", fy)
        super().__init__(axes, fx, segments, vec(-FAR, FAR), **props)

    def point_at(self, t: FloatVal) -> Expr[Vec]:  # pyright: ignore[reportIncompatibleMethodOverride] - parameter is t, not x
        """World position of the curve at parameter `t` (reactive when `t` is a signal)."""
        param = lift(t)
        return self.axes.point(_apply(self.fx, param), _apply(self.fy, param))
