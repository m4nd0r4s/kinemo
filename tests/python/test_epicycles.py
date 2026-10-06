"""`k.Epicycles`: Fourier coefficients of a path and the rotating chain."""

from __future__ import annotations

import math

import pytest

import kinemo as k
from conftest import build
from kinemo.objects.epicycles import fourier_coefficients


def test_a_circle_is_one_rotating_term() -> None:
    circle = [(2 * math.cos(a), 2 * math.sin(a)) for a in (2 * math.pi * i / 64 for i in range(64))]
    terms = fourier_coefficients(circle, 3)
    strongest = max((k for k in terms if k != 0), key=lambda k: abs(terms[k]))
    assert strongest == 1 and abs(terms[1]) == pytest.approx(2.0, rel=1e-3)
    assert abs(terms[0]) < 1e-9


def test_the_tip_follows_the_coefficients() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        epi = k.Epicycles(coefficients={1: 1 + 0j, 2: 0.5 + 0j})
        s.add(epi)
        s.play(epi.run(turns=0.25, duration=1))
        seen["tip"] = (float(epi.tip.x.now), float(epi.tip.y.now))
        seen["circles"] = len(epi.circles)

    # A quarter turn: e^{iπ/2} = i, e^{iπ} = -1 → 1·i + 0.5·(-1).
    assert seen["tip"] == pytest.approx((-0.5, 1.0), abs=1e-6)
    assert seen["circles"] == 2


def test_needs_points_or_coefficients() -> None:
    with pytest.raises(k.KinemoError):

        @build
        def scene(s: k.Scene) -> None:
            k.Epicycles()
