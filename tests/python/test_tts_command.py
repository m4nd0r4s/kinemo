"""`[tts] provider = "command"`: an external program makes the narration; `[tts] wpm` sets the
speaking rate of the estimate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from kinemo.cli.loader import build, find_scenes, load_module

SCENE = '''import kinemo as k


@k.scene
def narrated(s: k.Scene):
    with s.voice("One two [three]{three} four") as v:
        s.play(k.write(k.Text("hi")), duration=0.3)
'''

#: A stand-in voice: one second of silence per word, and the words' start times.
VOICE = '''import json, sys, wave
text_file, out = sys.argv[1], sys.argv[2]
words = open(text_file, encoding="utf-8").read().split()
with wave.open(out, "wb") as sound:
    sound.setnchannels(1); sound.setsampwidth(2); sound.setframerate(8000)
    sound.writeframes(b"\\x00\\x00" * 8000 * len(words))
if "--times" in sys.argv:
    json.dump({"word_times": [i * 1.0 for i in range(len(words))]}, open(out + ".json", "w", encoding="utf-8"))
'''


def project(tmp_path: Path, tts: str) -> Path:
    (tmp_path / "voice.py").write_text(VOICE, encoding="utf-8")
    (tmp_path / "kinemo.toml").write_text(f"[tts]\n{tts}\n", encoding="utf-8")
    scene = tmp_path / "scene.py"
    scene.write_text(SCENE, encoding="utf-8")
    return scene


def built(scene: Path):  # type: ignore[no-untyped-def]
    result = build(find_scenes(load_module(str(scene)))[0], {})
    assert result.scene is not None, [d.render() for d in result.diagnostics]
    return result


def command(*argv: str) -> str:
    """The `[tts]` lines of a command provider (JSON strings are valid TOML strings, and escape
    the backslashes of Windows paths)."""
    return 'provider = "command"\ncommand = ' + json.dumps([sys.executable, *argv])


def test_the_command_makes_the_narration_with_its_word_times(tmp_path: Path) -> None:
    result = built(project(tmp_path, command("voice.py", "{text_file}", "{out}", "--times")))
    assert result.scene.duration == pytest.approx(4.0 + result.scene.config.tail)
    assert result.scene.marks["three"] == pytest.approx(2.0)


def test_without_word_times_they_are_spread_over_the_audio(tmp_path: Path) -> None:
    result = built(project(tmp_path, command("voice.py", "{text_file}", "{out}")))
    assert result.scene.marks["three"] == pytest.approx(4.0 * 2 / 4)


def test_a_failing_command_is_k1401_with_its_error(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("import sys\nprint('model not found', file=sys.stderr)\nsys.exit(3)\n", encoding="utf-8")
    scene = project(tmp_path, command("broken.py", "{text_file}", "{out}"))
    result = build(find_scenes(load_module(str(scene)))[0], {})
    failure = next(d for d in result.diagnostics if d.code == "K1401")
    assert "exited with 3" in failure.message and "model not found" in failure.message


def test_wpm_sets_the_rate_of_the_estimate(tmp_path: Path) -> None:
    (tmp_path / "kinemo.toml").write_text("[tts]\nwpm = 120\n", encoding="utf-8")
    scene = tmp_path / "scene.py"
    scene.write_text(SCENE, encoding="utf-8")
    result = built(scene)
    assert result.scene.marks["three"] == pytest.approx(2 * 0.5)  # 120 wpm: 0.5 s per word
