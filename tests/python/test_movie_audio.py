"""Narrated movies: each scene's narration keeps its place in movie time (crossfades overlap
two scenes), so `kinemo render --subtitles` covers the whole movie."""

from __future__ import annotations

from pathlib import Path

import pytest

import kinemo as k
from kinemo.cli.main import main

MOVIE = '''import kinemo as k


@k.scene(size="720p", fps=12)
def one(s: k.Scene):
    with s.voice("First scene speaks."):  # kinemo: allow W1401
        s.play(k.fade_in(k.Dot()), duration=0.3)


@k.scene(size="720p", fps=12)
def two(s: k.Scene):
    with s.voice("Second scene speaks."):  # kinemo: allow W1401
        s.play(k.fade_in(k.Dot()), duration=0.3)


movie = k.movie([one, two], transitions=[k.crossfade(0.5)], name="film")
'''


def test_scenes_start_where_the_renderer_joins_them(tmp_path: Path) -> None:
    from kinemo.cli.loader import load_module

    path = tmp_path / "film.py"
    path.write_text(MOVIE, encoding="utf-8")
    module = load_module(str(path))
    film: k.Movie = module.movie  # type: ignore[attr-defined]
    built = film.build()
    starts = film.starts(built)
    assert starts == [0.0, pytest.approx(built[0].duration - 0.5)]
    lines = film.narration(built)
    assert [line.text for line in lines] == ["First scene speaks.", "Second scene speaks."]
    assert lines[1].start == pytest.approx(starts[1]) and lines[1].words[0][1] == pytest.approx(starts[1])


def test_render_writes_movie_subtitles(tmp_path: Path) -> None:
    path = tmp_path / "film.py"
    path.write_text(MOVIE, encoding="utf-8")
    assert main(["render", str(path), "--quality", "draft", "--progress", "none", "--subtitles", "--out", str(tmp_path)]) == 0
    vtt = (tmp_path / "film.vtt").read_text(encoding="utf-8")
    assert "First scene speaks." in vtt and "Second scene speaks." in vtt
