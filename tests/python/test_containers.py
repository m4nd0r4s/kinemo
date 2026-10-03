"""Groups and containers: order at the cursor, reflow transitions, Bar."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build, diagnostic_of, ir, position_at, presence, prop_at, snapshot_of


def test_row_indexing_reflects_order_and_lays_out_left_to_right() -> None:
    seen = {}

    @build
    def scene(s: k.Scene) -> None:
        a, b, c = k.Square(), k.Circle(r=0.5), k.Dot()
        row = k.Row(a, b, c, gap=0.5).place(at="center")
        s.add(row)
        seen["order"] = [row[0] is a, row[1] is b, row[2] is c]
        seen["len"] = len(row)
        seen["iter"] = [o is x for o, x in zip(row, (a, b, c))]
        seen["xs"] = [o.x.now for o in row]
        seen["gap"] = b.left.now - a.right.now

    assert seen["order"] == [True, True, True]
    assert seen["len"] == 3
    assert seen["iter"] == [True, True, True]
    assert seen["xs"] == sorted(seen["xs"])
    assert seen["gap"] == pytest.approx(0.5)


def test_column_stacks_top_to_bottom() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        col = k.Column(k.Square(), k.Circle(r=0.5), gap=0.2)
        s.add(col)
        seen.extend(o.y.now for o in col)

    assert seen[0] > seen[1]


def test_swap_reorders_children_at_the_cursor_and_reflows() -> None:
    seen = {}

    @build
    def scene(s: k.Scene) -> None:
        bars = [k.Bar(v) for v in (3, 1, 2)]
        row = k.Row(*bars, gap=0.2)
        s.add(row)
        seen["before"] = [b.value.now for b in row]
        xs = [b.x.now for b in row]
        s.play(row.swap(0, 2))
        seen["after"] = [b.value.now for b in row]
        seen["first_is_last"] = row[0] is bars[2]
        seen["moved"] = (bars[2].x.now, bars[0].x.now)
        seen["slots"] = (xs[0], xs[2])

    assert seen["before"] == [3.0, 1.0, 2.0]
    assert seen["after"] == [2.0, 1.0, 3.0]
    assert seen["first_is_last"] is True
    assert seen["moved"] == pytest.approx(seen["slots"])


def test_swap_is_animated_over_its_duration() -> None:
    @build
    def scene(s: k.Scene) -> None:
        a = k.Square()
        b = k.Square()
        row = k.Row(a, b, gap=0.0)
        s.add(row)
        s.play(row.swap(0, 1), duration=2)

    start, middle, end = (position_at(scene, t, "a")[0] for t in (0.0, 1.0, 2.0))
    assert start < middle < end


def test_to_children_is_the_general_form_of_swap() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        a = k.Square()
        b = k.Circle()
        row = k.Row(a, b)
        s.add(row)
        s.play(row.to(children=[b, a]))
        seen.append([row[0] is b, row[1] is a])

    assert seen == [[True, True]]


def test_insert_enters_and_pop_leaves() -> None:
    seen = {}

    @build
    def scene(s: k.Scene) -> None:
        first = k.Square()
        last = k.Square()
        row = k.Row(first, last)
        s.add(row)
        middle = k.Dot()
        s.play(row.insert(1, middle))
        seen["inserted"] = row[1] is middle
        s.play(row.pop(0))
        seen["len"] = len(row)

    assert seen == {"inserted": True, "len": 2}
    assert presence(scene, "middle") == [(0.0, True)]
    assert presence(scene, "first") == [(0.0, True), (2.0, False)]


def test_pop_and_insert_animate_the_reflow() -> None:
    @build
    def scene(s: k.Scene) -> None:
        first = k.Square()
        last = k.Square()
        row = k.Row(first, last, gap=0.5).place(at="center")
        s.add(row)
        s.play(row.pop(0), duration=1)
        middle = k.Dot()
        s.play(row.insert(0, middle), duration=1)

    def world_x(t: float, name: str) -> float:
        x0, _, x1, _ = snapshot_of(scene, t, name)["bbox"]
        return (x0 + x1) / 2

    # The leaving square stays in its slot while the other slides into the middle.
    xs = [world_x(t, "last") for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
    assert xs == sorted(xs, reverse=True) and len({round(x, 6) for x in xs}) == 5
    assert xs[-1] == pytest.approx(0.0)
    assert world_x(0.5, "first") == pytest.approx(world_x(0.0, "first"))
    assert presence(scene, "first") == [(0.0, True), (1.0, False)]
    assert presence(scene, "middle") == [(1.0, True)]
    # The row slides back while the dot makes room, with no jump when it enters.
    assert world_x(1.0, "last") == pytest.approx(world_x(0.999, "last"), abs=1e-2)


def test_overlapping_reorders_conflict_k0201() -> None:
    def body(s: k.Scene) -> None:
        row = k.Row(k.Square(), k.Square(), k.Square())
        s.add(row)
        s.start(row.swap(0, 1))
        s.play(row.swap(1, 2))

    diagnostic_of(body, "K0201")


def test_bar_value_drives_its_height() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        bar = k.Bar(5, unit=0.4)
        s.add(bar)
        seen.append((bar.value.now, bar.height.now))
        s.play(bar.value.to(2))
        seen.append((bar.value.now, bar.height.now))

    assert seen == [(5.0, pytest.approx(2.0)), (2.0, pytest.approx(0.8))]
    assert prop_at(scene, 1.0, "bar", "value") == 2.0


def test_bar_base_stays_fixed_while_value_changes() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        bar = k.Bar(1)
        s.add(bar)
        seen.append(bar.rect.bottom.now)
        s.play(bar.value.to(6))
        seen.append(bar.rect.bottom.now)

    assert seen[0] == pytest.approx(seen[1])


def test_bar_label_follows_value() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        bar = k.Bar(3, label=True)
        s.add(bar)
        seen.append(bar.label.text.now)
        s.play(bar.value.to(7))
        seen.append(bar.label.text.now)

    assert seen == ["3", "7"]


def test_bar_color_targets_its_rect() -> None:
    @build
    def scene(s: k.Scene) -> None:
        bar = k.Bar(3)
        s.add(bar)
        s.play(bar.to(color=k.RED))

    # The rect is unnamed (built by the Bar); look it up through the IR timeline.
    fills = [
        sig for sig in ir(scene)["signals"]
        if sig["owner"] and sig["owner"][1] == "fill" and any(e["k"] == "anim" for e in sig["timeline"])
    ]
    assert len(fills) == 1


def test_back_to_back_swaps_see_each_other_under_tempo() -> None:
    """Times cross into the core without losing bits: with `tempo(2)`, `1.4 + 0.2` is
    `1.5999999999999999`, and the next `row[j]` must see the swap that ends there."""
    final: list[float] = []

    @build
    def scene(s: k.Scene) -> None:
        row = k.Row(*[k.Bar(v) for v in [5, 2, 8, 1, 4]], gap=0.2, align="bottom")
        s.add(row)
        s.wait(1.2)
        n = len(row)
        with s.tempo(2):
            for i in range(n):
                for j in range(n - 1 - i):
                    if row[j].value.now > row[j + 1].value.now:
                        s.play(row.swap(j, j + 1), duration=0.4)
        final.extend(bar.value.now for bar in row)

    assert final == [1, 2, 4, 5, 8]
