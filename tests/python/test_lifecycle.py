"""Object lifecycle: created → in the scene → removed (K0101, K0102, K0103, K0104)."""

from __future__ import annotations

from typing import Any, Callable

import pytest

import kinemo as k
from conftest import build, diagnostic_of, inspect, ir, line_of, presence, raises_code, snapshot_of


def test_to_before_entering_is_k0101_with_entry_fixes() -> None:
    def body(s: k.Scene) -> None:
        c = k.Circle()
        s.play(c.to(x=2))  # K0101-here

    d = diagnostic_of(body, "K0101")
    assert d.spans[0].file == __file__
    assert d.spans[0].line == line_of("# K0101-here")
    assert d.time == 0.0
    assert d.objects == ["c"]
    codes = [f.code for f in d.fixes]
    assert "s.play(k.draw(c))" in codes
    assert "s.add(c)" in codes


def test_to_after_fade_out_is_k0102_with_exit_instant() -> None:
    def body(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.play(k.fade_out(c))
        s.play(c.to(x=2))  # K0102-here

    d = diagnostic_of(body, "K0102")
    assert d.spans[0].line == line_of("# K0102-here")
    assert d.time == 1.0
    assert "1.00" in d.message
    assert d.fixes


def test_k0102_points_at_the_exit_line() -> None:
    def body(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.play(k.fade_out(c))  # exit-here
        s.play(c.to(x=2))

    d = diagnostic_of(body, "K0102")
    assert line_of("# exit-here") in [span.line for span in d.spans]


def test_to_after_s_remove_is_k0102() -> None:
    def body(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.wait(1)
        s.remove(c)
        s.play(c.to(x=2))

    assert diagnostic_of(body, "K0102").time == 1.0


def test_add_and_remove_record_presence_at_cursor() -> None:
    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.wait(1)
        s.remove(c)
        s.wait(1)

    assert presence(scene, "c") == [(0.0, True), (1.0, False)]
    assert snapshot_of(scene, 0.5, "c")["present"] is True
    assert snapshot_of(scene, 1.5, "c")["present"] is False


def test_object_is_not_present_before_entering() -> None:
    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.wait(1)
        s.add(c)

    assert snapshot_of(scene, 0.5, "c")["present"] is False
    assert snapshot_of(scene, 1.0, "c")["present"] is True


def test_reentering_after_removal_allows_to_again() -> None:
    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.play(k.fade_out(c))
        s.play(k.fade_in(c))
        s.play(c.to(x=2))

    assert snapshot_of(scene, 0.5, "c")["present"] is True
    assert snapshot_of(scene, 1.5, "c")["present"] is True
    assert snapshot_of(scene, 3.0, "c")["props"]["x"] == {"Float": 2.0}


def test_entering_a_child_marks_its_ancestors_present() -> None:
    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        group = k.Group(c)
        outer = k.Group(group)
        s.add(c)

    for name in ("c", "group", "outer"):
        assert snapshot_of(scene, 0.0, name)["present"] is True


def test_entry_verb_on_a_child_marks_its_ancestors_present() -> None:
    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        group = k.Group(c)
        s.play(k.draw(c))

    assert presence(scene, "group") == [(0.0, True)]


def test_adding_a_group_adds_its_descendants() -> None:
    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        d = k.Dot()
        inner = k.Group(d)
        group = k.Group(c, inner)
        s.add(group)
        s.wait(1)
        s.remove(group)

    for name in ("c", "d", "inner", "group"):
        assert presence(scene, name) == [(0.0, True), (1.0, False)]


def test_second_parent_is_k0103_with_copy_and_reparent_fixes() -> None:
    def body(s: k.Scene) -> None:
        c = k.Circle()
        first = k.Group(c)
        second = k.Group(c)  # K0103-here

    d = diagnostic_of(body, "K0103")
    assert d.spans[0].line == line_of("# K0103-here")
    codes = " ".join(f.code or "" for f in d.fixes)
    assert "c.copy()" in codes
    assert "k.reparent" in codes


def test_copy_can_join_another_group() -> None:
    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        first = k.Group(c)
        second = k.Group(c.copy())
        s.add(first, second)

    assert snapshot_of(scene, 0.0, "second")["present"] is True


def test_group_cannot_contain_itself() -> None:
    def body(s: k.Scene) -> None:
        inner = k.Group()
        outer = k.Group(inner)
        k.Group(outer, inner)

    diagnostic_of(body, "K0103")


def test_creating_objects_outside_a_scene_is_k0104() -> None:
    with raises_code("K0104"):
        k.Circle()


def test_s_add_of_an_animation_is_k0105_with_play_fix() -> None:
    def body(s: k.Scene) -> None:
        s.add(k.draw(k.Circle()))  # type: ignore[arg-type]

    d = diagnostic_of(body, "K0105")
    assert any(f.code == "s.play(anim)" for f in d.fixes)


def test_assigning_a_prop_is_k0105_with_set_and_to_fixes() -> None:
    def body(s: k.Scene) -> None:
        c = k.Circle()
        c.x = 3

    d = diagnostic_of(body, "K0105")
    assert [f.code for f in d.fixes] == ["c.set(x=...)", "s.play(c.to(x=...))"]


@pytest.mark.parametrize("make", [lambda: k.Square(1), lambda: k.Text("hi"), lambda: k.Group(k.Square(1), k.Dot())])
def test_assigning_the_color_shorthand_is_k0105(make: Callable[[], k.Node]) -> None:
    def body(s: k.Scene) -> None:
        box = make()
        box.color = k.RED  # pyright: ignore[reportAttributeAccessIssue]

    d = diagnostic_of(body, "K0105")
    instant, animated = (str(f.code) for f in d.fixes)
    assert instant.endswith(".set(color=...)") and animated.endswith(".to(color=...))")


def test_objects_draw_in_the_order_they_enter() -> None:
    @build
    def scene(s: k.Scene) -> None:
        back = k.Circle()
        front = k.Square()
        s.add(front)
        s.add(back)
        s.remove(front)
        s.add(front)

    data = ir(scene)
    names = {o["id"]: o["name"] for o in data["objects"]}
    assert [names[r] for r in data["roots"]] == ["back", "front"]


def _world_center(scene: Any, t: float, node: k.Node) -> tuple[float, float]:
    entry = next(o for o in inspect(scene, t) if o["id"] == node._id)
    x0, y0, x1, y1 = entry["bbox"]
    return (x0 + x1) / 2, (y0 + y1) / 2


def test_reparent_keeps_the_children_of_a_moved_group_in_place() -> None:
    seen: dict[str, k.Node] = {}

    @build
    def scene(s: k.Scene) -> None:
        inner = k.Dot(r=0.2, x=1)
        card = k.Group(k.Square(1), inner, x=3, y=1)
        holder = k.Group(x=-2)
        s.add(card, holder)
        s.wait(0.5)
        s.play(k.reparent(card, holder))
        seen["inner"] = inner

    assert _world_center(scene, 1.0, seen["inner"]) == pytest.approx((4.0, 1.0))


def test_a_copied_group_keeps_its_children_in_place() -> None:
    seen: dict[str, k.Node] = {}

    @build
    def scene(s: k.Scene) -> None:
        inner = k.Dot(r=0.2, x=1)
        card = k.Group(k.Square(1), inner, x=3, y=1)
        s.add(card)
        twin = card.copy()
        s.add(twin)
        seen["inner"] = inner
        seen["twin_inner"] = twin.children[1]

    assert _world_center(scene, 0.0, seen["twin_inner"]) == pytest.approx(_world_center(scene, 0.0, seen["inner"]))


def test_objects_from_factories_carry_their_name_into_the_scene() -> None:
    @build
    def scene(s: k.Scene) -> None:
        hexagon = k.Polygon.regular(6)
        ax = k.Axes(x=(0, 4, 1), y=(0, 4, 1))
        curve = ax.plot(lambda x: x)
        limit = ax.vline(2)
        s.add(hexagon, ax)

    for name in ("hexagon", "curve", "limit"):
        assert presence(scene, name) == [(0.0, True)], name
