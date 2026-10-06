"""`ax.dot(open=)` and `ax.plot(holes=)`: open and closed points on curves."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build


def test_holes_sit_at_the_limit_and_are_hollow() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(0, 4), y=(0, 6), width=4, height=6)
        curve = ax.plot(lambda x: (x * x - 4) / (x - 2), holes=[2])
        s.add(ax)
        hole = curve.holes[0]
        seen["y"] = float(hole.y.now)
        seen["fill"] = hole.fill.now
        seen["bg"] = s.theme.bg

    # The plot spans -3..3 vertically for 0..6: y = 4 maps to 1.
    assert seen["y"] == pytest.approx(1.0, abs=1e-4)
    assert seen["fill"] == seen["bg"]


def test_holes_wait_for_a_growing_curve() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(0, 4), y=(0, 6))
        until = k.signal(0.0)
        curve = ax.plot(lambda x: x, holes=[3], until=until)
        s.add(ax)
        seen["before"] = bool(curve.holes[0].visible.now)
        s.play(until.to(4))
        seen["after"] = bool(curve.holes[0].visible.now)

    assert seen["before"] is False and seen["after"] is True
