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
    #: (top, right, bottom, left) covered by the app the video is made for (`platform=`).
    covered: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    @property
    def safe(self) -> Rect:
        """The frame inset by 0.5 u, or by more where the platform covers it."""
        top, right, bottom, left = (max(SAFE_MARGIN, c) for c in self.covered)
        return Rect(self.left + left, self.bottom + bottom, self.right - right, self.top - top)


def frame_of(width_units: float, height_units: float, covered: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)) -> Frame:
    return Frame(-width_units / 2, -height_units / 2, width_units / 2, height_units / 2, covered)
