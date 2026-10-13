"""`--size`: one scene rendered and checked in another format than the one it declares."""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from kinemo.cli.main import main

SCENE = '''import kinemo as k


@k.scene
def card(s: k.Scene):
    title = k.Text("Same scene", size=0.6).place(at="center")
    wide = k.Rect(w=14, h=1).place(below=title, gap=0.5)
    s.play(k.write(title), k.fade_in(wide))
    s.wait(0.5)
'''


def png_size(path: Path) -> tuple[int, int]:
    return struct.unpack(">II", path.read_bytes()[16:24])


def test_render_uses_the_size_given_on_the_command_line(tmp_path: Path) -> None:
    scene = tmp_path / "scene.py"
    scene.write_text(SCENE, encoding="utf-8")
    assert main(["render", str(scene), "--size", "vertical", "--at", "end", "--out", str(tmp_path / "v.png"), "--progress", "none"]) == 0
    assert png_size(tmp_path / "v.png") == (1080, 1920)
    assert main(["render", str(scene), "--at", "end", "--out", str(tmp_path / "w.png"), "--progress", "none"]) == 0
    assert png_size(tmp_path / "w.png") == (1920, 1080)


def test_check_lints_the_layout_of_the_other_format(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scene = tmp_path / "scene.py"
    scene.write_text(SCENE, encoding="utf-8")

    def codes(*extra: str) -> set[str]:
        main(["check", str(scene), "--json", *extra])
        report = json.loads(capsys.readouterr().out)
        return {d["code"] for s in report["scenes"] for d in s["diagnostics"]}

    assert "W1001" not in codes()
    assert "W1001" in codes("--size", "vertical"), "a 14-unit bar does not fit a vertical frame"


def test_an_unknown_size_is_an_error_with_the_sizes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    scene = tmp_path / "scene.py"
    scene.write_text(SCENE, encoding="utf-8")
    assert main(["check", str(scene), "--size", "huge"]) != 0
    assert "unknown size 'huge'" in capsys.readouterr().out
