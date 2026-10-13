"""`k.Captions()`: the narration burned into the video, a phrase at a time, in the safe area,
with the word being spoken highlighted."""

from __future__ import annotations

import json

import pytest

import kinemo as k
from kinemo.diagnostics import KinemoError
from kinemo.lints import run_lints
from conftest import build


def captions_of(scene: k.Scene) -> list[k.Text]:
    return [n for n in scene._nodes if isinstance(n, k.Text) and n._name != "title" and n._part is None]  # pyright: ignore[reportPrivateUsage]


def test_each_phrase_is_a_caption_shown_while_it_is_spoken() -> None:
    @build(size="vertical", platform="reels")
    def scene(s: k.Scene) -> None:
        k.Captions(chars=20, rows=1)
        title = k.Text("1089", size=1.2).place(at="center")
        with s.voice("Pick any three digit number whose first and last digits differ."):  # kinemo: allow W1401
            s.play(k.write(title))
        s.wait(0.5)

    captions = captions_of(scene)
    assert len(captions) >= 3, "one row of 20 characters at a time"
    texts = [c.text.now for c in captions]
    assert all(len(t) <= 20 for t in texts)
    assert " ".join(texts) == "Pick any three digit number whose first and last digits differ."
    # Each sits above the zone Reels covers.
    for caption in captions:
        assert float(caption.bottom.now) >= scene.frame.safe.bottom - 1e-6
    ir = json.loads(scene.builder.to_json())
    presence = {o["id"]: o["presence"] for o in ir["objects"]}
    first = presence[captions[0]._id]  # pyright: ignore[reportPrivateUsage]
    assert first[0][1] is True and first[-1][1] is False


def test_captions_pass_the_lints() -> None:
    @build(size="vertical", platform="tiktok")
    def scene(s: k.Scene) -> None:
        k.Captions(highlight=k.YELLOW)
        with s.voice("Reverse it, subtract, then reverse the answer and add."):  # kinemo: allow W1401
            s.wait(0.5)

    codes = {d.code for d in run_lints(scene)} - {"W1401"}
    assert codes == set(), codes


def test_markup_in_the_narration_stays_text() -> None:
    @build
    def scene(s: k.Scene) -> None:
        k.Captions()
        with s.voice("It costs $5 * 2 and `ten` dollars."):  # kinemo: allow W1401
            s.wait(0.2)

    assert " ".join(c._char_text() for c in captions_of(scene)) == "It costs $5 * 2 and `ten` dollars."  # pyright: ignore[reportPrivateUsage]


def test_a_scene_without_narration_gets_w1407() -> None:
    @build
    def scene(s: k.Scene) -> None:
        k.Captions()
        s.wait(0.5)

    assert "W1407" in {d.code for d in scene.lints.items}


def test_one_captions_per_scene() -> None:
    def scene(s: k.Scene) -> None:
        k.Captions()
        k.Captions()

    with pytest.raises(KinemoError):
        build(scene)
