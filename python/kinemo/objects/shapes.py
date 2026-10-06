"""Basic shapes. Closed shapes are centered on their position."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, ClassVar, Sequence, Unpack, cast

from .node import Node
from .props import STYLE, PropSpec

if TYPE_CHECKING:
    from ..values.aliases import FloatVal, VecLike, VecVal
    from ..values.color import Color
    from ..values.vec import Vec
    from .keywords import ArrowKeywords, RectKeywords, StyleKeywords, UnplacedStyleKeywords, UnscaledStyleKeywords
    from .props import PropAccessor


def _theme_fg(t: Any) -> Any:
    return t.fg


class Shape(Node):
    """A leaf with fill and stroke."""

    PROPS: ClassVar[dict[str, PropSpec]] = dict(STYLE)

    if TYPE_CHECKING:
        fill: PropAccessor[Color]
        fill_opacity: PropAccessor[float]
        stroke: PropAccessor[Color]
        stroke_width: PropAccessor[float]
        dash: PropAccessor[list[float]]
        glow: PropAccessor[float]
        glow_color: PropAccessor[Color]
        #: The stroke (`.to(color=...)` sets stroke and fill).
        color: PropAccessor[Color]


class Circle(Shape):
    kind = "circle"
    PROPS = {"r": PropSpec("float", 1.0)}

    if TYPE_CHECKING:
        r: PropAccessor[float]

    def __init__(self, r: FloatVal = 1.0, **props: Unpack[StyleKeywords]) -> None:
        super().__init__(r=r, **props)


class Dot(Shape):
    kind = "dot"
    PROPS = {
        "r": PropSpec("float", 0.08),
        "fill_opacity": PropSpec("float", 1.0),
        "stroke_width": PropSpec("float", 0.0),
    }

    if TYPE_CHECKING:
        r: PropAccessor[float]

    def __init__(self, r: FloatVal = 0.08, **props: Unpack[StyleKeywords]) -> None:
        super().__init__(r=r, **props)


class Ellipse(Shape):
    kind = "ellipse"
    PROPS = {"w": PropSpec("float", 2.0), "h": PropSpec("float", 1.0)}

    if TYPE_CHECKING:
        w: PropAccessor[float]
        h: PropAccessor[float]

    def __init__(self, w: FloatVal = 2.0, h: FloatVal = 1.0, **props: Unpack[StyleKeywords]) -> None:
        super().__init__(w=w, h=h, **props)


class Rect(Shape):
    kind = "rect"
    PROPS = {"w": PropSpec("float", 2.0), "h": PropSpec("float", 1.0), "radius": PropSpec("float", 0.0)}

    if TYPE_CHECKING:
        w: PropAccessor[float]
        h: PropAccessor[float]
        radius: PropAccessor[float]

    def __init__(self, w: FloatVal = 2.0, h: FloatVal = 1.0, **props: Unpack[RectKeywords]) -> None:
        super().__init__(w=w, h=h, **props)


class RoundedRect(Rect):
    def __init__(self, w: FloatVal = 2.0, h: FloatVal = 1.0, radius: FloatVal = 0.15, **props: Unpack[StyleKeywords]) -> None:
        super().__init__(w=w, h=h, radius=radius, **props)


class Square(Rect):
    def __init__(self, side: FloatVal = 1.0, **props: Unpack[RectKeywords]) -> None:
        super().__init__(w=side, h=side, **props)

    @staticmethod
    def on(side: Side, outward: bool = True, **props: Unpack[UnplacedStyleKeywords]) -> Polygon:
        """The square built on a polygon edge, outside (or inside) the polygon."""
        (ax, ay), (bx, by) = side.start, side.end
        dx, dy = bx - ax, by - ay
        nx, ny = -dy, dx
        mx, my = (ax + bx) / 2, (ay + by) / 2
        toward_interior = (side.interior[0] - mx) * nx + (side.interior[1] - my) * ny > 0
        if toward_interior == outward:
            nx, ny = -nx, -ny
        corners = [(ax, ay), (bx, by), (bx + nx, by + ny), (ax + nx, ay + ny)]
        cx = sum(p[0] for p in corners) / 4
        cy = sum(p[1] for p in corners) / 4
        from .node import name_from_factory

        square = Polygon(*corners, x=cx, y=cy, **props)
        name_from_factory(square, "on")
        return square


def _points(pts: Sequence[VecLike]) -> list[tuple[float, float]]:
    return [(float(x), float(y)) for x, y in pts]


class Polygon(Shape):
    kind = "polygon"
    PROPS = {"points": PropSpec("points", [], "pointwise")}

    if TYPE_CHECKING:
        points: PropAccessor[list[Vec]]

    def __init__(self, *points: VecLike | list[VecLike], **props: Unpack[StyleKeywords]) -> None:
        if len(points) == 1 and isinstance(points[0], list):
            points = tuple(points[0])
        # One list argument holds the points; otherwise each argument is a point.
        super().__init__(points=_centered(_points(cast("Sequence[VecLike]", points))), **props)

    @classmethod
    def regular(cls, n: FloatVal, r: FloatVal = 1.0, **props: Unpack[StyleKeywords]) -> "RegularPolygon":
        """Regular polygon with `n` sides (a signal works: the shape follows it) and
        circumradius `r`, a vertex on top."""
        from .node import name_from_factory

        shape = RegularPolygon(n, r, **props)
        name_from_factory(shape, "regular")
        return shape

    @property
    def sides(self) -> list[Side]:
        """Edges in world coordinates, at the cursor."""
        return _sides(self)

    @property
    def vertices(self) -> list[tuple[float, float]]:
        """Vertices in the polygon's own coordinates, at the cursor."""
        return [(p[0], p[1]) for p in self.points.now]


