"""`Axes.add`, `Axes.origin` and `Axes.in_view`: objects living in the axes' coordinates."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build


def test_add_adopts_and_enters_with_the_axes() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(0, 10, 2), y=(0, 10, 2)).place(at="center")
        dot = k.Dot(position=ax.local_point(4, 8))
        ax.add(dot)
        s.play(k.draw(ax))
        seen["adopted"] = dot in ax.children

    assert seen["adopted"] is True


def test_add_can_wait_for_its_own_verb() -> None:
    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(0, 10, 2), y=(0, 10, 2)).place(at="center")
        dot = k.Dot(position=ax.local_point(4, 8))
        ax.add(dot, enter_with_axes=False)
        s.play(k.draw(ax))
        s.play(k.fade_in(dot))
        s.play(ax.zoom_to(x=(2, 6)))


def test_origin_and_in_view_follow_zooms() -> None:
    @build
    def scene(s: k.Scene) -> None:
        ax = k.Axes(x=(-2, 8, 2), y=(-2, 8, 2)).place(at="center")
        tag = k.Text("8", size=0.3, position=ax.local_point(8, 1), visible=ax.in_view(x=8, y=1))
        ax.add(k.Dot(position=ax.origin()), tag)
        s.play(k.draw(ax))
        s.play(ax.zoom_to(x=(0, 5)))


def test_in_view_needs_a_value() -> None:
    with pytest.raises(k.KinemoError):

        @build
        def scene(s: k.Scene) -> None:
            k.Axes().in_view()
