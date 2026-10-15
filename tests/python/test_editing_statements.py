"""Inserting and removing statements of a scene function (the preview's editor mode)."""

from __future__ import annotations

import pytest

from kinemo.editing.call_sites import SourceFile
from kinemo.editing.source_edit import EditError
from kinemo.editing.statements import insert_statement, remove_statement, unique_name

SCENE = """import kinemo as k


@k.scene
def demo(s: k.Scene):
    dot = k.Dot()
    s.play(k.fade_in(dot))
    with s.voice("Hello there."):
        s.play(dot.to(x=2))
    for i in range(3):
        s.play(dot.to(y=i))
    s.wait(1)
"""


def src(text: str = SCENE) -> SourceFile:
    return SourceFile("scene.py", text)


def test_insert_after_a_statement_with_its_indentation() -> None:
    text = insert_statement(src(), "demo", 7, "box = k.Square(1)\ns.play(k.draw(box))")
    assert "    s.play(k.fade_in(dot))\n    box = k.Square(1)\n    s.play(k.draw(box))\n    with s.voice" in text


def test_insert_inside_a_with_block_keeps_its_indentation() -> None:
    text = insert_statement(src(), "demo", 9, "s.wait(0.5)")
    assert "        s.play(dot.to(x=2))\n        s.wait(0.5)\n    for i" in text


def test_insert_at_the_end_of_the_function() -> None:
    text = insert_statement(src(), "demo", None, "s.play(k.fade_out(dot))")
    assert text.endswith("    s.wait(1)\n    s.play(k.fade_out(dot))\n")


def test_insert_after_a_loop_header_goes_after_the_loop_but_inside_is_refused() -> None:
    text = insert_statement(src(), "demo", 10, "s.wait(0.2)")
    assert "        s.play(dot.to(y=i))\n    s.wait(0.2)\n    s.wait(1)" in text
    with pytest.raises(EditError, match="inside a loop"):
        insert_statement(src(), "demo", 11, "s.wait(0.2)")


def test_insert_refuses_code_that_is_not_a_statement() -> None:
    with pytest.raises(EditError, match="not a statement"):
        insert_statement(src(), "demo", 7, "s.play(")


def test_remove_a_statement_and_fill_an_empty_block() -> None:
    text = remove_statement(src(), "demo", 7)
    assert "s.play(k.fade_in(dot))" not in text and "    dot = k.Dot()\n    with s.voice" in text
    text = remove_statement(src(), "demo", 9)
    assert '    with s.voice("Hello there."):\n        pass\n' in text


def test_remove_needs_the_line_a_statement_starts_on() -> None:
    multi = SCENE.replace("    s.wait(1)\n", "    s.play(\n        k.fade_out(dot)\n    )\n")
    with pytest.raises(EditError, match="starts on line"):
        remove_statement(src(multi), "demo", 13)
    assert "fade_out" not in remove_statement(src(multi), "demo", 12)


def test_unique_names_skip_every_name_of_the_function() -> None:
    assert unique_name(src(), "demo", "box") == "box"
    assert unique_name(src(), "demo", "dot") == "dot_2"
    assert unique_name(src(), "demo", "Text label!") == "text_label"
    assert unique_name(src(), "demo", "class") == "class_"


def test_a_missing_scene_function_is_an_error() -> None:
    with pytest.raises(EditError, match="no longer in"):
        insert_statement(src(), "other", None, "s.wait(1)")


def session_with(tmp_path: object, text: str) -> tuple[object, object, object]:
    from pathlib import Path

    from kinemo.cli.dev import Session
    from test_dev_editing import FakeServer

    path = Path(str(tmp_path)) / "scene.py"
    path.write_text(text, encoding="utf-8")
    server = FakeServer()
    session = Session(str(path), None, {}, server)  # type: ignore[arg-type]
    assert session.rebuild()
    return session, server, path


