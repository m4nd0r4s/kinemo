"""Edge-case contracts (spec: "Defined behavior in edge cases"), one test per row.

Rows whose feature does not exist yet (events, components, morph, math, simulations,
voice, params export) are not listed; rows that exist but deviate are xfail.
"""

from __future__ import annotations

import importlib.util
import math
import pathlib
import random

import pytest

import kinemo as k
from conftest import build, diagnostic_of, line_of
from kinemo.lints import run_lints

EXAMPLES = pathlib.Path(__file__).resolve().parents[2] / "examples"


def test_row_01_to_outside_scene_is_k0101_with_entry_fixes() -> None:
    def body(s: k.Scene) -> None:
        c = k.Circle()
        s.play(c.to(x=1))

    codes = [f.code for f in diagnostic_of(body, "K0101").fixes]
    assert "s.play(k.draw(c))" in codes and "s.add(c)" in codes


def test_row_02_to_after_removal_is_k0102_with_exit_instant() -> None:
    def body(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.play(k.shrink(c))
        s.play(c.to(x=1))

    assert "t = 1.00 s" in diagnostic_of(body, "K0102").message


def test_row_03_same_prop_overlap_is_k0201_and_blend_add_sums() -> None:
    def conflict(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.start(c.to(x=1))
        s.play(c.to(x=2))

    assert len(diagnostic_of(conflict, "K0201").spans) == 2

    def additive(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.start(c.to(x=1))
        s.play(c.to(x=2, blend="add"))

    build(additive)


def test_row_04_entry_verb_in_during_is_k0204() -> None:
    def body(s: k.Scene) -> None:
        c = k.Circle()
        with s.during(k.draw(c)):
            pass

    diagnostic_of(body, "K0204")


def test_row_05_list_to_without_lerp_is_k0205_with_lerp_fix() -> None:
    def body(s: k.Scene) -> None:
        xs = k.signal([1.0, 2.0])
        s.play(xs.to([2.0, 3.0]))

    d = diagnostic_of(body, "K0205")
    assert any("lerp=" in (f.code or "") for f in d.fixes)

    def declared(s: k.Scene) -> None:
        xs = k.signal([1.0, 2.0], lerp=None)
        s.play(xs.to([2.0, 3.0]))

    build(declared)


def test_row_06_tracked_read_in_body_and_now_in_lambda() -> None:
    def tracked(s: k.Scene) -> None:
        k.signal(1.0)()

    def frozen(s: k.Scene) -> None:
        x = k.signal(1.0)
        k.Text(lambda: f"{x.now}")

    diagnostic_of(tracked, "K0301")
    diagnostic_of(frozen, "K0302")


def test_row_07_if_signal_and_math_sin_signal() -> None:
    def branch(s: k.Scene) -> None:
        if k.signal(1.0):
            pass

    def number(s: k.Scene) -> None:
        math.sin(k.signal(1.0))

    assert diagnostic_of(branch, "K0304").fixes[0].code == "if x.now > 2:"
    assert diagnostic_of(number, "K0305").fixes[0].code == "k.sin(x)"


def test_row_08_to_on_a_derived_is_k0303() -> None:
    def body(s: k.Scene) -> None:
        x = k.signal(1.0)
        s.play((x + 1).to(3))

    diagnostic_of(body, "K0303")


def test_row_09_animating_a_constrained_axis_is_k0401_with_fixes() -> None:
    def body(s: k.Scene) -> None:
        a = k.Square()
        b = k.Circle().place(below=a)
        s.add(a, b)
        s.play(b.to(x=1))

    d = diagnostic_of(body, "K0401")
    codes = " ".join(f.code or "" for f in d.fixes)
    assert ".to_place(" in codes and "unpin=True" in codes


def test_row_09_animating_a_bound_axis_is_k0401_with_unbind_fix() -> None:
    def body(s: k.Scene) -> None:
        a = k.Circle()
        b = k.Dot()
        s.add(a, b)
        b.set(x=a.x)
        s.play(b.to(x=3))

    d = diagnostic_of(body, "K0401")
    assert any("unbind" in (f.code or "") for f in d.fixes)


def test_row_10_constraint_cycle_is_k0402() -> None:
    @build
    def scene(s: k.Scene) -> None:
        a = k.Square()
        b = k.Circle().place(left_of=a)
        a.place(left_of=b)
        s.add(a, b)

    assert "K0402" in [d.code for d in run_lints(scene)]


def test_row_11_contradictory_constraints_are_k0403() -> None:
    def body(s: k.Scene) -> None:
        a = k.Square()
        k.Circle().place(left_of=a, right_of=a)

    diagnostic_of(body, "K0403")


def test_row_22_non_traceable_function_offers_native_and_k_python() -> None:
    def curve(h):  # type: ignore[no-untyped-def]
        return math.exp(h)

    def body(s: k.Scene) -> None:
        k.signal(1.0).map(curve)

    d = diagnostic_of(body, "K0310")
    assert len(d.fixes) == 2
    assert "k.python(curve)" in (d.fixes[1].code or "")


def test_row_23_second_parent_is_k0103() -> None:
    def body(s: k.Scene) -> None:
        c = k.Circle()
        k.Row(c)
        k.Column(c)

    diagnostic_of(body, "K0103")


def test_row_23_reparent_keeps_the_global_position() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        c = k.Circle(x=1.0, y=0.5)
        first = k.Group(c, x=-3.0)
        second = k.Group(x=2.0, y=1.0, scale=2.0)
        s.add(first, second)
        before = c.world.position.now
        s.play(k.reparent(c, second))
        seen["parent"] = c._parent is second
        seen["before"], seen["after"] = before, c.world.position.now
        s.play(c.to(color=k.RED))  # still animatable through the same Python object

    assert seen["parent"] is True
    assert seen["after"] == pytest.approx(seen["before"])


@pytest.mark.parametrize("name", ["Create", "ValueTracker", "UP"])
def test_row_26_manim_names_are_k11xx(name: str) -> None:
    with pytest.raises(k.KinemoError) as info:
        getattr(k, name)
    assert info.value.diagnostic.code.startswith("K11")


def test_row_27_random_is_seeded_per_scene() -> None:
    seen = []
    body = lambda s: seen.append(random.random())  # noqa: E731
    build(body)
    build(body)
    assert seen[0] == seen[1]


def test_row_31_play_with_at_behaves_like_start_and_lints_w0110() -> None:
    cursor = []

    def body(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.play(c.to(x=1), at=1)  # row-31
        cursor.append(s.cursor)

    scene = build(body)
    assert cursor == [0.0]
    (lint,) = scene.lints.items
    assert (lint.code, lint.spans[0].line) == ("W0110", line_of("# row-31"))


@pytest.mark.parametrize(
    "fn",
    [lambda h: 1.0 if h > 0 else 0.0, lambda h: math.sin(h), lambda h: int(h), lambda h: min(h, 2.0)],
    ids=["if", "math.sin", "int", "builtin-min"],
)
def test_row_33_python_constructs_inside_traced_function_are_k0310(fn) -> None:  # type: ignore[no-untyped-def]
    def body(s: k.Scene) -> None:
        k.signal(1.0).map(fn)

    diagnostic_of(body, "K0310")


def test_row_35_table_without_arrow_is_k1201() -> None:
    def body(s: k.Scene) -> None:
        k.interp(k.signal(1.0), object(), [1.0])

    d = diagnostic_of(body, "K1201")
    assert "object" in d.message


@pytest.mark.parametrize("example", ["hello", "bubble_sort"])
def test_spec_examples_build_and_render(example: str) -> None:
    path = EXAMPLES / f"{example}.py"
    spec = importlib.util.spec_from_file_location(f"example_{example}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    scene = getattr(module, example).build(size="720p")
    assert scene.duration > 1.0
    assert scene.builder.frame_png(scene.duration / 2).startswith(b"\x89PNG")
    assert [d.code for d in run_lints(scene) if d.level == "error"] == []
