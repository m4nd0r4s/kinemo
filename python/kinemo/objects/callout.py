"""`k.Callout`: a speech bubble or a callout whose tail points at an object, and follows it.

The callout is anchored at the target's edge on the chosen side (a reactive point); its box,
text and tail are laid out around that point, so the whole callout moves with the target."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Unpack

from ..values.aliases import ColorLike
from .groups import Group
from .keywords import VisibilityKeywords
from .node import Node
from .shapes import Line, Polygon, RoundedRect
from .text import Text

if TYPE_CHECKING:
    from ..reactive.expr import Expr

Side = Literal["top", "bottom", "left", "right", "top-left", "top-right", "bottom-left", "bottom-right"]
#: Unit direction of each side, from the target toward the callout.
SIDES: dict[str, tuple[int, int]] = {
    "top": (0, 1), "bottom": (0, -1), "left": (-1, 0), "right": (1, 0),
    "top-left": (-1, 1), "top-right": (1, 1), "bottom-left": (-1, -1), "bottom-right": (1, -1),
}
#: Half the width of the tail where it meets the box.
TAIL_HALF = 0.14


class Callout(Group):
    """`k.Callout("Wait, what?", to=folio, side="top-right")`: a box with `text` (wrapped at
    `max_width=`) beside `to` (an object), with a tail pointing at it, `gap=` away; it follows
    the target as it moves. `style="bubble"` (filled, the default), `"box"` (outlined) or
    `"line"` (text with a leader line). Parts: `callout.box`, `callout.label`, `callout.tail`."""

    if TYPE_CHECKING:
        box: RoundedRect | None
        label: Text
        tail: Node

    def __init__(
        self,
        text: str,
        *,
        to: Node,
        side: Side = "top-right",
        style: Literal["bubble", "box", "line"] = "bubble",
        gap: float = 0.45,
        max_width: float = 4.0,
        size: float = 0.32,
        pad: float = 0.22,
        color: ColorLike | None = None,
        **props: Unpack[VisibilityKeywords],
    ) -> None:
        from .._runtime.context import current_scene

        theme = current_scene().theme
        sx, sy = SIDES[side]
        bubble = style == "bubble"
        ink: ColorLike = theme.bg if bubble else theme.fg
        label = Text(text, size=size, width=max_width, fill=ink)
        if label.width.now > max_width:
            label.set(width=max_width)
        bw, bh = label.width.now + 2 * pad, label.height.now + 2 * pad
        # The box's center, relative to the tail's tip (the group's origin, on the target).
        cx, cy = sx * (gap + bw / 2), sy * (gap + bh / 2)
        label.set(x=cx, y=cy)
        stroke: ColorLike = color if color is not None else theme.fg
        parts: list[Node] = []
        box: RoundedRect | None = None
        if style != "line":
            box = RoundedRect(
                w=bw, h=bh, radius=min(0.25, bh / 3), x=cx, y=cy,
                fill=stroke if bubble else theme.bg, fill_opacity=1.0 if bubble else 0.0,
                stroke=stroke, stroke_width=0.0 if bubble else 2.5,
            )
            parts.append(box)
        tail: Node
        if style == "bubble":
            tail = Polygon(*_tail_base(sx, sy, cx, cy, bw, bh), (0.0, 0.0), fill=stroke, fill_opacity=1.0, stroke_width=0.0)
        else:
            # A leader from the box's edge (or the text's) to the target.
            ex, ey = _edge_toward_origin(sx, sy, cx, cy, bw, bh)
            tail = Line(start=(ex, ey), end=(0.0, 0.0), stroke=stroke, stroke_width=2.5)
        parts += [tail, label]
        for name, part in (("box", box), ("label", label), ("tail", tail)):
            if part is not None:
                object.__setattr__(part, "_part", name)
            object.__setattr__(self, name, part)
        x, y = _anchor(to, sx, sy)
        super().__init__(*parts, x=x, y=y, **props)


def _anchor(target: Node, sx: int, sy: int) -> "tuple[Expr[float], Expr[float]]":
    """The point of the target's box on that side (world coordinates, reactive)."""
    w = target.world
    x = w.right if sx > 0 else w.left if sx < 0 else w.center.x
    y = w.top if sy > 0 else w.bottom if sy < 0 else w.center.y
    return x, y


def _tail_base(sx: int, sy: int, cx: float, cy: float, bw: float, bh: float) -> list[tuple[float, float]]:
    """The two points where the tail meets the box: on its edge facing the target, near the
    corner on that side (centered for top, bottom, left and right)."""
    if sy != 0:
        y = cy - sy * bh / 2
        x = cx - sx * (bw / 2 - 0.4) if sx != 0 else cx
        return [(x - TAIL_HALF, y), (x + TAIL_HALF, y)]
    x = cx - sx * bw / 2
    return [(x, cy - TAIL_HALF), (x, cy + TAIL_HALF)]


def _edge_toward_origin(sx: int, sy: int, cx: float, cy: float, bw: float, bh: float) -> tuple[float, float]:
    base = _tail_base(sx, sy, cx, cy, bw, bh)
    return (base[0][0] + base[1][0]) / 2, (base[0][1] + base[1][1]) / 2

