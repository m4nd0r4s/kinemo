"""`k.Card`: a panel that holds content, with an optional title, caption and accent, for
side-by-side comparisons (`k.Row(card_a, card_b)`)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Unpack

from ..values.aliases import ColorLike
from ..values.color import Color
from .groups import Group
from .keywords import TransformKeywords
from .node import Node
from .shapes import Rect, RoundedRect
from .text import Text


class Card(Group):
    """`k.Card(content, title="Rocket", caption="Newton's third law", accent=k.ORANGE)`: a rounded
    panel around `content` (or `w=`, `h=` for a fixed size), the title in its top-left corner,
    the caption under it and a short accent bar beside the title. Parts: `card.box`,
    `card.content`, `card.title`, `card.caption`, `card.accent`."""

    if TYPE_CHECKING:
        box: RoundedRect
        #: The content (an empty group for a card made without one).
        content: Node
        title: Text | None
        caption: Text | None
        accent: Rect | None

    def __init__(
        self,
        content: Node | None = None,
        *,
        title: str | None = None,
        caption: str | None = None,
        accent: ColorLike | None = None,
        w: float | None = None,
        h: float | None = None,
        pad: float = 0.35,
        radius: float = 0.18,
        title_size: float = 0.32,
        caption_size: float = 0.28,
        **props: Unpack[TransformKeywords],
    ) -> None:
        from .._runtime.context import current_scene

        theme = current_scene().theme
        head = title_size * 1.6 if title else 0.0
        width = w if w is not None else (content.width.now if content is not None else 2.0) + 2 * pad
        height = h if h is not None else (content.height.now if content is not None else 1.0) + 2 * pad + head
        box = RoundedRect(w=width, h=height, radius=radius, fill=theme.fg, fill_opacity=0.05, stroke=theme.muted, stroke_width=1.5)
        parts: list[Node] = [box]
        heading: Text | None = None
        bar: Rect | None = None
        if title:
            heading = Text(title, size=title_size).place(inside=box, align="top-left", pad=pad)
            parts.append(heading)
        if accent is not None:
            bar = Rect(w=0.06, h=title_size * 1.1 if title else height - 2 * radius, fill=accent, fill_opacity=1.0, stroke_width=0.0)
            bar.place(inside=box, align="top-left", pad=(pad * 0.45) if title else 0.0)
            if heading is not None:
                bar.place(left_of=heading, gap=0.14)
            parts.append(bar)
        if content is not None:
            if title:
                content.place(inside=box, align="bottom", pad=pad)
            else:
                content.place(inside=box)
            parts.append(content)
        else:
            content = Group()
        note: Text | None = None
        if caption:
            # Dimmer than the title, still readable: 70% of the way from the background to the text.
            dim = Color(*(b + (f - b) * 0.7 for f, b in zip((theme.fg.r, theme.fg.g, theme.fg.b), (theme.bg.r, theme.bg.g, theme.bg.b))))
            note = Text(caption, size=caption_size, fill=dim).place(below=box, gap=0.2)
            parts.append(note)
        for name, part in (("box", box), ("content", content), ("title", heading), ("caption", note), ("accent", bar)):
            if part is not None:
                object.__setattr__(part, "_part", name)
            object.__setattr__(self, name, part)
        super().__init__(*parts, **props)
