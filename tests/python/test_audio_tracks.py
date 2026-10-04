"""The audio tracks of `kinemo dev`: one clip per narration line (with its text, words, beat,
script line and `s.voice` line), per sound and for the music, which lasts to the scene's end."""

from __future__ import annotations

import json
import wave
from pathlib import Path

from kinemo.cli.dev_meta import audio_tracks
from kinemo.cli.loader import build, find_scenes, load_module

SCRIPT = """# Title

### B01 · Start

> One two three.
"""

SCENE = '''import kinemo as k

script = k.Script("script.md")


@k.scene
def episode(s: k.Scene):
    s.start(k.music("bed.wav"))
    with s.voice(script["B01"]):
        s.play(k.sound("click.wav"), k.fade_in(k.Dot()), duration=0.3)
    with s.voice("Not recorded yet"):  # kinemo: allow W1401
        s.wait(0.2)
'''


def write_wav(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(8000)
        sound.writeframes(b"\x00\x00" * int(8000 * seconds))


def tracks(tmp_path: Path) -> list[dict[str, object]]:
    (tmp_path / "script.md").write_text(SCRIPT, encoding="utf-8")
    (tmp_path / "scene.py").write_text(SCENE, encoding="utf-8")
    write_wav(tmp_path / "audio" / "B01.wav", 1.5)
    write_wav(tmp_path / "click.wav", 0.2)
    write_wav(tmp_path / "bed.wav", 60.0)
    result = build(find_scenes(load_module(str(tmp_path / "scene.py")))[0], {})
    assert result.scene is not None, [d.render() for d in result.diagnostics]
    return audio_tracks(result, json.loads(result.scene.builder.to_json()))


def test_every_clip_is_on_its_track(tmp_path: Path) -> None:
    clips = tracks(tmp_path)
    by_role = {role: [c for c in clips if c["role"] == role] for role in ("voice", "sound", "music")}
    assert len(by_role["voice"]) == 2 and len(by_role["sound"]) == 1 and len(by_role["music"]) == 1
    (sound,) = by_role["sound"]
    assert sound["label"] == "click.wav" and sound["end"] - sound["start"] == 0.2  # type: ignore[operator]
    assert sound["span"]["line"] == 10  # type: ignore[index]


def test_music_ends_with_the_scene(tmp_path: Path) -> None:
    (music,) = [c for c in tracks(tmp_path) if c["role"] == "music"]
    clips = tracks(tmp_path)
    assert music["start"] == 0.0 and music["end"] == max(c["end"] for c in clips)  # type: ignore[type-var]


def test_a_beat_carries_its_text_words_and_sources(tmp_path: Path) -> None:
    beat = next(c for c in tracks(tmp_path) if c["role"] == "voice" and c["index"] is not None)
    narration = beat["narration"]
    assert narration["beat"] == "B01" and narration["text"] == "One two three."  # type: ignore[index]
    assert [w[0] for w in narration["words"]] == ["One", "two", "three."]  # type: ignore[index]
    assert narration["script"]["line"] == 3 and narration["script"]["file"].endswith("script.md")  # type: ignore[index]
    assert beat["span"]["line"] == 9  # type: ignore[index]


def test_a_line_without_audio_is_an_estimated_clip(tmp_path: Path) -> None:
    line = next(c for c in tracks(tmp_path) if c["role"] == "voice" and c["index"] is None)
    assert line["narration"]["timing"] == "estimated" and line["file"] is None  # type: ignore[index]
    assert line["end"] > line["start"]  # type: ignore[operator]
