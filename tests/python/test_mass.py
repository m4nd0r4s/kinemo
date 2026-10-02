"""Mass objects: `k.Points`, `k.VectorField`, `k.StreamLines` and the W0901 lint.

Per-point functions are traced once with the symbolic point `p` and evaluated natively;
the render never calls back into Python.
"""

from __future__ import annotations

import os
import time
from typing import Any

import numpy as np
import pytest

import kinemo as k
from kinemo.cli.main import main as cli_main
from kinemo.lints import run_lints

from conftest import build, ir, line_of, object_ir, raises_code

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "..", "examples", "field.py")


def spread(n: int, seed: int = 0) -> Any:
    """`n` points spread over most of the frame, as an `(n, 2)` array."""
    return np.random.default_rng(seed).uniform((-6.5, -3.5), (6.5, 3.5), size=(n, 2))


def ops_in(expr: Any) -> list[str]:
    """Every `op` in an IR expression tree."""
    if isinstance(expr, dict):
        out = [expr["op"]] if "op" in expr else []
        return out + [o for v in expr.values() for o in ops_in(v)]
    if isinstance(expr, list):
        return [o for v in expr for o in ops_in(v)]
    return []


def prop_signal(scene: Any, name: str, prop: str) -> dict[str, Any]:
    return ir(scene)["signals"][object_ir(scene, name)["props"][prop]]


def pixel(frame: tuple[int, int, bytes], x: int, y: int) -> tuple[int, ...]:
    width, _, rgba = frame
    i = (y * width + x) * 4
    return tuple(rgba[i : i + 4])


# ---- Points --------------------------------------------------------------------------


def test_points_accept_numpy_lists_and_columns() -> None:
    def scene(s: k.Scene) -> None:
        arr = k.Points(np.array([[0.0, 0.0], [1.0, 2.0]]))
        lst = k.Points([(0, 0), (1, 2)])
        cols = k.Points(x=np.array([0.0, 1.0]), y=[0.0, 2.0])
        pair = k.Points((np.array([0.0, 1.0]), np.array([0.0, 2.0])))
        s.add(arr, lst, cols, pair)
        assert len(arr) == len(lst) == len(cols) == len(pair) == 2

    sc = build(scene)
    for name in ("arr", "lst", "cols", "pair"):
        assert prop_signal(sc, name, "xy")["initial"] == {"List": [{"Vec2": [0.0, 0.0]}, {"Vec2": [1.0, 2.0]}]}


def test_bad_xy_shape_is_an_error() -> None:
    def scene(s: k.Scene) -> None:
        k.Points(np.zeros((4, 3)))

    with raises_code("K1201"):
        build(scene)


def test_per_point_lambda_is_traced_to_a_point_expression() -> None:
    def scene(s: k.Scene) -> None:
        pts = k.Points(spread(10), color=lambda t, p: k.mix(k.BLUE, k.RED, p.x + t), radius=lambda p: 0.01 * p.index)
        s.add(pts)

    sc = build(scene)
    color = prop_signal(sc, "pts", "color")["timeline"][-1]["src"]
    assert color["k"] == "expr"
    assert {"point", "time", "mix"} <= set(ops_in(color["e"]))
    radius = prop_signal(sc, "pts", "radius")["timeline"][-1]["src"]["e"]
    assert {"op": "point", "attr": "index"} in [radius["a"], radius["b"]]


def test_per_point_lists_and_vectorized_python() -> None:
    seen: list[Any] = []

    def sizes(p: Any) -> Any:
        seen.append(type(p.x))
        return 0.01 + 0.001 * p.index

    def scene(s: k.Scene) -> None:
        pts = k.Points([(0, 0), (1, 0), (2, 0)], radius=k.python(sizes, vectorized=True), color=[k.RED, k.GREEN, k.BLUE])
        s.add(pts)

    sc = build(scene)
    assert seen == [np.ndarray]
    radius = prop_signal(sc, "pts", "radius")["initial"]["List"]
    assert [round(r["Float"], 6) for r in radius] == [0.01, 0.011, 0.012]
    assert len(prop_signal(sc, "pts", "color")["initial"]["List"]) == 3


def test_non_vectorized_python_per_point_is_rejected() -> None:
    def scene(s: k.Scene) -> None:
        k.Points([(0, 0)], radius=k.python(lambda p: 0.1))

    with raises_code("K0310"):
        build(scene)


