"""`txt.to(text="...")`: changing the string of a text morphs its glyphs.

Equal characters travel to their new place and the rest fade, through `k.morph` with a
copy carrying the new string; at the end the text itself shows the new string again."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .._runtime.spans import Span
from .animation import Animation
from .ease import Ease
from .morph import Morph

if TYPE_CHECKING:
    from ..objects.text import Text
    from ..scene.scene import Scene


class TextChange(Animation):
    def __init__(self, text: "Text", new: str, duration: float | None, ease: Any, delay: float, span: Span) -> None:
        super().__init__(duration, ease, delay, span)
        self.text = text
        self.new = new

    def describe(self) -> str:
        return f"{self.text._label()}.to(text)"

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        from ..objects.text import Text

        old = self.text
        cursor = s.cursor
        s.cursor = start
        try:
            copy = Text(
                self.new,
                size=old.size.now,
                width=old.wrap.now or None,
                align=old.align.now,  # type: ignore[arg-type]
                fill=old.fill.now,
                fill_opacity=old.fill_opacity.now,
                name=f"{old._label()}→",
            )
            copy.place(at=old.world.center)
        finally:
            s.cursor = cursor
        Morph(old, copy, None, None, None, 0.0, self.span)._emit(s, start, duration, ease)
        end = start + duration
        old._scene._push_set(old._sig("text"), self.new, self.span, t=end)
        s._exit(copy, end)
        s._enter(old, end)
