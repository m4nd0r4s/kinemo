"""`k.Timeline`: event placement on rows, reveals and zooms."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build


def test_close_events_take_different_rows() -> None:
    seen: dict[str, float] = {}

    @build
    def scene(s: k.Scene) -> None:
        tl = k.Timeline([(1609, "Kepler"), (1610, "Galileo"), (1800, "Later")], range=(1600, 2000))
        s.add(tl)
        seen["kepler"] = float(tl.event("Kepler").label.y.now)
        seen["galileo"] = float(tl.event("Galileo").label.y.now)
        seen["later"] = float(tl.event("Later").label.y.now)

    assert seen["kepler"] != seen["galileo"]
    assert seen["later"] == seen["kepler"]  # far apart: back on the first row


def test_reveal_and_zoom() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        tl = k.Timeline([(1700, "a"), (1900, "b")], range=(1600, 2000), reveal=True)
        s.play(k.draw(tl))
        s.play(tl.reveal("a"))
        s.play(tl.zoom_to(range=(1650, 1750)))
        seen["b_visible"] = bool(tl.event("b").visible.now)
        seen["a_x"] = float(tl.event("a").marker.x.now)

    assert seen["b_visible"] is False
    assert seen["a_x"] == pytest.approx(0.0, abs=1e-6)  # the middle of 1650..1750


def test_unknown_event_is_an_error() -> None:
    with pytest.raises(k.KinemoError):

        @build
        def scene(s: k.Scene) -> None:
            k.Timeline([(1, "a")]).event("z")
