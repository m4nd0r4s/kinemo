"""Axes ticks: regenerated for the new ranges on `zoom_to`, explicit `x_ticks=`/`y_ticks=`,
and `tick_format=`."""

from __future__ import annotations

import kinemo as k
from conftest import build


def tick_labels(ax: k.Axes) -> list[str]:
    return [c.text.now for c in ax.children if isinstance(c, k.Text) and getattr(c, "_tick_axis", None) == "x"]  # type: ignore[attr-defined]


def test_zoom_regenerates_ticks_for_the_new_range() -> None:
    seen: dict[str, list[str]] = {}

    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(0, 10, 2), y=(0, 10, 2)).place(at="center")
        s.play(k.draw(ax))
        seen["before"] = tick_labels(ax)
        s.play(ax.zoom_to(x=(0, 1)))
        seen["after"] = tick_labels(ax)

    assert seen["before"] == ["0", "2", "4", "6", "8", "10"]
    assert seen["after"] == ["0", "0.2", "0.4", "0.6", "0.8", "1"]


def test_zoom_keeps_plots_on_top() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(0, 10, 2), y=(0, 10, 2)).place(at="center")
        curve = ax.plot(lambda x: x)
        s.play(k.draw(ax))
        s.play(ax.zoom_to(x=(0, 1), y=(0, 1)))
        seen["last"] = ax.children[-1] is curve

    assert seen["last"] is True


def test_explicit_ticks_and_format() -> None:
    seen: dict[str, list[str]] = {}

    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(0, 30), y=(0, 5), x_ticks=[4, 9, 16, 25], tick_format="{:.1f}").place(at="center")
        s.play(k.draw(ax))
        s.play(ax.zoom_to(x=(0, 20)))
        seen["labels"] = tick_labels(ax)

    assert seen["labels"] == ["4.0", "9.0", "16.0", "25.0"]


def test_tick_format_function() -> None:
    seen: dict[str, list[str]] = {}

    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(0, 1, 0.5), tick_format=lambda v: f"{v:.0%}")
        s.add(ax)
        seen["labels"] = tick_labels(ax)

    assert seen["labels"] == ["0%", "50%", "100%"]
