"""`k.ComplexPlane`: a `k.NumberPlane` labelled as the complex plane, whose points are complex
numbers: `cp.dot(2 + 1j)`, `cp.apply(lambda z: z * 1j)`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Sequence, Unpack, cast

from .node import Node
from .number_plane import NumberPlane, PlaneTransform
from .shapes import Arrow, Dot
from .text import Text

if TYPE_CHECKING:
    from ..anim.animation import Animation, AnimationTiming
    from .keywords import UnplacedKeywords, UnplacedStyleKeywords

#: `cp.apply(...)`: multiply by a complex number, or map every point with a function of `z`.
ComplexTransform = complex | float | Callable[[complex], complex]


def _imaginary_label(v: float) -> str:
    if v == 1:
        return "i"
    if v == -1:
        return "−i"
    return f"{v:g}i".replace("-", "−")


class ComplexPlane(NumberPlane):
    """`k.ComplexPlane(re=(-4, 4, 1), im=(-3, 3, 1))`: the plane with real ticks along the real
    axis, `i` ticks along the imaginary one and `Re`/`Im` labels. Points are complex numbers:
    `cp.dot(2 + 1j)`, `cp.vector(1 - 2j)`, `cp.coords(z)`. `cp.apply(1j)` multiplies everything
    by `i` (a quarter turn), `cp.apply(lambda z: z ** 2)` maps it; the labels move along."""

    if TYPE_CHECKING:
        _labels: bool

    def __init__(
        self,
        re: Sequence[float] = (-6, 6, 1),
        im: Sequence[float] = (-3, 3, 1),
        *,
        unit: float = 1.0,
        labels: bool = True,
        samples: int = 24,
        **props: Unpack[UnplacedKeywords],
    ) -> None:
        object.__setattr__(self, "_labels", labels)
        super().__init__(x=re, y=im, unit=unit, basis=False, samples=samples, **props)

    def _parts(self) -> list[Node]:
        parts = super()._parts()
        if not self._labels:
            return parts
        (x0, x1, xs), (y0, y1, ys), unit, _ = self._plane_opts
        size = 0.24
        # Data-unit offsets, so the labels move with the plane.
        below, left = -0.32 / unit, -0.32 / unit
        for i in range(int((x1 - x0) / xs + 1e-9) + 1):
            v = round(x0 + i * xs, 10)
            if v != 0:
                parts.append(self._anchored_label(f"{v:g}".replace("-", "−"), v, below, size))
        for j in range(int((y1 - y0) / ys + 1e-9) + 1):
            v = round(y0 + j * ys, 10)
            if v != 0:
                parts.append(self._anchored_label(_imaginary_label(v), left, v, size))
        parts.append(self._anchored_label("Re", x1 - 0.35 / unit, 0.35 / unit, size * 1.2))
        parts.append(self._anchored_label("Im", 0.45 / unit, y1 - 0.25 / unit, size * 1.2))
        return parts

    def _anchored_label(self, text: str, x: float, y: float, size: float) -> Text:
        lx, ly = self._local(x, y)
        # Labels travel with the plane and may leave the frame, like its grid lines.
        label = Text(text, size=size, x=lx, y=ly, bleed=True)
        self._anchored.append((label, (x, y)))
        return label

    def coords(self, value: complex) -> tuple[float, float]:  # pyright: ignore[reportIncompatibleMethodOverride] - points are complex numbers
        """Where the complex number `value` is now, in the plane's own coordinates."""
        return super().coords(value.real, value.imag)

    def dot(self, value: complex, *, radius: float = 0.1, **style: Unpack[UnplacedStyleKeywords]) -> Dot:  # pyright: ignore[reportIncompatibleMethodOverride] - points are complex numbers
        """A dot at the complex number `value` that the transformations carry."""
        return super().dot(value.real, value.imag, radius=radius, **style)

    def vector(self, value: complex, **style: Unpack[UnplacedStyleKeywords]) -> Arrow:  # pyright: ignore[reportIncompatibleMethodOverride] - points are complex numbers
        """An arrow from 0 to the complex number `value` that the transformations carry."""
        return super().vector(value.real, value.imag, **style)

    def apply(self, transform: ComplexTransform | PlaneTransform, **kw: Unpack[AnimationTiming]) -> Animation:  # pyright: ignore[reportIncompatibleMethodOverride] - also complex factors and functions of z
        """Multiply the plane by a complex number (`cp.apply(1j)`: a quarter turn), or map it
        with a function of `z` (`cp.apply(lambda z: z ** 2)`); a 2×2 matrix also works."""
        if isinstance(transform, (complex, int, float)):
            factor = complex(transform)
            return super().apply(lambda x, y: _pair(factor * complex(x, y)), **kw)
        if callable(transform):
            fn = cast("Callable[[complex], complex]", transform)
            return super().apply(lambda x, y: _pair(complex(fn(complex(x, y)))), **kw)
        return super().apply(cast("PlaneTransform", transform), **kw)


def _pair(z: complex) -> tuple[float, float]:
    return (z.real, z.imag)
