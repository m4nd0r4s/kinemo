"""Data charts: BarChart, LineChart and Table build cleanly, `to(data=...)` schedules the
transition (values, slots, entering and leaving keys) and the frames render."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import kinemo as k
from conftest import build, diagnostic_of, inspect, presence, raises_code
from kinemo.testing import build as checked_build

pl = pytest.importorskip("polars")
ROOT = Path(__file__).resolve().parents[2]
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

BEFORE = pl.DataFrame({"pais": ["PT", "ES", "FR"], "gwh": [50, 260, 540]})
AFTER = pl.DataFrame({"pais": ["FR", "PT", "DE"], "gwh": [600, 80, 1200]})


def by_id(scene: Any, t: float) -> dict[int, dict[str, Any]]:
    """The core's snapshot at `t`, by object id (ids are recorded during the build)."""
    return {o["id"]: o for o in inspect(scene, t)}


def value_of(entry: dict[str, Any], prop: str) -> Any:
    raw = entry["props"][prop]
    return next(iter(raw.values())) if isinstance(raw, dict) else raw


IDS: dict[str, int] = {}


def bar_chart_scene(s: k.Scene) -> None:
    chart = k.BarChart(BEFORE, x="pais", y="gwh", key="pais").place(at="center")
    s.play(k.draw(chart))
    IDS["ES"] = chart.bar("ES")._id
    s.play(chart.to(data=AFTER), duration=2)
    IDS["DE"] = chart.bar("DE")._id
    s.wait(0.5)


# ---- BarChart ---------------------------------------------------------------------------------

def test_bar_chart_builds_without_diagnostics_in_strict_mode() -> None:
    built = checked_build(bar_chart_scene, strict=True)
    assert built.diagnostics == []


def test_bar_chart_reads_rows_from_every_source() -> None:
    seen = {}
    pa = pytest.importorskip("pyarrow")

    @build
    def scene(s: k.Scene) -> None:
        for name, data in (
            ("polars", BEFORE),
            ("pyarrow", pa.table({"pais": ["PT", "ES", "FR"], "gwh": [50, 260, 540]})),
            ("dict", {"pais": ["PT", "ES", "FR"], "gwh": [50, 260, 540]}),
            ("rows", [{"pais": "PT", "gwh": 50}, {"pais": "ES", "gwh": 260}, {"pais": "FR", "gwh": 540}]),
        ):
            chart = k.BarChart(data, x="pais", y="gwh")
            seen[name] = (chart.keys, [chart.bar(key).value.now for key in chart.keys], chart.y_max.now)

    expected = (["PT", "ES", "FR"], [50.0, 260.0, 540.0], 600.0)
    assert all(v == expected for v in seen.values()), seen


def test_bar_chart_transition_animates_values_slots_and_scale() -> None:
    seen: dict[str, Any] = {}

    @build
    def scene(s: k.Scene) -> None:
        chart = k.BarChart(BEFORE, x="pais", y="gwh", key="pais")
        s.add(chart)
        seen["slots"] = [chart.bar(key).x.now for key in chart.keys]
        seen["ids"] = {key: chart.bar(key)._id for key in chart.keys}
        span = s.play(chart.to(data=AFTER), duration=2)
        seen["span"] = (span.start, span.end)
        seen["keys"] = chart.keys
        seen["values"] = [chart.bar(key).value.now for key in chart.keys]
        seen["xs"] = [chart.bar(key).x.now for key in chart.keys]
        seen["top"] = chart.y_max.now

    assert seen["span"] == (0.0, 2.0)
    assert seen["keys"] == ["FR", "PT", "DE"]
    assert seen["values"] == [600.0, 80.0, 1200.0]
    assert seen["xs"] == pytest.approx(seen["slots"])  # FR travelled to the first slot
    assert seen["top"] == 1250.0
    middle = by_id(scene, 1.0)
    assert 50.0 < value_of(middle[seen["ids"]["PT"]], "value") < 80.0
    fr_start, fr_middle = by_id(scene, 0.0)[seen["ids"]["FR"]], middle[seen["ids"]["FR"]]
    assert fr_middle["position"][0] < fr_start["position"][0]  # FR travels left, towards slot 0


