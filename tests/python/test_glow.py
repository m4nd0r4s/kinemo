"""`glow=` and `glow_color=`: a halo that brightens pixels around a shape and animates."""

from __future__ import annotations

import kinemo as k
from conftest import build


def brightness_beside(builder: object, t: float) -> int:
    w, h, data = builder.frame_rgba(t, "draft")  # type: ignore[attr-defined]
    # A pixel just right of the dot at the frame's center.
    x, y = w // 2 + int(h / 9 * 0.25) + 6, h // 2  # 6 px past the edge of the dot
    i = (y * w + x) * 4
    return sum(data[i : i + 3])


def test_glow_lights_the_surroundings_and_animates() -> None:
    @build
    def scene(s: k.Scene) -> None:
        dot = k.Dot(r=0.25, fill=k.YELLOW, glow=0.0).place(at="center")
        s.add(dot)
        s.play(dot.to(glow=1.0), duration=1)

    before, after = brightness_beside(scene.builder, 0.0), brightness_beside(scene.builder, 1.0)
    assert after > before + 60


def test_glow_on_a_text_glows_its_glyphs() -> None:
    @build
    def scene(s: k.Scene) -> None:
        s.add(k.Text("O", size=1.0, glow=1.0, glow_color=k.RED).place(at="center"))

    w, h, data = scene.builder.frame_rgba(0.0, "draft")
    reds = sum(1 for i in range(0, len(data), 4) if data[i] > data[i + 2] + 40)
    assert reds > 50
