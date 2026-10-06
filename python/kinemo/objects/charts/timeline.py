"""`k.Timeline`: events along a time axis, labels kept apart, revealed one by one, with the
view panning and zooming like an axes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence, Unpack

from ..._runtime.spans import user_span
from ...anim.animation import Animation
from ...anim.verbs import fade_in
from ...diagnostics import KinemoError
from ...reactive.native import vec
from ..groups import Group
from ..shapes import Dot, Line
from ..text import Text
from .axes import NumberLine
from .sampling import nice_step

if TYPE_CHECKING:
    from ...anim.animation import AnimationTiming
    from ...values.aliases import ColorLike
    from ..keywords import UnplacedKeywords

#: Label rows tried, alternating above and below the axis (units from the axis).
LEVELS = (0.75, -0.75, 1.35, -1.35, 1.95, -1.95)


class TimelineEvent(Group):
    """An event of a `k.Timeline`: its `marker` on the axis, the `stem` to its `label`, and its
    `time`."""

    if TYPE_CHECKING:
        marker: Dot
        stem: Line
        label: Text
        time: float


class Timeline(NumberLine):
    """`k.Timeline([(1687, "Principia"), (1905, "Relativity")], range=(1600, 2000))`: a time
    axis with labelled ticks and the events as markers whose labels sit on rows above and below
    the axis so they do not collide. `reveal=True` keeps the events hidden until
    `tl.reveal("Principia")`; `tl.zoom_to(range=(1850, 1950))` pans and zooms (ticks are
    regenerated, events out of view hide). `tl.event(name)` is an event."""

    if TYPE_CHECKING:
        events: list[TimelineEvent]

    def __init__(
        self,
        events: Sequence[tuple[float, str]],
        *,
        range: tuple[float, float] | None = None,
        step: float | None = None,
        width: float = 12.0,
        reveal: bool = False,
        color: ColorLike | None = None,
        size: float = 0.26,
        **props: Unpack[UnplacedKeywords],
    ) -> None:
        if not events:
            raise KinemoError.make("K0105", "k.Timeline needs at least one event (time, label)")
        times = [float(t) for t, _ in events]
        low, high = range if range is not None else (min(times), max(times))
        if high <= low:
            pad = max(1.0, abs(low) * 0.05)
            low, high = low - pad, high + pad
        spacing = step if step is not None else nice_step(low, high, 6)
        super().__init__(x=(low, high, spacing), width=width, **props)
        accent = color if color is not None else self._scene.theme.accent
        placed: list[TimelineEvent] = []
        # Greedy rows: each label takes the first row where it clears the labels already there.
        rows: dict[float, list[tuple[float, float]]] = {level: [] for level in LEVELS}
        units_per_year = width / (high - low)
        for time, name in sorted(((float(t), str(n)) for t, n in events), key=lambda e: e[0]):
            label = Text(name, size=size)
            half = float(label.width.now) / 2 + size * 0.4
            center = (time - low) * units_per_year
            level = next((lv for lv in LEVELS if all(center - half >= b or center + half <= a for a, b in rows[lv])), LEVELS[-1])
            rows[level].append((center - half, center + half))
            x = self.map_x(time)
            marker = Dot(r=size * 0.32, x=x, y=0.0, fill=accent)
            sign = 1.0 if level > 0 else -1.0
            stem = Line(start=vec(x, sign * size * 0.4), end=vec(x, level - sign * size * 0.6), stroke=accent, stroke_width=2.0, opacity=0.7)
            label.set(x=x, y=level)
            event = TimelineEvent(marker, stem, label, visible=self.in_view(x=time))
            for part, attr in ((marker, "marker"), (stem, "stem"), (label, "label")):
                object.__setattr__(event, attr, part)
                object.__setattr__(part, "_part", attr)
            object.__setattr__(event, "time", time)
            object.__setattr__(event, "_part", f".event({name!r})")
            placed.append(event)
        object.__setattr__(self, "events", placed)
        self.add(*placed, enter_with_axes=not reveal)

    def event(self, name: str) -> TimelineEvent:
        """The event labelled `name`."""
        for event in self.events:
            if event.label.text.now == name:
                return event
        raise KinemoError.make("K0105", f"the timeline has no event {name!r}", spans=[user_span()], fixes=[(f"events: {', '.join(str(e.label.text.now) for e in self.events)}", None)])

    def reveal(self, name: str, **kw: Unpack[AnimationTiming]) -> Animation:
        """Show an event (for a timeline made with `reveal=True`)."""
        return fade_in(self.event(name), shift=(0.0, 0.15), duration=kw.get("duration"), ease=kw.get("ease"), delay=kw.get("delay", 0.0))

    def zoom_to(self, *, range: tuple[float, float] | None = None, x: Sequence[float] | None = None, y: Sequence[float] | None = None, **kw: Unpack[AnimationTiming]) -> Animation:  # pyright: ignore[reportIncompatibleMethodOverride] - `range=` names the time span
        """Pan and zoom to the time span `range=(start, end)`."""
        return super().zoom_to(x=range if range is not None else x, y=y, **kw)
