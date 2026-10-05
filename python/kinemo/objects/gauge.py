"""`k.Gauge`: a dial whose needle follows a value (a speedometer, a pressure gauge), with
numbered ticks, colored zones and a readout."""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence, Unpack

import builtins

from ..anim.animation import Animation, par
from ..anim.ease import EaseLike
from ..reactive.expr import Expr
from ..reactive.native import clamp, cos, sin, vec
from ..reactive.signal import Signal, signal
from ..values.aliases import ColorLike
from ..values.color import RED
from .groups import Group
from .keywords import TransformKeywords
from .node import Node
from .shapes import Arc, Circle, Line
from .text import Text

DEGREES = 3.141592653589793 / 180.0


class Gauge(Group):
    """`k.Gauge(value=speed, range=(0, 120), ticks=6, label="km/h")`: a dial over `sweep`
    degrees (240 by default) whose needle points at `value` (a number or a signal);
    `zones=[(90, 120, k.RED)]` colors stretches of the scale and `readout=True` writes the value
    under the hub. `gauge.value` is the signal; `gauge.to(value=80)` animates it.
    Parts: `track`, `zones`, `ticks`, `labels`, `needle`, `hub`, `readout`."""

    if TYPE_CHECKING:
        value: Signal[float]
        track: Arc
        zones: list[Arc]
        ticks: list[Line]
        labels: list[Text]
        needle: Line
        hub: Circle
        readout: Text | None
        _gauge_opts: tuple[float, float, float, float]

    def __init__(
        self,
        *,
        value: float | Signal[float] = 0.0,
        range: tuple[float, float] = (0.0, 100.0),  # noqa: A002 - the dial's range
        ticks: int = 5,
        sweep: float = 240.0,
        r: float = 1.5,
        label: str = "",
        zones: Sequence[tuple[float, float, ColorLike]] = (),
        readout: bool = True,
        needle_color: ColorLike = RED,
        digits: int = 0,
        **props: Unpack[TransformKeywords],
    ) -> None:
        from .._runtime.context import current_scene

        theme = current_scene().theme
        lo, hi = float(range[0]), float(range[1])
        span = (hi - lo) or 1.0
        level: Signal[float] = value if isinstance(value, Signal) else signal(float(value))
        object.__setattr__(self, "value", level)
        object.__setattr__(self, "_gauge_opts", (lo, hi, sweep, r))
        left = 90.0 + sweep / 2.0

        def angle_of(v: float) -> float:
            return left - (min(max(v, lo), hi) - lo) / span * sweep

        track = Arc(r=r, start_angle=90.0 - sweep / 2.0, angle=sweep, stroke=theme.muted, stroke_width=6.0, fill_opacity=0.0)
        bands: list[Arc] = []
        for z_lo, z_hi, color in zones:
            start = angle_of(z_hi)
            bands.append(Arc(r=r, start_angle=start, angle=angle_of(z_lo) - start, stroke=color, stroke_width=6.0, fill_opacity=0.0))
        marks: list[Line] = []
        numbers: list[Text] = []
        count = max(1, ticks)
        for i in builtins.range(count + 1):  # `range` is the dial's
            v = lo + span * i / count
            a = angle_of(v) * DEGREES
            marks.append(Line(start=(r * 0.86 * cos(a), r * 0.86 * sin(a)), end=(r * 0.98 * cos(a), r * 0.98 * sin(a)), stroke=theme.fg, stroke_width=3.0))
            numbers.append(Text(f"{v:.{digits}f}", size=r * 0.14, x=r * 0.72 * cos(a), y=r * 0.72 * sin(a)))
        # The needle points at the value (clamped to the range), live.
        clamped: Expr[float] = (clamp(level, lo, hi) - lo) / span
        turn = (left - clamped * sweep) * DEGREES
        needle = Line(start=(0.0, 0.0), end=vec(r * 0.58 * cos(turn), r * 0.58 * sin(turn)), stroke=needle_color, stroke_width=5.0)
        hub = Circle(r=r * 0.07, fill=needle_color, fill_opacity=1.0, stroke_width=0.0)
        text: Text | None = None
        if readout:
            unit = f" {label}" if label else ""
            text = Text(lambda: f"{level():.{digits}f}{unit}", size=r * 0.17, y=-r * 0.38)
        parts: list[Node] = [track, *bands, *marks, *numbers, needle, hub] + ([text] if text is not None else [])
        names = {"track": track, "needle": needle, "hub": hub, "readout": text}
        for name, part in names.items():
            if part is not None:
                object.__setattr__(part, "_part", name)
            object.__setattr__(self, name, part)
        for group_name, items in (("zones", bands), ("ticks", marks), ("labels", numbers)):
            for i, part in enumerate(items):
                object.__setattr__(part, "_part", f".{group_name}[{i}]")
            object.__setattr__(self, group_name, items)
        super().__init__(*parts, **props)

    def to(self, *, value: float | None = None, duration: float | None = None, ease: EaseLike | None = None, **kw: object) -> Animation:  # pyright: ignore[reportIncompatibleMethodOverride] - `value=` is the gauge's own input
        """`gauge.to(value=80)`: the needle (and readout) move to a new value; other props as
        for any group."""
        if value is not None and not kw:
            return self.value.to(float(value), duration=duration, ease=ease)
        anim = super().to(duration=duration, ease=ease, **kw)  # type: ignore[arg-type]
        if value is not None:
            return par(anim, self.value.to(float(value), duration=duration, ease=ease))
        return anim
