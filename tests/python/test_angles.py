"""Angle markers: `k.Angle` spans the smaller angle between two rays (and follows reactive
points), shows a label or its value; `k.RightAngle` draws the square at the vertex."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build, inspect, prop_at, snapshot_of


def test_the_arc_spans_the_angle_between_the_rays() -> None:
    @build
    def scene(s: k.Scene) -> None:
        theta = k.Angle((2.0, 0.0), (0.0, 0.0), (0.0, 2.0), r=0.6)
        s.add(theta)

    arc = next(o for o in inspect(scene, 0.0) if o["kind"] == "arc")
    assert arc["props"]["start_angle"]["Float"] == pytest.approx(0.0, abs=1e-6)
    assert arc["props"]["angle"]["Float"] == pytest.approx(90.0, abs=1e-6)


def test_the_smaller_angle_is_taken_whichever_ray_comes_first() -> None:
    @build
    def scene(s: k.Scene) -> None:
        theta = k.Angle((0.0, 2.0), (0.0, 0.0), (2.0, 0.0))
        s.add(theta)

    arc = next(o for o in inspect(scene, 0.0) if o["kind"] == "arc")
    assert arc["props"]["angle"]["Float"] == pytest.approx(-90.0, abs=1e-6)


def test_the_value_follows_a_reactive_point() -> None:
    texts: list[str] = []

    @build
    def scene(s: k.Scene) -> None:
        deg = k.signal(30.0)
        tip = k.vec(k.cos(deg * k.pi / 180), k.sin(deg * k.pi / 180))
        theta = k.Angle((1.0, 0.0), (0.0, 0.0), tip, show_value=True)
        s.add(theta)
        s.play(deg.to(75), duration=1)
        assert theta.label is not None
        texts.append(theta.label.text.now)

    assert texts == ["75°"]


def test_the_right_angle_mark_sits_in_the_corner() -> None:
    @build
    def scene(s: k.Scene) -> None:
        mark = k.RightAngle((3.0, 0.0), (0.0, 0.0), (0.0, 3.0), size=0.5)
        s.add(mark)

    box = snapshot_of(scene, 0.0, "mark")["bbox"]
    assert box == pytest.approx([0.0, 0.0, 0.5, 0.5], abs=0.05)


def test_labels_and_names() -> None:
    @build
    def scene(s: k.Scene) -> None:
        alpha = k.Angle((1.0, 0.0), (0.0, 0.0), (0.0, 1.0), label="α")
        s.add(alpha)

    assert prop_at(scene, 0.0, "alpha", "opacity") == 1.0
