"""`k.StreamLines`: integral curves of a field (RK4, in the core), with a fading tail."""

from __future__ import annotations

from typing import TYPE_CHECKING, Unpack

from ..props import PropSpec, accent
from .per_point import MassNode, PerPointColor, PointsInput, per_point_value
from .vector_field import FieldFunction, VectorField, _secondary, field_expr
from .xy_input import to_xy

if TYPE_CHECKING:
    from ...reactive.expr import Expr
    from ...values.aliases import FloatVal, VecVal
    from ...values.color import Color
    from ...values.vec import Vec
    from ..keywords import FieldKeywords
    from ..props import PropAccessor


class StreamLines(MassNode):
    """Lines that follow `field` (a `VectorField`, or a function like `VectorField`'s).

        lines = k.StreamLines(field, seeds=200)
        s.play(lines.to(progress=1), duration=3)

    `seeds`: a count (deterministic Halton points over the region) or the starting
    points (`(n, 2)` array or list). Lines advance `step` units per RK4 step along the
    field direction, at most `steps` steps, and stop at the region border or where the
    field vanishes. `progress` (0..1) draws them over time; `tail` is the fraction of
    each line visible behind its head; the tail fades to `fade` opacity. Colors mix
    `color_low` → `color_high` by mean magnitude, unless `color` is given.
    """

    kind = "stream_lines"
    PROPS = {
        "field": PropSpec("vec2", (0.0, 0.0)),
        "seeds": PropSpec("points", [], "step_end"),
        "seed_count": PropSpec("float", 200.0, "step_end"),
        "step": PropSpec("float", 0.05),
        "steps": PropSpec("float", 60.0, "step_end"),
        "progress": PropSpec("float", 1.0),
        "tail": PropSpec("float", 1.0),
        "fade": PropSpec("float", 0.0),
        "x_range": PropSpec("vec2", None),
        "y_range": PropSpec("vec2", None),
        "color": PropSpec("color", None),
        "color_low": PropSpec("color", accent),
        "color_high": PropSpec("color", _secondary),
        "stroke_width": PropSpec("float", 2.0),
    }

    if TYPE_CHECKING:
        field: PropAccessor[Vec]
        seeds: PropAccessor[list[Vec]]
        seed_count: PropAccessor[float]
        step: PropAccessor[float]
        steps: PropAccessor[float]
        progress: PropAccessor[float]
        tail: PropAccessor[float]
        fade: PropAccessor[float]
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
        field: FieldFunction,
        seeds: int | PointsInput = 200,
        *,
        step: FloatVal = 0.05,
        steps: FloatVal = 60,
        progress: FloatVal = 1.0,
        tail: FloatVal = 1.0,
        fade: FloatVal = 0.0,
        x_range: VecVal | None = None,
        y_range: VecVal | None = None,
        color: PerPointColor | None = None,
        **props: Unpack[FieldKeywords],
    ) -> None:
        expression = field_expr(field)
        object.__setattr__(self, "field_expression", expression)
        if isinstance(field, VectorField):
            x_range = field.x_range if x_range is None else x_range
            y_range = field.y_range if y_range is None else y_range
        if isinstance(seeds, int | float) and not isinstance(seeds, bool):
            seed_points: list[tuple[float, float]] = []
            seed_count = float(seeds)
        else:
            xs, ys = to_xy(seeds)
            seed_points, seed_count = list(zip(xs, ys)), float(len(xs))
        super().__init__(
            field=expression,
            seeds=seed_points,
            seed_count=seed_count,
            step=step,
            steps=steps,
            progress=progress,
            tail=tail,
            fade=fade,
            x_range=x_range,
            y_range=y_range,
            color=per_point_value(color, "color"),
            **props,
        )