def test_the_preview_inserts_and_removes_statements(tmp_path: object) -> None:
    session, server, path = session_with(tmp_path, SCENE)
    meta = server.scenes[-1]  # type: ignore[attr-defined]
    assert meta["scene_function"]["name"] == "demo" and meta["scene_function"]["alias"] == "k"
    insert = {"op": "insert", "after": 7, "code": "box = k.Square(1)\ns.play(k.draw(box))"}
    session.process_edits([{"id": 1, "live": False, "changes": [insert]}])  # type: ignore[attr-defined]
    text = path.read_text(encoding="utf-8")  # type: ignore[attr-defined]
    assert "    box = k.Square(1)\n    s.play(k.draw(box))\n" in text
    assert server.notes[-1]["ok"] is True  # type: ignore[attr-defined]
    assert session.rebuild()  # type: ignore[attr-defined] - the file watcher does this in kinemo dev
    assert '"box"' in json_dump(server.scenes[-1]["objects"])  # type: ignore[attr-defined]
    session.process_edits([{"id": 2, "live": False, "changes": [{"op": "remove", "line": 9}]}])  # type: ignore[attr-defined]
    assert "s.play(k.draw(box))" not in path.read_text(encoding="utf-8")  # type: ignore[attr-defined]


def test_the_preview_refuses_an_insertion_inside_a_loop(tmp_path: object) -> None:
    session, server, path = session_with(tmp_path, SCENE)
    session.process_edits([{"id": 1, "live": False, "changes": [{"op": "insert", "after": 11, "code": "s.wait(1)"}]}])  # type: ignore[attr-defined]
    assert server.notes[-1]["ok"] is False and "inside a loop" in server.notes[-1]["message"]  # type: ignore[attr-defined]
    assert path.read_text(encoding="utf-8") == SCENE  # type: ignore[attr-defined]


def json_dump(value: object) -> str:
    import json

    return json.dumps(value)


def test_palette_objects_are_written_with_a_fresh_name_and_their_entrance() -> None:
    from kinemo.editing.statements import OBJECT_KINDS, object_statements

    code = object_statements(src(), "demo", "text", (1.234, -0.5), "k")
    assert code == 'label = k.Text("Text", size=0.5).place(at=(1.23, -0.5))\ns.play(k.write(label))'
    assert object_statements(src(), "demo", "circle", (0, 0), "k").startswith("circle = k.Circle(r=0.5).place(at=(0, 0))")
    arrow = object_statements(src(), "demo", "arrow", (1, 2), "kn")
    assert arrow.startswith("arrow = kn.Arrow(start=(0.25, 2), end=(1.75, 2))") and arrow.endswith("s.play(kn.draw(arrow))")
    for kind in OBJECT_KINDS:
        ast_ok = object_statements(src(), "demo", kind, (0.5, 0.5), "k")
        assert ast_ok.count("\n") == 1
    with pytest.raises(EditError, match="unknown object"):
        object_statements(src(), "demo", "teapot", (0, 0), "k")
    with pytest.raises(EditError, match="import kinemo as k"):
        object_statements(src(), "demo", "text", (0, 0), None)


def test_the_preview_adds_a_palette_object_at_the_playhead(tmp_path: object) -> None:
    session, server, path = session_with(tmp_path, SCENE)
    add = {"op": "add", "kind": "square", "at": [2, -1], "after": 7}
    session.process_edits([{"id": 1, "live": False, "changes": [add]}])  # type: ignore[attr-defined]
    text = path.read_text(encoding="utf-8")  # type: ignore[attr-defined]
    assert "    s.play(k.fade_in(dot))\n    square = k.Square(1).place(at=(2, -1))\n    s.play(k.draw(square))\n" in text
    assert session.rebuild()  # type: ignore[attr-defined]
    for kind in ("text", "math", "circle", "arrow", "axes"):
        session.process_edits([{"id": 2, "live": False, "changes": [{"op": "add", "kind": kind, "at": [0, 0], "after": None}]}])  # type: ignore[attr-defined]
        assert server.notes[-1]["ok"] is True, server.notes[-1]  # type: ignore[attr-defined]
        assert session.rebuild(), kind  # type: ignore[attr-defined]
