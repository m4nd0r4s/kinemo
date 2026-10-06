"""BarChart motion: bars that pass each other narrow and hide their labels mid-way, and the
value label rides on `k.indicate`'s pulse."""

from __future__ import annotations

import json
from typing import Any

import kinemo as k
from conftest import build
from kinemo.values.encode import decode
from kinemo.objects.charts.bar_chart import _crossing_keys  # pyright: ignore[reportPrivateUsage]


def value_at(signal: Any, t: float) -> Any:
    return decode(json.loads(signal._scene._b.eval_signal(signal._id, t)))


def test_crossing_keys_are_the_pairs_that_swap_order() -> None:
    assert _crossing_keys(["a", "b", "c"], ["a", "b", "c"]) == set()
    assert _crossing_keys(["a", "b", "c"], ["b", "a", "c"]) == {"a", "b"}
    assert _crossing_keys(["a", "b", "c"], ["c", "a", "b"]) == {"a", "b", "c"}


def test_crossing_bars_narrow_and_hide_labels_at_the_midpoint() -> None:
    seen: dict[str, float] = {}

    @build
    def scene(s: k.Scene) -> None:
        chart = k.BarChart({"c": ["a", "b", "c"], "v": [1.0, 2.0, 3.0]}, x="c", y="v")
        s.add(chart)
        s.play(chart.to(data={"c": ["b", "a", "c"], "v": [2.0, 1.0, 3.0]}), duration=2)
        a, c = chart.bar("a"), chart.bar("c")
        seen["a_width_mid"] = value_at(a._sig("bar_width"), 1.0)
        seen["a_width_end"] = value_at(a._sig("bar_width"), 2.0)
        seen["c_width_mid"] = value_at(c._sig("bar_width"), 1.0)
        seen["a_label_mid"] = value_at(a.category._sig("opacity"), 1.0)

    assert seen["a_width_mid"] < 0.5 * seen["a_width_end"]
    assert seen["c_width_mid"] == seen["a_width_end"]  # c does not cross anything
    assert seen["a_label_mid"] < 0.05


def test_value_label_rises_with_the_pulse() -> None:
    seen: dict[str, float] = {}

    @build
    def scene(s: k.Scene) -> None:
        chart = k.BarChart({"c": ["a"], "v": [4.0]}, x="c", y="v")
        s.add(chart)
        s.play(k.indicate(chart.bar("a")), duration=1)
        label = chart.bar("a").value_label
        seen["rest"] = value_at(label._sig("_shift"), 0.0)[1]
        seen["peak"] = value_at(label._sig("_shift"), 0.5)[1]

    assert seen["rest"] == 0.0 and seen["peak"] > 0.3
