"""`ax.segment(..., clip=True)`, `ax.hband` and `ax.vband`: cut to the visible ranges and
following zooms."""

from __future__ import annotations

import json
from typing import Any

import kinemo as k
from conftest import build
from kinemo.values.encode import decode


def at(signal: Any, t: float) -> Any:
    return decode(json.loads(signal._scene._b.eval_signal(signal._id, t)))


def test_segment_is_clipped_to_the_view_and_hides_outside_it() -> None:
    seen: dict[str, Any] = {}

    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(0, 10), y=(0, 10), width=10, height=10)
        line = ax.segment((-5, 5), (15, 5))
        gone = ax.segment((20, 1), (30, 2))
        s.add(ax)
        s.play(ax.zoom_to(x=(0, 5)), duration=1)
        seen["start"], seen["end"] = at(line._sig("start"), 0.0), at(line._sig("end"), 0.0)
        seen["end_zoomed"] = at(line._sig("end"), 1.0)
        seen["gone"] = at(gone._sig("visible"), 0.0)

    assert seen["start"][0] == -5.0 and seen["end"][0] == 5.0  # the plot spans -5..5 units
    assert seen["end_zoomed"][0] == 5.0
    assert seen["gone"] is False


def test_bands_follow_zooms_and_hide_out_of_range() -> None:
    seen: dict[str, Any] = {}

    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(0, 10), y=(0, 10), width=10, height=10)
        band = ax.hband(2, 4)
        column = ax.vband(1, 2)
        s.add(ax)
        s.play(ax.zoom_to(x=(5, 10), y=(0, 5)), duration=1)
        seen["height_before"], seen["height_after"] = at(band._sig("h"), 0.0), at(band._sig("h"), 1.0)
        seen["column_after"] = at(column._sig("visible"), 1.0)

    assert abs(seen["height_before"] - 2.0) < 1e-9 and abs(seen["height_after"] - 4.0) < 1e-9
    assert seen["column_after"] is False
