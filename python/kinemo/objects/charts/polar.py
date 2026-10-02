"""`k.PolarAxes`: rings and spokes in polar coordinates, with polar plots."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Callable, Unpack

from ...reactive.expr import Expr, Op, lift
from ...reactive.native import cos, sin, vec
from ..groups import Group
from ..node import Node
from ..props import PropSpec
from ..shapes import Circle, Line, Path
from ..text import Text
from .sampling import ticks

if TYPE_CHECKING:
    from ...values.aliases import ColorLike, FloatVal
    from ...values.vec import Vec
    from ..keywords import PlotStyleKeywords, UnplacedKeywords
    from ..props import PropAccessor

LABEL_SIZE = 0.22


class PolarAxes(Group[Node]):
    """`k.PolarAxes(r=(0, 2, 0.5), radius=3, spokes=12)`. `r_max` and `radius` are signals,
    so rings, spokes and plots follow when they animate."""

    PROPS = {"r_max": PropSpec("float", 1.0), "radius": PropSpec("float", 3.0)}

    if TYPE_CHECKING:
        r_max: PropAccessor[float]
        radius: PropAccessor[float]
        _polar_opts: tuple[float, float | None, int, bool]

    def __init__(self, r: tuple[float, ...] = (0, 1), *, radius: float = 3.0, spokes: int = 12, labels: bool = True, **props: Unpack[UnplacedKeywords]) -> None:
        r_max = float(r[1])
        step = float(r[2]) if len(r) > 2 else None
        object.__setattr__(self, "_polar_opts", (r_max, step, int(spokes), labels))
        options: dict[str, Any] = dict(props)
        super().__init__(r_max=r_max, radius=radius, **options)

    # ---- mapping -----------------------------------------------------------------
    def local_point(self, r: FloatVal, theta: FloatVal) -> Expr[Vec]:
        """Point at radius `r` (data units) and angle `theta` (radians, from +x), in the
        axes' own coordinates."""
        scale = self.radius / self.r_max
        rr = lift(r) * scale
        return vec(rr * cos(lift(theta)), rr * sin(lift(theta)))

    def point(self, r: FloatVal, theta: FloatVal) -> Expr[Vec]:
        """World position of `(r, theta)`."""
        return Op("to_world", {"obj": self._id, "p": self.local_point(r, theta)}, kind="vec2")

    # ---- construction ----------------------------------------------------------------
    def _parts(self) -> list[Node]:
        r_max, step, spokes, labels = self._polar_opts
        muted = self._scene.theme.muted
        scale = self.radius / self.r_max
        parts: list[Node] = []
        for value in ticks(0.0, r_max, step):
            if value <= 0:
                continue
            parts.append(Circle(r=scale * value, stroke=muted, stroke_width=1.5, opacity=0.6))
            if labels:
                parts.append(Text(f"{value:g}", size=LABEL_SIZE, x=scale * value + 0.08, y=-0.18))
        for i in range(spokes):
            angle = 2 * math.pi * i / spokes
            end = vec(self.radius * math.cos(angle), self.radius * math.sin(angle))
            parts.append(Line(start=(0.0, 0.0), end=end, stroke=muted, stroke_width=1.5, opacity=0.6))
        return parts

    def plot(
        self,
        fn: Callable[[float], float],
        *,
        theta: tuple[float, float] = (0.0, 2 * math.pi),
        samples: int = 360,
        color: ColorLike | None = None,
        enter_with_axes: bool = True,
        **style: Unpack[PlotStyleKeywords],
    ) -> Path:
        """Curve `r = fn(theta)` (sampled at build, in the axes' coordinates).
        `enter_with_axes=False` keeps it hidden until a verb brings it in."""
        t0, t1 = theta
        r_max = self.r_max.now
        scale = self.radius.now / r_max
        pts = []
        for i in range(samples + 1):
            a = t0 + (t1 - t0) * i / samples
            rr = max(0.0, min(float(fn(a)), r_max)) * scale
            pts.append((rr * math.cos(a), rr * math.sin(a)))
        options: dict[str, Any] = {"stroke": color if color is not None else self._scene.theme.accent, "stroke_width": 4.0, **style}
        curve = Path(pts, **options)
        self._add_child(curve, enter_with_axes)
        from .axes import _name_from_call

        _name_from_call(curve, "plot")
        return curve
