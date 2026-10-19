"""`kinemo render --format lesson`: a folder with the player, the IR with its baked layouts, and
the scene's audio and images, that plays from any static host."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kinemo.cli.main import main
from kinemo.export.lesson import player_available

pytestmark = pytest.mark.skipif(not player_available(), reason="the lesson player is not built (python scripts/build_player.py)")

LESSON = '''
import kinemo as k

@k.scene
def slope(s: k.Scene):
    s.add(k.Math(r"f(x) = x^2"))
    s.add(k.Image(r"{image}", width=1, x=4))
    s.play(k.sound(r"{sound}"))
    q = s.ask("Slope at x = 2?", k.Choice(["2", "4"]), correct="4")
    with q.correct():
        s.wait(0.5)
'''


@pytest.fixture
def scene_file(tmp_path: Path) -> Path:
    from kinemo.audio.sfx import effect_path

    image = Path(__file__).resolve().parents[2] / "docs" / "examples" / "images" / "editor-mode.png"
    path = tmp_path / "slope.py"
    path.write_text(LESSON.format(image=image, sound=effect_path("click", str(tmp_path / "cache"))), encoding="utf-8")
    return path


def test_the_folder_plays_without_kinemo(scene_file: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert main(["render", str(scene_file), "--format", "lesson", "--out", str(out)]) == 0
    folder = out / "slope"
    for name in ("index.html", "embed-test.html", "embed.js", "player.js", "lesson.js", "render_worker.js", "player.css", "pkg/kinemo_web_bg.wasm"):
        assert (folder / name).is_file(), name
    assert "<title>slope</title>" in (folder / "index.html").read_text(encoding="utf-8")
    data = json.loads((folder / "lesson.json").read_text(encoding="utf-8"))
    assert data["format"] == "kinemo-lesson" and data["version"] == 1
    assert [q["id"] for q in data["ir"]["questions"]] == ["q1"]
    assert {m["tex"] for m in data["baked"]["math"]} == {"f(x) = x^2"}
    (sound,) = data["audio"]
    assert sound["url"] == "audio/0.wav" and (folder / sound["url"]).is_file()
    (image,) = data["images"]
    assert image["url"] == "images/0.png" and (folder / image["url"]).is_file()
    assert image["path"].endswith("editor-mode.png")


def test_what_an_answer_drives_must_be_native(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "python_fn.py"
    path.write_text(
        '''
import math
import kinemo as k

@k.scene
def lesson(s: k.Scene):
    angle = s.answer(k.Float(0, 3))
    dot = k.Dot(x=k.python(math.cos)(angle))
    s.add(dot)
    s.ask("?", angle, correct=1, tolerance=0.1)
''',
        encoding="utf-8",
    )
    assert main(["render", str(path), "--format", "lesson", "--out", str(tmp_path / "out")]) == 1
    assert "W1302" in capsys.readouterr().out
    assert not (tmp_path / "out" / "lesson").exists()
