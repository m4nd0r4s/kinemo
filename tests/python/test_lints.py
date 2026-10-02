"""Post-build lints: visual (W10xx, sampled by the core) and code (W03xx, from the AST).

Visual lints are checked through `run_lints`, the entry point `kinemo check` uses, so
messages, spans, inline allows and fixes are exercised end to end. Code lints read the
scene function's source, so the offending lines carry a trailing marker comment.
"""

from __future__ import annotations

import importlib.util
import json
import textwrap
from pathlib import Path
from typing import Any

import kinemo as k
from kinemo.diagnostics import Diagnostic
from kinemo.lints import run_lints
from kinemo.linting import code_diagnostics

from conftest import build, line_of


def lints_of(scene: Any, code: str, scene_fn: Any = None) -> list[Diagnostic]:
    return [d for d in run_lints(scene, scene_fn) if d.code == code]


def only_one(diagnostics: list[Diagnostic]) -> Diagnostic:
    assert len(diagnostics) == 1, [d.render() for d in diagnostics]
    return diagnostics[0]


# ---- core JSON ------------------------------------------------------------------------


def test_core_reports_findings_as_json() -> None:
    def scene(s: k.Scene) -> None:
        box = k.Rect(w=1, h=1, x=7.8)
        s.add(box)
        s.wait(1)

    findings = json.loads(build(scene).builder.visual_lints(0.1))
    assert [f["code"] for f in findings] == ["W1001"]
    f = findings[0]
    assert f["t"] == 0.0
    assert f["details"] == {"kind": "safe_area", "edge": "right", "overshoot": f["details"]["overshoot"]}
    assert abs(f["details"]["overshoot"] - 0.8) < 1e-6
    assert f["fix"]["kind"] == "place_with_clamp"


def test_clean_scene_has_no_visual_lints() -> None:
    def scene(s: k.Scene) -> None:
        title = k.Text("Hello, kinemo").place(at="center")
        s.play(k.write(title))
        s.wait(1)

    assert [d.code for d in run_lints(build(scene)) if d.code.startswith("W10")] == []


# ---- W1001 ----------------------------------------------------------------------------


def test_w1001_points_at_the_object_and_names_the_edge() -> None:
    def scene(s: k.Scene) -> None:
        box = k.Rect(w=1, h=1, x=7.8)  # w1001-box
        s.add(box)
        s.wait(1)

    d = only_one(lints_of(build(scene), "W1001"))
    assert d.level == "warning"
    assert d.message == "box leaves the safe area (right, 0.8 u)"
    assert d.spans[0].line == line_of("# w1001-box")
    assert d.objects == ["box"]
    assert d.time == 0.0
    assert "clamp=True" in (d.fixes[0].code or "")


def test_w1001_on_a_placed_object_fixes_the_place_call() -> None:
    def scene(s: k.Scene) -> None:
        badge = k.Rect(w=1, h=1)
        badge.place(at="top", margin=0)  # w1001-place
        s.add(badge)
        s.wait(1)

    d = only_one(lints_of(build(scene), "W1001"))
    place_line = line_of("# w1001-place")
    assert [s.line for s in d.spans][1:] == [place_line]
    (edit,) = d.fixes[0].edits
    assert edit.line == place_line
    assert edit.replacement.strip().startswith('badge.place(at="top", margin=0, clamp=True)')


def test_w1001_inline_allow() -> None:
    def scene(s: k.Scene) -> None:
        box = k.Rect(w=1, h=1, x=7.8)  # kinemo: allow W1001
        s.add(box)
        s.wait(1)

    assert lints_of(build(scene), "W1001") == []


