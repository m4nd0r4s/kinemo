"""`k.Epicycles`: the Fourier series of a closed path as a chain of rotating circles whose tip
draws the path."""

from __future__ import annotations

import cmath
import math
from typing import TYPE_CHECKING, Any, Mapping, Sequence, Unpack

from ..anim.animation import Animation, par
from ..anim.verbs import draw, fade_in
from ..diagnostics import KinemoError
from ..reactive.native import cos, sin, vec
from .groups import Group
from .node import Node
from .props import PropSpec
from .shapes import Circle, Dot, Line, Path

if TYPE_CHECKING:
    from ..anim.ease import EaseLike
    from ..values.aliases import ColorLike
    from .keywords import UnplacedKeywords
    from .props import PropAccessor

#: Points the path is resampled to before the transform (by arc length).
SAMPLES = 256
#: Points of the drawn curve.
CURVE_POINTS = 400
#: Share of draw progress that traces an outline (the rest fills; see `k.draw`).
OUTLINE_SHARE = 0.7


def _as_complex(points: Sequence[Any]) -> list[complex]:
    return [p if isinstance(p, complex) else complex(float(p[0]), float(p[1])) for p in points]


def _resample(points: list[complex], count: int) -> list[complex]:
    """`count` points evenly spaced along the closed polyline through `points`."""
    ring = points + [points[0]]
    lengths = [abs(b - a) for a, b in zip(ring, ring[1:])]
    total = sum(lengths)
    if total <= 0:
        raise KinemoError.make("K0105", "k.Epicycles needs a path that goes somewhere")
    out: list[complex] = []
    segment, walked = 0, 0.0
    for i in range(count):
        target = total * i / count
        while walked + lengths[segment] < target:
            walked += lengths[segment]
            segment += 1
        along = (target - walked) / lengths[segment] if lengths[segment] > 0 else 0.0
        out.append(ring[segment] + (ring[segment + 1] - ring[segment]) * along)
    return out


def fourier_coefficients(points: Sequence[Any], terms: int) -> dict[int, complex]:
    """The `terms` largest Fourier coefficients (frequency → complex amplitude) of the closed
    path through `points`, plus the constant term (the center)."""
    samples = _resample(_as_complex(points), SAMPLES)
    count = len(samples)
    coefficients: dict[int, complex] = {}
    for k in range(-count // 2, count // 2):
        coefficients[k] = sum(z * cmath.exp(-2j * math.pi * k * j / count) for j, z in enumerate(samples)) / count
    center = coefficients.pop(0)
    kept = sorted(coefficients.items(), key=lambda item: -abs(item[1]))[:terms]
    return {0: center, **dict(kept)}


class Epicycles(Group):
    """`k.Epicycles(points, n=50)`: the Fourier series of the closed path through `points`
    (tuples or complex numbers), drawn as a chain of `n` rotating circles, largest first, whose
    tip traces the path; or `coefficients={1: 1+0j, -1: 0.5j, ...}` directly. `t` is the
    progress in turns: `epi.run(turns=1)` animates it, the curve appearing behind the tip.
    Parts: `epi.circles`, `epi.arms`, `epi.curve`, `epi.tip`."""

    PROPS = {"t": PropSpec("float", 0.0)}

    if TYPE_CHECKING:
        t: PropAccessor[float]
        circles: list[Circle]
        arms: list[Line]
        curve: Path
        tip: Dot
        coefficients: dict[int, complex]
        _epicycle_opts: tuple[Any, Any]

    def __init__(
        self,
        points: Sequence[Any] | None = None,
        n: int = 50,
        *,
        coefficients: Mapping[int, complex] | None = None,
        color: ColorLike | None = None,
        circle_color: ColorLike | None = None,
        **props: Unpack[UnplacedKeywords],
    ) -> None:
        if (points is None) == (coefficients is None):
            raise KinemoError.make("K0105", "k.Epicycles takes points or coefficients=")
        terms = dict(coefficients) if coefficients is not None else fourier_coefficients(points or [], max(1, n))
        terms.setdefault(0, 0j)
        center = terms.pop(0)
        ordered = {0: center, **dict(sorted(terms.items(), key=lambda item: -abs(item[1])))}
        object.__setattr__(self, "coefficients", ordered)
        object.__setattr__(self, "_epicycle_opts", (color, circle_color))
        super().__init__(**props)

    def _position(self, at: float) -> complex:
        return sum(c * cmath.exp(2j * math.pi * k * at) for k, c in self.coefficients.items())

    def _parts(self) -> list[Node]:
        color, circle_color = self._epicycle_opts
        theme = self._scene.theme
        stroke = color if color is not None else theme.accent
        faint = circle_color if circle_color is not None else theme.muted
        turn = self.t * (2 * math.pi)
        center = self.coefficients[0]
        x: Any = center.real
        y: Any = center.imag
        circles: list[Circle] = []
        arms: list[Line] = []
        for k, c in list(self.coefficients.items())[1:]:
            # c·e^{ikθ}: rotate the amplitude by kθ.
            dx = c.real * cos(turn * k) - c.imag * sin(turn * k)
            dy = c.real * sin(turn * k) + c.imag * cos(turn * k)
            circles.append(Circle(r=abs(c), x=x, y=y, stroke=faint, stroke_width=1.5, opacity=0.7))
            arms.append(Line(start=vec(x, y), end=vec(x + dx, y + dy), stroke_width=2.0))
            x, y = x + dx, y + dy
        points = [self._position(i / (CURVE_POINTS - 1)) for i in range(CURVE_POINTS)]
        curve = Path([(z.real, z.imag) for z in points], stroke=stroke, stroke_width=4.0)
        # The curve appears behind the tip, up to the progress of the first turn (draw progress
        # traces the outline over its first 70%).
        self._scene._push_set(curve._sig("_draw"), self.t * OUTLINE_SHARE, curve._span)
        tip = Dot(r=0.07, x=x, y=y, fill=stroke)
        object.__setattr__(self, "circles", circles)
        object.__setattr__(self, "arms", arms)
        object.__setattr__(self, "curve", curve)
        object.__setattr__(self, "tip", tip)
        object.__setattr__(curve, "_part", "curve")
        object.__setattr__(tip, "_part", "tip")
        return [curve, *circles, *arms, tip]

    def enter(self) -> Animation:
        """`k.draw(epi)`: the circles and arms are drawn, the tip appears (the curve waits
        for `run`)."""
        return par(draw(*self.circles, *self.arms), fade_in(self.tip))

    def run(self, turns: float = 1.0, *, duration: float | None = None, ease: EaseLike | None = None) -> Animation:
        """Turn the chain `turns` times at a steady speed (the tip traces the path once per
        turn; `ease=` for another speed profile)."""
        from ..anim.ease import ease as eases

        target = float(self.t.now) + turns
        return self.to(t=target, duration=duration if duration is not None else 4.0 * abs(turns), ease=ease if ease is not None else eases.linear)
