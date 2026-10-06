"""Cards for a series: `k.TitleCard` (an episode's opening), `k.EndCard` (what comes next) and
`k.LowerThird` (a name over the bottom-left corner). Themed, with named parts, and with an
entrance of their own for `k.draw(card)`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Unpack

from ..anim.animation import Animation, par, seq
from ..anim.verbs import draw, fade_in, grow, write
from ..values.aliases import ColorLike
from ..values.color import Color
from .groups import Group
from .keywords import TransformKeywords
from .node import Node
from .shapes import Line, Rect
from .text import Text

#: `k.LowerThird(side=)`.
LowerThirdSide = Literal["left", "right"]


def _accent(color: ColorLike | None) -> ColorLike:
    from .._runtime.context import current_scene

    return color if color is not None else current_scene().theme.accent


def _soft() -> ColorLike:
    """Dimmer than the main text, still readable: 70% of the way from the background to it."""
    from .._runtime.context import current_scene

    theme = current_scene().theme
    return Color(*(b + (f - b) * 0.7 for f, b in zip((theme.fg.r, theme.fg.g, theme.fg.b), (theme.bg.r, theme.bg.g, theme.bg.b))))


def _named(group: Group, part: Node | None, name: str) -> None:
    object.__setattr__(group, name, part)
    if part is not None:
        object.__setattr__(part, "_part", name)


class TitleCard(Group):
    """`k.TitleCard("How a Computer Adds", kicker="EPISODE 2", subtitle="How computers do math")`:
    the title, a kicker above it, an accent rule under it and a subtitle. `k.draw(card)` fades
    the kicker in, writes the title, draws the rule, then shows the subtitle. Parts:
    `card.kicker`, `card.title`, `card.rule`, `card.subtitle`."""

    if TYPE_CHECKING:
        kicker: Text | None
        title: Text
        rule: Line
        subtitle: Text | None

    def __init__(
        self,
        title: str,
        *,
        kicker: str | None = None,
        subtitle: str | None = None,
        accent: ColorLike | None = None,
        size: float = 0.9,
        **props: Unpack[TransformKeywords],
    ) -> None:
        color = _accent(accent)
        heading = Text(title, size=size)
        half = heading.width.now / 2
        rule = Line(start=(-half, -size * 0.75), end=(half, -size * 0.75), stroke=color, stroke_width=4.0)
        parts: list[Node] = [heading, rule]
        top: Text | None = None
        under: Text | None = None
        if kicker:
            top = Text(kicker, size=size * 0.35, fill=color, y=size * 0.85)
            parts.insert(0, top)
        if subtitle:
            under = Text(subtitle, size=size * 0.42, fill=_soft(), y=-size * 1.35)
            parts.append(under)
        for part, name in ((top, "kicker"), (heading, "title"), (rule, "rule"), (under, "subtitle")):
            _named(self, part, name)
        super().__init__(*parts, **props)

    def enter(self) -> Animation:
        steps: list[Animation] = []
        opening = [write(self.title)] + ([fade_in(self.kicker, shift=(0, -0.2))] if self.kicker is not None else [])
        steps.append(par(*opening))
        steps.append(draw(self.rule))
        if self.subtitle is not None:
            steps.append(fade_in(self.subtitle, shift=(0, 0.15)))
        return seq(*steps)


class EndCard(Group):
    """`k.EndCard("Floating Point, Unmasked", heading="Next", brand="Until It Clicks",
    series="How computers do math", invite="Subscribe for the next one")`: what comes next, with
    the channel and series names. `k.draw(card)` writes the heading and the next title, then
    fades the rest in. Parts: `card.heading`, `card.next`, `card.brand`, `card.series`,
    `card.invite`."""

    if TYPE_CHECKING:
        heading: Text
        next: Text | None
        brand: Text | None
        series: Text | None
        invite: Text | None

    def __init__(
        self,
        next_title: str | None = None,
        *,
        heading: str = "Next",
        brand: str | None = None,
        series: str | None = None,
        invite: str | None = None,
        accent: ColorLike | None = None,
        size: float = 0.7,
        **props: Unpack[TransformKeywords],
    ) -> None:
        color = _accent(accent)
        label = Text(heading, size=size * 0.45, fill=color, y=size * 1.1)
        upcoming = Text(next_title, size=size) if next_title else None
        name = Text(brand, size=size * 0.5, y=-size * 1.4) if brand else None
        line = Text(series, size=size * 0.36, fill=_soft(), y=-size * 2.05) if series else None
        call = Text(invite, size=size * 0.36, fill=color, y=-size * 2.75) if invite else None
        for part, attr in ((label, "heading"), (upcoming, "next"), (name, "brand"), (line, "series"), (call, "invite")):
            _named(self, part, attr)
        super().__init__(*[p for p in (label, upcoming, name, line, call) if p is not None], **props)

    def enter(self) -> Animation:
        first = [write(self.heading)] + ([write(self.next)] if self.next is not None else [])
        rest = [p for p in (self.brand, self.series, self.invite) if p is not None]
        return seq(par(*first), fade_in(*rest, shift=(0, 0.15))) if rest else par(*first)


class LowerThird(Group):
    """`k.LowerThird("Ada Lovelace", role="Mathematician")`: a name and a role beside an accent
    bar, for the bottom-left corner (`side="right"` for the other one; place it as usual).
    `k.draw(card)` grows the bar, then slides the texts in. Parts: `card.bar`, `card.title`,
    `card.role`."""

    if TYPE_CHECKING:
        bar: Rect
        title: Text
        role: Text | None

    def __init__(
        self,
        title: str,
        role: str | None = None,
        *,
        side: LowerThirdSide = "left",
        accent: ColorLike | None = None,
        size: float = 0.42,
        **props: Unpack[TransformKeywords],
    ) -> None:
        color = _accent(accent)
        sign = 1.0 if side == "left" else -1.0
        height = size * (2.3 if role else 1.3)
        bar = Rect(w=0.08, h=height, fill=color, fill_opacity=1.0, stroke_width=0.0)
        heading = Text(title, size=size)
        lines: list[Node] = [heading]
        subtitle: Text | None = None
        if role:
            subtitle = Text(role, size=size * 0.62, fill=_soft())
            lines.append(subtitle)
        # Texts aligned on the edge next to the bar.
        gap = size * 0.45
        for text, y in zip(lines, (size * 0.45, -size * 0.6) if role else (0.0,)):
            text.set(x=sign * (gap + text.width.now / 2), y=y)
        for part, attr in ((bar, "bar"), (heading, "title"), (subtitle, "role")):
            _named(self, part, attr)
        super().__init__(bar, *lines, **props)

    def enter(self) -> Animation:
        shift = (-0.3 if self.bar.x.now <= self.title.x.now else 0.3, 0.0)
        texts = [p for p in (self.title, self.role) if p is not None]
        return seq(grow(self.bar, from_="bottom"), fade_in(*texts, shift=shift))
