"""Undo and redo of edits made from the preview (Ctrl/⌘+Z, Shift+Ctrl/⌘+Z)."""

from __future__ import annotations

from pathlib import Path

from test_dev_editing import FakeServer, SCENE, session_for, site_of


def edit(session: object, server: FakeServer, request_id: int, changes: list[dict[str, object]]) -> dict[str, object]:
    session.process_edits([{"id": request_id, "live": False, "changes": changes}])  # type: ignore[attr-defined]
    return server.notes[-1]


def test_undo_restores_the_file_and_redo_writes_the_edit_again(tmp_path: Path) -> None:
    session, server, path = session_for(tmp_path)
    key = site_of(server.scenes[-1], "k.Dot")
    assert edit(session, server, 1, [{"site": key, "target": "r", "value": "0.5"}])["ok"]
    edited = path.read_text(encoding="utf-8")
    assert "k.Dot(r=0.5)" in edited
    assert edit(session, server, 2, [{"op": "undo"}])["ok"]
    assert path.read_text(encoding="utf-8") == SCENE
    assert edit(session, server, 3, [{"op": "redo"}])["ok"]
    assert path.read_text(encoding="utf-8") == edited


def test_nothing_to_undo_and_a_file_changed_elsewhere_are_refused(tmp_path: Path) -> None:
    session, server, path = session_for(tmp_path)
    note = edit(session, server, 1, [{"op": "undo"}])
    assert note["ok"] is False and note["message"] == "nothing to undo"
    key = site_of(server.scenes[-1], "k.Dot")
    edit(session, server, 2, [{"site": key, "target": "r", "value": "0.5"}])
    path.write_text(path.read_text(encoding="utf-8") + "\n# edited in the editor\n", encoding="utf-8")
    note = edit(session, server, 3, [{"op": "undo"}])
    assert note["ok"] is False and "changed outside the preview" in str(note["message"])


def test_a_new_edit_clears_redo(tmp_path: Path) -> None:
    session, server, path = session_for(tmp_path)
    key = site_of(server.scenes[-1], "k.Dot")
    edit(session, server, 1, [{"site": key, "target": "r", "value": "0.5"}])
    edit(session, server, 2, [{"op": "undo"}])
    assert session.rebuild()
    key = site_of(server.scenes[-1], "k.Dot")
    edit(session, server, 3, [{"site": key, "target": "r", "value": "0.7"}])
    assert edit(session, server, 4, [{"op": "redo"}])["message"] == "nothing to redo"
