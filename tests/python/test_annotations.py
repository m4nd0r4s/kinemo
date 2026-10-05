"""Annotation marks follow their target: `k.underline`, `k.box`, `k.encircle`, `k.strike` and
`k.cross` sit on the target's box (in world coordinates, so parts of text work too)."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build, snapshot_of


def bbox(scene, t: float, name: str) -> list[float]:  # type: ignore[no-untyped-def]
    return snapshot_of(scene, t, name)["bbox"]


def test_marks_sit_on_their_target() -> None:
    @build
    def scene(s: k.Scene) -> None:
        word = k.Text("answer", size=0.5)
        s.add(word)
        line = k.underline(word, pad=0.1)
        frame = k.box(word, pad=0.2)
        out = k.strike(word, overhang=0.0)
        s.add(line, frame, out)

    x0, y0, x1, y1 = bbox(scene, 0.0, "word")
    lx0, ly0, lx1, _ = bbox(scene, 0.0, "line")
    assert lx0 == pytest.approx(x0, abs=0.05) and lx1 == pytest.approx(x1, abs=0.05) and ly0 < y0
    fx0, fy0, fx1, fy1 = bbox(scene, 0.0, "frame")
    assert fx0 < x0 - 0.15 and fx1 > x1 + 0.15 and fy0 < y0 - 0.15 and fy1 > y1 + 0.15
    _, sy0, _, sy1 = bbox(scene, 0.0, "out")
    assert y0 < (sy0 + sy1) / 2 < y1


def test_marks_follow_a_moving_target_and_parts_of_formulas() -> None:
    @build
    def scene(s: k.Scene) -> None:
        eq = k.Math(r"a^2 + b^2 = c^2")
        s.add(eq)
        ring = k.encircle(eq["c^2"])
        x = k.cross(eq["b^2"])
        s.play(k.draw(ring), k.draw(x))
        s.play(eq.to(x=2), duration=1)

    before = bbox(scene, 1.0, "ring")
    after = bbox(scene, 2.0, "ring")
    assert after[0] - before[0] == pytest.approx(2.0, abs=1e-3)
    part = bbox(scene, 2.0, "eq")
    assert part[0] < after[0] < part[2]


def test_marks_are_named_by_their_variable() -> None:
    labels: list[str] = []

    @build
    def scene(s: k.Scene) -> None:
        word = k.Text("x")
        s.add(word)
        cut = k.strike(word)
        s.add(cut)
        labels.append(cut._label())

    assert labels == ["cut"]
