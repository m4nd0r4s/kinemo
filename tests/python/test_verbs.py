"""Verbs: scheduling, presence, render-only ramps, K0204 in during, K0201 conflicts."""

from __future__ import annotations

from typing import Callable

import pytest

import kinemo as k

FIXTURES = __import__("pathlib").Path(__file__).resolve().parents[1] / "fixtures"
from conftest import animations, build, diagnostic_of, ir, line_of, presence, prop_timeline, snapshot_of

ENTRY_VERBS: dict[str, Callable[[k.Node], k.Animation]] = {
    "draw": lambda o: k.draw(o),
    "write": lambda o: k.write(o),
    "fade_in": lambda o: k.fade_in(o),
    "grow": lambda o: k.grow(o),
}

EXIT_VERBS: dict[str, Callable[[k.Node], k.Animation]] = {
    "fade_out": lambda o: k.fade_out(o),
    "shrink": lambda o: k.shrink(o),
}


@pytest.mark.parametrize("verb", sorted(ENTRY_VERBS))
def test_entry_verb_enters_at_its_start_and_lasts_one_second(verb: str) -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        s.wait(0.5)
        obj = k.Text("hi")
        seen.append(s.play(ENTRY_VERBS[verb](obj)))
        s.play(obj.to(x=1))

    (span,) = seen
    assert (span.start, span.end) == (0.5, 1.5)
    assert presence(scene, "obj") == [(0.5, True)]
    assert snapshot_of(scene, 0.25, "obj")["present"] is False


@pytest.mark.parametrize("verb", sorted(EXIT_VERBS))
def test_exit_verb_leaves_at_its_end(verb: str) -> None:
    @build
    def scene(s: k.Scene) -> None:
        obj = k.Circle()
        s.add(obj)
        s.play(EXIT_VERBS[verb](obj), duration=2)

    assert presence(scene, "obj") == [(0.0, True), (2.0, False)]
    assert snapshot_of(scene, 1.0, "obj")["present"] is True


@pytest.mark.parametrize("verb", sorted(EXIT_VERBS))
def test_exit_verb_on_object_outside_the_scene_is_k0101(verb: str) -> None:
    def body(s: k.Scene) -> None:
        obj = k.Circle()
        s.play(EXIT_VERBS[verb](obj))

    diagnostic_of(body, "K0101")


@pytest.mark.parametrize(
    ("verb", "prop", "kind"),
    [("draw", "_draw", k.Circle), ("write", "_write", k.Text), ("write", "_draw", k.Circle), ("fade_in", "_fade", k.Circle), ("grow", "_grow", k.Circle)],
)
def test_entry_verbs_ramp_a_render_only_prop(verb: str, prop: str, kind: type) -> None:
    @build
    def scene(s: k.Scene) -> None:
        obj = kind(name="obj")
        s.play(ENTRY_VERBS[verb](obj))

    (ramp,) = [e for e in prop_timeline(scene, "obj", prop) if e["k"] == "anim"]
    assert (ramp["t0"], ramp["t1"]) == (0.0, 1.0)
    assert ramp["from"]["v"] == {"Float": 0.0}
    assert ramp["to"]["v"] == {"Float": 1.0}


def test_draw_of_a_group_draws_every_leaf_and_enters_the_group() -> None:
    @build
    def scene(s: k.Scene) -> None:
        a = k.Circle()
        b = k.Square()
        group = k.Group(a, b)
        s.play(k.draw(group))

    assert animations(scene, "a", "_draw") == [(0.0, 1.0)]
    assert animations(scene, "b", "_draw") == [(0.0, 1.0)]
    assert presence(scene, "group") == [(0.0, True)]


def test_fade_in_with_shift_arrives_from_minus_shift() -> None:
    @build
    def scene(s: k.Scene) -> None:
        obj = k.Circle()
        s.play(k.fade_in(obj, shift=(0, 1)))

    (ramp,) = [e for e in prop_timeline(scene, "obj", "_shift") if e["k"] == "anim"]
    assert ramp["from"]["v"] == {"Vec2": [-0.0, -1.0]}
    assert ramp["to"]["v"] == {"Vec2": [0.0, 0.0]}


def test_fade_in_of_several_objects() -> None:
    @build
    def scene(s: k.Scene) -> None:
        a = k.Circle()
        b = k.Square()
        s.play(k.fade_in(a, b))

    assert presence(scene, "a") == presence(scene, "b") == [(0.0, True)]


def test_grow_from_a_side_records_the_origin() -> None:
    @build
    def scene(s: k.Scene) -> None:
        obj = k.Square()
        s.play(k.grow(obj, from_="bottom"))

    (origin,) = prop_timeline(scene, "obj", "_grow_from")
    assert origin["src"]["v"] == {"Vec2": [0.0, -1.0]}


def test_grow_from_an_unknown_side_is_k0404() -> None:
    def body(s: k.Scene) -> None:
        k.grow(k.Square(), from_="middle")

    diagnostic_of(body, "K0404")


