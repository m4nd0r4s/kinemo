"""Synthesized narration is cached: a second build reuses the audio instead of calling the
provider again."""

from __future__ import annotations

import wave
from pathlib import Path
import pytest

from kinemo.audio import voice
from kinemo.audio.tts import Speech
from kinemo.cli.loader import build, find_scenes, load_module

SCENE = '''import kinemo as k


@k.scene
def narrated(s: k.Scene):
    with s.voice("Every right [triangle]{tri} hides a relation"):
        s.play(k.write(k.Text("a² + b² = c²")))
'''


class CountingProvider:
    name = "counting"

    def __init__(self) -> None:
        self.calls = 0

    def synthesize(self, text: str, voice_name: str | None, out_path: str) -> Speech:
        self.calls += 1
        with wave.open(out_path, "wb") as sound:
            sound.setnchannels(1)
            sound.setsampwidth(2)
            sound.setframerate(8000)
            sound.writeframes(b"\x00\x00" * 16000)
        return Speech(out_path, 2.0, [0.0, 0.3, 0.6, 0.9, 1.2, 1.5])


def build_marks(path: Path) -> dict[str, float]:
    module = load_module(str(path))
    result = build(find_scenes(module)[0], {})
    assert result.scene is not None
    return dict(result.scene.marks)


def test_a_second_build_reuses_the_synthesized_audio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "kinemo.toml").write_text('[tts]\nprovider = "counting"\n', encoding="utf-8")
    scene = tmp_path / "scene.py"
    scene.write_text(SCENE, encoding="utf-8")
    provider = CountingProvider()
    monkeypatch.setattr(voice, "load_provider", lambda name: provider if name == "counting" else None)

    first = build_marks(scene)
    second = build_marks(scene)

    assert provider.calls == 1
    assert first == second == {"tri": pytest.approx(0.6)}  # "triangle" is the third word


def test_an_unfinished_entry_is_synthesized_again(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "kinemo.toml").write_text('[tts]\nprovider = "counting"\n', encoding="utf-8")
    scene = tmp_path / "scene.py"
    scene.write_text(SCENE, encoding="utf-8")
    provider = CountingProvider()
    monkeypatch.setattr(voice, "load_provider", lambda name: provider if name == "counting" else None)
    build_marks(scene)
    for record in (tmp_path / ".kinemo-cache").glob("*.json"):
        record.unlink()  # the audio exists, but its record (written last) does not
    build_marks(scene)
    assert provider.calls == 2
