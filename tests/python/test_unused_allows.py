"""W0120: `# kinemo: allow CODE` comments that silence nothing are reported, and `--fix`
removes them."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kinemo.cli.main import main

SCENE = '''import kinemo as k


@k.scene
def demo(s: k.Scene):
    box = k.Rect(w=1, h=1, x=7.8)  # kinemo: allow W1001 (cropped on purpose)
    label = k.Text("hi", size=0.4)  # kinemo: allow W1003 (stale)
    dot = k.Dot(x=7.9)  # kinemo: allow W1001, W1002 (only one is real)
    s.add(box, label, dot)
    s.wait(1)
'''


def check_json(path: Path, capsys: pytest.CaptureFixture[str], *extra: str) -> list[dict[str, object]]:
    main(["check", str(path), "--json", *extra])
    report = json.loads(capsys.readouterr().out)
    return [d for scene in report["scenes"] for d in scene["diagnostics"] if d["code"] == "W0120"]


def test_allows_that_silence_nothing_are_reported(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "scene.py"
    path.write_text(SCENE, encoding="utf-8")
    found = check_json(path, capsys)
    assert [(d["spans"][0]["line"], d["message"]) for d in found] == [  # type: ignore[index]
        (7, "# kinemo: allow W1003 silences nothing on this line"),
        (8, "# kinemo: allow W1002 silences nothing on this line"),
    ]


def test_fix_removes_only_the_unused_codes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "scene.py"
    path.write_text(SCENE, encoding="utf-8")
    main(["check", str(path), "--fix"])
    text = path.read_text(encoding="utf-8")
    assert '    box = k.Rect(w=1, h=1, x=7.8)  # kinemo: allow W1001 (cropped on purpose)\n' in text
    assert '    label = k.Text("hi", size=0.4)\n' in text
    assert "    dot = k.Dot(x=7.9)  # kinemo: allow W1001 (only one is real)\n" in text
    capsys.readouterr()
    assert check_json(path, capsys) == []


def test_allows_are_not_judged_for_one_scene_of_a_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "scene.py"
    path.write_text(SCENE, encoding="utf-8")
    assert check_json(path, capsys, "--scene", "demo") == []