class RegularPolygon(Shape):
    kind = "regular_polygon"
    PROPS = {"sides": PropSpec("float", 5.0, "round"), "r": PropSpec("float", 1.0)}

    if TYPE_CHECKING:
        sides: PropAccessor[float]
        r: PropAccessor[float]

    def __init__(self, sides: FloatVal = 5, r: FloatVal = 1.0, **props: Unpack[StyleKeywords]) -> None:
        super().__init__(sides=sides, r=r, **props)


class Side:
    """An edge of a polygon in world coordinates (at the cursor when it was read)."""

    def __init__(self, start: tuple[float, float], end: tuple[float, float], interior: tuple[float, float]) -> None:
        self.start, self.end, self.interior = start, end, interior

    @property
    def length(self) -> float:
        return math.dist(self.start, self.end)

    def __repr__(self) -> str:
        return f"Side({self.start} → {self.end})"


def _sides(poly: "Polygon") -> list[Side]:
    import json

    s = poly._scene
    local = [(p[0], p[1]) for p in poly.points.now]
    world: list[tuple[float, float]] = []
    for x, y in local:
        expr = {"op": "to_world", "obj": poly._id, "p": {"op": "const", "v": {"Vec2": [x, y]}}}
        world.append(tuple(json.loads(s._b.eval_expr(json.dumps(expr), s.cursor))["Vec2"]))
    cx = sum(p[0] for p in world) / len(world)
    cy = sum(p[1] for p in world) / len(world)
    return [Side(world[i], world[(i + 1) % len(world)], (cx, cy)) for i in range(len(world))]


class Triangle(Polygon):
    def __init__(self, *points: VecLike | list[VecLike], **props: Unpack[StyleKeywords]) -> None:
        if not points:
            points = tuple((math.cos(math.pi / 2 + 2 * math.pi * i / 3), math.sin(math.pi / 2 + 2 * math.pi * i / 3)) for i in range(3))
        super().__init__(*points, **props)

    # On a triangle, `right` is this constructor rather than the layout-derived right edge
    # (the class attribute wins at runtime too); `tri.edge("right")` reads the edge.
    @classmethod
    def right(cls, a: float, b: float, scale: float = 1.0, **props: Unpack[UnscaledStyleKeywords]) -> "Triangle":  # pyright: ignore[reportIncompatibleVariableOverride]
        """Right triangle with legs `a` (horizontal) and `b` (vertical)."""
        return cls((0.0, 0.0), (a * scale, 0.0), (0.0, b * scale), **props)


