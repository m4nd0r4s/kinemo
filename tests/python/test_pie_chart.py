"""`k.PieChart`: contiguous slices, data transitions by key, and labels."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build

MIX = {"source": ["a", "b", "c"], "v": [1.0, 1.0, 2.0]}


def test_slices_split_the_circle_clockwise_from_the_top() -> None:
    seen: dict[str, list[float]] = {}

    @build
    def scene(s: k.Scene) -> None:
        pie = k.PieChart(MIX, labels="source", values="v")
        s.add(pie)
        seen["shares"] = [float(pie.slice(key).share.now) for key in pie.keys]
        seen["starts"] = [float(pie.slice(key).start.now) for key in pie.keys]

    assert seen["shares"] == pytest.approx([0.25, 0.25, 0.5])
    assert seen["starts"] == pytest.approx([90.0, 0.0, -90.0])


def test_data_transitions_match_by_key() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        pie = k.PieChart(MIX, labels="source", values="v")
        s.add(pie)
        s.play(pie.to(data={"source": ["c", "d"], "v": [1.0, 3.0]}))
        seen["keys"] = pie.keys
        seen["d"] = float(pie.slice("d").share.now)
        seen["percent"] = pie.slice("d").percent.text.now  # type: ignore[union-attr]

    assert seen["keys"] == ["c", "d"]
    assert seen["d"] == pytest.approx(0.75)
    assert seen["percent"] == "75%"


def test_unknown_keys_are_errors() -> None:
    with pytest.raises(k.KinemoError):

        @build
        def scene(s: k.Scene) -> None:
            k.PieChart(MIX, labels="source", values="v").slice("z")
