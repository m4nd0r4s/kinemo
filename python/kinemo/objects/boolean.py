"""Boolean shape operations: `k.union`, `k.intersect`, `k.subtract`.

The result is a new `k.Path` with the outline computed natively from both objects'
world outlines at the cursor (it does not follow later changes of the operands)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Unpack

from ..diagnostics import KinemoError
from .node import Node
from .shapes import Path

if TYPE_CHECKING:
    from .keywords import StyleKeywords


def _boolean(operation: str, a: Node, b: Node, given: Mapping[str, Any]) -> Path:
    if not isinstance(a, Node) or not isinstance(b, Node):
        raise KinemoError.make("K0105", f"k.{operation} takes two objects")
    s = a._scene
    d = s._b.boolean_path(operation, a._id, b._id, s.cursor)
    style: dict[str, Any] = dict(given)
    for prop in ("fill", "fill_opacity", "stroke", "stroke_width"):
        if prop in a._all_props and prop not in style and "color" not in style:
            style[prop] = a._sig(prop).now
    from .node import name_from_factory

    result = Path(d, closed=True, **style)
    name_from_factory(result, operation)
    return result


def union(a: Node, b: Node, **style: Unpack[StyleKeywords]) -> Path:
    """Shape covering `a` or `b` (style of `a` unless given)."""
    return _boolean("union", a, b, style)


def intersect(a: Node, b: Node, **style: Unpack[StyleKeywords]) -> Path:
    """Shape covering both `a` and `b`."""
    return _boolean("intersect", a, b, style)


def subtract(a: Node, b: Node, **style: Unpack[StyleKeywords]) -> Path:
    """`a` with `b` cut out."""
    return _boolean("subtract", a, b, style)
