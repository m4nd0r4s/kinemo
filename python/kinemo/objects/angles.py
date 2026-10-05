"""Angle markers: `k.Angle(a, vertex, b)` draws the arc between the rays vertex→a and
vertex→b, with an optional label or value; `k.RightAngle(a, vertex, b)` draws the square mark.

The points can be fixed or reactive (a dot's `world.center`, a signal-driven `k.vec`), so a
marker follows an angle as it opens and closes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, Unpack, cast

from ..reactive.native import atan2, cos, sin, sqrt, vec
from ..reactive.native import max as native_max
from ..values.aliases import ColorLike
from ..values.color import YELLOW
from .groups import Group
from .keywords import VisibilityKeywords
from .shapes import Arc, Line
from .text import Text

if TYPE_CHECKING:
    from ..values.aliases import VecVal

DEGREES = 180.0 / 3.141592653589793


def _xy(point: "VecVal") -> tuple[Any, Any]:
    """`(x, y)` of a point: numbers for a fixed one, expressions for a reactive one."""
    if isinstance(point, (tuple, list)):
        x, y = cast("tuple[float, float]", tuple(point))
        return float(x), float(y)
    return point.x, point.y  # type: ignore[union-attr]


class Angle(Group):
    """`k.Angle(a, vertex, b, r=0.5, label="θ")`: the arc of the angle from the ray vertex→a to
    the ray vertex→b (the smaller one), with `label=` beside it or `show_value=True` for its
    measure (`unit="deg"` or `"rad"`). Parts: `angle.arc` and `angle.label`."""

    if TYPE_CHECKING:
        arc: Arc
        label: Text | None

    def __init__(
        self,
        a: "VecVal",
        vertex: "VecVal",
        b: "VecVal",
        *,
        r: float = 0.5,
        label: str | None = None,
        show_value: bool = False,
        unit: Literal["deg", "rad"] = "deg",
        color: ColorLike = YELLOW,
        stroke_width: float = 3.0,
        label_size: float = 0.34,
        **props: Unpack[VisibilityKeywords],
    ) -> None:
        (ax, ay), (vx, vy), (bx, by) = _xy(a), _xy(vertex), _xy(b)
        first = atan2(ay - vy, ax - vx) * DEGREES
        second = atan2(by - vy, bx - vx) * DEGREES
        # The smaller angle, signed: from the first ray to the second.
        sweep = ((second - first + 540.0) % 360.0) - 180.0
        arc = Arc(r=r, start_angle=first, angle=sweep, x=vx, y=vy, stroke=color, stroke_width=stroke_width, fill_opacity=0.0)
        object.__setattr__(arc, "_part", "arc")
        parts: list[Any] = [arc]
        text: Text | None = None
        if label is not None or show_value:
            middle = (first + sweep / 2.0) / DEGREES
            gap = r + label_size * 0.4
            if show_value:
                size = native_max(sweep, -sweep)
                value = size if unit == "deg" else size / DEGREES
                suffix = "°" if unit == "deg" else " rad"
                prefix = f"{label} = " if label else ""
                text = Text(lambda: f"{prefix}{value():.{0 if unit == 'deg' else 2}f}{suffix}", size=label_size, fill=color)
            else:
                text = Text(label or "", size=label_size, fill=color)
            # Clear of the arc: half the label's extent along the bisector, past the radius.
            along = gap + native_max(cos(middle), -cos(middle)) * text.width / 2.0 + native_max(sin(middle), -sin(middle)) * text.height / 2.0
            text.set(x=vx + along * cos(middle), y=vy + along * sin(middle))
            object.__setattr__(text, "_part", "label")
            parts.append(text)
        object.__setattr__(self, "arc", arc)
        object.__setattr__(self, "label", text)
        super().__init__(*parts, **props)


class RightAngle(Group):
    """`k.RightAngle(a, vertex, b, size=0.3)`: the square mark of a right angle at `vertex`,
    along the rays toward `a` and `b`. Parts: `mark.lines`."""

    if TYPE_CHECKING:
        lines: list[Line]

    def __init__(
        self,
        a: "VecVal",
        vertex: "VecVal",
        b: "VecVal",
        *,
        size: float = 0.3,
        color: ColorLike = YELLOW,
        stroke_width: float = 3.0,
        **props: Unpack[VisibilityKeywords],
    ) -> None:
        (ax, ay), (vx, vy), (bx, by) = _xy(a), _xy(vertex), _xy(b)
        la = sqrt((ax - vx) ** 2 + (ay - vy) ** 2) + 1e-9
        lb = sqrt((bx - vx) ** 2 + (by - vy) ** 2) + 1e-9
        ux, uy = (ax - vx) / la * size, (ay - vy) / la * size
        wx, wy = (bx - vx) / lb * size, (by - vy) / lb * size
        corner = vec(vx + ux + wx, vy + uy + wy)
        first = Line(start=vec(vx + ux, vy + uy), end=corner, stroke=color, stroke_width=stroke_width)
        second = Line(start=corner, end=vec(vx + wx, vy + wy), stroke=color, stroke_width=stroke_width)
        for i, line in enumerate((first, second)):
            object.__setattr__(line, "_part", f".lines[{i}]")
        object.__setattr__(self, "lines", [first, second])
        super().__init__(first, second, **props)
