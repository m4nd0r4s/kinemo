"""`k.Points`: thousands of dots in one object, with per-point radius and color."""

from __future__ import annotations

from typing import TYPE_CHECKING, Unpack

from ..props import PropSpec, accent
from .per_point import MassNode, PerPointColor, PerPointFloat, PointsInput, per_point_value
from .xy_input import to_xy

if TYPE_CHECKING:
    from ...data.arrow import FloatColumn
    from ...values.color import Color
    from ...values.vec import Vec
    from ..keywords import UnplacedKeywords
    from ..props import PropAccessor


class Points(MassNode):
    """Dots at `xy`, drawn natively in batches (10k dots render in a few ms).

        pts = k.Points(xy, radius=0.02, color=lambda t, p: k.mix(k.BLUE, k.RED, p.x))

    `xy`: `(n, 2)` numpy array, list of `(x, y)`, a pair of columns, or `x=`/`y=`
    columns (Arrow, polars, pandas). `radius` and `color` are a value, a signal, one
    value per point, a function of the symbolic point `p` (`p.x`, `p.y`, `p.index`,
    `p.count`, `p.t`), or `k.python(fn, vectorized=True)`. `k.draw` reveals the dots in
    index order.
    """

    kind = "points"
    PROPS = {
        "xy": PropSpec("points", [], "pointwise"),
        "radius": PropSpec("float", 0.02),
        "color": PropSpec("color", accent),
    }

    if TYPE_CHECKING:
        xy: PropAccessor[list[Vec]]
        radius: PropAccessor[float]
        color: PropAccessor[Color]
        #: Number of points.
        count: int

    def __init__(self, xy: PointsInput | None = None, radius: PerPointFloat = 0.02, color: PerPointColor | None = None, *, x: FloatColumn | None = None, y: FloatColumn | None = None, **props: Unpack[UnplacedKeywords]) -> None:
        xs, ys = to_xy(xy, x, y)
        object.__setattr__(self, "count", len(xs))
        super().__init__(
            xy=list(zip(xs, ys)),
            radius=per_point_value(radius, "float", xs, ys),
            color=per_point_value(color, "color", xs, ys),
            **props,
        )

    def __len__(self) -> int:
        return self.count