def test_w1001_clamp_fix_produces_a_scene_without_the_lint(tmp_path: Path) -> None:
    source = textwrap.dedent(
        """
        import kinemo as k

        @k.scene
        def edge(s: k.Scene):
            badge = k.Rect(w=1, h=1)
            badge.place(at="top", margin=0)
            s.add(badge)
            s.wait(1)
        """
    )
    path = tmp_path / "edge_scene.py"
    path.write_text(source, encoding="utf-8")

    def load() -> Any:
        spec = importlib.util.spec_from_file_location(f"edge_scene_{len(path.read_text())}", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.edge

    definition = load()
    d = only_one(lints_of(definition.build(), "W1001", definition))
    (edit,) = d.fixes[0].edits
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[edit.line - 1] = edit.replacement
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    fixed = load()
    assert lints_of(fixed.build(), "W1001", fixed) == []


def test_w1001_ignores_entrances_from_off_frame() -> None:
    def scene(s: k.Scene) -> None:
        box = k.Rect(w=1, h=1, x=12)
        s.add(box)
        s.play(box.to(x=0, duration=1))
        s.wait(1)

    assert lints_of(build(scene), "W1001") == []


# ---- W1002 – W1004 --------------------------------------------------------------------


def test_w1002_text_over_text() -> None:
    def scene(s: k.Scene) -> None:
        a = k.Text("First")  # w1002-a
        b = k.Text("Second", x=0.3)
        s.add(a, b)
        s.wait(1)

    d = only_one(lints_of(build(scene), "W1002"))
    assert d.objects == ["a", "b"]
    assert d.message.startswith("text over text: a and b overlap")
    assert d.spans[0].line == line_of("# w1002-a")


def test_w1002_not_reported_for_separate_texts() -> None:
    def scene(s: k.Scene) -> None:
        a = k.Text("First")
        b = k.Text("Second").place(below=a, gap=0.3)
        s.add(a, b)
        s.wait(1)

    assert lints_of(build(scene), "W1002") == []


def test_w1003_low_contrast_against_the_background() -> None:
    def scene(s: k.Scene) -> None:
        hint = k.Text("almost invisible", color=k.rgb(0.15, 0.15, 0.17))
        s.add(hint)
        s.wait(1)

    d = only_one(lints_of(build(scene), "W1003"))
    assert d.message.startswith("low contrast: hint has ")
    assert d.message.endswith(":1 against the background (minimum 4.5:1)")


def test_w1003_fade_in_is_not_low_contrast() -> None:
    def scene(s: k.Scene) -> None:
        title = k.Text("Hello")
        s.play(k.fade_in(title, duration=1))
        s.wait(1)

    assert lints_of(build(scene), "W1003") == []


def test_w1004_small_text_in_pixels() -> None:
    def scene(s: k.Scene) -> None:
        note = k.Text("footnote", size=0.1)
        s.add(note)
        s.wait(1)

    d = only_one(lints_of(build(scene), "W1004"))
    assert d.message == "small text: note is 12 px at the final resolution (minimum 18 px)"


# ---- W1005 – W1007 --------------------------------------------------------------------


def test_w1005_invisible_object_never_removed() -> None:
    def scene(s: k.Scene) -> None:
        ghost = k.Rect(w=1, h=1)
        s.add(ghost)
        s.play(ghost.to(opacity=0, duration=0.5))
        s.wait(4)

    d = only_one(lints_of(build(scene), "W1005"))
    assert d.objects == ["ghost"]
    assert "is invisible for" in d.message and "(opacity 0) and never removed" in d.message
    assert d.fixes[0].code == "s.remove(ghost)"


def test_w1005_not_reported_when_removed() -> None:
    def scene(s: k.Scene) -> None:
        ghost = k.Rect(w=1, h=1)
        s.add(ghost)
        s.play(k.fade_out(ghost, duration=0.5))
        s.wait(4)

    assert lints_of(build(scene), "W1005") == []


def test_w1006_many_short_animations() -> None:
    def scene(s: k.Scene) -> None:
        dots = [k.Dot(x=-6 + i) for i in range(13)]
        s.add(*dots)
        s.play(k.par(*[d.to(y=1, duration=0.2) for d in dots]))
        s.wait(0.5)

    d = only_one(lints_of(build(scene), "W1006"))
    assert d.message == "visual noise: 13 short animations (< 0.3 s) at the same time"
    assert len(d.objects) == 13


def test_w1007_long_static_stretch() -> None:
    def scene(s: k.Scene) -> None:
        box = k.Rect(w=1, h=1)
        s.add(box)
        s.play(box.to(x=1, duration=1))
        s.wait(9)

    d = only_one(lints_of(build(scene), "W1007"))
    assert d.time == 1.0
    assert d.message.startswith("static scene: ")
    assert d.message.endswith(" s without any visual change")


def test_w1007_time_bound_motion_is_a_change() -> None:
    def scene(s: k.Scene) -> None:
        spinner = k.Rect(w=1, h=1, rotate=k.Time() * 30)
        s.add(spinner)
        s.wait(9)

    assert lints_of(build(scene), "W1007") == []


# ---- W0310 ----------------------------------------------------------------------------


def test_w0310_lambda_in_loop_captures_the_loop_variable() -> None:
    def scene(s: k.Scene) -> None:
        for i in range(3):
            s.add(k.Dot(x=lambda: i * 1.0))  # w0310-loop

    d = only_one([x for x in code_diagnostics(scene_fn=scene) if x.code == "W0310"])
    line = line_of("# w0310-loop")
    assert d.spans[0].line == line
    assert "'i'" in d.message and "late binding" in d.message
    (edit,) = d.fixes[0].edits
    assert edit.line == line
    assert "k.Dot(x=lambda i=i: i * 1.0)" in edit.replacement


def test_w0310_default_argument_and_immediate_calls_are_fine() -> None:
    def scene(s: k.Scene) -> None:
        for i in range(3):
            s.add(k.Dot(x=lambda i=i: i * 1.0))
            order = sorted([3, 1], key=lambda v: v + i)
            assert order

    assert [d for d in code_diagnostics(scene_fn=scene) if d.code == "W0310"] == []


def test_w0310_in_comprehension_keeps_existing_parameters() -> None:
    def scene(s: k.Scene) -> None:
        fns = [lambda t: t + n for n in range(3)]  # w0310-comp
        assert fns

    d = only_one([x for x in code_diagnostics(scene_fn=scene) if x.code == "W0310"])
    assert "lambda t, n=n: t + n" in d.fixes[0].edits[0].replacement


def test_w0310_found_from_object_spans_by_run_lints() -> None:
    def scene(s: k.Scene) -> None:
        for i in range(2):
            s.add(k.Text(lambda: f"{i}"))  # w0310-run

    diagnostics = [d for d in run_lints(build(scene)) if d.code == "W0310"]
    assert [d.spans[0].line for d in diagnostics] == [line_of("# w0310-run")]


def test_w0310_inline_allow() -> None:
    def scene(s: k.Scene) -> None:
        for i in range(3):
            s.add(k.Dot(x=lambda: i * 1.0))  # kinemo: allow W0310

    assert [d for d in code_diagnostics(scene_fn=scene) if d.code == "W0310"] == []


# ---- W0311 ----------------------------------------------------------------------------


def test_w0311_lambda_captures_a_list_mutated_later() -> None:
    def scene(s: k.Scene) -> None:
        items = [1, 2]  # w0311-list
        s.add(k.Text(lambda: f"{len(items)} itens"))  # w0311-lambda
        items.append(3)

    d = only_one([x for x in code_diagnostics(scene_fn=scene) if x.code == "W0311"])
    assert [s.line for s in d.spans] == [line_of("# w0311-lambda"), line_of("# w0311-list")]
    assert "'items'" in d.message
    (edit,) = d.fixes[0].edits
    assert edit.line == line_of("# w0311-list")
    assert "items = k.list([1, 2])" in edit.replacement


def test_w0311_unmutated_list_is_fine() -> None:
    def scene(s: k.Scene) -> None:
        items = [1, 2]
        items.append(0)
        s.add(k.Text(lambda: f"{len(items)} itens"))

    assert [d for d in code_diagnostics(scene_fn=scene) if d.code == "W0311"] == []


def test_w0311_mutation_in_the_same_loop_counts() -> None:
    def scene(s: k.Scene) -> None:
        seen = []
        for i in range(3):
            seen.append(i)
            s.add(k.Text(lambda i=i: f"{seen}"))  # w0311-loop

    d = only_one([x for x in code_diagnostics(scene_fn=scene) if x.code == "W0311"])
    assert d.spans[0].line == line_of("# w0311-loop")


# ---- W0312 ----------------------------------------------------------------------------


def test_w0312_eased_clock() -> None:
    def scene(s: k.Scene) -> None:
        clock = k.signal(0.0)
        energy = k.integrate(k.signal(1.0), d=clock)  # type: ignore[attr-defined]
        s.play(clock.to(10, duration=10))  # w0312-to
        assert energy

    d = only_one([x for x in code_diagnostics(scene_fn=scene) if x.code == "W0312"])
    assert d.spans[0].line == line_of("# w0312-to")
    (edit,) = d.fixes[0].edits
    assert "clock.to(10, duration=10, ease=k.ease.linear)" in edit.replacement


def test_w0312_linear_clock_is_fine() -> None:
    def scene(s: k.Scene) -> None:
        clock = k.signal(0.0)
        energy = k.integrate(k.signal(1.0), d=clock)  # type: ignore[attr-defined]
        s.play(clock.to(10, duration=10, ease=k.ease.linear))
        other = k.signal(0.0)
        s.play(other.to(1))
        assert energy

    assert [d for d in code_diagnostics(scene_fn=scene) if d.code == "W0312"] == []
