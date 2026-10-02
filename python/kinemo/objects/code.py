"""`k.Code`: syntax-highlighted code with stable tokens, line highlight and code morphs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Mapping, Sequence, Unpack

from .._runtime.spans import user_span
from ..anim.animation import Animation, Seq
from ..anim.prop import PropTo
from ..diagnostics import KinemoError
from .node import Node
from .props import PropSpec
from .text import TEXT_STYLE, GlyphRun, TextLike

if TYPE_CHECKING:
    from ..anim.ease import EaseLike
    from ..theme.tokens import Theme
    from .keywords import StyleKeywords
    from .props import PropAccessor


def _palette_for(theme: Theme) -> str:
    bg = theme.bg
    luminance = 0.2126 * bg.r + 0.7152 * bg.g + 0.0722 * bg.b
    return "light" if luminance > 0.5 else "dark"


class CodeRun(GlyphRun):
    """A run of code glyphs: recoloring it overrides the syntax colors."""

    PROPS = {"recolor": PropSpec("float", 0.0)}

    if TYPE_CHECKING:
        recolor: PropAccessor[float]

    def _expand(self, props: Mapping[str, Any], *, for_write: bool) -> list[Any]:
        out = super()._expand(props, for_write=for_write)
        if "color" in props or "fill" in props:
            out.append((self._sig("recolor"), 1.0))
        return out


class Code(TextLike):
    """`k.Code(src, lang="python", theme="auto", line_numbers=True)`."""

    kind = "code"
    PROPS = {
        **TEXT_STYLE,
        "code": PropSpec("str", "", "step_end"),
        "lang": PropSpec("str", "text", "step_end"),
        "size": PropSpec("float", 0.32),
        "line_numbers": PropSpec("bool", False, "step_end"),
        "palette": PropSpec("str", "dark", "step_end"),
        "highlight": PropSpec("floats", (), "step_start"),
        "highlight_amount": PropSpec("float", 0.0),
    }

    if TYPE_CHECKING:
        code: PropAccessor[str]
        lang: PropAccessor[str]
        line_numbers: PropAccessor[bool]
        palette: PropAccessor[str]
        highlight_amount: PropAccessor[float]

    def __init__(self, src: str, lang: str = "python", *, theme: str = "auto", line_numbers: bool = False, size: float = 0.32, **props: Unpack[StyleKeywords]) -> None:
        from .._runtime.context import current_scene

        palette = _palette_for(current_scene().theme) if theme == "auto" else theme
        super().__init__(code=src.strip("\n"), lang=lang, line_numbers=line_numbers, size=size, palette=palette, **props)

    def _new_run(self, rest: bool = False, indices: Sequence[int] = ()) -> GlyphRun:
        bindings: dict[str, Any] = {p: self._sig(p) for p in self.STYLE_BINDINGS}
        return CodeRun(rest=rest, indices=[float(i) for i in indices], **bindings)

    def highlight(self, lines: Sequence[int] | None = None, *, duration: float | None = None, ease: EaseLike | None = None) -> Animation:
        """Dim every line except `lines` (1-based); `None` removes the highlight.
        ≡ `.to(highlight=lines, highlight_amount=1)` (fading out first when changing)."""
        span = user_span()
        amount = self._sig("highlight_amount")
        if lines is None:
            return PropTo([(amount, 0.0)], duration=duration, ease=ease, span=span)
        count = len(str(self.code.now).split("\n"))
        outside = [n for n in lines if not 1 <= n <= count]
        if outside:
            raise KinemoError.make(
                "K0105",
                f"{self._label()}.highlight: line {outside[0]} does not exist; the code has {count} line(s), numbered from 1",
                spans=[span],
                fixes=[(f"use line numbers between 1 and {count}", None)],
            )
        chosen = [float(n) for n in lines]
        show = PropTo([(self._sig("highlight"), chosen), (amount, 1.0)], duration=duration, ease=ease, span=span)
        if self.highlight_amount.now > 0:
            half = (duration if duration is not None else 1.0) / 2
            hide = PropTo([(amount, 0.0)], duration=half, ease=ease, span=span)
            return Seq([hide, show.with_(duration=half)], span=span)
        return show

    def _color_targets(self) -> list[tuple[Node, str]]:
        return [(self, "fill")]

    def _char_text(self) -> str:
        """Code glyphs index the source itself."""
        return str(self.code.now)
