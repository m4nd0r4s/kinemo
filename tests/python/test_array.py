"""`k.Array`: cells with values and indices, swaps, comparisons, value changes and pointers
that appear once and then move."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build


def test_cells_hold_the_values_in_index_order_after_swaps() -> None:
    seen: dict[str, list[str]] = {}

    @build
    def scene(s: k.Scene) -> None:
        arr = k.Array([5, 2, 9])
        s.add(arr)
        seen["before"] = [c.value.text.now for c in arr.cells]
        s.play(arr.swap(0, 2))
        seen["after"] = [c.value.text.now for c in arr.cells]
        s.play(arr.set(1, 7))
        seen["set"] = [c.value.text.now for c in arr.cells]

    assert seen == {"before": ["5", "2", "9"], "after": ["9", "2", "5"], "set": ["9", "7", "5"]}


def test_pointers_appear_then_move_with_the_array() -> None:
    xs: list[float] = []

    @build
    def scene(s: k.Scene) -> None:
        arr = k.Array([1, 2, 3, 4], cell=1.0)
        s.add(arr)
        s.play(arr.pointer("i", 0), arr.pointer("j", 1))
        i = arr.pointers["i"]
        xs.append(i.world.center.now[0])
        s.play(arr.pointer("i", 3))
        xs.append(i.world.center.now[0])
        s.play(arr.to(x=2), duration=0.5)
        xs.append(i.world.center.now[0])

    assert xs[0] == pytest.approx(-1.5) and xs[1] == pytest.approx(1.5) and xs[2] == pytest.approx(3.5)


def test_indices_can_be_hidden_and_compare_passes_the_lints() -> None:
    counts: list[int] = []

    @build
    def scene(s: k.Scene) -> None:
        arr = k.Array([3, 1], index=False).place(at="center")
        s.add(arr)
        s.play(arr.compare(0, 1))
        counts.append(len(arr.indices))

    assert counts == [0]
    assert not [d for d in scene.lints.items if d.level in ("error", "warning")]
