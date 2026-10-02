"""`k.LineChart`: one piecewise-linear series per `y` column, drawn on a `k.Axes`.

Every point is a pair of signals, so `chart.to(data=...)` morphs the lines point by
point; points the new data adds grow out of the old last point, points it drops fold
into the new last point and leave."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Sequence, Unpack

from ..._runtime.spans import Span, user_span
from ...anim.animation import Animation
from ...anim.ease import Ease
from ...anim.prop import PropTo
from ...data.arrow import column, columns
from ...diagnostics import KinemoError
from ...reactive.signal import Signal, signal
from ...theme.tokens import ThemeToken
from ..groups import Group, Reorder
from ..node import Node
from ..shapes import Dot, Line
from ..text import Text
from .axes import Axes
from .data_transition import DataTransition, animate, nice_scale

if TYPE_CHECKING:
    from ...data.arrow import DataTable
    from ...scene.scene import Scene
    from ...values.aliases import ColorLike
    from ..keywords import ChangeKeywords, TransformKeywords, UnplacedKeywords, VisibilityKeywords

Points = list[tuple[float, float]]


def read_series(data: DataTable, x: str, ys: Sequence[str]) -> dict[str, Points]:
    """`{y column: [(x, y), ...]}` sorted by x, without rows where x or y is null."""
    cols = columns(data)
    xs = column(cols, x).floats()
    out: dict[str, Points] = {}
    for name in ys:
        values = column(cols, name).floats()
        pts = sorted((a, b) for a, b in zip(xs, values) if not (math.isnan(a) or math.isnan(b)))
        if not pts:
            raise KinemoError.make("K1203", f"series '{name}' has no points (all null)", fixes=[("check the x= and y= columns", None)])
        out[name] = pts
    return out


def _padded_range(lo: float, hi: float) -> tuple[float, float]:
    if hi <= lo:
        return lo - 1.0, hi + 1.0
    return lo, hi


def _value_range(series: dict[str, Points]) -> tuple[float, float]:
    lo = min(min(y for _, y in pts) for pts in series.values())
    hi = max(max(y for _, y in pts) for pts in series.values())
    top, _ = nice_scale(hi) if hi > 0 else (0.0, 1.0)
    bottom = 0.0 if lo >= 0 else -nice_scale(-lo)[0]
    return _padded_range(bottom, top)


class DataLine(Group):
    """One series: segments between consecutive points (and optional dots)."""

    if TYPE_CHECKING:
        _line_opts: tuple[Axes, ColorLike, bool]
        _label_text: str | None
        _end: tuple[Signal[float], Signal[float]]
        #: x and y of every point, as signals.
        xs: list[Signal[float]]
        ys: list[Signal[float]]
        segments: list[Line]
        dots: list[Dot]
        #: The series name at the end of the line (with `legend=True`).
        label: Text

    def __init__(self, axes: Axes, points: Points, *, stroke: ColorLike, dots: bool, label: str | None, **props: Unpack[TransformKeywords]) -> None:
        object.__setattr__(self, "_line_opts", (axes, stroke, dots))
        object.__setattr__(self, "xs", [signal(p[0]) for p in points])
        object.__setattr__(self, "ys", [signal(p[1]) for p in points])
        object.__setattr__(self, "segments", [])
        object.__setattr__(self, "dots", [])
        object.__setattr__(self, "_label_text", label)
        super().__init__(**props)

    def _parts(self) -> list[Node]:
        parts: list[Node] = []
        for i in range(len(self.xs)):
            parts += self._point_parts(i)
        label = self._label_text
        if label:
            axes, stroke, _ = self._line_opts
            end_x, end_y = signal(self.xs[-1].now), signal(self.ys[-1].now)
            object.__setattr__(self, "_end", (end_x, end_y))
            tag = Text(label, size=0.28, fill=stroke, x=axes.map_x(end_x) + 0.5, y=axes.map_y(end_y) + 0.25)
            object.__setattr__(tag, "_part", "label")
            object.__setattr__(self, "label", tag)
            parts.append(tag)
        return parts

    def _point_parts(self, i: int, **props: Unpack[VisibilityKeywords]) -> list[Node]:
        """The dot of point `i` and the segment that arrives at it."""
        axes, stroke, dots = self._line_opts
        parts: list[Node] = []
        if i > 0:
            seg = Line(start=axes.local_point(self.xs[i - 1], self.ys[i - 1]), end=axes.local_point(self.xs[i], self.ys[i]), stroke=stroke, stroke_width=4.0, **props)
            object.__setattr__(seg, "_part", f".segments[{i - 1}]")
            self.segments.append(seg)
            parts.append(seg)
        if dots:
            dot = Dot(r=0.07, fill=stroke, x=axes.map_x(self.xs[i]), y=axes.map_y(self.ys[i]), **props)
            object.__setattr__(dot, "_part", f".dots[{i}]")
            self.dots.append(dot)
            parts.append(dot)
        return parts

    def retarget(self, points: Points, s: "Scene", start: float, duration: float, ease: Ease, span: Span) -> None:
        old = len(self.xs)
        last = points[-1]
        targets: list[tuple[Signal[float], float]] = []
        entering: list[Node] = []
        for i in range(old, len(points)):
            self.xs.append(signal(_value_at(s, self.xs[old - 1], start)))
            self.ys.append(signal(_value_at(s, self.ys[old - 1], start)))
            entering += self._point_parts(i)
        for i, (sx, sy) in enumerate(zip(self.xs, self.ys)):
            px, py = points[i] if i < len(points) else last
            targets += [(sx, px), (sy, py)]
        leaving = self._parts_after(len(points))
        if entering:
            Reorder(self, self._children_at(start) + entering, span, entering=entering)._emit(s, start, 0.0, ease)
        end = self.__dict__.get("_end")
        if end is not None:
            targets += [(end[0], last[0]), (end[1], last[1])]
        animate(s, targets, start, duration, ease, span)
        for p in leaving:
            s._exit(p, start + duration)
        n = len(points)
        object.__setattr__(self, "xs", self.xs[:n])
        object.__setattr__(self, "ys", self.ys[:n])
        object.__setattr__(self, "segments", self.segments[: n - 1])
        object.__setattr__(self, "dots", self.dots[:n] if self.dots else [])

    def _parts_after(self, n: int) -> list[Node]:
        """Segments and dots of the points from index `n` on."""
        return [*self.segments[max(n - 1, 0):], *self.dots[n:]]


def _value_at(s: "Scene", sig: Signal[float], t: float) -> float:
    import json

    raw = json.loads(s._b.eval_signal(sig._id, t))
    return float(raw["Float"]) if isinstance(raw, dict) else float(raw)


class LineChart(Axes):
    """`k.LineChart(df, x="hour", y=["solar", "load"])`: a k.Axes with one line per
    `y` column. `chart.to(data=df2)` morphs the lines; the axes ranges stay fixed
    (pass `x_range=`/`y_range=` covering every dataset you will show)."""

    if TYPE_CHECKING:
        _series_opts: tuple[str, list[str], dict[str, Points], Sequence[ColorLike] | None, bool, bool]
        #: One `DataLine` per `y` column, by name.
        lines: dict[str, DataLine]

    def __init__(
        self,
        data: DataTable,
        x: str,
        y: str | Sequence[str],
        *,
        x_range: Sequence[float] | None = None,
        y_range: Sequence[float] | None = None,
        width: float = 8.0,
        height: float = 4.5,
        colors: Sequence[ColorLike] | None = None,
        dots: bool = False,
        legend: bool = True,
        **props: Unpack[UnplacedKeywords],
    ) -> None:
        ys = [y] if isinstance(y, str) else list(y)
        series = read_series(data, x, ys)
        xr: Sequence[float] = tuple(x_range) if x_range is not None else _padded_range(min(p[0] for pts in series.values() for p in pts), max(p[0] for pts in series.values() for p in pts))
        yr: Sequence[float] = tuple(y_range) if y_range is not None else _value_range(series)
        object.__setattr__(self, "_series_opts", (x, ys, series, colors, dots, legend and len(ys) > 1))
        object.__setattr__(self, "lines", {})
        super().__init__(x=xr, y=yr, width=width, height=height, **props)

    def _parts(self) -> list[Node]:
        parts = super()._parts()
        _, ys, series, colors, dots, legend = self._series_opts
        for i, name in enumerate(ys):
            stroke: ColorLike = colors[i % len(colors)] if colors else self._next_color()
            if isinstance(stroke, ThemeToken):
                stroke = stroke.resolve()
            line = DataLine(self, series[name], stroke=stroke, dots=dots, label=name if legend else None)
            object.__setattr__(line, "_part", f'.lines["{name}"]')
            self.lines[name] = line
            parts.append(line)
        return parts

    def to(self, *, data: DataTable | None = None, **kw: Unpack[ChangeKeywords]) -> Animation:  # pyright: ignore[reportIncompatibleMethodOverride] - `data=` is the chart's own input
        """`chart.to(data=df2)`: the lines morph to the new values (plus any other props)."""
        anim = super().to(**kw)
        if data is None:
            return anim
        assert isinstance(anim, PropTo)
        x, ys = self._series_opts[:2]
        series = read_series(data, x, ys)

        def apply(s: "Scene", start: float, duration: float, ease: Ease, span: Span) -> None:
            for name, line in self.lines.items():
                line.retarget(series[name], s, start, duration, ease, span)

        anim.extra.append(DataTransition(self, apply, user_span()))
        return anim


__all__ = ["DataLine", "LineChart"]
