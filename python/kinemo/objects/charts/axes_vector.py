"""Vectors on axes: `ax.vector((1, 2), at=(0, 0), label="F", components=True)` draws an arrow
in data units (its tail `at` and its components `v` are signals), with optional dashed x/y
components; `a + b` and `k.vector_sum(a, b, a + b)` add vectors tip to tail."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ...anim.animation import Animation, seq
from ...anim.verbs import draw
from ...reactive.native import vec, where
from ..groups import Group
from ..node import Node
from ..props import PropSpec
from ..shapes import Arrow, Line
from ..text import Text

if TYPE_CHECKING:
    from ...values.vec import Vec
    from ..props import PropAccessor
    from .axes import Axes


class AxesVector(Group):
    """A vector of an axes: `at` (its tail) and `v` (its components) are data-unit signals, so
    `vector.to(v=(2, 1))` turns it and the arrow follows zooms. Parts: `vector.arrow`,
    `vector.label`, and with components `vector.x_component`, `vector.y_component` (dashed)
    and their labels `vector.x_label`, `vector.y_label`."""

    PROPS = {"at": PropSpec("vec2", (0.0, 0.0)), "v": PropSpec("vec2", (1.0, 0.0))}

    if TYPE_CHECKING:
        at: PropAccessor[Vec]
        v: PropAccessor[Vec]
        axes: Axes
        arrow: Arrow
        label: Text | None
        x_component: Line | None
        y_component: Line | None
        x_label: Text | None
        y_label: Text | None
        _vector_opts: tuple[str | None, bool, Any, float]

    def __init__(self, axes: "Axes", v: tuple[Any, Any], at: tuple[Any, Any], *, label: str | None, components: bool, color: Any, size: float) -> None:
        object.__setattr__(self, "axes", axes)
        object.__setattr__(self, "_vector_opts", (label, components, color, size))
        super().__init__(at=vec(at[0], at[1]), v=vec(v[0], v[1]))

    def _parts(self) -> list[Node]:
        label, components, color, size = self._vector_opts
        ax, at, v = self.axes, self.at, self.v
        tail = ax.local_point(at.x, at.y)
        tip = ax.local_point(at.x + v.x, at.y + v.y)
        corner = ax.local_point(at.x + v.x, at.y)
        arrow = Arrow(start=tail, end=tip, stroke=color, fill=color, stroke_width=4.0, tip=0.22)
        parts: list[Node] = []
        named: dict[str, Node | None] = {"arrow": arrow, "label": None, "x_component": None, "y_component": None, "x_label": None, "y_label": None}
        if components:
            dashed: dict[str, Any] = {"stroke": color, "stroke_width": 2.5, "dash": (10.0, 8.0), "opacity": 0.8}
            along_x = Line(start=tail, end=corner, **dashed)
            along_y = Line(start=corner, end=tip, **dashed)
            parts += [along_x, along_y]
            named.update(x_component=along_x, y_component=along_y)
            if label:
                # Inside the right triangle: on the arrow's side of the x component (clear of
                # the axis labels), and beside the y component.
                side = where(v.y >= 0, 1.0, -1.0)
                named["x_label"] = Text(f"{label}ₓ", size=size * 0.8, fill=color, x=(tail.x + corner.x) / 2 + size * 0.6, y=tail.y + side * size * 0.55)
                named["y_label"] = Text(f"{label}ᵧ", size=size * 0.8, fill=color, x=corner.x + size * 1.3, y=(corner.y + tip.y) / 2)
                parts += [named["x_label"], named["y_label"]]  # type: ignore[list-item]
        parts.append(arrow)
        if label:
            named["label"] = Text(label, size=size, fill=color, x=tip.x + size * 0.9, y=tip.y + size * 0.6)
            parts.append(named["label"])  # type: ignore[arg-type]
        for name, part in named.items():
            object.__setattr__(self, name, part)
            if part is not None:
                object.__setattr__(part, "_part", name)
        return parts

    def __add__(self, other: "AxesVector") -> "AxesVector":
        """The resultant: from this vector's tail, the sum of the components (not yet in the
        scene; show it with `k.vector_sum(a, b, a + b)`)."""
        at, a, b = self.at.now, self.v.now, other.v.now
        color = self._scene.theme.fg
        return self.axes.vector((a[0] + b[0], a[1] + b[1]), at=(at[0], at[1]), color=color, enter_with_axes=False)


def vector_sum(a: AxesVector, b: AxesVector, resultant: AxesVector, *, duration: float = 1.0) -> Animation:
    """Adds two vectors tip to tail: `b` slides so its tail sits on `a`'s tip, then
    `resultant` (from `a + b`) is drawn from `a`'s tail to the end of the chain."""
    (x, y), (dx, dy) = a.at.now, a.v.now
    return seq(b.to(at=(x + dx, y + dy), duration=duration), draw(resultant, duration=duration))
