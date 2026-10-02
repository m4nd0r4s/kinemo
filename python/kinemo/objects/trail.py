"""`k.trace(point, length=)`: the path a point took over the last seconds."""

from __future__ import annotations

from typing import TYPE_CHECKING, Unpack

from .props import PropSpec
from .shapes import Shape

if TYPE_CHECKING:
    from ..values.aliases import VecVal
    from ..values.vec import Vec
    from .keywords import StyleKeywords
    from .props import PropAccessor


class Trail(Shape):
    kind = "trail"
    PROPS = {"point": PropSpec("vec2", (0.0, 0.0)), "length": PropSpec("float", 2.0)}

    if TYPE_CHECKING:
        point: PropAccessor[Vec]
        length: PropAccessor[float]

    def __init__(self, point: VecVal, length: float = 2.0, **props: Unpack[StyleKeywords]) -> None:
        props.setdefault("stroke_width", 3.0)
        super().__init__(point=point, length=length, **props)


def trace(point: VecVal, length: float = 2.0, **style: Unpack[StyleKeywords]) -> Trail:
    """Last `length` seconds of a moving point (e.g. `dot.world.position`), as a stroke.
    Sampled from the timeline at render time, so the render stays pure."""
    return Trail(point, length, **style)