def _centered(pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Points relative to their bounding-box center (so the shape is centered on x, y)."""
    if not pts:
        return pts
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    return [(x - cx, y - cy) for x, y in pts]


class Line(Shape):
    """A segment from `start` to `end` (local coordinates), or centered with `length=`."""

    kind = "line"
    PROPS = {"start": PropSpec("vec2", (-1.0, 0.0)), "end": PropSpec("vec2", (1.0, 0.0))}

    if TYPE_CHECKING:
        start: PropAccessor[Vec]
        end: PropAccessor[Vec]

    def __init__(self, start: VecVal | None = None, end: VecVal | None = None, *, length: float | None = None, **props: Unpack[StyleKeywords]) -> None:
        if length is not None:
            start, end = (-length / 2, 0.0), (length / 2, 0.0)
        super().__init__(start=(-1.0, 0.0) if start is None else start, end=(1.0, 0.0) if end is None else end, **props)


class Arrow(Shape):
    kind = "arrow"
    PROPS = {
        "start": PropSpec("vec2", (-1.0, 0.0)),
        "end": PropSpec("vec2", (1.0, 0.0)),
        "tip": PropSpec("float", 0.25),
        "fill_opacity": PropSpec("float", 1.0),
    }

    if TYPE_CHECKING:
        start: PropAccessor[Vec]
        end: PropAccessor[Vec]
        tip: PropAccessor[float]

    def __init__(self, start: VecVal | None = None, end: VecVal | None = None, **props: Unpack[ArrowKeywords]) -> None:
        super().__init__(start=(-1.0, 0.0) if start is None else start, end=(1.0, 0.0) if end is None else end, **props)


class Arc(Shape):
    kind = "arc"
    PROPS = {"r": PropSpec("float", 1.0), "start_angle": PropSpec("float", 0.0), "angle": PropSpec("float", 90.0)}

    if TYPE_CHECKING:
        r: PropAccessor[float]
        start_angle: PropAccessor[float]
        angle: PropAccessor[float]

    def __init__(self, r: FloatVal = 1.0, start_angle: FloatVal = 0.0, angle: FloatVal = 90.0, **props: Unpack[StyleKeywords]) -> None:
        super().__init__(r=r, start_angle=start_angle, angle=angle, **props)


class Sector(Shape):
    """`k.Sector(r=1, angle=90, start_angle=0, inner=0)`: a pie slice from the center, or a ring
    slice with `inner=` (its inner radius). Angles in degrees, counterclockwise from +x; all
    props animate."""

    kind = "sector"
    PROPS = {"r": PropSpec("float", 1.0), "inner": PropSpec("float", 0.0), "start_angle": PropSpec("float", 0.0), "angle": PropSpec("float", 90.0)}

    if TYPE_CHECKING:
        r: PropAccessor[float]
        inner: PropAccessor[float]
        start_angle: PropAccessor[float]
        angle: PropAccessor[float]

    def __init__(self, r: FloatVal = 1.0, angle: FloatVal = 90.0, start_angle: FloatVal = 0.0, *, inner: FloatVal = 0.0, **props: Unpack[StyleKeywords]) -> None:
        super().__init__(r=r, inner=inner, start_angle=start_angle, angle=angle, **props)


class Path(Shape):
    """An SVG path (`d="M 0 0 L 1 1"`) or a polyline through points."""

    kind = "path"
    PROPS = {"d": PropSpec("str", "", "step_end"), "closed": PropSpec("bool", False, "step_end")}

    if TYPE_CHECKING:
        d: PropAccessor[str]
        closed: PropAccessor[bool]

    def __init__(self, d: str | Sequence[VecLike] = "", *, closed: bool = False, **props: Unpack[StyleKeywords]) -> None:
        if not isinstance(d, str):
            pts = _points(d)
            d = " ".join(("M" if i == 0 else "L") + f" {x} {y}" for i, (x, y) in enumerate(pts))
            if closed:
                d += " Z"
        super().__init__(d=d, closed=closed, **props)
