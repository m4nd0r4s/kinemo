"""`k.PieChart`: one slice per row of a table (a donut with `donut=`); `pie.to(data=...)`
animates the slices' angles. Slices are matched by `key`, like the bars of `k.BarChart`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Unpack, cast

from ..._runtime.spans import Span, user_span
from ...anim.animation import Animation, par, stagger
from ...anim.ease import Ease
from ...anim.prop import PropTo
from ...anim.verbs import draw, fade_in
from ...reactive.native import cos, pi, sin, vec
from ..groups import Group
from ..node import Node
from ..props import PropSpec
from ..shapes import Line, Sector
from ..text import Text
from .bar_chart import BarRow, read_rows
from .data_transition import DataTransition, animate, set_at

if TYPE_CHECKING:
    from ...data.arrow import DataTable
    from ...scene.scene import Scene
    from ...values.aliases import ColorLike
    from ..keywords import ChangeKeywords, ChartKeywords
    from ..props import PropAccessor

#: Colors given to slices in order (theme tokens), when `color=` does not map a key.
SLICE_COLORS = ("BLUE", "YELLOW", "RED", "GREEN", "PURPLE", "ORANGE", "TEAL", "PINK")
#: Slices narrower than this (degrees) get a leader line to their label.
LEADER_BELOW = 30.0
#: The first slice starts at the top and slices go clockwise.
TOP = 90.0


def _shares(rows: list[BarRow]) -> list[float]:
    total = sum(max(r.value, 0.0) for r in rows)
    return [max(r.value, 0.0) / total if total > 0 else 0.0 for r in rows]


class PieSlice(Group):
    """A slice of a PieChart: `share` (of the whole, 0–1) and `start` (degrees) are signals.
    Parts: `slice.sector`, `slice.label` (the category), `slice.percent`."""

    PROPS = {"share": PropSpec("float", 0.0), "start": PropSpec("float", TOP)}

    if TYPE_CHECKING:
        share: PropAccessor[float]
        start: PropAccessor[float]
        sector: Sector
        label: Text
        percent: Text | None
        leader: Line | None
        _slice_opts: tuple[str, float, float, Any, bool, float]

    def __init__(self, category: str, *, share: float, start: float, radius: float, inner: float, color: Any, percent: bool, label_size: float) -> None:
        object.__setattr__(self, "_slice_opts", (category, radius, inner, color, percent, label_size))
        super().__init__(share=share, start=start)

    def _parts(self) -> list[Node]:
        category, radius, inner, color, percent, label_size = self._slice_opts
        angle = self.share * -360.0
        sector = Sector(r=radius, inner=inner, start_angle=self.start, angle=angle, fill=color, fill_opacity=0.9, stroke_width=2.0)
        # The label sits outside the slice, at its middle angle; small slices get a leader line.
        middle = (self.start + angle / 2) * (pi / 180)
        reach = radius + label_size * 2.4
        name = Text(category, size=label_size, x=cos(middle) * reach, y=sin(middle) * reach)
        parts: list[Node] = [sector, name]
        value_text: Text | None = None
        if percent:
            value_text = Text(lambda: f"{self.share() * 100:.0f}%", size=label_size * 0.85, x=cos(middle) * reach, y=sin(middle) * reach - label_size * 1.1)
            parts.append(value_text)
        leader: Line | None = None
        if float(self.share.now) * 360.0 < LEADER_BELOW:
            # A narrow slice: a line from it to its label.
            near, far = radius * 1.02, reach - label_size * 0.9
            leader = Line(start=vec(cos(middle) * near, sin(middle) * near), end=vec(cos(middle) * far, sin(middle) * far), stroke_width=1.5)
            parts.append(leader)
        for part, attr in ((sector, "sector"), (name, "label"), (value_text, "percent"), (leader, "leader")):
            object.__setattr__(self, attr, part)
            if part is not None:
                object.__setattr__(part, "_part", attr)
        return parts

    def _labels(self) -> list[Node]:
        return [p for p in (self.label, self.percent, self.leader) if p is not None]

    def _indicate_target(self) -> Node:
        return self.sector

    def _color_targets(self) -> list[tuple[Node, str]]:
        return [(self.sector, "fill")]


class PieChart(Group):
    """`k.PieChart(df, labels="pais", values="gwh")`, a donut with `donut=0.5` (the hole, as a
    fraction of the radius). Slices start at the top and go clockwise; labels sit outside with
    their percentage. `pie.slice("IT")` is the slice of a key, `pie.to(data=df2)` animates
    the slices to the new shares (new keys grow in, missing keys shrink away)."""

    if TYPE_CHECKING:
        _pie_opts: tuple[str, str, str | None, float, float, ColorLike | Mapping[str, ColorLike] | None, bool, float]
        _initial: list[BarRow]
        _slices: dict[str, PieSlice]
        _order: list[str]
        _colors_used: int

    def __init__(
        self,
        data: DataTable,
        labels: str,
        values: str,
        *,
        key: str | None = None,
        radius: float = 2.0,
        donut: float = 0.0,
        color: ColorLike | Mapping[str, ColorLike] | None = None,
        percent: bool = True,
        label_size: float = 0.26,
        **props: Unpack[ChartKeywords],
    ) -> None:
        rows = read_rows(data, labels, values, key)
        object.__setattr__(self, "_pie_opts", (labels, values, key, float(radius), max(0.0, min(float(donut), 0.95)), color, percent, label_size))
        object.__setattr__(self, "_initial", rows)
        object.__setattr__(self, "_slices", {})
        object.__setattr__(self, "_order", [r.key for r in rows])
        object.__setattr__(self, "_colors_used", 0)
        super().__init__(**props)

    def _parts(self) -> list[Node]:
        rows = self._initial
        shares = _shares(rows)
        starts = [TOP - sum(shares[:i]) * 360.0 for i in range(len(rows))]
        return [self._new_slice(r, share, start) for r, share, start in zip(rows, shares, starts)]

    def _color_for(self, key: str) -> Any:
        color = self._pie_opts[5]
        if isinstance(color, dict):
            mapped = cast("Mapping[str, ColorLike]", color).get(key)
            if mapped is not None:
                return mapped
        elif color is not None:
            return color
        from ...values import color as palette

        name = SLICE_COLORS[self._colors_used % len(SLICE_COLORS)]
        object.__setattr__(self, "_colors_used", self._colors_used + 1)
        return getattr(palette, name)

    def _new_slice(self, row: BarRow, share: float, start: float) -> PieSlice:
        _, _, _, radius, donut, _, percent, label_size = self._pie_opts
        piece = PieSlice(row.category, share=share, start=start, radius=radius, inner=radius * donut, color=self._color_for(row.key), percent=percent, label_size=label_size)
        object.__setattr__(piece, "_part", f'["{row.key}"]')
        self._slices[row.key] = piece
        return piece

    @property
    def keys(self) -> list[str]:
        """Keys of the slices, in order (as of the last scheduled transition)."""
        return list(self._order)

    def slice(self, key: object) -> PieSlice:
        """The slice of `key`."""
        from ...diagnostics import KinemoError

        if str(key) not in self._slices:
            raise KinemoError.make("K1202", f"the chart has no key {key!r}", fixes=[(f"keys: {', '.join(self._slices)}", None)])
        return self._slices[str(key)]

    def enter(self) -> Animation:
        """`k.draw(pie)`: the slices are drawn one after the other, then their labels appear."""
        slices = [self._slices[k] for k in self._order]
        return par(stagger([draw(s.sector) for s in slices], lag=0.12), fade_in(*[label for s in slices for label in s._labels() if label is not s.leader]))

    def to(self, *, data: DataTable | None = None, **kw: Unpack[ChangeKeywords]) -> Animation:  # pyright: ignore[reportIncompatibleMethodOverride] - `data=` is the chart's own input
        """`pie.to(data=df2)`: animated change of data (plus any other props)."""
        anim = super().to(**kw)
        if data is None:
            return anim
        assert isinstance(anim, PropTo)
        labels, values, key = self._pie_opts[:3]
        rows = read_rows(data, labels, values, key)
        anim.extra.append(DataTransition(self, lambda s, t0, d, e, sp: self._transition(rows, s, t0, d, e, sp), user_span()))
        return anim

    def _transition(self, rows: list[BarRow], s: "Scene", start: float, duration: float, ease: Ease, span: Span) -> None:
        slices = self._slices
        wanted = {r.key for r in rows}
        leaving = [piece for k, piece in slices.items() if k not in wanted]
        for k in [k for k in slices if k not in wanted]:
            del slices[k]
        shares = _shares(rows)
        targets: list[tuple[Any, Any]] = []
        position = TOP
        for row, share in zip(rows, shares):
            piece = slices.get(row.key)
            if piece is None:
                # Grows from nothing where it will sit; its labels fade in.
                piece = self._new_slice(row, 0.0, position)
                self._adopt(piece)
                self._children_sig.set(self.children + [piece])
                s._enter(piece, start)
                set_at(s, [(label._sig("opacity"), 0.0) for label in piece._labels()], start, span)
                targets += [(label._sig("opacity"), 1.0) for label in piece._labels()]
            targets += [(piece._sig("share"), share), (piece._sig("start"), position)]
            position -= share * 360.0
        # Leaving slices shrink where they are, and their labels fade out.
        targets += [(piece._sig("share"), 0.0) for piece in leaving]
        targets += [(label._sig("opacity"), 0.0) for piece in leaving for label in piece._labels()]
        animate(s, targets, start, duration, ease, span)
        for piece in leaving:
            s._exit(piece, start + duration)
        object.__setattr__(self, "_order", [r.key for r in rows])
