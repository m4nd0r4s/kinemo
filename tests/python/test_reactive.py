"""Reactive system: signals, operators, tracing, guards (K03xx) and k.python tables."""

from __future__ import annotations

import math

import numpy as np
import pytest

import kinemo as k
from conftest import build, diagnostic_of, ir, line_of, prop_at, prop_timeline


# ---- signals -------------------------------------------------------------------------

def test_signal_now_set_and_to() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        x = k.signal(1.0)
        seen.append(x.now)
        x.set(5)
        seen.append(x.now)
        s.play(x.to(3))
        seen.append(x.now)

    assert seen == [1.0, 5.0, 3.0]


def test_signal_to_interpolates_over_time() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        x = k.signal(0.0)
        s.start(x.to(2, duration=2, ease=k.ease.linear))
        s.wait(1)
        seen.append(x.now)

    assert seen == [pytest.approx(1.0)]


def test_prop_signal_to_is_object_to() -> None:
    @build
    def scene(s: k.Scene) -> None:
        dot = k.Dot()
        s.add(dot)
        s.play(dot.x.to(3))
        dot.y.set(2)

    assert prop_at(scene, 1.0, "dot", "x") == 3.0
    assert prop_at(scene, 1.0, "dot", "y") == 2.0


def test_set_with_a_signal_creates_a_binding() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        a = k.Circle()
        b = k.Dot()
        s.add(a, b)
        b.set(scale=a.scale)
        s.play(a.to(scale=2))
        seen.append(b.scale.now)

    assert seen == [2.0]
    assert prop_at(scene, 0.5, "b", "scale") == pytest.approx(prop_at(scene, 0.5, "a", "scale"))


def test_unbind_keeps_current_value() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        a = k.Circle()
        b = k.Dot()
        s.add(a, b)
        b.set(scale=a.scale)
        s.play(a.to(scale=2))
        b.unbind("scale")
        s.play(a.to(scale=4))
        seen.append((a.scale.now, b.scale.now))

    assert seen == [(4.0, 2.0)]


# ---- operators build expressions evaluated natively ------------------------------------

def test_operators_build_native_expressions() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        x = k.signal(2.0)
        exprs = {
            "x * 2 + 1": x * 2 + 1,
            "1 - x": 1 - x,
            "2 ** x": 2**x,
            "x / 4": x / 4,
            "x % 2": x % 2,
            "-x": -x,
            "abs(-x)": abs(-x),
            "round(x / 3, 2)": round(x / 3, 2),
            "x > 1": x > 1,
            "x <= 1": x <= 1,
            "(x > 1) & (x < 3)": (x > 1) & (x < 3),
            "(x < 1) | (x > 3)": (x < 1) | (x > 3),
            "~(x > 1)": ~(x > 1),
        }
        for label, e in exprs.items():
            assert isinstance(e, k.Expr), label
        seen.update({label: e.now for label, e in exprs.items()})

    assert seen == {
        "x * 2 + 1": 5.0,
        "1 - x": -1.0,
        "2 ** x": 4.0,
        "x / 4": 0.5,
        "x % 2": 0.0,
        "-x": -2.0,
        "abs(-x)": 2.0,
        "round(x / 3, 2)": 0.67,
        "x > 1": True,
        "x <= 1": False,
        "(x > 1) & (x < 3)": True,
        "(x < 1) | (x > 3)": False,
        "~(x > 1)": False,
    }


def test_expression_follows_its_source_over_time() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        x = k.signal(1.0)
        doubled = x * 2
        seen.append(doubled.now)
        s.play(x.to(4))
        seen.append(doubled.now)

    assert seen == [2.0, 8.0]


def test_time_is_a_signal() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        clock = k.time * 90
        s.wait(2)
        seen.append(clock.now)

    assert seen == [180.0]


def test_computed_and_map_are_traced() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        a = k.signal(2.0)
        b = k.signal(3.0)
        total = k.computed(lambda: a() * b() + 1)
        squared = a.map(lambda v: v * v)
        seen.extend([total.now, squared.now])

    assert seen == [7.0, 4.0]


# ---- native functions are polymorphic ----------------------------------------------------

