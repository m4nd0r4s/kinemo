"""`s.frame`: the visible area in scene units, with its edges and safe area."""

from __future__ import annotations

from dataclasses import dataclass

from ..values.vec import Vec

SAFE_MARGIN = 0.5


@dataclass(frozen=True)
class Rect:
    left: float
    bottom: float
    right: float
    top: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.top - self.bottom

    @property
    def center(self) -> Vec:
        return Vec((self.left + self.right) / 2, (self.bottom + self.top) / 2)

    def inset(self, m: float) -> "Rect":
        return Rect(self.left + m, self.bottom + m, self.right - m, self.top - m)


@dataclass(frozen=True)
class Frame(Rect):
    @property
    def safe(self) -> Rect:
        return self.inset(SAFE_MARGIN)


def frame_of(width_units: float, height_units: float) -> Frame:
    return Frame(-width_units / 2, -height_units / 2, width_units / 2, height_units / 2)
