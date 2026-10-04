"""`k.Script`: narration by beat, read from Markdown (MinuteMath's format) or JSON; a beat uses
its recorded audio by convention, adds the marks `<id>` and `<id>.end`, and is W1404 when its
audio was made from a different text."""

from __future__ import annotations

import json
import wave
from pathlib import Path

import pytest

from kinemo.audio.script import text_hash
from kinemo.cli.loader import build, find_scenes, load_module

SCRIPT = """---
status: approved
---
# E001 · Speed right now

Intro notes that are not narration.

### B01 · Hook (~6 s)

> Your speedometer says sixty.
> But sixty what, at this very instant?

### B02 · Average (~4 s)

> Distance over time is an average.
"""

SCENE = '''import kinemo as k

script = k.Script("script.md")


@k.scene
def episode(s: k.Scene):
    with s.voice(script["B01"]) as v:  # kinemo: allow W1401
        s.play(k.fade_in(k.Dot()), duration=0.5)
    with s.voice(script["B02"]):  # kinemo: allow W1401
        s.wait(0.2)
'''


def wav(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(8000)
        sound.writeframes(b"\x00\x00" * int(8000 * seconds))


def build_scene(folder: Path, script: str = SCRIPT, scene: str = SCENE, name: str = "script.md"):  # type: ignore[no-untyped-def]
    (folder / name).write_text(script, encoding="utf-8")
    path = folder / "scene.py"
    path.write_text(scene, encoding="utf-8")
    return build(find_scenes(load_module(str(path)))[0], {})


def test_beats_are_read_from_markdown_and_estimated_without_audio(tmp_path: Path) -> None:
    result = build_scene(tmp_path)
    scene = result.scene
    assert scene is not None
    # 11 + 6 words at 150 wpm (0.4 s each).
    assert scene.marks == {"B01": 0.0, "B01.end": pytest.approx(4.4), "B02": pytest.approx(4.4), "B02.end": pytest.approx(6.8)}


def test_a_beat_uses_its_recorded_audio(tmp_path: Path) -> None:
    wav(tmp_path / "audio" / "B01.wav", 3.0)
    result = build_scene(tmp_path)
    assert result.scene is not None
    assert result.scene.marks["B01.end"] == pytest.approx(3.0)
    assert [d.code for d in result.diagnostics if d.code == "W1404"] == []


def test_audio_made_from_another_text_is_w1404(tmp_path: Path) -> None:
    wav(tmp_path / "audio" / "B01.wav", 3.0)
    (tmp_path / "audio" / "manifest.json").write_text(json.dumps({"B01": text_hash("an older version of the line")}), encoding="utf-8")
    result = build_scene(tmp_path)
    assert "W1404" in [d.code for d in result.diagnostics]


def test_json_scripts_and_unknown_beats(tmp_path: Path) -> None:
    scene = SCENE.replace("script.md", "script.json").replace('script["B02"]', 'script["B2"]')
    result = build_scene(tmp_path, json.dumps({"B01": "One two three", "B02": "Four"}), scene, "script.json")
    error = next(d for d in result.diagnostics if d.level == "error")
    assert "no beat 'B2'" in error.message and "'B02'" in error.fixes[0].description
