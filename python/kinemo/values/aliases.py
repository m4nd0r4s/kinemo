"""Type aliases shared by the public API: what each kind of reactive input accepts.

Every object prop accepts `k.Val[T]`: a plain value, a signal or expression, or a lambda
traced to native code. These aliases name the common `T`s."""

from __future__ import annotations

from typing import Literal, Sequence, Union, get_args

from ..reactive.expr import Expr, Val
from ..theme.tokens import ThemeToken
from .color import Color
from .vec import Vec

#: A color: `k.BLUE`, `k.rgb(...)`, a theme token (`k.theme.accent`) or a hex string.
ColorLike = Union[Color, ThemeToken, str]
#: A 2D point or vector: `k.Vec` or a pair of numbers.
VecLike = Union[Vec, tuple[float, float]]

FloatVal = Val[float]
BoolVal = Val[bool]
StrVal = Val[str]
ColorVal = Val[ColorLike]
FloatsVal = Val[Sequence[float]]
#: A point input: a point, a vector expression, a lambda, or a pair whose coordinates
#: may themselves be expressions (`(x, k.sin(k.time))`).
VecVal = Union[Val[VecLike], tuple[Union[float, Expr[float]], Union[float, Expr[float]]]]

#: Named points of a box (`place(at="top-left")`, `k.grow(obj, from_="bottom")`).
Anchor = Literal[
    "center", "top", "bottom", "left", "right",
    "top-left", "top-right", "bottom-left", "bottom-right",
]
#: Cross-axis alignment in containers and placements.
Align = Literal["center", "left", "right", "top", "bottom", "top-left", "top-right", "bottom-left", "bottom-right"]

#: The values of `Anchor` and `Align`, for props that store them as strings.
ANCHORS: tuple[str, ...] = get_args(Anchor)
ALIGNMENTS: tuple[str, ...] = get_args(Align)
