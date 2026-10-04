"""`kinemo inspect --at` with several instants: one build, one entry per instant (seconds,
marks, shifted marks, `marks`), in the CLI and the MCP tool."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kinemo.cli.main import main
from kinemo.mcp.tools import inspect_tool

SCENE = '''import kinemo as k


@k.scene
def moving(s: k.Scene):
    dot = k.Dot(x=-3)
    s.add(dot)
    s.mark("start")
    s.play(dot.to(x=3), duration=2)
    s.mark("start.end")
    s.wait(0.5)
'''


@pytest.fixture
def scene_file(tmp_path: Path) -> Path:
    path = tmp_path / "scene.py"
    path.write_text(SCENE, encoding="utf-8")
    return path


def dot_x(objects: list[dict[str, object]]) -> float:
    (dot,) = [o for o in objects if o["label"] == "dot"]
    return dot["position"][0]  # type: ignore[index]


def test_several_instants_give_one_entry_each(scene_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", str(scene_file), "--at", "0,start+50%,end", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [e["at"] for e in payload["instants"]] == ["0", "start+50%", "end"]
    assert [round(e["t"], 2) for e in payload["instants"]] == [0.0, 1.0, 3.0]
    xs = [dot_x(e["objects"]) for e in payload["instants"]]
    assert xs[0] < xs[1] < xs[2] == pytest.approx(3.0)


def test_marks_stands_for_every_mark(scene_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", str(scene_file), "--at", "marks"]) == 0
    out = capsys.readouterr().out
    assert "── start (0.00 s)" in out and "── start.end (2.00 s)" in out


def test_one_instant_keeps_the_single_shape(scene_file: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["inspect", str(scene_file), "--at", "end", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "instants" not in payload and payload["t"] == pytest.approx(3.0, abs=1e-3)


def test_the_mcp_tool_takes_several_instants(scene_file: Path) -> None:
    result = inspect_tool({"file": str(scene_file), "at": "start,end"})
    payload = json.loads(result["content"][0]["text"])
    (scene,) = payload["scenes"]
    assert [e["at"] for e in scene["instants"]] == ["start", "end"]
