"""2D vectors used for positions, sizes and offsets."""

from __future__ import annotations

import math
from typing import NamedTuple


class Vec(NamedTuple):
    x: float
    y: float

    def __add__(self, o: object) -> "Vec":  # type: ignore[override]
        ox, oy = _xy(o)
        return Vec(self.x + ox, self.y + oy)

    def __sub__(self, o: object) -> "Vec":
        ox, oy = _xy(o)
        return Vec(self.x - ox, self.y - oy)

    def __mul__(self, k: object) -> "Vec":  # type: ignore[override]
        if isinstance(k, int | float):
            return Vec(self.x * k, self.y * k)
        return NotImplemented

    __rmul__ = __mul__

    def __truediv__(self, k: float) -> "Vec":
        return Vec(self.x / k, self.y / k)

    def __neg__(self) -> "Vec":
        return Vec(-self.x, -self.y)

    @property
    def length(self) -> float:
        """Euclidean length of the vector."""
        return math.hypot(self.x, self.y)


def _xy(o: object) -> tuple[float, float]:
    if isinstance(o, tuple | list) and len(o) == 2:
        return float(o[0]), float(o[1])
    raise TypeError(f"not a 2D vector: {o!r}")


def as_vec(o: object) -> Vec:
    return Vec(*_xy(o))
