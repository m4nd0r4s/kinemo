"""`k.Text`: text with minimal inline markup and addressable parts.

A text is a group of glyph runs: one `rest` run draws every glyph, and each part you
address (`txt["world"]`, `txt.words[1]`) becomes its own run with its own props."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Mapping, Iterator, Sequence, Unpack, overload

from ..diagnostics import KinemoError
from .groups import Group
from .node import Node
from ..values.aliases import ALIGNMENTS
from .props import STYLE, PropSpec

if TYPE_CHECKING:
    from ..anim.animation import Animation
    from ..anim.ease import EaseLike
    from ..reactive.signal import Blend
    from .keywords import PlaceKeywords, PropChanges
    from ..values.aliases import Align, FloatVal, StrVal
    from ..values.color import Color
    from .keywords import TextKeywords
    from .props import PropAccessor

TEXT_STYLE = {
    **STYLE,
    "fill_opacity": PropSpec("float", 1.0),
    "stroke_width": PropSpec("float", 0.0),
}


#: Char index of glyphs that are not part of the text (line numbers in code).
NOT_IN_TEXT = 2**53


class GlyphRun(Node):
    """Glyphs selected from the text-like object it belongs to. Styled and moved like
    any object; its glyphs disappear from the text's `rest` run."""

    kind = "glyphs"
    PROPS = {**TEXT_STYLE, "indices": PropSpec("floats", (), "step_end"), "rest": PropSpec("bool", False, "step_end")}

    if TYPE_CHECKING:
        fill: PropAccessor[Color]
        fill_opacity: PropAccessor[float]
        stroke: PropAccessor[Color]
        stroke_width: PropAccessor[float]
        dash: PropAccessor[list[float]]
        color: PropAccessor[Color]
        indices: PropAccessor[list[float]]
        rest: PropAccessor[bool]


class TextLike(Group):
    """Common base of `Text`, `Math` and `Code`: glyph runs and part lookup."""

    STYLE_BINDINGS = ("fill", "fill_opacity", "stroke", "stroke_width")

    if TYPE_CHECKING:
        # Style props of every text-like object (each subclass's PROPS include TEXT_STYLE).
        fill: PropAccessor[Color]
        fill_opacity: PropAccessor[float]
        stroke: PropAccessor[Color]
        stroke_width: PropAccessor[float]
        dash: PropAccessor[list[float]]
        #: The fill (`.to(color=...)` recolors the glyphs).
        color: PropAccessor[Color]
        size: PropAccessor[float]
        _runs: dict[tuple[Any, ...], GlyphRun]
        _rest: GlyphRun

    def _parts(self) -> list[Node]:
        object.__setattr__(self, "_runs", {})
        rest = self._new_run(rest=True)
        object.__setattr__(self, "_rest", rest)
        object.__setattr__(rest, "_part", "rest")
        return [rest]

    def _new_run(self, rest: bool = False, indices: Sequence[int] = ()) -> GlyphRun:
        bindings: dict[str, Any] = {p: self._sig(p) for p in self.STYLE_BINDINGS}
        return GlyphRun(rest=rest, indices=[float(i) for i in indices], **bindings)

    def _color_props(self) -> tuple[str, ...]:
        return ("fill",)

    def _color_targets(self) -> list[tuple[Node, str]]:
        return [(self, "fill")]

    # ---- glyph lookup --------------------------------------------------------------
    def _glyphs(self) -> tuple[str, list[dict[str, Any]]]:
        s = self._scene
        info = json.loads(s._b.glyph_info(self._id, s.cursor))
        return info["text"], info["glyphs"]

    def _run_for(self, key: tuple[Any, ...], indices: list[int]) -> GlyphRun:
        if not indices:
            raise KinemoError.make("K0105", f"no glyph matches {key[1]!r}", fixes=[("check the text you are looking for", None)])
        runs: dict[tuple[Any, ...], GlyphRun] = self._runs
        if key not in runs:
            run = self._new_run(indices=indices)
            label = f'["{key[1]}"]' if key[0] in ("find", "tex") else f"{key[0]}[{key[1]}]"
            if key[0] == "find" and key[2]:
                label = f'.find_all("{key[1]}")[{key[2]}]'
            object.__setattr__(run, "_part", label)
            run._adopt_into(self)
            runs[key] = run
        return runs[key]

    def find_all(self, needle: str) -> list[GlyphRun]:
        """Every occurrence of `needle` (in the text without markup), as parts."""
        _, glyphs = self._glyphs()
        chars = self._char_text()
        out: list[GlyphRun] = []
        start = chars.find(needle)
        occurrence = 0
        while start >= 0 and needle:
            span = range(start, start + len(needle))
            indices = [i for i, g in enumerate(glyphs) if g["char_index"] in span]
            out.append(self._run_for(("find", needle, occurrence), indices))
            occurrence += 1
            start = chars.find(needle, start + len(needle))
        return out

    def _char_text(self) -> str:
        """The plain text characters by char index (markup removed)."""
        _, glyphs = self._glyphs()
        glyphs = [g for g in glyphs if g["char_index"] < NOT_IN_TEXT]
        size = max((g["char_index"] for g in glyphs), default=-1) + 1
        chars = [" "] * size
        for g in glyphs:
            chars[g["char_index"]] = g["key"]
        return "".join(chars)

    @overload
    def __getitem__(self, key: str) -> GlyphRun: ...
    @overload
    def __getitem__(self, key: int) -> Node: ...
    def __getitem__(self, key: str | int) -> Node:
        """`txt["world"]`: the part with that text; `txt[i]`: the i-th child."""
        if isinstance(key, str):
            found = self.find_all(key)
            if not found:
                raise KinemoError.make("K0105", f"{key!r} does not appear in the text", fixes=[("check the text you are looking for", None)])
            return found[0]
        return super().__getitem__(key)

    @property
    def chars(self) -> "PartView":
        """Characters as parts: `txt.chars[3:7]` (markup removed)."""
        return PartView(self, "chars")

    @property
    def words(self) -> "PartView":
        """Whitespace-separated words as parts: `txt.words[1]`."""
        return PartView(self, "words")

    @property
    def lines(self) -> "PartView":
        """Laid-out lines as parts: `txt.lines[0]`."""
        return PartView(self, "lines")


