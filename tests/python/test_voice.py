"""`with s.voice(...) as v`: the line as a `k.Voice` to sync with what is said; W1403 when the
block's content runs past the narration."""

from __future__ import annotations

import wave
from pathlib import Path
from typing import Any

import pytest

import kinemo as k
from conftest import build, diagnostic_of, lint_codes

#: The silent estimate speaks 150 words per minute: 0.4 s per word.
WORD = 0.4
seen: dict[str, Any] = {}


def test_the_block_gives_a_voice_with_its_words() -> None:
    @build
    def scene(s: k.Scene) -> None:
        s.wait(1)
        with s.voice("The slope is the rate of change") as v:  # kinemo: allow W1401
            seen["voice"] = v
            s.wait(0.5)

    v = seen["voice"]
    assert isinstance(v, k.Voice)
    assert (v.start, v.duration, v.end) == pytest.approx((1.0, 7 * WORD, 1.0 + 7 * WORD))
    assert [w for w, _, _ in v.words] == ["The", "slope", "is", "the", "rate", "of", "change"]
    assert v.words[1][1:] == pytest.approx((1.0 + WORD, 1.0 + 2 * WORD))
    assert scene.duration == pytest.approx(1.0 + 7 * WORD + scene.config.tail)


def test_at_waits_for_a_fraction_or_a_phrase_and_time_does_not_wait() -> None:
    @build
    def scene(s: k.Scene) -> None:
        with s.voice("The slope is the rate of change, the slope again") as v:  # kinemo: allow W1401
            seen["half"] = v.time(0.5)
            seen["cursor_after_time"] = s.cursor
            seen["rate"] = v.at("Rate of")
            seen["cursor_after_at"] = s.cursor
            seen["second"] = v.time("slope", occurrence=2)
            seen["back"] = v.at(0.1)          # already past it: the cursor stays
            seen["cursor_end"] = s.cursor

    assert seen["half"] == pytest.approx(10 * WORD / 2)
    assert seen["cursor_after_time"] == 0.0
    assert seen["rate"] == seen["cursor_after_at"] == pytest.approx(4 * WORD)
    assert seen["second"] == pytest.approx(8 * WORD)
    assert seen["cursor_end"] == pytest.approx(4 * WORD)


def test_a_phrase_that_is_not_said_suggests_the_closest() -> None:
    def scene(s: k.Scene) -> None:
        with s.voice("The slope is the rate of change") as v:  # kinemo: allow W1401
            v.at("rate of chance")

    d = diagnostic_of(scene, "K0105")
    assert "'rate of chance' is not in the narration" in d.message
    assert "rate of change" in d.fixes[0].description


def test_content_past_the_narration_is_w1403() -> None:
    @build
    def too_long(s: k.Scene) -> None:
        with s.voice("Short line"):  # kinemo: allow W1401
            s.play(k.draw(k.Circle()), duration=2)

    @build
    def fits(s: k.Scene) -> None:
        with s.voice("A line long enough for the circle"):  # kinemo: allow W1401
            s.play(k.draw(k.Circle()), duration=2)

    assert "W1403" in lint_codes(too_long)
    assert "W1403" not in lint_codes(fits)


def test_an_audio_file_with_its_text_gets_words_and_marks(tmp_path: Path) -> None:
    audio = tmp_path / "line.wav"
    with wave.open(str(audio), "wb") as sound:
        sound.setnchannels(1)
        sound.setsampwidth(2)
        sound.setframerate(8000)
        sound.writeframes(b"\x00\x00" * 8000 * 2)  # 2 s

    @build
    def scene(s: k.Scene) -> None:
        with s.voice(str(audio), text="Every right [triangle]{tri} hides a relation") as v:
            seen["voice"] = v
            seen["relation"] = v.time("relation")

    assert seen["voice"].duration == pytest.approx(2.0)
    assert len(seen["voice"].words) == 6
    assert seen["relation"] == pytest.approx(2.0 * 5 / 6)
    assert scene.marks["tri"] == pytest.approx(2.0 * 2 / 6)
