"""The value axis of a `k.BarChart`: ticks keyed by value that follow the chart's scale."""

from __future__ import annotations

from typing import TYPE_CHECKING, Unpack

from ... import _core
from ..._runtime.spans import Span
from ...anim.ease import Ease
from ...reactive.native import vec
from ..groups import Group, Reorder
from ..node import Node
from ..shapes import Line
from ..text import Text
from .data_transition import animate, number_text, tick_values

if TYPE_CHECKING:
    from ...reactive.expr import Expr
    from ...scene.scene import Scene
    from ..keywords import TransformKeywords

TICK_LENGTH = 0.1
TICK_LABEL_SIZE = 0.24
TICK_LABEL_GAP = 0.12


class ValueTick(Group):
    """One tick (mark, label and optional grid line) at a fixed data value."""

    if TYPE_CHECKING:
        _tick_opts: tuple[float, Expr[float], float, float]

    def __init__(self, value: float, top: Expr[float], height: float, grid_width: float, **props: Unpack[TransformKeywords]) -> None:
        object.__setattr__(self, "_tick_opts", (value, top, height, grid_width))
        super().__init__(**props)

    def _parts(self) -> list[Node]:
        value, top, height, grid_width = self._tick_opts
        y = value / top * height - height / 2
        visible = top >= value - 1e-9
        text = number_text(value)
        x0, _, x1, _ = _core.measure_text(text, TICK_LABEL_SIZE)
        mark = Line(start=vec(-TICK_LENGTH, y), end=vec(0.0, y), stroke_width=2.5, visible=visible)
        label = Text(text, size=TICK_LABEL_SIZE, x=-TICK_LENGTH - TICK_LABEL_GAP - (x1 - x0) / 2, y=y, visible=visible)
        parts: list[Node] = [mark, label]
        if grid_width > 0 and value > 0:
            muted = self._scene.theme.muted
            parts.append(Line(start=vec(0.0, y), end=vec(grid_width, y), stroke=muted, stroke_width=1.5, opacity=0.5, visible=visible))
        for part, name in zip(parts, ("mark", "label", "grid")):
            object.__setattr__(part, "_part", name)
        return parts


class ValueAxis(Group):
    """Vertical axis at the left edge of the plot area (its origin), with keyed ticks."""

    if TYPE_CHECKING:
        _axis_opts: tuple[Expr[float], float, list[float], float]
        #: Ticks by value.
        ticks: dict[float, ValueTick]
        line: Line

    def __init__(self, top: Expr[float], height: float, ticks: list[float], grid_width: float, **props: Unpack[TransformKeywords]) -> None:
        object.__setattr__(self, "_axis_opts", (top, height, ticks, grid_width))
        object.__setattr__(self, "ticks", {})
        super().__init__(**props)

    def _parts(self) -> list[Node]:
        top, height, values, grid_width = self._axis_opts
        line = Line(start=(0.0, -height / 2), end=(0.0, height / 2), stroke_width=3.0)
        object.__setattr__(line, "_part", "line")
        object.__setattr__(self, "line", line)
        parts: list[Node] = [line]
        for v in values:
            parts.append(self._new_tick(v))
        return parts

    def _new_tick(self, value: float, **props: Unpack[TransformKeywords]) -> ValueTick:
        top, height, _, grid_width = self._axis_opts
        tick = ValueTick(value, top, height, grid_width, **props)
        object.__setattr__(tick, "_part", f"[{number_text(value)}]")
        self.ticks[value] = tick
        return tick

    def retarget(self, s: "Scene", top: float, step: float, start: float, duration: float, ease: Ease, span: Span) -> None:
        """Fade in the ticks of the new scale and fade out the ones it no longer has."""
        wanted = tick_values(top, step)
        leaving = [t for v, t in self.ticks.items() if v not in wanted]
        for v in [v for v in self.ticks if v not in wanted]:
            del self.ticks[v]
        entering = [self._new_tick(v, opacity=0.0) for v in wanted if v not in self.ticks]
        if entering:
            Reorder(self, self._children_at(start) + entering, span, entering=entering)._emit(s, start, 0.0, ease)
        targets = [(t._sig("opacity"), 1.0) for t in entering] + [(t._sig("opacity"), 0.0) for t in leaving]
        animate(s, targets, start, duration, ease, span)
        for t in leaving:
            s._exit(t, start + duration)
