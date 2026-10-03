"""`k.Bar`: a value as a bar that grows from its base, with an optional label."""

from __future__ import annotations

from typing import TYPE_CHECKING, Unpack

from .groups import Group
from .node import Node
from .props import PropSpec, accent
from .shapes import Rect
from .text import Text

if TYPE_CHECKING:
    from ..values.aliases import ColorLike, FloatVal
    from .keywords import TransformKeywords
    from .props import PropAccessor


class Bar(Group):
    """`k.Bar(5, label=True)`. `bar.value` is a signal; the bar grows up from its base,
    which stays where `x=`/`y=` put it (`place` aligns the whole bar, so a placed bar
    moves as it grows). The label shows the value rounded to two decimals."""

    PROPS = {"value": PropSpec("float", 0.0)}

    if TYPE_CHECKING:
        value: PropAccessor[float]
        _bar_opts: tuple[bool, float, float, ColorLike | None]
        #: The bar itself (created at construction).
        rect: Rect
        #: The value label (only with `label=True`).
        label: Text

    def __init__(self, value: FloatVal = 0.0, *, label: bool = False, width: float = 0.6, unit: float = 0.4, color: ColorLike | None = None, **props: Unpack[TransformKeywords]) -> None:
        object.__setattr__(self, "_bar_opts", (label, width, unit, color))
        super().__init__(value=value, **props)

    def _parts(self) -> list[Node]:
        label, width, unit, color = self._bar_opts
        v = self.value
        rect = Rect(w=width, h=v * unit, y=v * (unit / 2), fill=color if color is not None else accent(self._scene.theme), fill_opacity=0.85, stroke_width=0.0)
        object.__setattr__(self, "rect", rect)
        object.__setattr__(rect, "_part", "rect")
        parts: list[Node] = [rect]
        if label:
            text = Text(lambda: f"{round(v(), 2):g}", size=0.32).place(below=rect, gap=0.12)
            object.__setattr__(self, "label", text)
            object.__setattr__(text, "_part", "label")
            parts.append(text)
        return parts

    def _grow_parts(self) -> tuple[list[Node], list[Node]]:
        label = self.__dict__.get("label")
        return [self.rect], [label] if label is not None else []

    def _color_targets(self) -> list[tuple[Node, str]]:
        return [(self.rect, "fill"), (self.rect, "stroke")]
