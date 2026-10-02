"""`k.Axes`: coordinate axes with ticks, labels and plots, built with the public API."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Literal, Sequence, Unpack

from ...reactive.expr import Expr, Op, lift
from ...reactive.native import clamp, vec
from ...theme.tokens import ThemeToken
from ..groups import Group
from ..node import Node
from ..props import PropSpec
from ..shapes import Dot, Line
from ..text import Text
from .plot import FAR, Area, Plot
from .sampling import sample, ticks

if TYPE_CHECKING:
    from ...anim.animation import Animation, AnimationTiming
    from ...data.arrow import FloatColumn
    from ...values.aliases import ColorLike, FloatVal
    from ...values.color import Color
    from ...values.vec import Vec
    from ...reactive.native import FloatExpr
    from ..keywords import PlotStyleKeywords, StyleKeywords, UnplacedKeywords, UnplacedStyleKeywords
    from ..props import PropAccessor
    from .plot import ParametricPlot

#: A plotted function: called with floats to sample the curve and traced with a signal
#: for reactive reads (`curve.point_at(x)`), so it is written for plain numbers.
PlotFunction = Callable[[float], float]

TICK = 0.08
LABEL_SIZE = 0.24
PALETTE_CYCLE = ("BLUE", "YELLOW", "RED", "GREEN", "PURPLE", "ORANGE")

#: `ax.vline(..., style=)`.
LineStyle = Literal["solid", "dashed"]


def _name_from_call(node: Node, factory: Callable[..., Any]) -> None:
    """`curve = ax.plot(...)`: name the returned object after the variable, so labels and
    fixes say `curve` instead of an internal id. The method is kept as the object's factory:
    the preview binds that call's arguments to its parameters, not the constructor's."""
    import re

    object.__setattr__(node, "_factory", factory)
    if node._name is not None:
        return
    match = re.match(rf"^\s*([A-Za-z_]\w*)\s*=\s*[\w.\[\]]+\.{factory.__name__}\(", node._span.source_line())
    if match:
        object.__setattr__(node, "_name", match.group(1))


def _range(spec: Sequence[float]) -> tuple[float, float, float | None]:
    lo, hi = float(spec[0]), float(spec[1])
    step = float(spec[2]) if len(spec) > 2 else None
    return lo, hi, step


class Axes(Group):
    """`k.Axes(x=(0, 24, 6), y=(0, 7), labels=("h", "kW"), grid=True)`.

    `x_range`, `y_range` and `size` are signals: `ax.zoom_to(x=(4, 8))` animates them and
    every plot, tick and point follows."""

    #: Whether the y axis gets ticks and tick labels (`NumberLine` has none).
    _y_ticks = True

    PROPS = {
        "x_range": PropSpec("vec2", (0.0, 1.0)),
        "y_range": PropSpec("vec2", (0.0, 1.0)),
        "size": PropSpec("vec2", (8.0, 4.5)),
    }

    if TYPE_CHECKING:
        x_range: PropAccessor[Vec]
        y_range: PropAccessor[Vec]
        size: PropAccessor[Vec]
        _axes_opts: tuple[float, float, float | None, float, float, float | None, tuple[str, str] | None, bool, bool]
        _plot_count: int

    def __init__(
        self,
        x: Sequence[float] = (0, 10),
        y: Sequence[float] = (0, 5),
        *,
        labels: tuple[str, str] | None = None,
        grid: bool = False,
        width: float = 8.0,
        height: float = 4.5,
        tick_labels: bool = True,
        **props: Unpack[UnplacedKeywords],
    ) -> None:
        x0, x1, xs = _range(x)
        y0, y1, ys = _range(y)
        object.__setattr__(self, "_axes_opts", (x0, x1, xs, y0, y1, ys, labels, grid, tick_labels))
        object.__setattr__(self, "_plot_count", 0)
        super().__init__(x_range=(x0, x1), y_range=(y0, y1), size=(width, height), **props)

    # ---- coordinate mapping ------------------------------------------------------
    def map_x(self, x: FloatVal) -> Expr[float]:
        """Data x → x in the axes' own coordinates (reactive: follows zooms)."""
        xr, w = self.x_range, self.size
        data_x: Expr[float] = lift(x)
        return (data_x - xr.x) / (xr.y - xr.x) * w.x - w.x / 2

    def map_y(self, y: FloatVal) -> Expr[float]:
        """Data y → y in the axes' own coordinates (reactive: follows zooms)."""
        yr, h = self.y_range, self.size
        data_y: Expr[float] = lift(y)
        return (data_y - yr.x) / (yr.y - yr.x) * h.y - h.y / 2

    def local_point(self, x: FloatVal, y: FloatVal) -> Expr[Vec]:
        """Data point in the axes' own coordinates."""
        return vec(self.map_x(x), self.map_y(y))

    def point(self, x: FloatVal, y: FloatVal) -> Expr[Vec]:
        """Data point in world coordinates (`place(at=ax.point(3, 9))`)."""
        return Op("to_world", {"obj": self._id, "p": self.local_point(x, y)}, kind="vec2")

    def _axis_y(self) -> Expr[float]:
        yr = self.y_range
        return self.map_y(clamp(0.0, yr.x, yr.y))

    def _axis_x(self) -> Expr[float]:
        xr = self.x_range
        return self.map_x(clamp(0.0, xr.x, xr.y))

    def _visible_x(self, v: float) -> Expr[bool]:
        xr = self.x_range
        return (xr.x <= v + 1e-9) & (xr.y >= v - 1e-9)

    def _visible_y(self, v: float) -> Expr[bool]:
        yr = self.y_range
        return (yr.x <= v + 1e-9) & (yr.y >= v - 1e-9)

    # ---- construction ----------------------------------------------------------------
    def _parts(self) -> list[Node]:
        x0, x1, xs, y0, y1, ys, labels, grid, tick_labels = self._axes_opts
        w = self.size
        muted = self._scene.theme.muted
        parts: list[Node] = []
        ax_y, ax_x = self._axis_y(), self._axis_x()
        x_axis = Line(start=vec(-w.x / 2, ax_y), end=vec(w.x / 2, ax_y), stroke_width=3.0)
        y_axis = Line(start=vec(ax_x, -w.y / 2), end=vec(ax_x, w.y / 2), stroke_width=3.0)
        self._name_part(x_axis, "x_axis")
        self._name_part(y_axis, "y_axis")
        parts += [x_axis, y_axis]
        for v in ticks(x0, x1, xs):
            px = self.map_x(v)
            vis = self._visible_x(v)
            if grid:
                parts.append(Line(start=vec(px, -w.y / 2), end=vec(px, w.y / 2), stroke=muted, stroke_width=1.5, opacity=0.5, visible=vis))
            parts.append(Line(start=vec(px, ax_y - TICK), end=vec(px, ax_y + TICK), stroke_width=2.5, visible=vis))
            if tick_labels:
                parts.append(Text(f"{v:g}", size=LABEL_SIZE, x=px, y=ax_y - 0.28, visible=vis))
        for v in ticks(y0, y1, ys) if self._y_ticks else ():
            py = self.map_y(v)
            vis = self._visible_y(v)
            if grid:
                parts.append(Line(start=vec(-w.x / 2, py), end=vec(w.x / 2, py), stroke=muted, stroke_width=1.5, opacity=0.5, visible=vis))
            parts.append(Line(start=vec(ax_x - TICK, py), end=vec(ax_x + TICK, py), stroke_width=2.5, visible=vis))
            if tick_labels:
                parts.append(Text(f"{v:g}", size=LABEL_SIZE, x=ax_x - 0.3, y=py, visible=vis))
        if labels:
            xl = Text(labels[0], size=0.3, x=w.x / 2 + 0.5, y=ax_y - 0.28)
            yl = Text(labels[1], size=0.3, x=ax_x, y=w.y / 2 + 0.4)
            self._name_part(xl, "x_label")
            self._name_part(yl, "y_label")
            parts += [xl, yl]
        return parts

    @staticmethod
    def _name_part(node: Node, part: str) -> None:
        object.__setattr__(node, "_part", part)

    def _append(self, node: Node, enter_with_axes: bool = True) -> Node:
        """Add a child at the cursor (plots and markers created after the axes). With
        `enter_with_axes=False` it stays hidden until a verb or `s.add` brings it in."""
        self._adopt(node)
        if not enter_with_axes:
            object.__setattr__(node, "_enters_on_its_own", True)
        kids = self.children + [node]
        self._children_sig.set(kids)
        if enter_with_axes and self._scene._b.present(self._id, self._scene.cursor):
            self._scene._enter(node, self._scene.cursor)
        return node

    def _next_color(self) -> Color:
        from ...values import color as palette

        name = PALETTE_CYCLE[self._plot_count % len(PALETTE_CYCLE)]
        object.__setattr__(self, "_plot_count", self._plot_count + 1)
        return getattr(palette, name)

    # ---- plots -------------------------------------------------------------------
    def plot(
        self,
        fn: PlotFunction,
        *,
        until: FloatExpr | None = None,
        from_: FloatExpr | None = None,
        domain: tuple[float, float] | None = None,
        color: ColorLike | None = None,
        label: str | None = None,
        samples: int = 160,
        enter_with_axes: bool = True,
        **style: Unpack[PlotStyleKeywords],
    ) -> Plot:
        """Curve of `fn` (also usable with floats). `until=`/`from_=` accept signals: the
        curve grows while the signal moves. `enter_with_axes=False` keeps it (and its label)
        hidden until a verb brings it in."""
        x0, x1 = domain or tuple(self.x_range.now)
        y0, y1 = self.y_range.now
        segments = sample(fn, float(x0), float(x1), float(y1 - y0), samples)
        clip = vec(from_ if from_ is not None else -FAR, until if until is not None else FAR)
        stroke = color if color is not None else self._next_color()
        if isinstance(stroke, ThemeToken):
            stroke = stroke.resolve()
        plot_props: dict[str, Any] = {**style, "stroke": stroke, "stroke_width": style.get("stroke_width", 4.0)}
        curve = Plot(self, fn, segments, clip, **plot_props)
        self._append(curve, enter_with_axes)
        _name_from_call(curve, Axes.plot)
        if label:
            xe = float(x1)
            ye = float(fn(xe)) if segments else 0.0
            tag = Text(label, size=0.28, fill=stroke, x=self.map_x(xe) + 0.5, y=self.map_y(ye) + self._label_offset(ye))
            object.__setattr__(curve, "label", tag)
            object.__setattr__(tag, "_part", "label")
            object.__setattr__(tag, "_parent_label", curve)
            self._append(tag, enter_with_axes)
            if not enter_with_axes:
                object.__setattr__(curve, "_companions", [tag])
        return curve

    def _label_offset(self, y_data: float) -> float:
        """Vertical offset (units) for a curve label so labels of different curves never sit
        on top of each other at the end of a shared domain."""
        y0, y1 = self.y_range.now
        h = self.size.now[1]
        local = (y_data - y0) / (y1 - y0) * h - h / 2
        taken: list[float] = self.__dict__.setdefault("_label_slots", [])
        offset = 0.25
        while any(abs(local + offset - other) < 0.34 for other in taken):
            offset += 0.36
        taken.append(local + offset)
        return offset

    def area(self, f: Plot | PlotFunction, *, between: Plot | PlotFunction | None = None, domain: tuple[float, float] | None = None, until: FloatExpr | None = None, samples: int = 200, enter_with_axes: bool = True, **style: Unpack[StyleKeywords]) -> Area:
        """Filled region under `f` (to the x axis) or between `f` and `between`."""
        top_fn = f.fn if isinstance(f, Plot) else f
        base_fn = between.fn if isinstance(between, Plot) else between
        x0, x1 = domain or tuple(self.x_range.now)
        xs = [x0 + (x1 - x0) * i / samples for i in range(samples + 1)]
        top = [(x, float(top_fn(x))) for x in xs]
        base = [(x, float(base_fn(x))) for x in xs] if base_fn is not None else None
        style.setdefault("fill", f._sig("stroke") if isinstance(f, Plot) else self._scene.theme.accent)
        clip = vec(-FAR, until if until is not None else FAR)
        region = Area(self, top, base, clip, **style)
        self._append(region, enter_with_axes)
        _name_from_call(region, Axes.area)
        return region

    def vline(self, at: FloatVal, *, style: LineStyle = "solid", enter_with_axes: bool = True, **props: Unpack[StyleKeywords]) -> Line:
        h = self.size
        if style == "dashed":
            props.setdefault("dash", (12.0, 10.0))
        props.setdefault("stroke_width", 2.5)
        line = Line(start=vec(self.map_x(at), -h.y / 2), end=vec(self.map_x(at), h.y / 2), **props)
        self._append(line, enter_with_axes)
        _name_from_call(line, Axes.vline)
        return line

    def hline(self, at: FloatVal, *, style: LineStyle = "solid", enter_with_axes: bool = True, **props: Unpack[StyleKeywords]) -> Line:
        w = self.size
        if style == "dashed":
            props.setdefault("dash", (12.0, 10.0))
        props.setdefault("stroke_width", 2.5)
        line = Line(start=vec(-w.x / 2, self.map_y(at)), end=vec(w.x / 2, self.map_y(at)), **props)
        self._append(line, enter_with_axes)
        _name_from_call(line, Axes.hline)
        return line

    def scatter(self, xs: FloatColumn, ys: FloatColumn, *, radius: float = 0.06, enter_with_axes: bool = True, **props: Unpack[UnplacedStyleKeywords]) -> Group[Dot]:
        from ...data.arrow import to_float_list

        dots = [Dot(r=radius, x=self.map_x(x), y=self.map_y(y), **props) for x, y in zip(to_float_list(xs), to_float_list(ys))]
        group = Group(*dots)
        self._append(group, enter_with_axes)
        _name_from_call(group, Axes.scatter)
        return group

    def parametric(
        self,
        fx: PlotFunction,
        fy: PlotFunction,
        *,
        t: tuple[float, float] = (0.0, 6.283185307179586),
        samples: int = 300,
        color: ColorLike | None = None,
        enter_with_axes: bool = True,
        **style: Unpack[PlotStyleKeywords],
    ) -> "ParametricPlot":
        """Curve `(fx(t), fy(t))` for `t` in `t=(start, end)`; cut at the visible ranges."""
        from .plot import ParametricPlot

        t0, t1 = float(t[0]), float(t[1])
        points = [(float(fx(t0 + (t1 - t0) * i / samples)), float(fy(t0 + (t1 - t0) * i / samples))) for i in range(samples + 1)]
        stroke = color if color is not None else self._next_color()
        if isinstance(stroke, ThemeToken):
            stroke = stroke.resolve()
        options: dict[str, Any] = dict(style)
        curve = ParametricPlot(self, fx, fy, [points], stroke=stroke, stroke_width=options.pop("stroke_width", 4.0), **options)
        self._append(curve, enter_with_axes)
        _name_from_call(curve, Axes.parametric)
        return curve

    def bars(self, xs: FloatColumn, heights: FloatColumn, *, width: float = 0.6, enter_with_axes: bool = True, **props: Unpack[UnplacedStyleKeywords]) -> Group[Node]:
        """Vertical bars at data `xs` with data `heights` (from the x axis); `width` is in
        data units. Bars follow the axes when it zooms."""
        from ...data.arrow import to_float_list
        from ..shapes import Rect

        options_in: dict[str, Any] = dict(props)
        fill = options_in.pop("color", None) or self._scene.theme.accent
        xr, size = self.x_range, self.size
        unit_w = size.x / (xr.y - xr.x)
        base = self._axis_y()
        bars: list[Node] = []
        for x, h in zip(to_float_list(xs), to_float_list(heights)):
            top = self.map_y(h)
            options: dict[str, Any] = {"fill": fill, "fill_opacity": 0.85, "stroke_width": 0.0, **options_in}
            bars.append(Rect(w=unit_w * width, h=abs(top - base), x=self.map_x(x), y=(top + base) / 2, **options))
        group = Group(*bars)
        self._append(group, enter_with_axes)
        _name_from_call(group, Axes.bars)
        return group

    def zoom_to(self, *, x: Sequence[float] | None = None, y: Sequence[float] | None = None, **kw: Unpack[AnimationTiming]) -> Animation:
        """Animated change of the visible ranges. ≡ `.to(x_range=..., y_range=...)`."""
        props: dict[str, Any] = {}
        if x is not None:
            props["x_range"] = (float(x[0]), float(x[1]))
        if y is not None:
            props["y_range"] = (float(y[0]), float(y[1]))
        return self.to(**props, **kw)


class NumberLine(Axes):
    """A single horizontal axis."""

    _y_ticks = False

    def __init__(self, x: Sequence[float] = (0, 10, 1), *, width: float = 10.0, **props: Unpack[UnplacedKeywords]) -> None:
        super().__init__(x=x, y=(-1, 1), width=width, height=0.0001, **props)

    def _parts(self) -> list[Node]:
        parts = super()._parts()
        return [p for p in parts if getattr(p, "_part", None) != "y_axis"]
