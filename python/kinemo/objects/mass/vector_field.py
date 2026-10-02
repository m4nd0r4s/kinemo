"""`k.VectorField`: arrows of a field sampled on a grid, scaled and colored by magnitude."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Union, Unpack

from ...reactive.expr import Expr
from ..props import PropSpec, accent
from .per_point import MassNode, PerPointColor, per_point_value
from .symbolic_point import SymbolicPoint, trace_field

if TYPE_CHECKING:
    from ...reactive.native import FloatExpr, VecExpr
    from ...theme.tokens import Theme
    from ...values.aliases import FloatVal, VecVal
    from ...values.color import Color
    from ...values.vec import Vec
    from ..keywords import FieldKeywords
    from ..props import PropAccessor

#: A vector field: `lambda x, y: (vx, vy)` (written for numbers, traced once),
#: `lambda t, x, y: ...` (with time), `lambda p: ...` (the symbolic point), a vector
#: expression, or another field object.
FieldFunction = Union[
    Callable[[float, float], "VecExpr | tuple[FloatExpr, FloatExpr]"],
    Callable[[float, float, float], "VecExpr | tuple[FloatExpr, FloatExpr]"],
    Callable[[SymbolicPoint], "VecExpr | tuple[FloatExpr, FloatExpr]"],
    "Expr[Vec]",
    MassNode,
]


def _secondary(t: Theme) -> Color:
    return t.secondary


def field_expr(fn: FieldFunction) -> Expr[Vec]:
    """A field given as a function (`lambda x, y: (-y, x)`, `lambda p:`, `lambda t, x, y:`),
    an expression, or another `VectorField`/`StreamLines` → its per-point vec2 expression."""
    expression = getattr(fn, "field_expression", None) if isinstance(fn, MassNode) else None
    if isinstance(expression, Expr):
        return expression
    if isinstance(fn, Expr):
        return fn
    if isinstance(fn, MassNode) or not callable(fn):
        raise TypeError(f"invalid field: {fn!r} (pass a function, such as lambda x, y: (-y, x))")
    return trace_field(fn)


class VectorField(MassNode):
    """Arrows of `fn(x, y) -> (vx, vy)` on a grid with `density` columns across the
    region (`x_range` × `y_range`, default: the frame inset by 1 unit).

        field = k.VectorField(lambda x, y: (-y, x), density=30)

    `fn` is traced once (it may use `k.time` and signals) and evaluated natively at
    every grid point. Arrow length is `length` × cell × |v| / max|v|; color mixes
    `color_low` → `color_high` (theme accent → secondary) by the same magnitude, unless
    `color` is given (a value or a function of the point).
    """

    kind = "vector_field"
    PROPS = {
        "field": PropSpec("vec2", (0.0, 0.0)),
        "density": PropSpec("float", 30.0),
        "length": PropSpec("float", 0.8),
        "x_range": PropSpec("vec2", None),
        "y_range": PropSpec("vec2", None),
        "color": PropSpec("color", None),
        "color_low": PropSpec("color", accent),
        "color_high": PropSpec("color", _secondary),
        "stroke_width": PropSpec("float", 2.5),
    }

    if TYPE_CHECKING:
        field: PropAccessor[Vec]
        density: PropAccessor[float]
        length: PropAccessor[float]
        x_range: PropAccessor[Vec]
        y_range: PropAccessor[Vec]
        color: PropAccessor[Color]
        color_low: PropAccessor[Color]
        color_high: PropAccessor[Color]
        stroke_width: PropAccessor[float]
        #: The field as a per-point vector expression.
        field_expression: Expr[Vec]

    def __init__(
        self,
        fn: FieldFunction,
        density: FloatVal = 30,
        *,
        length: FloatVal = 0.8,
        x_range: VecVal | None = None,
        y_range: VecVal | None = None,
        color: PerPointColor | None = None,
        **props: Unpack[FieldKeywords],
    ) -> None:
        expression = field_expr(fn)
        object.__setattr__(self, "field_expression", expression)
        super().__init__(
            field=expression,
            density=density,
            length=length,
            x_range=x_range,
            y_range=y_range,
            color=per_point_value(color, "color"),
            **props,
        )
