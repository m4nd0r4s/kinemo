"""Device frames that hold content: `k.BrowserWindow`, `k.Phone` and `k.Laptop`. The content
sits in the screen, scaled down to fit when it is larger, so a screen can be shown in context."""

from __future__ import annotations

from typing import TYPE_CHECKING, Unpack

from ..values.color import Color
from .groups import Group
from .node import Node
from .shapes import Circle, Polygon, Rect, RoundedRect
from .terminal import DOT_COLORS
from .text import Text

if TYPE_CHECKING:
    from .keywords import TransformKeywords


def _light() -> bool:
    from .._runtime.context import current_scene

    bg = current_scene().theme.bg
    return (bg.r + bg.g + bg.b) / 3 > 0.5


def _palette() -> tuple[Color, Color, Color]:
    """(frame fill, screen fill, edge) for the scene's theme."""
    if _light():
        return Color.hex("#D9DCE1"), Color.hex("#FFFFFF"), Color.hex("#9AA0A8")
    return Color.hex("#2A2D34"), Color.hex("#0D0E12"), Color.hex("#4A4F59")


def _quiet_text() -> Color:
    """Secondary text on a screen, still readable."""
    return Color.hex("#4B5260") if _light() else Color.hex("#A3A9B3")


def _fit(content: Node | None, width: float, height: float, y: float) -> Node:
    """`content` centered in a `width` × `height` screen at `y`, scaled down to fit."""
    if content is None:
        return Group(y=y)
    w, h = float(content.width.now), float(content.height.now)
    scale = min(1.0, width / w if w > 0 else 1.0, height / h if h > 0 else 1.0)
    holder = Group(content, y=y, scale=scale)
    return holder


def _named(group: Group, part: Node | None, name: str) -> None:
    object.__setattr__(group, name, part)
    if part is not None:
        object.__setattr__(part, "_part", name)


class BrowserWindow(Group):
    """`k.BrowserWindow(content, url="kinemo.dev/docs", w=8, h=5)`: a window with the three
    dots, an address bar and the content in its page. Parts: `window.frame`, `window.address`,
    `window.url`, `window.page`, `window.content`."""

    if TYPE_CHECKING:
        frame: RoundedRect
        address: RoundedRect
        url: Text
        page: Rect
        content: Node

    def __init__(self, content: Node | None = None, *, url: str = "example.com", w: float = 8.0, h: float = 5.0, **props: Unpack[TransformKeywords]) -> None:
        frame_fill, screen, edge = _palette()
        bar = 0.55
        frame = RoundedRect(w=w, h=h, radius=0.18, fill=frame_fill, fill_opacity=1.0, stroke=edge, stroke_width=1.5)
        page_h = h - bar - 0.08
        page = Rect(w=w - 0.16, h=page_h, y=-bar / 2, fill=screen, fill_opacity=1.0, stroke_width=0.0)
        bar_y = h / 2 - bar / 2
        dots = [Circle(r=0.08, fill=Color.hex(color), fill_opacity=1.0, stroke_width=0.0, x=-w / 2 + 0.3 + 0.27 * i, y=bar_y) for i, color in enumerate(DOT_COLORS)]
        address = RoundedRect(w=w * 0.55, h=bar * 0.6, radius=bar * 0.3, fill=screen, fill_opacity=1.0, stroke_width=0.0, y=bar_y)
        label = Text(url, size=0.2, fill=_quiet_text(), y=bar_y)
        inner = _fit(content, w - 0.6, page_h - 0.4, -bar / 2)
        for part, name in ((frame, "frame"), (page, "page"), (address, "address"), (label, "url"), (inner, "content")):
            _named(self, part, name)
        super().__init__(frame, page, *dots, address, label, inner, **props)


class Phone(Group):
    """`k.Phone(content, w=2.4, h=5)`: a phone body with its screen, a camera pill and a home
    bar; the content fills the screen. Parts: `phone.body`, `phone.screen`, `phone.content`."""

    if TYPE_CHECKING:
        body: RoundedRect
        screen: RoundedRect
        content: Node

    def __init__(self, content: Node | None = None, *, w: float = 2.4, h: float = 5.0, **props: Unpack[TransformKeywords]) -> None:
        frame_fill, screen_fill, edge = _palette()
        body = RoundedRect(w=w, h=h, radius=w * 0.16, fill=frame_fill, fill_opacity=1.0, stroke=edge, stroke_width=2.0)
        bezel = w * 0.06
        screen = RoundedRect(w=w - 2 * bezel, h=h - 2 * bezel, radius=w * 0.12, fill=screen_fill, fill_opacity=1.0, stroke_width=0.0)
        camera = RoundedRect(w=w * 0.28, h=w * 0.07, radius=w * 0.035, fill=frame_fill, fill_opacity=1.0, stroke_width=0.0, y=h / 2 - bezel - w * 0.08)
        home = RoundedRect(w=w * 0.32, h=w * 0.025, radius=w * 0.0125, fill=edge, fill_opacity=1.0, stroke_width=0.0, y=-h / 2 + bezel + w * 0.06)
        inner = _fit(content, w - 2 * bezel - 0.2, h - 2 * bezel - w * 0.4, 0.0)
        for part, name in ((body, "body"), (screen, "screen"), (inner, "content")):
            _named(self, part, name)
        super().__init__(body, screen, inner, camera, home, **props)


class Laptop(Group):
    """`k.Laptop(content, w=7)`: a laptop screen in its bezel above a keyboard base; the content
    fills the screen. Parts: `laptop.lid`, `laptop.screen`, `laptop.base`, `laptop.content`."""

    if TYPE_CHECKING:
        lid: RoundedRect
        screen: Rect
        base: Polygon
        content: Node

    def __init__(self, content: Node | None = None, *, w: float = 7.0, **props: Unpack[TransformKeywords]) -> None:
        frame_fill, screen_fill, edge = _palette()
        h = w * 0.62
        bezel = w * 0.03
        lid = RoundedRect(w=w, h=h, radius=w * 0.025, fill=frame_fill, fill_opacity=1.0, stroke=edge, stroke_width=1.5, y=h * 0.06)
        screen = Rect(w=w - 2 * bezel, h=h - 2 * bezel, fill=screen_fill, fill_opacity=1.0, stroke_width=0.0, y=h * 0.06)
        # A trapezoid under the lid (a polygon is centered on its position: place it there).
        thickness = w * 0.05
        base = Polygon([(-w * 0.58, -thickness / 2), (w * 0.58, -thickness / 2), (w * 0.5, thickness / 2), (-w * 0.5, thickness / 2)], fill=frame_fill, fill_opacity=1.0, stroke=edge, stroke_width=1.5, y=-h / 2 + h * 0.06 - thickness / 2)
        inner = _fit(content, w - 2 * bezel - 0.3, h - 2 * bezel - 0.3, h * 0.06)
        for part, name in ((lid, "lid"), (screen, "screen"), (base, "base"), (inner, "content")):
            _named(self, part, name)
        super().__init__(lid, screen, base, inner, **props)
