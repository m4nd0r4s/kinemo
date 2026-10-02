"""Layout by constraints: place(at=/above=/below=/...), K0401, K0402, K0403, K0404."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build, diagnostic_of, line_of, position_at, prop_at, raises_code
from kinemo.lints import run_lints


def test_place_at_center_and_at_point() -> None:
    seen = {}

    @build
    def scene(s: k.Scene) -> None:
        centered = k.Circle().place(at="center")
        pointed = k.Dot().place(at=(2, 1))
        s.add(centered, pointed)
        seen["centered"] = (centered.x.now, centered.y.now)
        seen["pointed"] = (pointed.x.now, pointed.y.now)

    assert seen == {"centered": (0.0, 0.0), "pointed": (2.0, 1.0)}
    assert position_at(scene, 0.0, "pointed") == (2.0, 1.0)


def test_place_at_corner_sits_inside_the_safe_area() -> None:
    seen = {}

    @build
    def scene(s: k.Scene) -> None:
        corner = k.Dot().place(at="top-left")
        s.add(corner)
        seen["left"] = corner.left.now
        seen["top"] = corner.top.now
        seen["safe"] = s.frame.safe

    assert seen["left"] == pytest.approx(seen["safe"].left)
    assert seen["top"] == pytest.approx(seen["safe"].top)


@pytest.mark.parametrize(
    ("side", "gap"),
    [("above", 0.5), ("below", 0.5), ("above", 0.0), ("below", 1.25)],
)
def test_above_and_below_keep_the_gap(side: str, gap: float) -> None:
    seen = {}

    @build
    def scene(s: k.Scene) -> None:
        base = k.Square().place(at="center")
        other = k.Circle(r=0.5).place(**{side: base}, gap=gap)
        s.add(base, other)
        seen.update(
            base_top=base.top.now,
            base_bottom=base.bottom.now,
            other_top=other.top.now,
            other_bottom=other.bottom.now,
            other_x=other.x.now,
            base_x=base.x.now,
        )

    if side == "above":
        assert seen["other_bottom"] == pytest.approx(seen["base_top"] + gap)
    else:
        assert seen["other_top"] == pytest.approx(seen["base_bottom"] - gap)
    assert seen["other_x"] == pytest.approx(seen["base_x"])


def test_left_of_and_right_of_keep_the_gap() -> None:
    seen = {}

    @build
    def scene(s: k.Scene) -> None:
        base = k.Square()
        left = k.Dot().place(left_of=base, gap=0.3)
        right = k.Dot().place(right_of=base, gap=0.3)
        s.add(base, left, right)
        seen.update(base_left=base.left.now, base_right=base.right.now, left=left.right.now, right=right.left.now)

    assert seen["left"] == pytest.approx(seen["base_left"] - 0.3)
    assert seen["right"] == pytest.approx(seen["base_right"] + 0.3)


def test_x_now_and_left_now_reflect_placement() -> None:
    seen = {}

    @build
    def scene(s: k.Scene) -> None:
        base = k.Square()
        other = k.Circle(r=0.5).place(right_of=base, gap=0.25)
        s.add(base, other)
        seen.update(x=other.x.now, left=other.left.now, width=other.width.now)

    assert seen["left"] == pytest.approx(0.75)
    assert seen["width"] == pytest.approx(1.0)
    assert seen["x"] == pytest.approx(1.25)


def test_constraint_keeps_holding_while_the_reference_moves() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        base = k.Square()
        label = k.Text("hi").place(above=base)
        s.add(base, label)
        s.play(base.to(x=3))
        seen.append(label.x.now)

    assert seen == [pytest.approx(3.0)]
    assert position_at(scene, 0.5, "label")[0] == pytest.approx(position_at(scene, 0.5, "base")[0])


def test_animating_a_placed_axis_is_k0401_pointing_at_both_lines() -> None:
    def body(s: k.Scene) -> None:
        base = k.Triangle()
        title = k.Text("t").place(above=base)  # place-here
        s.add(base, title)
        s.play(title.to(x=3))  # K0401-here

    d = diagnostic_of(body, "K0401")
    assert [span.line for span in d.spans] == [line_of("# K0401-here"), line_of("# place-here")]
    assert all(span.file == __file__ for span in d.spans)
    codes = " ".join(f.code or "" for f in d.fixes)
    assert "title.to_place(" in codes
    assert "title.to(x=..., unpin=True)" in codes
    assert d.objects == ["title"]


def test_set_on_a_placed_axis_is_k0401() -> None:
    def body(s: k.Scene) -> None:
        base = k.Square()
        title = k.Text("t").place(below=base)
        s.add(base, title)
        title.set(y=2)

    diagnostic_of(body, "K0401")


def test_unpinned_axes_other_than_position_still_animate() -> None:
    @build
    def scene(s: k.Scene) -> None:
        base = k.Square()
        title = k.Text("t").place(above=base)
        s.add(base, title)
        s.play(title.to(scale=2, color=k.RED))

    assert prop_at(scene, 1.0, "title", "scale") == 2.0


def test_to_place_changes_constraint_animated() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        base = k.Square()
        title = k.Circle(r=0.5).place(above=base)
        s.add(base, title)
        s.play(title.to(place=dict(right_of=base)))
        seen.append((title.left.now, base.right.now, title.y.now))

    ((left, base_right, y),) = seen
    assert left == pytest.approx(base_right + 0.25)
    assert y == pytest.approx(0.0)
    halfway = position_at(scene, 0.5, "title")[1]
    assert 0.0 < halfway < 1.25


def test_to_place_takes_timing_like_to() -> None:
    @build
    def scene(s: k.Scene) -> None:
        base = k.Square()
        title = k.Circle(r=0.5).place(above=base)
        s.add(base, title)
        s.play(title.to_place(right_of=base, gap=0.5, duration=2))

    assert scene.duration == pytest.approx(2.0 + scene.config.tail)
    assert position_at(scene, 2.0, "title") == pytest.approx((1.5, 0.0))
    assert 0.0 < position_at(scene, 1.0, "title")[1] < 1.25


def test_to_with_unpin_releases_where_the_animation_starts() -> None:
    @build
    def scene(s: k.Scene) -> None:
        base = k.Square()
        title = k.Circle(r=0.5).place(above=base, gap=0.5)
        s.add(base, title)
        s.wait(1)
        s.play(title.to(x=3, unpin=True))

    assert position_at(scene, 1.0, "title") == pytest.approx((0.0, 1.5))
    assert position_at(scene, 1.5, "title")[0] == pytest.approx(1.5, abs=0.75)
    assert position_at(scene, 2.0, "title") == pytest.approx((3.0, 1.5))


def test_unpin_keeps_position_then_animates() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        base = k.Square()
        title = k.Circle(r=0.5).place(above=base, gap=0.5)
        s.add(base, title)
        title.unpin()
        seen.append((title.x.now, title.y.now))
        s.play(title.to(x=3))
        seen.append((title.x.now, title.y.now))

    assert seen == [(0.0, 1.5), (3.0, 1.5)]


def test_animating_a_container_child_axis_is_k0401() -> None:
    def body(s: k.Scene) -> None:
        a = k.Circle()
        row = k.Row(a, k.Dot())
        s.add(row)
        s.play(a.to(x=3))

    d = diagnostic_of(body, "K0401")
    assert "container" in d.message


def test_contradictory_sides_are_k0403() -> None:
    def body(s: k.Scene) -> None:
        base = k.Square()
        k.Circle().place(left_of=base, right_of=base)  # K0403-here

    d = diagnostic_of(body, "K0403")
    assert d.spans[0].line == line_of("# K0403-here")
    assert any("weak=True" in f.description for f in d.fixes)


def test_two_sides_on_different_axes_in_one_call_is_k0105() -> None:
    def body(s: k.Scene) -> None:
        base = k.Square()
        k.Circle().place(left_of=base, above=base)

    diagnostic_of(body, "K0105")


def test_placing_relative_to_itself_is_k0402() -> None:
    def body(s: k.Scene) -> None:
        c = k.Circle()
        c.place(below=c)

    diagnostic_of(body, "K0402")


def test_constraint_cycle_is_reported_as_k0402_after_build() -> None:
    @build
    def scene(s: k.Scene) -> None:
        a = k.Square()
        b = k.Circle().place(below=a)
        a.place(below=b)
        s.add(a, b)

    found = [d for d in run_lints(scene) if d.code == "K0402"]
    assert found
    assert "a" in found[0].message and "b" in found[0].message


def test_unknown_anchor_is_k0404() -> None:
    with raises_code("K0404"):
        build(lambda s: k.Circle().place(at="middle"))


def test_unknown_place_argument_is_k0105() -> None:
    with raises_code("K0105"):
        build(lambda s: k.Circle().place(at="center", padding=1))