def test_bar_chart_new_keys_enter_and_missing_keys_leave() -> None:
    scene = build(bar_chart_scene)
    leaving, entering = IDS["ES"], IDS["DE"]
    middle = by_id(scene, 2.0)
    assert 0.0 < value_of(middle[leaving], "value") < 260.0
    assert 0.0 < value_of(middle[leaving], "opacity") < 1.0
    assert 0.0 < value_of(middle[entering], "value") < 1200.0
    assert not by_id(scene, 0.5)[entering]["present"]
    assert by_id(scene, 1.0)[entering]["present"]
    assert by_id(scene, 2.9)[leaving]["present"] and not by_id(scene, 3.1)[leaving]["present"]


def test_consecutive_transitions_chain_from_the_previous_state() -> None:
    seen = {}

    @build
    def scene(s: k.Scene) -> None:
        chart = k.BarChart({"k": ["a", "b"], "v": [1, 2]}, x="k", y="v")
        s.add(chart)
        s.play(chart.to(data={"k": ["b", "c"], "v": [3, 4]}))
        s.play(chart.to(data={"k": ["a", "c"], "v": [5, 6]}))
        seen["keys"] = chart.keys
        seen["values"] = [chart.bar(key).value.now for key in chart.keys]

    assert seen == {"keys": ["a", "c"], "values": [5.0, 6.0]}


def test_overlapping_data_transitions_conflict_k0201() -> None:
    def body(s: k.Scene) -> None:
        chart = k.BarChart({"k": ["a"], "v": [1]}, x="k", y="v")
        s.add(chart)
        s.start(chart.to(data={"k": ["a"], "v": [2]}))
        s.play(chart.to(data={"k": ["a"], "v": [3]}))

    diagnostic_of(body, "K0201")


def test_bar_chart_errors_point_at_columns_and_keys() -> None:
    with raises_code("K1202"):
        build(lambda s: k.BarChart({"pais": ["PT"], "gwh": [1]}, x="pais", y="gw"))
    with raises_code("K1203"):
        build(lambda s: k.BarChart({"pais": ["PT"], "gwh": ["x"]}, x="pais", y="gwh"))
    with raises_code("K1204"):
        build(lambda s: k.BarChart({"pais": ["PT", "PT"], "gwh": [1, 2]}, x="pais", y="gwh"))


def test_bar_chart_frames_render_and_change() -> None:
    scene = build(bar_chart_scene, size="720p")
    start, middle, end = (scene.builder.frame_png(t) for t in (0.9, 2.0, 3.4))
    assert start.startswith(PNG_SIGNATURE) and end.startswith(PNG_SIGNATURE)
    assert len({start, middle, end}) == 3
    assert scene.builder.frame_png(2.0) == middle


# ---- LineChart --------------------------------------------------------------------------------

DAY = {"hour": [0, 6, 12, 18, 24], "solar": [0, 2, 6, 2, 0], "load": [1, 3, 2, 4, 1.5]}
FINER = pl.DataFrame({"hour": [0, 4, 8, 12, 16, 20, 24], "solar": [0, 1, 4, 7, 4, 1, 0], "load": [2, 2, 3, 3, 5, 4, 2]})


def line_chart_scene(s: k.Scene) -> None:
    chart = k.LineChart(DAY, x="hour", y=["solar", "load"], y_range=(0, 8), dots=True).place(at="center")
    s.play(k.draw(chart))
    s.play(chart.to(data=FINER), duration=2)
    s.play(chart.to(data=DAY), duration=2)


def test_line_chart_builds_strict_and_is_an_axes() -> None:
    checked_build(line_chart_scene, strict=True)
    seen = {}

    @build
    def scene(s: k.Scene) -> None:
        chart = k.LineChart(DAY, x="hour", y="solar")
        seen["axes"] = isinstance(chart, k.Axes)
        seen["ranges"] = (tuple(chart.x_range.now), tuple(chart.y_range.now))
        seen["segments"] = len(chart.lines["solar"].segments)

    assert seen == {"axes": True, "ranges": ((0.0, 24.0), (0.0, 6.0)), "segments": 4}