def test_exit_verbs_restore_render_props_after_leaving() -> None:
    @build
    def scene(s: k.Scene) -> None:
        obj = k.Circle()
        s.add(obj)
        s.play(k.fade_out(obj))

    timeline = prop_timeline(scene, "obj", "_fade")
    assert timeline[-1]["k"] == "set" and timeline[-1]["t"] == 1.0
    assert timeline[-1]["src"]["v"] == {"Float": 1.0}


def test_indicate_keeps_presence_and_returns_to_initial_state() -> None:
    @build
    def scene(s: k.Scene) -> None:
        obj = k.Circle()
        s.add(obj)
        s.play(k.indicate(obj, scale=1.5))
        s.play(obj.to(x=1))

    pulse = [e for e in prop_timeline(scene, "obj", "_pulse") if e["k"] == "anim"]
    assert [(e["t0"], e["t1"]) for e in pulse] == [(0.0, 0.5), (0.5, 1.0)]
    assert pulse[-1]["to"]["v"] == {"Float": 1.0}
    assert presence(scene, "obj") == [(0.0, True)]


def test_indicate_on_object_outside_the_scene_is_k0101() -> None:
    def body(s: k.Scene) -> None:
        s.play(k.indicate(k.Circle()))

    diagnostic_of(body, "K0101")


def test_indicate_is_reversible_inside_during() -> None:
    @build
    def scene(s: k.Scene) -> None:
        obj = k.Circle()
        s.add(obj)
        with s.during(k.indicate(obj)):
            s.wait(1)

    pulse = [e for e in prop_timeline(scene, "obj", "_pulse") if e["k"] == "anim"]
    assert [(e["t0"], e["t1"]) for e in pulse] == [(0.0, 1.0), (2.0, 3.0)]


@pytest.mark.parametrize("verb", sorted({**ENTRY_VERBS, **EXIT_VERBS}))
def test_entry_and_exit_verbs_in_during_are_k0204(verb: str) -> None:
    def body(s: k.Scene) -> None:
        obj = k.Circle()
        s.add(obj)
        with s.during({**ENTRY_VERBS, **EXIT_VERBS}[verb](obj)):
            pass

    d = diagnostic_of(body, "K0204")
    assert d.fixes


def test_verbs_inside_the_during_body_are_allowed() -> None:
    @build
    def scene(s: k.Scene) -> None:
        a = k.Circle()
        b = k.Square()
        s.add(a)
        with s.during(a.to(color=k.YELLOW)):
            s.play(k.draw(b))

    assert presence(scene, "b") == [(1.0, True)]


def test_overlapping_animations_on_the_same_prop_are_k0201_with_both_lines() -> None:
    def body(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.start(c.to(x=1, duration=2))  # first-here
        s.play(c.to(x=2))  # second-here

    d = diagnostic_of(body, "K0201")
    assert [span.line for span in d.spans] == [line_of("# second-here"), line_of("# first-here")]
    assert any('blend="add"' in (f.code or "") for f in d.fixes)


def test_blend_add_allows_overlapping_animations() -> None:
    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.start(c.to(x=1, duration=2))
        s.play(c.to(x=0.5, blend="add"))

    blends = [e["blend"] for e in prop_timeline(scene, "c", "x")]
    assert blends == ["replace", "add"]


def test_back_to_back_animations_do_not_conflict() -> None:
    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.play(c.to(x=1))
        s.play(c.to(x=2))

    assert animations(scene, "c", "x") == [(0.0, 1.0), (1.0, 2.0)]


def test_different_props_may_overlap() -> None:
    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.start(c.to(x=1))
        s.play(c.to(y=1))

    assert animations(scene, "c", "x") == animations(scene, "c", "y") == [(0.0, 1.0)]


def test_invalid_blend_is_k0105() -> None:
    def body(s: k.Scene) -> None:
        c = k.Circle()
        c.to(x=1, blend="mul")

    diagnostic_of(body, "K0105")


def test_verbs_reject_non_objects() -> None:
    def body(s: k.Scene) -> None:
        k.draw("circle")  # type: ignore[arg-type]

    diagnostic_of(body, "K0105")


def test_verb_duration_and_delay() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        obj = k.Circle()
        seen.append(s.play(k.draw(obj, duration=2, delay=0.5)))

    assert (seen[0].start, seen[0].end) == (0.0, 2.5)
    assert animations(scene, "obj", "_draw") == [(0.5, 2.5)]
    assert presence(scene, "obj") == [(0.5, True)]


def test_sound_is_scheduled_at_the_cursor() -> None:
    @build
    def scene(s: k.Scene) -> None:
        s.wait(1)
        s.play(k.sound(str(FIXTURES / "click.wav"), gain=0.5))

    (clip,) = ir(scene)["audio"]
    assert clip["t"] == 1.0
