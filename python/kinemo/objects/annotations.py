"""Annotation marks: `k.underline`, `k.box`, `k.encircle`, `k.strike` and `k.cross` draw on
top of any object or part of a text or formula (`eq["dx"]`), and follow it as it moves.

Each returns an ordinary object (bound to the target's box in world coordinates), so it
enters with a verb (`s.play(k.draw(k.underline(eq["dx"])))`) and leaves with another."""

from __future__ import annotations

from typing import TYPE_CHECKING, Unpack

from ..reactive.native import vec
from ..values.aliases import ColorLike
from ..values.color import RED, YELLOW
from .groups import Group
from .keywords import VisibilityKeywords
from .node import Node, name_from_factory
from .shapes import Ellipse, Line, RoundedRect

if TYPE_CHECKING:
    from ..values.aliases import FloatVal

#: Default stroke width of a mark (pixels at 1080p).
MARK_WIDTH = 4.0


def underline(target: Node, *, pad: float = 0.08, color: ColorLike = YELLOW, stroke_width: FloatVal = MARK_WIDTH, **props: Unpack[VisibilityKeywords]) -> Line:
    """A line under `target`, `pad` below its box; `k.draw` draws it left to right."""
    w = target.world
    mark = Line(start=vec(w.left, w.bottom - pad), end=vec(w.right, w.bottom - pad), stroke=color, stroke_width=stroke_width, **props)
    name_from_factory(mark, "underline")
    return mark


def box(target: Node, *, pad: float = 0.12, radius: float = 0.08, color: ColorLike = YELLOW, stroke_width: FloatVal = MARK_WIDTH, **props: Unpack[VisibilityKeywords]) -> RoundedRect:
    """A rounded box around `target`, `pad` away from its box."""
    w = target.world
    mark = RoundedRect(w=w.width + 2 * pad, h=w.height + 2 * pad, radius=radius, x=w.center.x, y=w.center.y, stroke=color, stroke_width=stroke_width, fill_opacity=0.0, **props)
    name_from_factory(mark, "box")
    return mark


def encircle(target: Node, *, pad: float = 0.18, color: ColorLike = YELLOW, stroke_width: FloatVal = MARK_WIDTH, **props: Unpack[VisibilityKeywords]) -> Ellipse:
    """An ellipse around `target` (its box, `pad` larger on each side, times √2 so the
    corners fit inside)."""
    w = target.world
    mark = Ellipse(w=(w.width + 2 * pad) * 1.414, h=(w.height + 2 * pad) * 1.414, x=w.center.x, y=w.center.y, stroke=color, stroke_width=stroke_width, fill_opacity=0.0, **props)
    name_from_factory(mark, "encircle")
    return mark


def strike(target: Node, *, overhang: float = 0.06, color: ColorLike = RED, stroke_width: FloatVal = MARK_WIDTH, **props: Unpack[VisibilityKeywords]) -> Line:
    """A line through the middle of `target` (struck out), `overhang` past each side."""
    w = target.world
    mark = Line(start=vec(w.left - overhang, w.center.y), end=vec(w.right + overhang, w.center.y), stroke=color, stroke_width=stroke_width, **props)
    name_from_factory(mark, "strike")
    return mark


def cross(target: Node, *, pad: float = 0.06, color: ColorLike = RED, stroke_width: FloatVal = MARK_WIDTH, **props: Unpack[VisibilityKeywords]) -> Group:
    """An X over `target`: two lines corner to corner, `pad` past its box."""
    w = target.world
    down = Line(start=vec(w.left - pad, w.top + pad), end=vec(w.right + pad, w.bottom - pad), stroke=color, stroke_width=stroke_width)
    up = Line(start=vec(w.left - pad, w.bottom - pad), end=vec(w.right + pad, w.top + pad), stroke=color, stroke_width=stroke_width)
    mark = Group(down, up, **props)
    name_from_factory(mark, "cross")
    return mark
