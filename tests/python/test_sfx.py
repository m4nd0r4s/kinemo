"""`k.sfx`: built-in sound effects, made by kinemo, identical in every render."""

from __future__ import annotations

import wave
from pathlib import Path

import pytest

import kinemo as k
from kinemo.audio.sfx import RECIPES, effect_path
from conftest import build


@pytest.mark.parametrize("name", sorted(RECIPES))
def test_each_effect_is_a_short_mono_wav_that_does_not_clip(name: str, tmp_path: Path) -> None:
    path = effect_path(name, str(tmp_path))
    with wave.open(path) as w:
        assert (w.getnchannels(), w.getsampwidth(), w.getframerate()) == (1, 2, 44100)
        seconds = w.getnframes() / w.getframerate()
        frames = w.readframes(w.getnframes())
    assert 0.02 <= seconds <= 1.5
    peak = max(abs(int.from_bytes(frames[i : i + 2], "little", signed=True)) for i in range(0, len(frames), 2))
    assert 0.3 * 32767 < peak <= 0.81 * 32767


def test_effects_are_the_same_bytes_every_time(tmp_path: Path) -> None:
    first = Path(effect_path("whoosh", str(tmp_path / "a"))).read_bytes()
    second = Path(effect_path("whoosh", str(tmp_path / "b"))).read_bytes()
    assert first == second


def test_an_effect_is_made_once_and_reused(tmp_path: Path) -> None:
    path = Path(effect_path("click", str(tmp_path)))
    stamp = path.stat().st_mtime_ns
    assert effect_path("click", str(tmp_path)) == str(path)
    assert path.stat().st_mtime_ns == stamp


def test_k_sfx_plays_with_k_sound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    @build
    def scene(s: k.Scene) -> None:
        dot = k.Dot()
        s.play(k.fade_in(dot), k.sound(k.sfx.pop(), gain=0.5))

    assert "pop-v" in scene.builder.to_json()
