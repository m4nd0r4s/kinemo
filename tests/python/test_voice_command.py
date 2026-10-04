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


#: A batch voice: every line of `{lines_file}` in one run (one "model load", logged once).
BATCH_VOICE = '''import json, sys, wave
lines = json.load(open(sys.argv[1], encoding="utf-8"))
open("runs.log", "a", encoding="utf-8").write(str(len(lines)) + "\\n")
for line in lines:
    if "skip" in line["text"]:
        continue
    words = line["text"].split()
    with wave.open(line["out"], "wb") as sound:
        sound.setnchannels(1); sound.setsampwidth(2); sound.setframerate(8000)
        sound.writeframes(b"\\x00\\x00" * 4000 * len(words))
    json.dump({"word_times": [i * 0.5 for i in range(len(words))]}, open(line["out"] + ".json", "w", encoding="utf-8"))
'''


def batch(folder: Path) -> None:
    (folder / "batch.py").write_text(BATCH_VOICE, encoding="utf-8")
    (folder / "kinemo.toml").write_text('[tts]\nprovider = "command"\ncommand = ' + json.dumps([sys.executable, "batch.py", "{lines_file}"]) + "\n", encoding="utf-8")


def test_a_lines_file_command_makes_every_line_in_one_run(folder: Path, capsys: pytest.CaptureFixture[str]) -> None:
    batch(folder)
    assert main(["voice", "scene.py", "--progress", "json"]) == 0
    assert (folder / "runs.log").read_text(encoding="utf-8").split() == ["3"]
    assert (folder / "audio" / "B01.wav").exists() and (folder / "audio" / "B02.wav.json").exists()
    assert main(["voice", "scene.py", "--check"]) == 0
    progress = [json.loads(line) for line in capsys.readouterr().err.splitlines() if line.startswith("{")]
    steps = [(p["done"], p["total"]) for p in progress if p["event"] == "progress"]
    assert steps[-1] == (3, 3) and progress[-1]["event"] == "done"


def test_a_batch_that_skips_a_line_is_k1401_naming_it(folder: Path, capsys: pytest.CaptureFixture[str]) -> None:
    batch(folder)
    (folder / "scene.py").write_text(SCENE.replace("An inline line", "Please skip this"), encoding="utf-8")
    assert main(["voice", "scene.py", "--progress", "none"]) == 1
    out = capsys.readouterr().out
    assert "K1401" in out and "1 of 3 line(s)" in out


def test_a_build_with_a_batch_command_makes_one_line_per_run(folder: Path) -> None:
    from kinemo.cli.loader import build, find_scenes, load_module

    batch(folder)
    (folder / "scene.py").write_text('import kinemo as k\n\n\n@k.scene\ndef one(s: k.Scene):\n    with s.voice("Just one line"):\n        s.wait(0.2)\n', encoding="utf-8")
    result = build(find_scenes(load_module(str(folder / "scene.py")))[0], {})
    assert result.scene is not None and result.scene.duration > 1.5
    assert (folder / "runs.log").read_text(encoding="utf-8").split() == ["1"]
