"""`k.Gauge`: the needle points at the value (a number or a signal, clamped to the range),
`gauge.to(value=)` animates it and the readout follows."""

from __future__ import annotations

import math

import pytest

import kinemo as k
from conftest import build


def needle_angle(end: tuple[float, float]) -> float:
    return math.degrees(math.atan2(end[1], end[0]))


def test_the_needle_points_at_the_value() -> None:
    angles: list[float] = []

    @build
    def scene(s: k.Scene) -> None:
        gauge = k.Gauge(value=0, range=(0, 100), sweep=180)
        s.add(gauge)
        for v in (0, 50, 100, 150):
            s.play(gauge.to(value=v), duration=0.1)
            angles.append(needle_angle(gauge.needle.end.now))

    # 180°: 0 at the left (180°), 50 straight up (90°), 100 at the right (0°); 150 is clamped.
    assert angles[0] == pytest.approx(180.0, abs=1e-6) or angles[0] == pytest.approx(-180.0, abs=1e-6)
    assert angles[1] == pytest.approx(90.0, abs=1e-6)
    assert angles[2] == pytest.approx(0.0, abs=1e-6)
    assert angles[3] == pytest.approx(0.0, abs=1e-6)


def test_a_signal_drives_the_needle_and_the_readout() -> None:
    texts: list[str] = []

    @build
    def scene(s: k.Scene) -> None:
        speed = k.signal(10.0)
        gauge = k.Gauge(value=speed, range=(0, 120), label="km/h")
        s.add(gauge)
        s.play(speed.to(80), duration=1)
        assert gauge.readout is not None and gauge.value is speed
        texts.append(gauge.readout.text.now)

    assert texts == ["80 km/h"]


def test_zones_and_ticks_are_parts() -> None:
    counts: list[int] = []

    @build
    def scene(s: k.Scene) -> None:
        gauge = k.Gauge(range=(0, 10), ticks=5, zones=[(8, 10, k.RED), (0, 2, k.BLUE)])
        s.add(gauge)
        counts.extend([len(gauge.ticks), len(gauge.labels), len(gauge.zones)])

    assert counts == [6, 6, 2]
