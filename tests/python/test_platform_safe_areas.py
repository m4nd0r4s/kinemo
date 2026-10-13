"""`platform=`: the zones a vertical video's app covers narrow the safe area (W1001,
`clamp=True`, `s.frame.safe`)."""

from __future__ import annotations

import pytest

import kinemo as k
from kinemo.diagnostics import KinemoError
from conftest import build


def safe_of(**config: object) -> k.Scene:
    @k.scene(name="probe", **config)  # type: ignore[arg-type]
    def probe(s: k.Scene) -> None:
        s.wait(0.1)

    return probe.build()


def test_reels_raise_the_bottom_of_the_safe_area() -> None:
    plain = safe_of(size="vertical").frame.safe
    reels = safe_of(size="vertical", platform="reels").frame.safe
    assert plain.bottom == pytest.approx(-8.0 + 0.5)
    # 420 of 1920 px at the bottom: 3.5 of 16 units.
    assert reels.bottom == pytest.approx(-8.0 + 3.5)
    assert reels.right == pytest.approx(4.5 - 140 / 120)
    assert reels.top < plain.top


def test_platforms_only_apply_to_vertical_frames() -> None:
    assert safe_of(size="1080p", platform="reels").frame.safe == safe_of(size="1080p").frame.safe


def test_w1001_reports_content_under_the_platform_buttons() -> None:
    @build(size="vertical", platform="tiktok")
    def scene(s: k.Scene) -> None:
        caption = k.Text("Look here", size=0.5, y=-6.5)
        s.add(caption)
        s.wait(0.5)

    @build(size="vertical")
    def plain(s: k.Scene) -> None:
        caption = k.Text("Look here", size=0.5, y=-6.5)
        s.add(caption)
        s.wait(0.5)

    from kinemo.lints import run_lints

    assert "W1001" in {d.code for d in run_lints(scene)}
    assert "W1001" not in {d.code for d in run_lints(plain)}


def test_clamp_keeps_a_placed_object_above_the_covered_zone() -> None:
    @build(size="vertical", platform="shorts")
    def scene(s: k.Scene) -> None:
        note = k.Text("Subscribe", size=0.5).place(at="bottom", margin=0.2, clamp=True)
        s.add(note)
        s.wait(0.1)

    note = next(n for n in scene._nodes if n._name == "note")
    assert float(note.bottom.now) >= scene.frame.safe.bottom - 1e-6


def test_an_unknown_platform_is_an_error() -> None:
    with pytest.raises(KinemoError, match="unknown platform 'snapchat'"):
        safe_of(size="vertical", platform="snapchat")
