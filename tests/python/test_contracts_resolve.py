"""Edge-case contracts of events, components, morphs, math and outputs (spec rows 12–21,
24, 25, 28–30, 32, 34). Rows 1–11, 22, 23, 26, 27, 31, 33 and 35 live in test_contracts.py."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any

import pytest

import kinemo as k
from conftest import build, diagnostic_of
from kinemo.cli.loader import build as build_with_lints
from kinemo.lints import run_lints


def lints_of(scene: Any) -> list[str]:
    return [d.code for d in run_lints(scene)]


def firing_times(scene: Any, source: Any) -> list[float]:
    from kinemo.events.resolve import collect

    return [f.t for f in collect(scene, scene.duration).get(source._id, [])]


# ---- 12: event → handler → signal → event loops ---------------------------------------

def test_row_12_event_loop_stops_after_8_passes_with_k0501() -> None:
    def body(s: k.Scene) -> None:
        target = k.signal(1.0)
        tick = k.EventSource(s, "tick")
        k.when(k.time >= target, tick)

        @tick.on
        def _(s: k.Scene, e: k.EventInfo) -> None:
            target.set(e.time + 0.1)  # every firing schedules the next one: no fixed point

        s.wait(4)

    d = diagnostic_of(body, "K0501")
    assert "8 passes" in d.message and "tick" in d.message


# ---- 13, 14: component channels -------------------------------------------------------

class Box(k.Component):
    box_width: float = 1.0
    level: k.Prop[float] = 0.5
    reading: k.Out[float]

    def build(self) -> k.Node:
        self.reading = self.level * 100
        return k.Rect(w=self.box_width, h=1.0)


def test_row_13_signal_into_static_field_is_k0601() -> None:
    def body(s: k.Scene) -> None:
        Box(box_width=k.signal(2.0))

    d = diagnostic_of(body, "K0601")
    assert "k.Prop" in (d.fixes[0].code or "")


def test_row_14_out_not_assigned_is_k0602() -> None:
    class Broken(k.Component):
        value: k.Out[float]

        def build(self) -> k.Node:
            return k.Circle()

    def body(s: k.Scene) -> None:
        Broken()

    diagnostic_of(body, "K0602")


# ---- 15, 16: wait_for ----------------------------------------------------------------

def test_row_15_wait_for_timeout_reports_the_maximum_reached() -> None:
    def body(s: k.Scene) -> None:
        x = k.signal(0.0)
        full = k.EventSource(s, "full")
        k.when(x >= 1.0, full)
        s.start(x.to(0.6), duration=2)
        s.wait_for(full, timeout=3)

    d = diagnostic_of(body, "K0702")
    assert "maximum 0.6" in d.message


def test_row_16_wait_for_an_event_already_past_is_k0703() -> None:
    def body(s: k.Scene) -> None:
        x = k.signal(0.0)
        full = k.EventSource(s, "full")
        k.when(x >= 1.0, full)
        s.play(x.to(1.0), duration=1)  # blocks past the event
        s.wait(0.5)
        s.wait_for(full, timeout=2)

    d = diagnostic_of(body, "K0703")
    assert "start" in (d.fixes[0].code or "")


# ---- 17: edge detection ----------------------------------------------------------------

def test_row_17_oscillating_condition_fires_only_on_edges() -> None:
    seen: dict[str, Any] = {}

    @build
    def scene(s: k.Scene) -> None:
        wave = k.sin(k.time * 2 * k.pi)  # crosses 0.5 twice per second
        hi = k.EventSource(s, "hi")
        k.when(wave > 0.5, hi)
        seen["src"] = hi
        s.wait(3)

    times = firing_times(scene, seen["src"])
    assert len(times) == 4  # once per period over 3.5 s (tail included), not once per frame
    assert times[0] == pytest.approx(1 / 12, abs=2e-3)


def test_row_17_rearm_adds_hysteresis() -> None:
    seen: dict[str, Any] = {}

    @build
    def scene(s: k.Scene) -> None:
        wave = k.sin(k.time * 2 * k.pi)
        hi = k.EventSource(s, "hi")
        k.when(wave > 0.5, hi, rearm=wave < -0.9)  # must dip below -0.9 to fire again
        seen["src"] = hi
        s.wait(3)

    assert len(firing_times(scene, seen["src"])) == 4

    @build
    def never_rearmed(s: k.Scene) -> None:
        wave = k.sin(k.time * 2 * k.pi)
        hi = k.EventSource(s, "hi")
        k.when(wave > 0.5, hi, rearm=wave < -2)  # impossible: fires once
        seen["src"] = hi
        s.wait(3)

    assert len(firing_times(never_rearmed, seen["src"])) == 1


# ---- 18, 19: morphs -------------------------------------------------------------------

def test_row_18_morph_without_correspondences_is_crossfade_with_w0801() -> None:
    @build
    def scene(s: k.Scene) -> None:
        a = k.Text("abc")
        b = k.Circle()
        s.add(a)
        s.play(k.morph(a, b))

    assert "W0801" in lints_of(scene)


def test_a_text_change_without_shared_characters_is_not_w0801() -> None:
    @build
    def scene(s: k.Scene) -> None:
        mark = k.Text("?")
        s.add(mark)
        for value in ("6", "100", "-3", "42"):
            s.play(mark.to(text=value), duration=0.3)

    assert "W0801" not in lints_of(scene)


def test_row_19_repeated_terms_pair_by_relative_position() -> None:
    from kinemo.anim.morph import pair_parts

    a = [("x", (0.0, 0.0)), ("+", (1.0, 0.0)), ("x", (2.0, 0.0))]
    b = [("x", (2.1, 1.0)), ("x", (-0.1, 1.0))]  # both x's moved and swapped order
    pairs = dict(pair_parts(a, b))
    assert pairs[0] in (0, 1) and pairs[2] in (0, 1) and pairs[0] != pairs[2]
    forced = dict(pair_parts(a, b, match={"+": "x"}))
    assert forced[1] == 0


# ---- 20: LaTeX ------------------------------------------------------------------------

def test_row_20_unsupported_latex_is_k0801_with_a_fix() -> None:
    def body(s: k.Scene) -> None:
        k.Math(r"\begin{tikzpicture}\end{tikzpicture}")

    d = diagnostic_of(body, "K0801")
    assert d.fixes and 'engine="tex"' in d.fixes[0].description


# ---- 21: thousands of objects -----------------------------------------------------------

def test_row_21_loop_creating_thousands_of_objects_is_w0901() -> None:
    @build
    def scene(s: k.Scene) -> None:
        dots = [k.Dot(x=i * 0.001) for i in range(1001)]
        s.add(*dots)

    assert "W0901" in lints_of(scene)


# ---- 24, 25: lints of handlers and clocks ------------------------------------------------

def test_row_24_object_created_in_handler_and_never_removed_is_w0701() -> None:
    @build
    def scene(s: k.Scene) -> None:
        x = k.signal(0.0)
        full = k.EventSource(s, "full")
        k.when(x >= 1.0, full)
        s.start(x.to(1.0))

        @full.on
        def _(s: k.Scene, e: k.EventInfo) -> None:
            s.play(k.fade_in(k.Text("full!")))

        s.wait(2)

    assert "W0701" in lints_of(scene)


def test_row_25_clock_animated_with_easing_is_w0312(tmp_path: Any) -> None:
    src = tmp_path / "clock.py"
    src.write_text(
        "import kinemo as k\n\n"
        "@k.scene\n"
        "def clock(s: k.Scene):\n"
        "    hour = k.signal(0.0)\n"
        "    soc = k.integrate(1.0, d=hour)\n"
        "    s.add(k.Text(lambda: f'{soc():.1f}'))\n"
        "    s.play(hour.to(24), duration=4)\n"
    , encoding="utf-8")
    from kinemo.cli.loader import find_scenes, load_module

    result = build_with_lints(find_scenes(load_module(str(src)))[0])
    w = [d for d in result.diagnostics if d.code == "W0312"]
    assert w and "linear" in (w[0].fixes[0].code or "")


# ---- 28: exception during dev keeps the last good build ----------------------------------

class FakeServer:
    def __init__(self) -> None:
        self.scenes: list[str] = []
        self.errors: list[Any] = []

    def set_scene(self, builder: Any, meta: str) -> int:
        self.scenes.append(meta)
        return len(self.scenes)

    def set_error(self, diagnostics: str) -> None:
        self.errors.append(json.loads(diagnostics))


def test_row_28_python_exception_in_dev_keeps_the_last_good_version(tmp_path: Any) -> None:
    from kinemo.cli.dev import Session

    path = tmp_path / "scene.py"
    path.write_text("import kinemo as k\n\n@k.scene\ndef scene(s: k.Scene):\n    s.add(k.Circle())\n", encoding="utf-8")
    server = FakeServer()
    session = Session(str(path), None, {}, server)  # type: ignore[arg-type]
    assert session.rebuild()
    path.write_text("import kinemo as k\n\n@k.scene\ndef scene(s: k.Scene):\n    1 / 0\n", encoding="utf-8")
    os.utime(path, None)
    assert not session.rebuild()
    assert len(server.scenes) == 1  # the good version stays published
    assert server.errors and "ZeroDivisionError" in json.dumps(server.errors[-1])


# ---- 29: a duration changing mid-scene ----------------------------------------------------

def _timeline(first_duration: float) -> tuple[list[tuple[float, float]], float]:
    @build
    def scene(s: k.Scene) -> None:
        a, b = k.Circle(), k.Square()
        s.add(a, b)
        s.play(a.to(x=2), duration=first_duration)
        s.mark("anchor")
        s.play(b.to(x=-2))
        s.start(a.to(y=1), at=1.5)  # anchored at an absolute instant

    spans = [(e.start, e.end) for e in scene._log]
    return spans, scene.marks["anchor"]


def test_row_29_changing_a_duration_pushes_what_comes_after() -> None:
    short, mark_short = _timeline(1.0)
    long, mark_long = _timeline(2.0)
    assert long[1][0] == pytest.approx(short[1][0] + 1.0)  # the next play moved
    assert mark_long == pytest.approx(mark_short + 1.0)  # marks follow the cursor
    anchored_short = [s for s in short if s[0] == pytest.approx(1.5)]
    anchored_long = [s for s in long if s[0] == pytest.approx(1.5)]
    assert anchored_short and anchored_long  # `at=` stays in place


# ---- 30: handler changing what a simulation reads ------------------------------------------

@dataclass
class Hit:
    v: float


class Body(k.State):
    x: float = 0.0
    hit: k.Event[Hit]


def test_row_30_handler_changing_simulation_input_recomputes_it() -> None:
    seen: dict[str, Any] = {}

    @build
    def scene(s: k.Scene) -> None:
        wind = k.signal(1.0)

        def step(st: Body, dt: float) -> Body:
            return st.replace(x=st.x + wind() * dt)

        sim = k.simulate(step, Body(), dt=1 / 60, until=4)
        finish = k.EventSource(s, "finish")
        k.when(sim.x >= 1.0, finish)

        @finish.on
        def _(s: k.Scene, e: k.EventInfo) -> None:
            s.start(wind.to(0.0), duration=0.01)  # the wind stops when x reaches 1

        s.start(sim)
        s.wait(4)
        seen["sim"] = sim

    end = json.loads(scene._b.eval_expr(json.dumps(seen["sim"].x._ir()), 3.9))["Float"]
    assert end == pytest.approx(1.0, abs=0.05)  # without the recompute it would reach ~3.9


# ---- 32, 34: parameters and interactive export ---------------------------------------------

def test_row_32_param_read_with_now_is_w1301() -> None:
    @build(params={"n": k.Int(3, 9, default=5)})
    def scene(s: k.Scene, n: Any) -> None:
        s.add(k.Polygon.regular(n.now))

    assert "W1301" in lints_of(scene)


def test_row_34_python_depending_on_a_param_is_w1302() -> None:
    @build(params={"f": k.Float(0.5, 2.0, default=1.0)})
    def scene(s: k.Scene, f: Any) -> None:
        y = (k.time * f).map(k.python(lambda v: v * 2))
        s.add(k.Dot(y=y))
        s.wait(1)

    assert "W1302" in lints_of(scene)


def test_dev_warns_when_two_builds_differ(tmp_path: Any, capsys: Any, monkeypatch: Any) -> None:
    from kinemo.cli import dev_session
    from kinemo.cli.dev import Session
    from test_dev_determinism import wait_for_checks

    # The check runs in the background after a quiet moment: no wait here, then join it.
    monkeypatch.setattr(dev_session, "DETERMINISM_IDLE_SECONDS", 0.0)

    path = tmp_path / "impure.py"
    path.write_text(
        "import itertools\nimport kinemo as k\n\n_counter = itertools.count()\n\n"
        "@k.scene\ndef scene(s: k.Scene):\n    s.add(k.Circle(r=1 + next(_counter)))\n"
    , encoding="utf-8")
    session = Session(str(path), None, {}, FakeServer())  # type: ignore[arg-type]
    assert session.rebuild()
    wait_for_checks()
    assert "gave different results" in capsys.readouterr().out
