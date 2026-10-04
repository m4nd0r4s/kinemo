"""`kinemo voice`: makes only the narration lines that have no audio yet or whose text changed,
writes a script's beats next to it (audio, word times, manifest), and `--check` lists them."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from kinemo.cli.main import main

#: A stand-in voice: 0.5 s per word and the words' start times; logs each line it makes.
VOICE = '''import json, sys, wave
text_file, out = sys.argv[1], sys.argv[2]
words = open(text_file, encoding="utf-8").read().split()
with wave.open(out, "wb") as sound:
    sound.setnchannels(1); sound.setsampwidth(2); sound.setframerate(8000)
    sound.writeframes(b"\\x00\\x00" * 4000 * len(words))
json.dump({"word_times": [i * 0.5 for i in range(len(words))]}, open(out + ".json", "w", encoding="utf-8"))
open("made.log", "a", encoding="utf-8").write(" ".join(words) + "\\n")
'''

SCRIPT = """### B01 · Start

> One two three four.

### B02 · End

> Five six.
"""

SCENE = '''import kinemo as k

script = k.Script("script.md")


@k.scene
def episode(s: k.Scene):
    with s.voice(script["B01"]) as v:
        s.play(k.fade_in(k.Dot()), duration=0.3)
    with s.voice(script["B02"]):
        s.wait(0.2)
    with s.voice("An inline line"):
        s.wait(0.2)
'''


@pytest.fixture
def folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "voice.py").write_text(VOICE, encoding="utf-8")
    (tmp_path / "kinemo.toml").write_text('[tts]\nprovider = "command"\ncommand = ' + json.dumps([sys.executable, "voice.py", "{text_file}", "{out}"]) + "\n", encoding="utf-8")
    (tmp_path / "script.md").write_text(SCRIPT, encoding="utf-8")
    (tmp_path / "scene.py").write_text(SCENE, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def made(folder: Path) -> list[str]:
    log = folder / "made.log"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def test_check_lists_missing_lines_and_makes_nothing(folder: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["voice", "scene.py", "--check"]) == 1
    out = capsys.readouterr().out
    assert "3 line(s), 3 to make" in out and "missing  B01" in out
    assert made(folder) == []


def test_voice_makes_beats_next_to_the_script_and_inline_lines_in_the_cache(folder: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["voice", "scene.py", "--progress", "none"]) == 0
    assert sorted(made(folder)) == ["An inline line", "Five six.", "One two three four."]
    assert (folder / "audio" / "B01.wav").exists() and (folder / "audio" / "B01.wav.json").exists()
    manifest = json.loads((folder / "audio" / "manifest.json").read_text(encoding="utf-8"))
    assert set(manifest) == {"B01", "B02"}
    # Everything is made: a second run makes nothing.
    assert main(["voice", "scene.py", "--check"]) == 0
    assert main(["voice", "scene.py", "--progress", "none"]) == 0
    assert len(made(folder)) == 3
    # The build uses the beats' audio and their word times.
    capsys.readouterr()
    main(["check", "--json", "scene.py"])
    report = json.loads(capsys.readouterr().out)["scenes"][0]
    assert [(n["beat"], n["timing"]) for n in report["narration"]] == [("B01", "provider"), ("B02", "provider"), (None, "provider")]
    assert report["marks"]["B01.end"] == pytest.approx(2.0)


def test_a_changed_beat_is_stale_and_made_again(folder: Path, capsys: pytest.CaptureFixture[str]) -> None:
    main(["voice", "scene.py", "--progress", "none"])
    (folder / "script.md").write_text(SCRIPT.replace("Five six.", "Five six seven."), encoding="utf-8")
    capsys.readouterr()
    assert main(["voice", "scene.py", "--check"]) == 1
    assert "stale    B02" in capsys.readouterr().out
    main(["voice", "scene.py", "--progress", "none"])
    assert made(folder)[-1] == "Five six seven."
    assert main(["voice", "scene.py", "--force", "B01", "--progress", "none"]) == 0
    assert made(folder)[-1] == "One two three four."
