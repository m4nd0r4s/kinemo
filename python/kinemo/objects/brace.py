"""`k.Brace`: a curly brace along one side of an object, following it as it moves."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Literal, Unpack, cast, get_args

from .._runtime.spans import user_span
from ..diagnostics import KinemoError
from .groups import Group
from .node import Node
from .props import PropSpec, fg
from .shapes import Shape
from .text import Text

if TYPE_CHECKING:
    from ..values.aliases import ColorLike, FloatVal
    from .keywords import PlaceKeywords, TransformKeywords
    from .props import PropAccessor

#: Side of the target a brace spans; its tip points outward.
BraceDirection = Literal["down", "up", "left", "right"]

DIRECTIONS = ("down", "up", "left", "right")
_LABEL_SIDE = {"down": "below", "up": "above", "left": "left_of", "right": "right_of"}


class BraceShape(Shape):
    """The brace outline, computed by the layout from the target's box at every frame."""

    kind = "brace"
    PROPS: ClassVar[dict[str, PropSpec]] = {
        "target": PropSpec("object", None, "step_end"),
        "direction": PropSpec("str", "down", "step_end", get_args(BraceDirection)),
        "gap": PropSpec("float", 0.1),
        "depth": PropSpec("float", 0.25),
        "fill_opacity": PropSpec("float", 1.0),
        "stroke_width": PropSpec("float", 0.0),
    }

    if TYPE_CHECKING:
        target: PropAccessor[int]
        direction: PropAccessor[str]
        gap: PropAccessor[float]
        depth: PropAccessor[float]


class Brace(Group):
    """`k.Brace(obj, "down", label="n")`: spans the side of `obj` named by `direction`,
    `gap` units away, tip pointing outward; `label` (text or an object) sits beyond the
    tip as `brace.label`. The brace itself is `brace.shape`."""

    if TYPE_CHECKING:
        _brace_opts: tuple[Node, str, str | Node | None, FloatVal, FloatVal, ColorLike | None, float]
        #: The brace outline.
        shape: BraceShape
        #: The label beyond the tip (`None` without `label=`).
        label: Node | None

    def __init__(self, target: Node, direction: BraceDirection = "down", label: str | Node | None = None, gap: FloatVal = 0.1, *, depth: FloatVal = 0.25, color: ColorLike | None = None, label_gap: float = 0.12, **props: Unpack[TransformKeywords]) -> None:
        if not isinstance(target, Node):
            raise KinemoError.make("K0105", f"k.Brace expects an object, got {type(target).__name__}", spans=[user_span()])
        if direction not in DIRECTIONS:
            raise KinemoError.make(
                "K0105",
                f"unknown k.Brace direction: {direction!r}",
                spans=[user_span()],
                fixes=[(f"use one of {', '.join(DIRECTIONS)}", None)],
            )
        object.__setattr__(self, "_brace_opts", (target, direction, label, gap, depth, color, label_gap))
        super().__init__(**props)

    def _parts(self) -> list[Node]:
        target, direction, label, gap, depth, color, label_gap = self._brace_opts
        fill = color if color is not None else fg(self._scene.theme)
        shape = BraceShape(target=target, direction=direction, gap=gap, depth=depth, fill=fill)
        object.__setattr__(shape, "_part", "shape")
        object.__setattr__(self, "shape", shape)
        parts: list[Node] = [shape]
        text: Node | None = None
        if label is not None:
            text = label if isinstance(label, Node) else Text(str(label), size=0.4)
            text.place(**cast("PlaceKeywords", {_LABEL_SIDE[direction]: shape, "gap": label_gap}))
            object.__setattr__(text, "_part", "label")
            parts.append(text)
        object.__setattr__(self, "label", text)
        return parts

    def _color_targets(self) -> list[tuple[Node, str]]:
        return [(self.shape, "fill")]
