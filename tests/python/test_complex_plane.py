"""`k.ComplexPlane`: complex points, multiplication and maps of `z`."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build


def test_multiplying_by_i_turns_points_a_quarter() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        cp = k.ComplexPlane(re=(-4, 4, 1), im=(-3, 3, 1))
        arrow = cp.vector(2 + 1j)
        point = cp.dot(-1 + 2j)
        s.play(k.draw(cp))
        s.play(cp.apply(1j))
        seen["arrow"] = tuple(arrow.end.now)
        seen["point"] = (float(point.x.now), float(point.y.now))

    assert seen["arrow"] == pytest.approx((-1.0, 2.0))
    assert seen["point"] == pytest.approx((-2.0, -1.0))


def test_functions_of_z_and_labels() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        cp = k.ComplexPlane(re=(-2, 2, 1), im=(-2, 2, 1))
        point = cp.dot(1 + 1j)
        s.play(k.draw(cp))
        s.play(cp.apply(lambda z: z * z))
        seen["point"] = (float(point.x.now), float(point.y.now))
        seen["labels"] = sorted(str(c.text.now) for c in cp.children if isinstance(c, k.Text))

    assert seen["point"] == pytest.approx((0.0, 2.0))
    assert "i" in seen["labels"] and "Re" in seen["labels"]  # type: ignore[operator]
