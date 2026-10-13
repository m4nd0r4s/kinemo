"""`k.Captions()`: the narration shown as captions burned into the video.

Most short videos are watched muted. Created anywhere in a scene, `k.Captions()` waits for the
end of the build, then turns every `s.voice` line into short captions: a phrase at a time, on
a plate at the bottom of the safe area (above the buttons of `platform=`), with the word being
spoken in the highlight color when the words have times.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from .._runtime.spans import user_span
from ..diagnostics import KinemoError

if TYPE_CHECKING:
    from ..scene.scene import Scene
    from ..values.aliases import ColorLike
    from .node import Node

#: Seconds a caption takes to appear and to go.
FADE = 0.08


def _escaped(word: str) -> str:
    """A spoken word as literal text: no markup (`*`, `` ` ``, `$`) in captions."""
    for mark in ("\\", "*", "`", "$"):
        word = word.replace(mark, "\\" + mark)
    return word


class Captions:
    """`k.Captions(size=0.5, highlight=k.YELLOW)`: the scene's narration as captions in the
    video, a phrase at a time (`chars=` per row, `rows=` per caption), at the bottom of the
    safe area (`at="top"` or `"center"` for elsewhere), on a plate (`plate=False` for none).
    The word being spoken takes `highlight` (`None`: no highlight). Create it once, anywhere
    in the scene: the captions are made from every `s.voice` line when the build ends."""

    def __init__(
        self,
        *,
        size: float = 0.5,
        highlight: "ColorLike | None" = None,
        chars: int = 28,
        rows: int = 2,
        at: Literal["bottom", "top", "center"] = "bottom",
        plate: bool = True,
    ) -> None:
        from .._runtime.context import current_scene

        s = current_scene()
        if s.__dict__.get("_captions") is not None:
            raise KinemoError.make("K0105", "a scene has one k.Captions", spans=[user_span()], fixes=[("keep the first one", None)])
        if chars < 8 or rows < 1:
            raise KinemoError.make("K0105", "k.Captions needs chars >= 8 and rows >= 1", spans=[user_span()])
        self.size, self.highlight, self.chars, self.rows, self.at, self.plate = size, highlight, chars, rows, at, plate
        self.span = user_span()
        s.__dict__["_captions"] = self

    def _build(self, s: "Scene") -> None:
        """Called when the build ends: one caption per phrase of the narration."""
        from ..anim.ease import ease
        from ..anim.verbs import _ramp, _set  # pyright: ignore[reportPrivateUsage]
        from ..export.subtitles import timed_cues
        from .shapes import RoundedRect
        from .text import Text

        lines = list(s.__dict__.get("_narration", []))
        if not lines:
            s.lints.warn("W1407", "k.Captions has no narration to show", spans=[self.span], fixes=[("narrate with s.voice(...)", None)])
            return
        theme = s.theme
        highlight = self.highlight
        safe = s.frame.safe
        cursor = s.cursor
        for start, end, rows in timed_cues(lines, self.chars, self.rows):
            words = [word for row in rows for word in row]
            text = "\n".join(" ".join(_escaped(w) for w, _, _ in row) for row in rows)
            s.cursor = start
            pad = self.size * 0.35 if self.plate else 0.0
            # Never wider than the safe area: platforms cover the sides unevenly.
            caption = Text(text, size=self.size, width=safe.width - 2 * pad, align="center", fill=theme.fg)
            if highlight is not None and all(t1 > t0 for _, t0, t1 in words):
                # The word being spoken takes the highlight while it is said (its parts are made
                # before the caption enters, so they come and go with it).
                for index, (_, t0, t1) in enumerate(words):
                    word = caption.words[index]
                    _set(s, word, "fill", t0, highlight, self.span)
                    _set(s, word, "fill", min(t1, end), theme.fg, self.span)
            parts: list[Node] = [caption]
            if self.plate:
                plate = RoundedRect(w=float(caption.width.now) + 2 * pad, h=float(caption.height.now) + 2 * pad, radius=pad, fill=theme.bg, fill_opacity=0.72, stroke_width=0.0)
                parts.insert(0, plate)
            half = float(caption.height.now) / 2 + pad
            y = {"bottom": safe.bottom + half, "top": safe.top - half, "center": (safe.bottom + safe.top) / 2}[self.at]
            for part in parts:
                part.set(x=(safe.left + safe.right) / 2, y=y)
                s._enter(part, start)
                _ramp(s, part, "_fade", start, FADE, ease.smooth, 0.0, 1.0, self.span)
                _ramp(s, part, "_fade", max(start, end - FADE), FADE, ease.smooth, 1.0, 0.0, self.span)
                s._exit(part, end)
        s.cursor = cursor


def build_captions(s: "Scene") -> None:
    """The scene's `k.Captions`, made from its narration (end of the build)."""
    captions: Captions | None = s.__dict__.get("_captions")
    if captions is not None:
        captions._build(s)  # pyright: ignore[reportPrivateUsage]



