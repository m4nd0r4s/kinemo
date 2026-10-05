"""`k.Card`: a panel sized to its content (or fixed), with the title at the top-left, the
content below it, the caption under the panel and an accent bar."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build


def test_the_panel_wraps_its_content_with_the_title_above() -> None:
    seen: dict[str, float] = {}

    @build
    def scene(s: k.Scene) -> None:
        shape = k.Square(1)
        card = k.Card(shape, title="Square", caption="four equal sides", accent=k.ORANGE)
        s.add(card)
        assert card.title is not None and card.caption is not None and card.accent is not None
        box, title, note, bar = card.box.world, card.title.world, card.caption.world, card.accent.world
        seen.update(
            panel_left=box.left.now, panel_right=box.right.now, panel_bottom=box.bottom.now,
            shape_left=shape.world.left.now, shape_right=shape.world.right.now, shape_top=shape.world.top.now,
            title_bottom=title.bottom.now, title_left=title.left.now,
            caption_top=note.top.now, bar_right=bar.right.now,
        )

    assert seen["panel_left"] < seen["shape_left"] and seen["panel_right"] > seen["shape_right"]
    assert seen["title_bottom"] > seen["shape_top"]  # the title is above the content
    assert seen["caption_top"] < seen["panel_bottom"]  # the caption is under the panel
    assert seen["bar_right"] <= seen["title_left"] + 1e-6  # the accent bar is left of the title


def test_a_fixed_size_overrides_the_content() -> None:
    size: list[tuple[float, float]] = []

    @build
    def scene(s: k.Scene) -> None:
        card = k.Card(k.Dot(), w=4, h=2)
        s.add(card)
        size.append((card.box.width.now, card.box.height.now))

    assert size[0] == pytest.approx((4.0, 2.0), abs=0.05)


def test_cards_line_up_in_a_row_and_pass_the_lints() -> None:
    @build
    def scene(s: k.Scene) -> None:
        a = k.Card(k.Circle(r=0.5), title="A", caption="first")
        b = k.Card(k.Square(1), title="B", caption="second")
        s.add(k.Row(a, b, gap=0.5).place(at="center"))

    assert not [d for d in scene.lints.items if d.level in ("error", "warning")]
