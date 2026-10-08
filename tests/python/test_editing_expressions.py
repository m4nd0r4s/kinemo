"""Editing numbers inside computed arguments: the expression stays, only the number's
characters change (`title.x + 1.2` → `title.x + 0.8`)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from kinemo._runtime.spans import Span
from kinemo.editing.call_sites import CallSite, SourceFile
from kinemo.editing.source_edit import Change, EditError, apply_changes

from test_dev_editing import FakeServer, site_of
from kinemo.cli.dev import Session


def call(text: str, callee: str) -> tuple[SourceFile, CallSite]:
    """The first call to `callee` in `text`, found the way the preview finds it: by span."""
    source = SourceFile("scene.py", text)
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Call) and ast.unparse(node.func) == callee:
            start = source.position(node.lineno, node.col_offset)
            end = source.position(node.end_lineno or node.lineno, node.end_col_offset or 0)
            site = source.call_at(Span("scene.py", start.line, start.col, end.line, end.col))
            assert site is not None
            return source, site
    raise AssertionError(f"no call to {callee}")


def numbers(site: CallSite, keyword: str) -> list[str]:
    argument = site.keyword(keyword)
    assert argument is not None
    return [n.text for n in argument.numbers]


def test_numbers_inside_arithmetic_and_lambdas_in_source_order() -> None:
    _, site = call("k.Dot(x=title.x + 1.2, y=lambda: 3 * t() - 0.75 * t() ** 2)\n", "k.Dot")
    assert numbers(site, "x") == ["1.2"]
    assert numbers(site, "y") == ["3", "0.75", "2"]


def test_a_sign_written_against_a_number_belongs_to_it() -> None:
    _, site = call("box.place(at=(a, -2))\n", "box.place")
    assert numbers(site, "at") == ["-2"]


def test_literals_have_no_inner_numbers_and_booleans_are_not_numbers() -> None:
    _, site = call("k.Dot(r=0.2, visible=flag or True)\n", "k.Dot")
    r = site.keyword("r")
    assert r is not None and r.kind == "number" and r.numbers == ()
    assert numbers(site, "visible") == []


def test_format_specs_are_not_numbers_but_numbers_in_fstring_fields_are() -> None:
    _, site = call('k.Text(lambda: f"{x() * 100:.0f}% of {total}")\n', "k.Text")
    argument = site.positional(0)
    assert argument is not None
    assert [n.text for n in argument.numbers] == ["100"]


def test_offsets_count_characters_across_unicode_and_lines() -> None:
    text = 'k.Text("v₀ = " + str(3), x=(\n    left\n    + 0.5\n))\n'
    _, site = call(text, "k.Text")
    label = site.positional(0)
    assert label is not None and label.numbers[0].text == "3"
    assert label.text[label.numbers[0].offset] == "3"
    x = site.keyword("x")
    assert x is not None and x.text[x.numbers[0].offset :].startswith("0.5")


def test_editing_a_number_keeps_the_expression() -> None:
    text = "dot = k.Dot(x=title.x + 1.2, y=lambda: 3 * t() - 0.75 * t() ** 2)\n"
    source, site = call(text, "k.Dot")
    edited = apply_changes(source, [Change(site, "y", "0.5", number=1), Change(site, "x", "-0.8", number=0)])
    assert edited == "dot = k.Dot(x=title.x + -0.8, y=lambda: 3 * t() - 0.5 * t() ** 2)\n"


def test_number_edits_refuse_other_values_and_missing_numbers() -> None:
    source, site = call("k.Dot(x=title.x + 1.2)\n", "k.Dot")
    with pytest.raises(EditError, match="not a number"):
        apply_changes(source, [Change(site, "x", "offset", number=0)])
    with pytest.raises(EditError, match="no longer has that number"):
        apply_changes(source, [Change(site, "x", "2", number=3)])
    with pytest.raises(EditError, match="computed"):
        apply_changes(source, [Change(site, "x", "2")])


SCENE = '''import kinemo as k


@k.scene
def demo(s: k.Scene):
    title = k.Text("hi")
    dot = k.Dot(r=0.2, x=title.x + 1.2)
    s.add(title, dot)
    s.wait(0.5)
'''


def test_the_preview_gets_the_numbers_and_an_edit_writes_one(tmp_path: Path) -> None:
    path = tmp_path / "scene.py"
    path.write_text(SCENE, encoding="utf-8")
    server = FakeServer()
    session = Session(str(path), None, {}, server)  # type: ignore[arg-type]
    assert session.rebuild()
    meta = server.scenes[-1]
    key = site_of(meta, "k.Dot")
    x = next(a for a in meta["sources"][key]["arguments"] if a["param"] == "x")
    assert x["kind"] is None
    assert x["numbers"] == [{"text": "1.2", "value": 1.2, "offset": 10}]
    session.process_edits([{"id": 1, "live": False, "changes": [{"site": key, "target": "x", "number": 0, "value": "2.5"}]}])
    assert "dot = k.Dot(r=0.2, x=title.x + 2.5)" in path.read_text(encoding="utf-8")
    assert server.notes[-1]["ok"] is True


PLOT = '''import kinemo as k


@k.scene
def demo(s: k.Scene):
    ax = k.Axes(x=(0, 4, 1), y=(0, 3, 1))
    curve = ax.plot(lambda x: 3 * x - 0.75 * x**2, domain=(0, 4))
    s.add(ax)
    s.wait(0.5)
'''


def test_a_lambda_number_rebuilds_live_and_commits(tmp_path: Path) -> None:
    path = tmp_path / "scene.py"
    path.write_text(PLOT, encoding="utf-8")
    server = FakeServer()
    session = Session(str(path), None, {}, server)  # type: ignore[arg-type]
    assert session.rebuild()
    key = site_of(server.scenes[-1], "ax.plot")
    fn = next(a for a in server.scenes[-1]["sources"][key]["arguments"] if a["param"] == "fn")
    assert [n["text"] for n in fn["numbers"]] == ["3", "0.75", "2"]
    built = len(server.scenes)
    live = {"id": 1, "live": True, "changes": [{"site": key, "target": "fn", "number": 1, "value": "1.5"}]}
    session.process_edits([live])
    assert len(server.scenes) == built + 1, "a live edit rebuilds the scene"
    assert "0.75" in path.read_text(encoding="utf-8"), "a live edit does not write the file"
    session.process_edits([{**live, "id": 2, "live": False}])
    assert "lambda x: 3 * x - 1.5 * x**2" in path.read_text(encoding="utf-8")


# ---- values held by a variable ----------------------------------------------------------


def variable_of(text: str, callee: str, keyword: str) -> object:
    _, site = call(text, callee)
    argument = site.keyword(keyword)
    assert argument is not None
    return argument.variable


def test_a_name_bound_once_to_a_literal_in_the_function_is_editable() -> None:
    text = "def demo(s):\n    gap = 0.4\n    title.place(above=box, gap=gap)\n    label.place(below=box, gap=gap)\n"
    variable = variable_of(text, "title.place", "gap")
    assert variable is not None
    assert (variable.name, variable.text, variable.kind, variable.line, variable.uses) == ("gap", "0.4", "number", 2, 2)


def test_a_module_constant_is_editable_from_a_scene_function() -> None:
    text = "import kinemo as k\n\nACCENT = k.YELLOW\n\ndef demo(s):\n    dot = k.Dot(color=ACCENT)\n"
    variable = variable_of(text, "k.Dot", "color")
    assert variable is not None and variable.kind == "color" and variable.value == "YELLOW"


@pytest.mark.parametrize(
    "text",
    [
        "def demo(s):\n    gap = 0.4\n    gap = 0.5\n    t.place(gap=gap)\n",          # assigned twice
        "def demo(s, gap=0.4):\n    t.place(gap=gap)\n",                            # a parameter
        "def demo(s):\n    for gap in (0.1, 0.2):\n        t.place(gap=gap)\n",     # a loop variable
        "def demo(s):\n    gap = base * 2\n    t.place(gap=gap)\n",                  # computed
        "gap = 0.4\n\ndef demo(s):\n    global gap\n    gap = 0.2\n    t.place(gap=gap)\n",  # rebound elsewhere
        "def demo(s):\n    gap += 0.1\n    t.place(gap=gap)\n",                      # augmented
    ],
)
def test_names_that_do_not_hold_one_literal_stay_read_only(text: str) -> None:
    assert variable_of(text, "t.place", "gap") is None


def test_editing_through_a_variable_rewrites_the_assignment() -> None:
    text = "def demo(s):\n    gap = 0.4\n    title.place(above=box, gap=gap)\n"
    source, site = call(text, "title.place")
    edited = apply_changes(source, [Change(site, "gap", "0.25", variable=True)])
    assert edited == "def demo(s):\n    gap = 0.25\n    title.place(above=box, gap=gap)\n"
    _, literal_site = call("title.place(gap=0.4)\n", "title.place")
    with pytest.raises(EditError, match="no longer names a variable"):
        apply_changes(SourceFile("scene.py", "title.place(gap=0.4)\n"), [Change(literal_site, "gap", "0.2", variable=True)])


VARIABLE_SCENE = '''import kinemo as k


@k.scene
def demo(s: k.Scene):
    size = 0.4
    title = k.Text("hi", size=size)
    s.add(title)
    s.wait(0.5)
'''


def test_the_preview_edits_a_value_through_its_variable(tmp_path: Path) -> None:
    path = tmp_path / "scene.py"
    path.write_text(VARIABLE_SCENE, encoding="utf-8")
    server = FakeServer()
    session = Session(str(path), None, {}, server)  # type: ignore[arg-type]
    assert session.rebuild()
    key = site_of(server.scenes[-1], "k.Text")
    size = next(a for a in server.scenes[-1]["sources"][key]["arguments"] if a["param"] == "size")
    assert size["variable"] == {"name": "size", "text": "0.4", "kind": "number", "value": 0.4, "line": 6, "uses": 1}
    session.process_edits([{"id": 1, "live": False, "changes": [{"site": key, "target": "size", "variable": True, "value": "0.6"}]}])
    assert "    size = 0.6\n" in path.read_text(encoding="utf-8")


# ---- dragging computed positions ----------------------------------------------------------


@pytest.mark.parametrize(
    ("x", "expected"),
    [("title.x + 1.2", (0, 1)), ("title.x - 1.2", (0, -1)), ("1.2 + title.x", (0, 1)), ("title.x * 2", None), ("2 * a + 0.5", (1, 1))],
)
def test_a_computed_coordinate_moves_through_the_number_it_adds(x: str, expected: tuple[int, int] | None) -> None:
    _, site = call(f"k.Dot(x={x})\n", "k.Dot")
    argument = site.keyword("x")
    assert argument is not None
    found = (argument.offset.number, argument.offset.sign) if argument.offset is not None else None
    assert found == expected


def test_a_computed_pair_moves_each_coordinate_through_its_own_number() -> None:
    _, site = call("dot.place(at=(left + 0.5, top - 1))\n", "dot.place")
    at = site.keyword("at")
    assert at is not None and [(o.number, o.sign) if o else None for o in at.offsets] == [(0, 1), (1, -1)]
    _, site = call("dot.place(at=(a, 2.0))\n", "dot.place")
    at = site.keyword("at")
    assert at is not None and [(o.number, o.sign) if o else None for o in at.offsets] == [None, (0, 1)]