def test_native_functions_on_floats() -> None:
    assert k.where(True, 1.0, 2.0) == 1.0
    assert k.where(False, 1.0, 2.0) == 2.0
    assert k.clamp(5.0, 0.0, 1.0) == 1.0
    assert k.clamp(-1.0, 0.0, 1.0) == 0.0
    assert k.interp(5.0, [0.0, 10.0], [0.0, 100.0]) == 50.0
    assert k.interp(-1.0, [0.0, 10.0], [0.0, 100.0]) == 0.0
    assert k.interp(11.0, [0.0, 10.0], [0.0, 100.0]) == 100.0
    assert k.sin(0.0) == 0.0
    assert k.max(1.0, 3.0, 2.0) == 3.0
    assert k.min(1.0, 3.0, 2.0) == 1.0


def test_native_functions_on_arrays() -> None:
    xs = np.array([-1.0, 0.5, 2.0])
    np.testing.assert_allclose(k.clamp(xs, 0.0, 1.0), [0.0, 0.5, 1.0])
    np.testing.assert_allclose(k.where(xs > 0, 1.0, 0.0), [0.0, 1.0, 1.0])
    np.testing.assert_allclose(k.interp(xs, [0.0, 1.0], [0.0, 10.0]), [0.0, 5.0, 10.0])
    np.testing.assert_allclose(k.sin(xs), np.sin(xs))


def test_native_functions_on_signals() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        x = k.signal(5.0)
        exprs = [
            k.where(x > 2, 10.0, 20.0),
            k.clamp(x, 0.0, 1.0),
            k.interp(x, [0.0, 10.0], [0.0, 100.0]),
            k.sin(x),
            k.max(x, 7.0),
        ]
        assert all(isinstance(e, k.Expr) for e in exprs)
        seen.extend(e.now for e in exprs)
        s.play(x.to(1.0))
        seen.extend(e.now for e in exprs)

    assert seen[:5] == [10.0, 1.0, 50.0, pytest.approx(math.sin(5.0)), 7.0]
    assert seen[5:] == [20.0, 1.0, 10.0, pytest.approx(math.sin(1.0)), 7.0]


def test_same_function_works_with_floats_and_traced() -> None:
    def tariff(h):  # type: ignore[no-untyped-def]
        return k.where((h >= 18) & (h < 21), 1.8, 0.6)

    assert tariff(19.0) == 1.8
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        hour = k.signal(19.0)
        seen.append(hour.map(tariff).now)

    assert seen == [1.8]


# ---- reactive text ------------------------------------------------------------------------

def test_lambda_text_with_format_is_traced() -> None:
    seen = []

    @build
    def scene(s: k.Scene) -> None:
        x = k.signal(1.0)
        label = k.Text(lambda: f"{x():.1f} kWh")
        s.add(label)
        seen.append(label.text.now)
        s.play(x.to(2.5))
        seen.append(label.text.now)

    assert seen == ["1.0 kWh", "2.5 kWh"]
    (entry,) = prop_timeline(scene, "label", "text")
    assert entry["k"] == "set" and entry["src"]["k"] == "expr"
    assert prop_at(scene, 1.0, "label", "text") == "2.5 kWh"


# ---- guards against classic mistakes -------------------------------------------------------

def test_tracked_read_in_scene_body_is_k0301() -> None:
    def body(s: k.Scene) -> None:
        x = k.signal(1.0)
        x()  # K0301-here

    d = diagnostic_of(body, "K0301")
    assert d.spans[0].line == line_of("# K0301-here")
    assert d.fixes[0].code == "x.now"


def test_formatting_a_signal_in_scene_body_is_k0301() -> None:
    def body(s: k.Scene) -> None:
        x = k.signal(1.0)
        f"{x:.2f}"

    diagnostic_of(body, "K0301")


def test_now_inside_lambda_is_k0302() -> None:
    def body(s: k.Scene) -> None:
        x = k.signal(1.0)
        k.Text(lambda: str(x.now))  # K0302-here

    d = diagnostic_of(body, "K0302")
    assert d.spans[0].line == line_of("# K0302-here")
    assert "x()" in d.fixes[0].description


def test_signal_as_bool_is_k0304() -> None:
    def body(s: k.Scene) -> None:
        x = k.signal(1.0)
        if x:  # K0304-here
            pass

    d = diagnostic_of(body, "K0304")
    assert d.spans[0].line == line_of("# K0304-here")
    assert [f.code for f in d.fixes] == ["if x.now > 2:", "k.when(x > 2, ...)"]


