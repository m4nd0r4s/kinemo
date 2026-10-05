"""`k.Callout`: a box with text beside its target, a tail pointing at it, following it."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build


def test_the_tail_points_at_the_target_and_the_callout_follows_it() -> None:
    seen: dict[str, float] = {}

    @build
    def scene(s: k.Scene) -> None:
        dot = k.Circle(r=0.5)
        s.add(dot)
        bubble = k.Callout("hello", to=dot, side="top-right")
        s.add(bubble)
        assert bubble.box is not None
        seen["box_left"] = bubble.box.world.left.now
        seen["box_bottom"] = bubble.box.world.bottom.now
        seen["dot_right"] = dot.world.right.now
        seen["dot_top"] = dot.world.top.now
        seen["x0"] = bubble.box.world.center.now[0]
        s.play(dot.to(x=2), duration=1)
        seen["x1"] = bubble.box.world.center.now[0]

    assert seen["box_left"] > seen["dot_right"] and seen["box_bottom"] > seen["dot_top"]
    assert seen["x1"] - seen["x0"] == pytest.approx(2.0, abs=1e-6)


@pytest.mark.parametrize("side", ["top", "bottom", "left", "right", "top-left", "bottom-right"])
def test_every_side_puts_the_box_on_that_side(side: str) -> None:
    seen: dict[str, tuple[float, float]] = {}

    @build
    def scene(s: k.Scene) -> None:
        dot = k.Dot()
        s.add(dot)
        note = k.Callout("x", to=dot, side=side, style="line")  # type: ignore[arg-type]
        s.add(note)
        c = note.label.world.center.now
        seen["center"] = (c[0], c[1])

    x, y = seen["center"]
    assert ("right" in side) == (x > 0.1) and ("left" in side) == (x < -0.1)
    assert ("top" in side) == (y > 0.1) and ("bottom" in side) == (y < -0.1)


def test_long_text_wraps_at_max_width() -> None:
    width: list[float] = []

    @build
    def scene(s: k.Scene) -> None:
        dot = k.Dot()
        s.add(dot)
        note = k.Callout("a fairly long sentence that cannot fit on one short line", to=dot, max_width=2.5)
        s.add(note)
        width.append(note.label.width.now)

    assert width[0] <= 2.5 + 1e-6


def test_a_bubble_passes_the_lints() -> None:
    @build
    def scene(s: k.Scene) -> None:
        fox = k.Circle(r=0.6, fill=k.ORANGE, fill_opacity=1).place(at="center")
        s.add(fox)
        s.play(k.fade_in(k.Callout("Wait, what?", to=fox)))

    assert not [d for d in scene.lints.items if d.level in ("error", "warning")]
