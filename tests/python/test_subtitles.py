"""Subtitles from narration: cues of at most two 42-character lines, timed by the words,
written as SRT and WebVTT next to the video with `kinemo render --subtitles`."""

from __future__ import annotations

from pathlib import Path

from kinemo.audio.voice import NarrationLine
from kinemo.cli.main import main
from kinemo.export.subtitles import cues, srt, vtt


def line(text: str, start: float, per_word: float = 0.4) -> NarrationLine:
    words = text.split()
    times = tuple((w, start + i * per_word, start + (i + 1) * per_word) for i, w in enumerate(words))
    return NarrationLine(start, start + len(words) * per_word, text, None, None, None, "estimated", None, times)


def test_a_long_line_becomes_several_cues_of_two_short_lines() -> None:
    text = "The derivative tells you how fast something changes at one instant, not over a whole trip, and that is the whole point of it."
    result = cues([line(text, 2.0)])
    assert len(result) >= 2
    for start, end, cue in result:
        assert end > start >= 2.0
        assert all(len(part) <= 42 for part in cue.split("\n")) and cue.count("\n") <= 1
    assert result[0][0] == 2.0 and result[-1][1] == 2.0 + len(text.split()) * 0.4
    assert [r[0] for r in result] == sorted(r[0] for r in result)


def test_srt_and_vtt_formats() -> None:
    lines = [line("Hello there.", 0.0), line("A second line.", 61.5)]
    assert srt(lines).startswith("1\n00:00:00,000 --> 00:00:00,800\nHello there.\n")
    assert "00:01:01.500 --> 00:01:02.700\nA second line." in vtt(lines)
    assert vtt(lines).startswith("WEBVTT\n\n")


def test_render_writes_subtitles_next_to_the_video(tmp_path: Path) -> None:
    scene = tmp_path / "scene.py"
    scene.write_text(
        'import kinemo as k\n\n\n@k.scene\ndef talk(s: k.Scene):\n'
        '    with s.voice("Every right triangle hides a relation."):  # kinemo: allow W1401\n'
        '        s.play(k.fade_in(k.Dot()), duration=0.3)\n',
        encoding="utf-8",
    )
    out = tmp_path / "talk.mp4"
    assert main(["render", str(scene), "--quality", "draft", "--progress", "none", "--subtitles", "--out", str(out)]) == 0
    assert (tmp_path / "talk.srt").read_text(encoding="utf-8").startswith("1\n00:00:00,000 --> ")
    assert "Every right triangle hides a relation." in (tmp_path / "talk.vtt").read_text(encoding="utf-8")