def test_line_chart_morphs_points_and_grows_new_ones() -> None:
    seen = {}

    @build
    def scene(s: k.Scene) -> None:
        chart = k.LineChart(DAY, x="hour", y=["solar", "load"], y_range=(0, 8))
        s.add(chart)
        s.play(chart.to(data=FINER), duration=2)
        line = chart.lines["solar"]
        seen["after"] = [(x.now, y.now) for x, y in zip(line.xs, line.ys)]
        seen["segments"] = len(line.segments)
        s.play(chart.to(data=DAY), duration=1)
        seen["back"] = [(x.now, y.now) for x, y in zip(line.xs, line.ys)]

    assert seen["after"] == [(0, 0), (4, 1), (8, 4), (12, 7), (16, 4), (20, 1), (24, 0)]
    assert seen["segments"] == 6
    assert seen["back"] == [(0, 0), (6, 2), (12, 6), (18, 2), (24, 0)]


def test_line_chart_renders() -> None:
    scene = build(line_chart_scene, size="720p")
    assert scene.builder.frame_png(2.0).startswith(PNG_SIGNATURE)
    assert scene.builder.frame_png(1.0) != scene.builder.frame_png(3.0)


# ---- Table ------------------------------------------------------------------------------------

def table_scene(s: k.Scene) -> None:
    table = k.Table(BEFORE, columns=["pais", "gwh"]).place(at="center")
    s.play(k.fade_in(table))
    s.play(table.to(data=pl.DataFrame({"pais": ["PT", "ES", "FR", "DE"], "gwh": [80, 260, 540, 1200]})), duration=1)
    s.play(table.to(data={"pais": ["PT"], "gwh": [90]}), duration=1)


def test_table_builds_strict_with_header_and_cells() -> None:
    checked_build(table_scene, strict=True)
    seen = {}

    @build
    def scene(s: k.Scene) -> None:
        table = k.Table(BEFORE)
        seen["header"] = [h.text.now for h in table.header]
        seen["cells"] = [[c.text.now for c in row] for row in table.cells]
        seen["columns_left_to_right"] = table.header[0].x.now < table.header[1].x.now

    assert seen == {
        "header": ["**pais**", "**gwh**"],
        "cells": [["PT", "50"], ["ES", "260"], ["FR", "540"]],
        "columns_left_to_right": True,
    }


def test_table_transition_changes_texts_adds_and_removes_rows() -> None:
    seen = {}

    @build
    def scene(s: k.Scene) -> None:
        table = k.Table(BEFORE)
        s.add(table)
        seen["ids"] = [c._id for c in table.cells[0]]
        s.play(table.to(data={"pais": ["PT", "ES", "FR", "DE"], "gwh": [80, 260, 540, 1200]}), duration=1)
        seen["grown"] = [[c.text.now for c in row] for row in table.cells]
        s.play(table.to(data={"pais": ["PT"], "gwh": [90]}), duration=1)
        seen["shrunk"] = [[c.text.now for c in row] for row in table.cells]

    assert seen["grown"] == [["PT", "80"], ["ES", "260"], ["FR", "540"], ["DE", "1200"]]
    assert seen["shrunk"] == [["PT", "90"]]
    middle = by_id(scene, 0.25)
    assert 0.0 < value_of(middle[seen["ids"][1]], "opacity") < 1.0  # 50 → 80 fades out first
    assert value_of(middle[seen["ids"][0]], "opacity") == 1.0  # unchanged cell stays
    assert value_of(by_id(scene, 0.75)[seen["ids"][1]], "text") == "80"
    assert presence(scene, "table") == [(0.0, True)]


def test_table_renders() -> None:
    scene = build(table_scene, size="720p")
    assert scene.builder.frame_png(1.5).startswith(PNG_SIGNATURE)


# ---- example ----------------------------------------------------------------------------------

def test_energy_example_passes_check_strict() -> None:
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "kinemo.cli", "check", "--strict", str(ROOT / "examples" / "energy.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
