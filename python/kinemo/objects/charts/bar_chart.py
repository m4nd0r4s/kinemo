"""`k.BarChart`: one bar per row of a table; `chart.to(data=...)` animates the change.

Bars are matched by `key`: kept bars grow or shrink to their new value and travel to
their new slot, new keys enter growing from the baseline, missing keys shrink and leave."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Mapping, TypedDict, Unpack, cast

from ..._runtime.spans import Span, user_span
from ...anim.animation import Animation, seq, stagger
from ...anim.ease import Ease
from ...anim.prop import PropTo
from ...anim.verbs import draw, grow
from ...data.arrow import column, columns
from ...diagnostics import KinemoError
from ..groups import Group, Reorder
from ..node import Node
from ..props import PropSpec, accent
from ..shapes import Line, Rect
from ..text import Text
from .data_transition import DataTransition, animate, nice_scale, set_at
from .value_axis import ValueAxis

if TYPE_CHECKING:
    from ...data.arrow import DataTable
    from ...reactive.expr import Expr
    from ...scene.scene import Scene
    from ...values.aliases import ColorLike
    from ..keywords import ChangeKeywords, ChartKeywords
    from ..props import PropAccessor

CATEGORY_GAP = 0.3
VALUE_GAP = 0.1
#: Room left of the plot for tick labels and above/below it for value and category labels.
BOUNDS_LEFT = 1.1
BOUNDS_MARGIN = 0.55


@dataclass(frozen=True)
class BarRow:
    key: str
    category: str
    value: float


def read_rows(data: DataTable, x: str, y: str, key: str | None) -> list[BarRow]:
    """Rows of a BarChart from any table (Arrow, dict of lists, list of dicts)."""
    cols = columns(data)
    categories = column(cols, x).strings()
    values = column(cols, y).floats()
    keys = column(cols, key).strings() if key is not None else categories
    seen: set[str] = set()
    for k in keys:
        if k in seen:
            raise KinemoError.make(
                "K1204",
                f"key '{k}' appears more than once in column '{key or x}'",
                fixes=[("aggregate before drawing", f'df.group_by("{key or x}").sum()'), ("or pick another column for key=", None)],
            )
        seen.add(k)
    return [BarRow(k, c, 0.0 if math.isnan(v) else v) for k, c, v in zip(keys, categories, values)]


def _decimals(values: list[float]) -> int:
    if all(v == int(v) for v in values):
        return 0
    return 1 if all(round(v, 1) == v for v in values) else 2


class ChartBar(Group):
    """A bar of a BarChart: `value` and `bar_width` are signals; its origin is the baseline."""

    PROPS = {"value": PropSpec("float", 0.0), "bar_width": PropSpec("float", 0.6)}

    if TYPE_CHECKING:
        value: PropAccessor[float]
        bar_width: PropAccessor[float]
        _bar_opts: tuple[str, Expr[float], float, ColorLike | None, bool, int, float]
        rect: Rect
        #: The category name under the bar.
        category: Text
        #: The value above the bar (with `labels=True`).
        value_label: Text

    def __init__(self, category: str, *, top: Expr[float], height: float, color: ColorLike | None, labels: bool, decimals: int, label_size: float, **props: Unpack[ChartBarKeywords]) -> None:
        object.__setattr__(self, "_bar_opts", (category, top, height, color, labels, decimals, label_size))
        super().__init__(**props)

    def _parts(self) -> list[Node]:
        category, top, height, color, labels, decimals, label_size = self._bar_opts
        v = self.value
        h = v / top * height
        fill = color if color is not None else accent(self._scene.theme)
        rect = Rect(w=self.bar_width, h=h, y=h / 2, fill=fill, fill_opacity=0.85, stroke_width=0.0)
        name = Text(category, size=label_size, y=-CATEGORY_GAP)
        # `k.indicate(bar)` pulses the rectangle from the baseline; the labels stay put.
        self._scene._push_set(rect._sig("_pulse_from"), (0.0, -1.0), rect._span)
        parts: list[Node] = [rect, name]
        for part, attr in ((rect, "rect"), (name, "category")):
            object.__setattr__(self, attr, part)
            object.__setattr__(part, "_part", attr)
        if labels:
            text = _value_text(v, decimals)
            value_label = Text(text, size=label_size).place(above=rect, gap=VALUE_GAP)
            object.__setattr__(self, "value_label", value_label)
            object.__setattr__(value_label, "_part", "value_label")
            parts.append(value_label)
        return parts

    def _indicate_target(self) -> Node:
        return self.rect

    def _grow_parts(self) -> tuple[list[Node], list[Node]]:
        faded: list[Node] = [self.category]
        if "value_label" in self.__dict__:
            faded.append(self.value_label)
        return [self.rect], faded

    def _color_targets(self) -> list[tuple[Node, str]]:
        return [(self.rect, "fill")]


def _value_text(v: Expr[float], decimals: int) -> Callable[[], str]:
    if decimals == 0:
        return lambda: f"{v():.0f}"
    if decimals == 1:
        return lambda: f"{v():.1f}"
    return lambda: f"{v():.2f}"


class NewBarKeywords(TypedDict, total=False):
    value: float
    opacity: float
    bar_width: float


class ChartBarKeywords(NewBarKeywords, total=False):
    x: float
    y: float


class BarChart(Group):
    """`k.BarChart(df, x="pais", y="gwh", key="pais")`. `chart.to(data=df2)` animates bars
    to the new values: they grow, reorder, enter and leave by key."""

    PROPS = {"y_max": PropSpec("float", 1.0)}

    if TYPE_CHECKING:
        y_max: PropAccessor[float]
        _chart_opts: tuple[str, str, str | None, float, float, ColorLike | Mapping[str, ColorLike] | None, bool, bool, float, float, int]
        _initial: tuple[list[BarRow], float, float]
        _bars: dict[str, ChartBar]
        _categories: dict[str, str]
        _order: list[str]
        baseline: Line
        axis: ValueAxis
        #: The group of bars, in slot order.
        bars: Group
        bounds: Rect

    def __init__(
        self,
        data: DataTable,
        x: str,
        y: str,
        *,
        key: str | None = None,
        width: float = 8.0,
        height: float = 4.5,
        color: ColorLike | Mapping[str, ColorLike] | None = None,
        labels: bool = True,
        grid: bool = False,
        bar_ratio: float = 0.7,
        label_size: float = 0.28,
        **props: Unpack[ChartKeywords],
    ) -> None:
        rows = read_rows(data, x, y, key)
        top, step = nice_scale(max((r.value for r in rows), default=0.0))
        decimals = _decimals([r.value for r in rows])
        object.__setattr__(self, "_chart_opts", (x, y, key, width, height, color, labels, grid, bar_ratio, label_size, decimals))
        object.__setattr__(self, "_initial", (rows, top, step))
        object.__setattr__(self, "_bars", {})
        object.__setattr__(self, "_categories", {r.key: r.category for r in rows})
        object.__setattr__(self, "_order", [r.key for r in rows])
        super().__init__(y_max=top, **props)

    # ---- construction --------------------------------------------------------------
    def _parts(self) -> list[Node]:
        _, _, _, width, height, _, _, grid, _, _, _ = self._chart_opts
        rows, top, step = self._initial
        from .data_transition import tick_values

        baseline = Line(start=(-width / 2, -height / 2), end=(width / 2, -height / 2), stroke_width=3.0)
        axis = ValueAxis(self.y_max, height, tick_values(top, step), width if grid else 0.0, x=-width / 2)
        bars = Group(*[self._new_bar(r, i, len(rows)) for i, r in enumerate(rows)])
        # Invisible box with room for every label: the chart's layout bounds stay put while
        # the data changes, so placements relative to it do not jump.
        bounds = Rect(w=width + BOUNDS_LEFT, h=height + 2 * BOUNDS_MARGIN, x=-BOUNDS_LEFT / 2, fill_opacity=0.0, stroke_width=0.0)
        for part, name in ((baseline, "baseline"), (axis, "axis"), (bars, "bars"), (bounds, "bounds")):
            object.__setattr__(self, name, part)
            object.__setattr__(part, "_part", name)
        return [bounds, axis, bars, baseline]

    def _slot(self, i: int, n: int) -> tuple[float, float]:
        """(center x, bar width) of slot `i` of `n`."""
        width, bar_ratio = self._chart_opts[3], self._chart_opts[8]
        slot = width / max(n, 1)
        return -width / 2 + slot * (i + 0.5), slot * bar_ratio

    def _color_for(self, key: str) -> ColorLike | None:
        color = self._chart_opts[5]
        if isinstance(color, dict):
            return color.get(key)
        return cast("ColorLike | None", color)

    def _new_bar(self, row: BarRow, i: int, n: int, **props: Unpack[NewBarKeywords]) -> ChartBar:
        _, _, _, _, height, _, labels, _, _, label_size, decimals = self._chart_opts
        x, bar_width = self._slot(i, n)
        props.setdefault("value", row.value)
        props.setdefault("bar_width", bar_width)
        bar = ChartBar(row.category, top=self.y_max, height=height, color=self._color_for(row.key), labels=labels,
                       decimals=decimals, label_size=label_size, x=x, y=-height / 2, **props)
        object.__setattr__(bar, "_part", f'["{row.key}"]')
        self._bars[row.key] = bar
        return bar

    # ---- reading -------------------------------------------------------------------
    @property
    def keys(self) -> list[str]:
        """Keys of the bars, in slot order (as of the last scheduled transition)."""
        return list(self._order)

    def bar(self, key: object) -> ChartBar:
        """The bar of `key`."""
        bars: dict[str, ChartBar] = self._bars
        if str(key) not in bars:
            raise KinemoError.make("K1202", f"the chart has no key {key!r}", fixes=[(f"keys: {', '.join(bars)}", None)])
        return bars[str(key)]

    # ---- verbs and transitions -----------------------------------------------------------
    def enter(self) -> Animation:
        """`k.draw(chart)`: axes are drawn, then the bars grow from the baseline."""
        bars = [self._bars[k] for k in self._order]
        return seq(draw(self.bounds, self.baseline, self.axis), stagger([grow(b, from_="bottom") for b in bars], lag=0.08))

    def to(self, *, data: DataTable | None = None, **kw: Unpack[ChangeKeywords]) -> Animation:  # pyright: ignore[reportIncompatibleMethodOverride] - `data=` is the chart's own input
        """`chart.to(data=df2)`: animated change of data (plus any other props)."""
        anim = super().to(**kw)
        if data is None:
            return anim
        assert isinstance(anim, PropTo)
        x, y, key = self._chart_opts[:3]
        rows = read_rows(data, x, y, key)
        span = user_span()
        anim.extra.append(DataTransition(self, lambda s, t0, d, e, sp: self._transition(rows, s, t0, d, e, sp), span))
        return anim

    def _transition(self, rows: list[BarRow], s: "Scene", start: float, duration: float, ease: Ease, span: Span) -> None:
        bars: dict[str, ChartBar] = self._bars
        top, step = nice_scale(max((r.value for r in rows), default=0.0))
        targets: list[tuple[Any, Any]] = [(self._sig("y_max"), top)]
        self.axis.retarget(s, top, step, start, duration, ease, span)
        wanted = {r.key for r in rows}
        leaving = [b for k, b in bars.items() if k not in wanted]
        for k in [k for k in bars if k not in wanted]:
            del bars[k]
        entering: list[ChartBar] = []
        renamed: list[tuple[Any, Any]] = []
        n = len(rows)
        for i, row in enumerate(rows):
            x, bar_width = self._slot(i, n)
            bar = bars.get(row.key)
            if bar is None:
                # Grows in its slot from no width, so it does not cover bars that move.
                bar = self._new_bar(row, i, n, value=0.0, opacity=0.0, bar_width=0.0)
                entering.append(bar)
                targets.append((bar._sig("opacity"), 1.0))
            elif self._categories[row.key] != row.category:
                renamed.append((bar.category._sig("text"), row.category))
            self._categories[row.key] = row.category
            targets += [(bar._sig("value"), row.value), (bar._sig("x"), x), (bar._sig("bar_width"), bar_width)]
        group: Group = self.bars
        if entering:
            Reorder(group, group._children_at(start) + entering, span, entering=entering)._emit(s, start, 0.0, ease)
        set_at(s, renamed, start, span)
        targets += [(b._sig(p), 0.0) for b in leaving for p in ("value", "opacity", "bar_width")]
        animate(s, targets, start, duration, ease, span)
        for b in leaving:
            s._exit(b, start + duration)
        object.__setattr__(self, "_order", [r.key for r in rows])
