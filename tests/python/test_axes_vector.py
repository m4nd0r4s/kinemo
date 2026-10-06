"""`ax.vector`: arrows in data units with components, and tip-to-tail sums."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build


def test_vector_follows_its_signals_and_has_components() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(0, 10), y=(0, 10), width=10, height=10)
        f = ax.vector((3, 4), at=(1, 1), label="F", components=True)
        s.add(ax)
        seen["end"] = tuple(f.arrow.end.now)
        seen["corner"] = tuple(f.x_component.end.now)  # type: ignore[union-attr]
        s.play(f.to(v=(0, 2)))
        seen["end_after"] = tuple(f.arrow.end.now)

    # Data (x, y) maps to (x - 5, y - 5) on a 10×10 plot of 0..10.
    assert seen["end"] == pytest.approx((-1.0, 0.0))
    assert seen["corner"] == pytest.approx((-1.0, -4.0))
    assert seen["end_after"] == pytest.approx((-4.0, -2.0))


def test_vector_sum_moves_b_and_draws_the_resultant() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(0, 10), y=(0, 10), width=10, height=10)
        a, b = ax.vector((3, 0)), ax.vector((0, 2))
        r = a + b
        s.add(ax)
        s.play(k.vector_sum(a, b, r))
        seen["b_at"] = tuple(b.at.now)
        seen["r_v"] = tuple(r.v.now)

    assert seen["b_at"] == pytest.approx((3.0, 0.0))
    assert seen["r_v"] == pytest.approx((3.0, 2.0))
