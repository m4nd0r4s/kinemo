"""`k.NumberPlane`: grid, basis vectors, objects on the plane and `apply`/`reset`."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build


def test_apply_moves_basis_vectors_objects_and_shapes() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        plane = k.NumberPlane(x=(-4, 4, 1), y=(-3, 3, 1))
        v = plane.vector(2, 1)
        p = plane.dot(-2, 2)
        square = plane.polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
        s.play(k.draw(plane))
        s.play(plane.apply([[1, 1], [0, 1]]))
        j_hat = next(c for c in plane.children if getattr(c, "_part", None) == "j_hat")
        seen["j"] = tuple(j_hat.end.now)  # type: ignore[attr-defined]
        seen["v"] = tuple(v.end.now)
        seen["p"] = (p.x.now, p.y.now)
        seen["square"] = [tuple(pt) for pt in square.points.now]

    assert seen["j"] == pytest.approx((1.0, 1.0))
    assert seen["v"] == pytest.approx((3.0, 1.0))
    assert seen["p"] == pytest.approx((0.0, 2.0))
    assert seen["square"] == pytest.approx([(0, 0), (1, 0), (2, 1), (1, 1)])


def test_transformations_compose_and_reset() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        plane = k.NumberPlane(unit=0.5)
        p = plane.dot(1, 0)
        s.play(k.draw(plane))
        s.play(plane.apply([[0, -1], [1, 0]]))
        s.play(plane.apply(lambda x, y: (2 * x, 2 * y)))
        seen["turned"] = (p.x.now, p.y.now)
        s.play(plane.reset())
        seen["back"] = (p.x.now, p.y.now)

    assert seen["turned"] == pytest.approx((0.0, 1.0))
    assert seen["back"] == pytest.approx((0.5, 0.0))


def test_matrix_must_be_two_by_two() -> None:
    with pytest.raises(k.KinemoError):

        @build
        def scene(s: k.Scene) -> None:
            k.NumberPlane().apply([[1, 2, 3]])