def test_per_point_color_renders_natively_without_calling_python() -> None:
    calls = 0

    def color(p: Any) -> Any:
        nonlocal calls
        calls += 1
        return k.where(p.x < 0, k.BLUE, k.RED)

    def scene(s: k.Scene) -> None:
        pts = k.Points([(-4, 0), (4, 0)], radius=0.4, color=color)
        s.add(pts)
        s.wait(1)

    sc = build(scene)
    assert calls == 1
    frames = [sc.builder.frame_rgba(t, "final") for t in (0.0, 0.5, 1.0)]
    assert calls == 1, "the per-point function ran again at render time"
    width, height, _ = frames[0]
    scale = width / 16
    left = pixel(frames[0], int(width / 2 - 4 * scale), height // 2)
    right = pixel(frames[0], int(width / 2 + 4 * scale), height // 2)
    assert left[2] > left[0] and right[0] > right[2], (left, right)


def test_ten_thousand_points_render_fast() -> None:
    def scene(s: k.Scene) -> None:
        pts = k.Points(spread(10_000), radius=0.025, color=lambda t, p: k.mix(k.BLUE, k.RED, (p.x + 6.5) / 13))
        s.add(pts)
        s.wait(1)

    sc = build(scene, size="1080p")
    sc.builder.frame_rgba(0.0, "final")
    best = float("inf")
    for t in (0.25, 0.5, 0.75):
        start = time.perf_counter()
        width, height, rgba = sc.builder.frame_rgba(t, "final")
        best = min(best, time.perf_counter() - start)
    assert (width, height) == (1920, 1080) and len(rgba) == 1920 * 1080 * 4
    # Target: < 100 ms per 1080p frame on CPU (the Rust bench reports ~20 ms optimized).
    assert best < 0.25, f"10k points took {best * 1000:.0f} ms"


def test_draw_reveals_points() -> None:
    def scene(s: k.Scene) -> None:
        pts = k.Points([(-4, 0), (4, 0)], radius=0.4, color=k.WHITE)
        s.play(k.draw(pts), duration=1)

    sc = build(scene)
    frame = sc.builder.frame_rgba(0.3, "final")
    width, height, _ = frame
    scale = width / 16
    assert pixel(frame, int(width / 2 - 4 * scale), height // 2)[0] > 200
    assert pixel(frame, int(width / 2 + 4 * scale), height // 2)[0] < 60


# ---- fields ----------------------------------------------------------------------------


def test_vector_field_and_stream_lines_build_and_render() -> None:
    def scene(s: k.Scene) -> None:
        field = k.VectorField(lambda x, y: (-y, x), density=20)
        lines = k.StreamLines(field, seeds=50, progress=0.0)
        fixed = k.StreamLines(lambda p: (1, 0), seeds=[(-3, 0), (-3, 1)], color=k.WHITE)
        s.add(field, lines, fixed)
        s.play(lines.to(progress=1), duration=1)

    sc = build(scene)
    field = prop_signal(sc, "field", "field")["timeline"][-1]["src"]["e"]
    assert field["op"] == "vec2" and "point" in ops_in(field)
    assert prop_signal(sc, "lines", "field")["timeline"][-1]["src"]["e"] == field
    assert prop_signal(sc, "lines", "seed_count")["initial"] == {"Float": 50.0}
    assert len(prop_signal(sc, "fixed", "seeds")["initial"]["List"]) == 2
    early, late = sc.builder.frame_rgba(0.05, "final"), sc.builder.frame_rgba(1.0, "final")
    assert early[2] != late[2]


def test_field_with_time_animates() -> None:
    def scene(s: k.Scene) -> None:
        field = k.VectorField(lambda t, x, y: (k.cos(t), k.sin(t)), density=10)
        s.add(field)
        s.wait(2)

    sc = build(scene)
    assert sc.builder.frame_png(0.0) != sc.builder.frame_png(1.5)


# ---- check and W0901 -------------------------------------------------------------------


def test_mass_scene_is_strict_clean() -> None:
    def scene(s: k.Scene) -> None:
        field = k.VectorField(lambda x, y: (-y, x), density=24)
        lines = k.StreamLines(field, seeds=80, progress=0.0, tail=0.5)
        pts = k.Points(spread(2000), color=lambda p: k.mix(k.TEAL, k.PINK, p.t))
        s.play(k.draw(field))
        s.play(k.fade_in(lines), lines.to(progress=1), duration=2)
        s.play(k.draw(pts))

    diagnostics = run_lints(build(scene), scene)
    assert [d for d in diagnostics if d.level in ("error", "warning")] == [], [d.render() for d in diagnostics]


def test_example_campo_passes_check_strict(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli_main(["check", "--strict", EXAMPLE]) == 0, capsys.readouterr().out


def test_w0901_loop_creating_1001_dots() -> None:
    def scene(s: k.Scene) -> None:
        dots = [k.Dot(r=0.01, x=(i % 50) * 0.2 - 5, y=(i // 50) * 0.2 - 2) for i in range(1001)]  # W0901 here
        s.add(*dots)

    found = [d for d in run_lints(build(scene), scene) if d.code == "W0901"]
    assert len(found) == 1, [d.render() for d in found]
    d = found[0]
    assert d.spans[0].line == line_of("# W0901 here")
    assert "1001" in d.message and "Dot" in d.message
    assert any("k.Points" in (f.code or "") for f in d.fixes)


def test_w0901_not_reported_for_1000_objects_or_points() -> None:
    def scene(s: k.Scene) -> None:
        dots = [k.Dot(r=0.01, x=(i % 50) * 0.2 - 5, y=(i // 50) * 0.2 - 2) for i in range(1000)]
        s.add(*dots)
        s.add(k.Points(spread(5000)))

    assert [d for d in run_lints(build(scene), scene) if d.code == "W0901"] == []