class PartView:
    """`txt.chars[3:7]`, `txt.words[1]`, `txt.lines[0]`."""

    def __init__(self, owner: TextLike, unit: str) -> None:
        self.owner = owner
        self.unit = unit

    def _groups(self) -> list[list[int]]:
        _, glyphs = self.owner._glyphs()
        field = {"chars": "char_index", "words": "word", "lines": "line"}[self.unit]
        keys = sorted({g[field] for g in glyphs})
        return [[i for i, g in enumerate(glyphs) if g[field] == k] for k in keys]

    def __len__(self) -> int:
        return len(self._groups())

    def __iter__(self) -> Iterator[GlyphRun]:
        return (self[i] for i in range(len(self)))

    def __getitem__(self, index: int | slice) -> GlyphRun:
        groups = self._groups()
        if isinstance(index, slice):
            chosen = groups[index]
            indices = [i for g in chosen for i in g]
            key = (self.unit, f"{index.start}:{index.stop}:{index.step}")
        else:
            indices = groups[index]
            key = (self.unit, index if index >= 0 else len(groups) + index)
        return self.owner._run_for(key, indices)


class Text(TextLike):
    """`k.Text("Hello **world**", size=0.6, width=6, align="left")`. Reactive with a lambda."""

    kind = "text"
    PROPS = {
        **TEXT_STYLE,
        "text": PropSpec("str", "", "step_end"),
        "size": PropSpec("float", lambda t: t.font_size),
        "wrap": PropSpec("float", 0.0),
        "align": PropSpec("str", "left", "step_end", ALIGNMENTS),
        "mono": PropSpec("bool", False, "step_end"),
    }

    if TYPE_CHECKING:
        text: PropAccessor[str]
        wrap: PropAccessor[float]
        align: PropAccessor[str]
        mono: PropAccessor[bool]

    def __init__(self, text: StrVal = "", *, size: FloatVal | None = None, width: float | None = None, align: Align = "left", **props: Unpack[TextKeywords]) -> None:
        options: dict[str, Any] = dict(props)
        if size is not None:
            options["size"] = size
        super().__init__(text=text, wrap=width or 0.0, align=align, **options)

    def to(  # pyright: ignore[reportIncompatibleMethodOverride] - adds `text=`
        self,
        *,
        text: str | None = None,
        duration: float | None = None,
        ease: EaseLike | None = None,
        delay: float = 0.0,
        blend: Blend = "replace",
        place: PlaceKeywords | Mapping[str, object] | None = None,
        **props: Unpack[PropChanges],
    ) -> "Animation":
        """Like `Node.to`; a new `text=` string morphs the glyphs (equal characters travel)."""
        if text is None:
            return super().to(duration=duration, ease=ease, delay=delay, blend=blend, place=place, **props)
        from .._runtime.spans import user_span
        from ..anim.animation import Par
        from ..anim.text_change import TextChange

        span = user_span()
        change = TextChange(self, text, duration, ease, delay, span)
        if not props and place is None:
            return change
        rest = super().to(duration=duration, ease=ease, delay=delay, blend=blend, place=place, **props)
        return Par([rest, change], span=span)
