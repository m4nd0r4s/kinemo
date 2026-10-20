"""Scene configuration: output size presets, fps, theme, seed, tail."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..diagnostics import KinemoError
from ..theme.tokens import DEFAULT as DEFAULT_THEME, Theme, ThemeToken
from ..values.color import Color, parse as parse_color

SIZES: dict[str, tuple[int, int]] = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4k": (3840, 2160),
    "square": (1080, 1080),
    "vertical": (1080, 1920),
}

#: Scene units on the short side of the frame.
SHORT_SIDE_UNITS = 9.0

#: What each app covers with its buttons and captions on a vertical video, in pixels of a
#: 1080 × 1920 frame: (top, right, bottom, left). Approximations of the 2026 layouts.
PLATFORMS: dict[str, tuple[int, int, int, int]] = {
    "reels": (220, 140, 420, 60),
    "tiktok": (180, 160, 480, 60),
    "shorts": (160, 180, 380, 60),
}


@dataclass
class SceneConfig:
    name: str
    size: tuple[int, int] = (1920, 1080)
    fps: float = 60.0
    background: Any = None
    seed: int = 0
    tail: float = 0.5
    theme: Theme = DEFAULT_THEME
    camera: str = "2d"
    params: dict[str, Any] = field(default_factory=dict)
    #: Integrated loudness of the audio track in LUFS (`[audio] loudness`); None keeps the mix.
    loudness: float | None = None
    #: The app a vertical video is made for (`platform="reels"`): its covered zones narrow the
    #: safe area. Ignored for frames that are not vertical.
    platform: str | None = None
    #: What a video does at a lesson's questions: a quiz (time to answer, then the reveal) or
    #: the correct path.
    questions: str = "quiz"

    @property
    def covered_units(self) -> tuple[float, float, float, float]:
        """(top, right, bottom, left) of the frame the platform covers, in scene units."""
        w, h = self.size
        if self.platform is None or h <= w:
            return (0.0, 0.0, 0.0, 0.0)
        per_pixel = self.frame_units[1] / h * (h / 1920)
        top, right, bottom, left = PLATFORMS[self.platform]
        return (top * per_pixel, right * per_pixel, bottom * per_pixel, left * per_pixel)

    @property
    def frame_units(self) -> tuple[float, float]:
        w, h = self.size
        if w >= h:
            return SHORT_SIDE_UNITS * w / h, SHORT_SIDE_UNITS
        return SHORT_SIDE_UNITS, SHORT_SIDE_UNITS * h / w

    def background_color(self) -> Color:
        bg = self.background if self.background is not None else self.theme.bg
        if isinstance(bg, ThemeToken):
            bg = bg.resolve(self.theme)
        return parse_color(bg)

    def ir(self) -> dict[str, Any]:
        fw, fh = self.frame_units
        return {
            "name": self.name,
            "width": self.size[0],
            "height": self.size[1],
            "fps": float(self.fps),
            "seed": int(self.seed),
            "tail": float(self.tail),
            "background": self.background_color().components(),
            "frame_w": fw,
            "frame_h": fh,
            "loudness": self.loudness,
            "covered": list(self.covered_units),
            "questions": self.questions,
        }


def parse_size(size: Any) -> tuple[int, int]:
    if isinstance(size, str):
        if size not in SIZES:
            raise KinemoError.make(
                "K0105",
                f"unknown size {size!r}",
                fixes=[(f"use one of {', '.join(SIZES)} or (width, height)", None)],
            )
        return SIZES[size]
    w, h = size
    return int(w), int(h)
