"""`k.Matrix`: a matrix whose entries are objects in a grid (`m[0, 1]`, `m.row(0)`,
`m.column(1)`), with drawn brackets; `a @ b` and `k.matrix_product(a, b, c)` show a product
row by column."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Literal, Sequence, Unpack

from ..anim.animation import Animation, par, seq
from ..anim.verbs import draw, fade_in, indicate
from ..diagnostics import KinemoError
from ..values.aliases import ColorLike
from .groups import Group
from .keywords import TransformKeywords
from .node import Node
from .shapes import Path, RoundedRect
from .math import Math
from .text import Text

#: `k.Matrix(brackets=)`: square brackets, parentheses, bars (a determinant) or none.
Brackets = Literal["[", "(", "|", "none"]

#: An entry: a number, a TeX string (typeset with `k.Math`) or any object.
Entry = float | int | str | Node


def _entry_node(value: Entry, size: float) -> Node:
    if isinstance(value, Node):
        return value
    if isinstance(value, (int, float)):
        return Text(f"{value:g}", size=size)
    return Math(value, size=size * 1.15)


class Matrix(Group):
    """`k.Matrix([[1, 2], [3, 4]], brackets="[")`: entries laid out in a grid (columns as
    wide as their widest entry), between brackets. `m[i, j]` is an entry, `m.row(i)` and
    `m.column(j)` list them, `m.box(row=i)` / `m.box(column=j)` give a rounded frame around a row
    or a column to draw. Entries are numbers, TeX strings or objects. Parts: `m.entries`,
    `m.opening`, `m.closing` (the brackets)."""

    if TYPE_CHECKING:
        entries: list[list[Node]]
        opening: Path | None
        closing: Path | None
        _values: list[list[Entry]]
        _grid: tuple[list[float], list[float], list[float], list[float]]

    def __init__(
        self,
        entries: Sequence[Sequence[Entry]],
        *,
        brackets: Brackets = "[",
        size: float = 0.5,
        column_gap: float | None = None,
        row_gap: float | None = None,
        **props: Unpack[TransformKeywords],
    ) -> None:
        rows = [list(row) for row in entries]
        if not rows or not rows[0] or any(len(row) != len(rows[0]) for row in rows):
            raise KinemoError.make("K0105", "k.Matrix needs a non-empty rectangular list of rows", fixes=[("same number of entries in every row", "[[1, 2], [3, 4]]")])
        nodes = [[_entry_node(value, size) for value in row] for row in rows]
        column_gap = size * 0.9 if column_gap is None else column_gap
        row_gap = size * 0.55 if row_gap is None else row_gap
        widths = [max(float(nodes[r][c].width.now) for r in range(len(rows))) for c in range(len(rows[0]))]
        heights = [max(max(float(node.height.now), size) for node in row) for row in nodes]
        total_w = sum(widths) + column_gap * (len(widths) - 1)
        total_h = sum(heights) + row_gap * (len(heights) - 1)
        xs = [-total_w / 2 + sum(widths[:c]) + column_gap * c + widths[c] / 2 for c in range(len(widths))]
        ys = [total_h / 2 - sum(heights[:r]) - row_gap * r - heights[r] / 2 for r in range(len(heights))]
        for r, row in enumerate(nodes):
            for c, node in enumerate(row):
                node.set(x=xs[c], y=ys[r])
                object.__setattr__(node, "_part", f"[{r}, {c}]")
        parts: list[Node] = [node for row in nodes for node in row]
        opening = closing = None
        if brackets != "none":
            reach = total_w / 2 + size * 0.45
            half = total_h / 2 + size * 0.2
            opening, closing = (Path(_bracket(brackets, -reach, half, size, side), stroke_width=3.0, fill_opacity=0.0) for side in (-1.0, 1.0))
            for part, name in ((opening, "opening"), (closing, "closing")):
                object.__setattr__(part, "_part", name)
            parts += [opening, closing]
        object.__setattr__(self, "entries", nodes)
        object.__setattr__(self, "opening", opening)
        object.__setattr__(self, "closing", closing)
        object.__setattr__(self, "_values", rows)
        object.__setattr__(self, "_grid", (xs, ys, widths, heights))
        super().__init__(*parts, **props)

    @property
    def shape(self) -> tuple[int, int]:
        """(rows, columns)."""
        return len(self.entries), len(self.entries[0])

    def __getitem__(self, index: tuple[int, int]) -> Node:  # pyright: ignore[reportIncompatibleMethodOverride] - a matrix is indexed by (row, column)
        row, column = index
        return self.entries[row][column]

    def row(self, index: int) -> list[Node]:
        """The entries of row `index`."""
        return list(self.entries[index])

    def column(self, index: int) -> list[Node]:
        """The entries of column `index`."""
        return [row[index] for row in self.entries]

    def box(self, *, row: int | None = None, column: int | None = None, color: ColorLike | None = None) -> RoundedRect:
        """A rounded frame around a row or a column (in the matrix: it moves with it), not yet
        in the scene: draw it (`k.draw(m.box(row=0))`)."""
        if (row is None) == (column is None):
            raise KinemoError.make("K0105", "m.box takes row= or column=")
        xs, ys, widths, heights = self._grid
        pad = 0.12
        if row is not None:
            w, h, x, y = xs[-1] - xs[0] + widths[0] / 2 + widths[-1] / 2 + 2 * pad, heights[row] + 2 * pad, (xs[0] - widths[0] / 2 + xs[-1] + widths[-1] / 2) / 2, ys[row]
        else:
            assert column is not None
            w, h, x, y = widths[column] + 2 * pad, ys[0] - ys[-1] + heights[0] / 2 + heights[-1] / 2 + 2 * pad, xs[column], (ys[0] + heights[0] / 2 + ys[-1] - heights[-1] / 2) / 2
        from .._runtime.context import current_scene

        frame = RoundedRect(w=w, h=h, radius=0.12, stroke=color if color is not None else current_scene().theme.accent, stroke_width=2.5, fill_opacity=0.0, x=x, y=y)
        self._adopt(frame)
        self._children_sig.set(self.children + [frame])
        object.__setattr__(frame, "_enters_on_its_own", True)
        return frame

    def __matmul__(self, other: "Matrix") -> "Matrix":
        """The product of two numeric matrices, as a new matrix (not yet in the scene)."""
        rows, inner = self.shape
        if other.shape[0] != inner:
            raise KinemoError.make("K0105", f"cannot multiply a {rows}×{inner} matrix by a {other.shape[0]}×{other.shape[1]} one")
        a, b = self._numbers(), other._numbers()
        product = [[sum(a[i][k] * b[k][j] for k in range(inner)) for j in range(other.shape[1])] for i in range(rows)]
        return Matrix(product, size=float(self._size()))

    def _numbers(self) -> list[list[float]]:
        values = self._values
        if not all(isinstance(v, (int, float)) for row in values for v in row):
            raise KinemoError.make("K0105", "a matrix product needs numeric entries")
        return [[float(v) for v in row] for row in values]  # pyright: ignore[reportArgumentType] - checked above

    def _size(self) -> float:
        first = self.entries[0][0]
        return float(first.size.now) if isinstance(first, Text) else 0.5


def _bracket(kind: Brackets, reach: float, half: float, size: float, side: float) -> list[tuple[float, float]]:
    """Points of one bracket: `side` -1 for the left one, 1 for the right one."""
    x = reach * -side
    serif = size * 0.22 * -side
    if kind == "[":
        return [(x + serif, half), (x, half), (x, -half), (x + serif, -half)]
    if kind == "|":
        return [(x, half), (x, -half)]
    # A parenthesis: an arc bulging outwards.
    bulge = size * 0.25 * side
    return [(x + bulge * math.sin(math.pi * i / 16), half - 2 * half * i / 16) for i in range(17)]


def matrix_product(a: Matrix, b: Matrix, product: Matrix, *, step: float = 0.8) -> Animation:
    """Show `product` (from `a @ b`) cell by cell: for each entry, its row of `a` and its column
    of `b` are indicated while the entry appears. Its brackets are drawn first."""
    rows, columns = product.shape
    steps: list[Animation] = []
    if product.opening is not None and product.closing is not None:
        steps.append(draw(product.opening, product.closing, duration=0.5))
    for i in range(rows):
        for j in range(columns):
            emphasis = [indicate(node, scale=1.15, duration=step) for node in [*a.row(i), *b.column(j)]]
            steps.append(par(*emphasis, fade_in(product[i, j], duration=step)))
    return seq(*steps)
