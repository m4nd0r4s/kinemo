"""`kinemo dev` edits: the page sends changes to call-site arguments, the session rewrites
the file (or rebuilds from edited text while dragging) and reports the outcome."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kinemo.cli.dev import Session

SCENE = '''import kinemo as k


@k.scene
def demo(s: k.Scene):
    dot = k.Dot(r=0.2)
    box = k.Square(1.6).place(at=(1, -1))
    s.add(dot, box)
    s.play(dot.to(x=3), duration=0.4)
'''


class FakeServer:
    def __init__(self) -> None:
        self.scenes: list[dict[str, Any]] = []
        self.errors: list[Any] = []
        self.notes: list[dict[str, Any]] = []

    def set_scene(self, builder: Any, meta: str) -> int:
        self.scenes.append(json.loads(meta))
        return len(self.scenes)

    def set_error(self, diagnostics: str) -> None:
        self.errors.append(json.loads(diagnostics))

    def notify(self, message: str) -> None:
        self.notes.append(json.loads(message))


def session_for(tmp_path: Path) -> tuple[Session, FakeServer, Path]:
    path = tmp_path / "scene.py"
    path.write_text(SCENE, encoding="utf-8")
    server = FakeServer()
    session = Session(str(path), None, {}, server)  # type: ignore[arg-type]
    assert session.rebuild()
    return session, server, path


def site_of(meta: dict[str, Any], callee: str) -> str:
    return next(key for key, site in meta["sources"].items() if site["callee"] == callee)


def test_meta_lists_call_sites_and_bar_objects(tmp_path: Path) -> None:
    _, server, _ = session_for(tmp_path)
    meta = server.scenes[-1]
    dot = meta["sources"][site_of(meta, "k.Dot")]
    assert dot["arguments"][0] == {"keyword": "r", "index": None, "param": "r", "text": "0.2", "kind": "number", "value": 0.2}
    assert "fill" in dot["accepts"]
    bar = meta["timeline"][0]
    assert bar["code"] == "s.play(dot.to(x=3), duration=0.4)"
    assert [meta["objects"][str(i)]["label"] for i in bar["objects"]] == ["dot"]
    assert meta["sources"][bar["call"]]["callee"] == "s.play"


def test_a_committed_edit_rewrites_the_file(tmp_path: Path) -> None:
    session, server, path = session_for(tmp_path)
    meta = server.scenes[-1]
    request = {"id": 1, "live": False, "changes": [{"site": site_of(meta, "k.Dot"), "target": "r", "value": "0.5"}]}
    session.process_edits([request])
    assert "dot = k.Dot(r=0.5)" in path.read_text(encoding="utf-8")
    assert server.notes[-1] == {"type": "edit_result", "id": 1, "ok": True, "message": "", "live": False}


def test_live_edits_rebuild_without_writing_and_only_the_last_counts(tmp_path: Path) -> None:
    session, server, path = session_for(tmp_path)
    meta = server.scenes[-1]
    site = site_of(meta, "k.Dot")
    live = [{"id": i, "live": True, "changes": [{"site": site, "target": "r", "value": str(v)}]} for i, v in enumerate((0.3, 0.4, 0.5))]
    session.process_edits(live)
    assert path.read_text(encoding="utf-8") == SCENE
    assert len(server.scenes) == 2 and server.scenes[-1]["live"] is True
    assert [n["id"] for n in server.notes] == [2]


def test_a_cancelled_drag_shows_the_disk_version_again(tmp_path: Path) -> None:
    session, server, _ = session_for(tmp_path)
    site = site_of(server.scenes[-1], "k.Dot")
    session.process_edits([{"id": 1, "live": True, "changes": [{"site": site, "target": "r", "value": "0.9"}]}])
    session.process_edits([{"id": 2, "live": False, "changes": []}])
    assert server.scenes[-1]["live"] is False


def test_edits_against_a_file_changed_elsewhere_are_refused(tmp_path: Path) -> None:
    session, server, path = session_for(tmp_path)
    site = site_of(server.scenes[-1], "k.Dot")
    path.write_text(SCENE + "\n# edited in the editor\n", encoding="utf-8")
    session.process_edits([{"id": 1, "live": False, "changes": [{"site": site, "target": "r", "value": "0.5"}]}])
    assert server.notes[-1]["ok"] is False and "changed since the preview was built" in server.notes[-1]["message"]
    assert "edited in the editor" in path.read_text(encoding="utf-8")


def test_a_default_prop_is_added_and_unknown_targets_refused(tmp_path: Path) -> None:
    session, server, path = session_for(tmp_path)
    meta = server.scenes[-1]
    square = site_of(meta, "k.Square")
    session.process_edits([{"id": 1, "live": False, "changes": [{"site": square, "target": "rotate", "value": "45"}]}])
    assert "k.Square(1.6, rotate=45)" in path.read_text(encoding="utf-8")
    session.rebuild()
    play = site_of(server.scenes[-1], "s.play")
    session.process_edits([{"id": 2, "live": False, "changes": [{"site": play, "target": "nope", "value": "1"}]}])
    assert server.notes[-1]["ok"] is False and "does not set nope" in server.notes[-1]["message"]


AXES_SCENE = '''import kinemo as k


@k.scene
def chart(s: k.Scene):
    ax = k.Axes(x=(0, 10, 2), y=(0, 5, 1))
    limit = ax.vline(4, style="dashed")
    curve = ax.plot(lambda x: x / 2)
    tan = curve.tangent_at(2.0, length=3)
    s.play(k.draw(ax))
'''


def test_objects_made_by_a_method_bind_to_its_parameters(tmp_path: Path) -> None:
    path = tmp_path / "chart.py"
    path.write_text(AXES_SCENE, encoding="utf-8")
    server = FakeServer()
    session = Session(str(path), None, {}, server)  # type: ignore[arg-type]
    assert session.rebuild()
    meta = server.scenes[-1]
    vline = meta["sources"][site_of(meta, "ax.vline")]
    assert [(a["param"], a["kind"]) for a in vline["arguments"]] == [("at", "number"), ("style", "string")]
    assert vline["types"]["at"] == {"type": "number"} and "enter_with_axes" in vline["accepts"]
    tangent = meta["sources"][site_of(meta, "curve.tangent_at")]
    assert [a["param"] for a in tangent["arguments"]] == ["x", "length"]
    session.process_edits([{"id": 1, "live": False, "changes": [{"site": site_of(meta, "ax.vline"), "target": "at", "value": "6"}]}])
    assert 'limit = ax.vline(6, style="dashed")' in path.read_text(encoding="utf-8")