@pytest.mark.parametrize("convert", [math.sin, float, int], ids=["math.sin", "float", "int"])
def test_signal_as_number_is_k0305(convert) -> None:  # type: ignore[no-untyped-def]
    def body(s: k.Scene) -> None:
        convert(k.signal(1.0))

    d = diagnostic_of(body, "K0305")
    assert any(f.code == "k.sin(x)" for f in d.fixes)


def test_to_on_a_derived_is_k0303() -> None:
    def body(s: k.Scene) -> None:
        x = k.signal(1.0)
        s.play((x + 1).to(3))

    diagnostic_of(body, "K0303")


def test_set_on_a_layout_derived_is_k0303() -> None:
    def body(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        c.left.set(1)

    diagnostic_of(body, "K0303")


def test_to_of_a_layout_derived_prop_is_k0303() -> None:
    def body(s: k.Scene) -> None:
        c = k.Circle()
        s.add(c)
        s.play(c.to(width=3))

    diagnostic_of(body, "K0303")


def test_non_traceable_function_is_k0310_pointing_inside_it() -> None:
    def curve(h):  # type: ignore[no-untyped-def]
        return math.sin(h)  # K0310-here

    def body(s: k.Scene) -> None:
        k.signal(1.0).map(curve)

    d = diagnostic_of(body, "K0310")
    assert "'curve'" in d.message
    assert d.spans[0].line == line_of("# K0310-here")
    assert any("k.python(curve)" in (f.code or "") for f in d.fixes)


@pytest.mark.parametrize(
    "fn",
    [
        lambda h: 1.0 if h > 1 else 0.0,
        lambda h: h > 0 and h < 2,
        lambda h: int(h),
        lambda h: min(h, 1.0),
        lambda h: math.floor(h),
    ],
    ids=["if", "and", "int", "builtin-min", "math.floor"],
)
def test_untraceable_constructs_are_k0310(fn) -> None:  # type: ignore[no-untyped-def]
    def body(s: k.Scene) -> None:
        k.signal(1.0).map(fn)

    diagnostic_of(body, "K0310")


def test_untraceable_lambda_in_a_prop_is_k0310() -> None:
    def body(s: k.Scene) -> None:
        x = k.signal(1.0)
        k.Text(lambda: "big" if x() > 1 else "small")

    d = diagnostic_of(body, "K0310")
    assert "k.where" in d.fixes[0].description


# ---- k.python ---------------------------------------------------------------------------------

def test_k_python_is_precomputed_into_a_table() -> None:
    calls = []

    def opaque(v: float) -> float:
        calls.append(v)
        return v * v

    @build
    def scene(s: k.Scene) -> None:
        x = k.signal(0.0)
        squared = x.map(k.python(opaque))
        c = k.Circle(r=squared)
        s.add(c)
        s.play(x.to(2, ease=k.ease.linear))

    (table,) = ir(scene)["tables"]
    fps = scene.config.fps
    assert table["dt"] == pytest.approx(1 / fps)
    assert len(table["values"]) == len(calls) == math.ceil(scene.duration * fps) + 1
    assert table["values"][0] == 0.0
    assert table["values"][-1] == pytest.approx(4.0)
    assert table["values"][int(fps / 2)] == pytest.approx(1.0)
    # The render reads the table; no Python call happens after the build.
    count = len(calls)
    scene.builder.frame_png(0.5)
    assert len(calls) == count


def test_k_python_vectorized_receives_the_whole_timeline() -> None:
    batches = []

    def opaque(values):  # type: ignore[no-untyped-def]
        batches.append(len(values))
        return values + 1

    @build
    def scene(s: k.Scene) -> None:
        x = k.signal(0.0)
        c = k.Circle(r=x.map(k.python(opaque, vectorized=True)))
        s.add(c)
        s.play(x.to(1))

    assert len(batches) == 1
    assert ir(scene)["tables"][0]["values"][0] == 1.0


def test_k_python_called_with_a_float_is_plain_python() -> None:
    assert k.python(lambda v: v + 1)(1.0) == 2.0
