"""`k.Array`: an array for algorithm videos — cells with values and indices, pointers
(`arr.pointer("i", 2)`), animated swaps, comparisons and value changes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence, Unpack

from ..anim.animation import Animation, par
from ..anim.verbs import fade_in, indicate
from ..reactive.signal import Signal, signal
from ..values.aliases import ColorLike
from ..values.color import YELLOW
from .groups import Group, ReorderTiming, Row
from .keywords import TransformKeywords
from .node import Node
from .shapes import Arrow, Square
from .text import Text


class ArrayCell(Group):
    """A cell of a `k.Array`: its `box` and the `value` text."""

    if TYPE_CHECKING:
        box: Square
        value: Text

    def __init__(self, box: Square, value: Text) -> None:
        object.__setattr__(self, "box", box)
        object.__setattr__(self, "value", value)
        object.__setattr__(box, "_part", "box")
        object.__setattr__(value, "_part", "value")
        super().__init__(box, value)


class Array(Group):
    """`k.Array([5, 2, 9, 1], index=True)`: a row of cells holding the values, with the indices
    under them. `arr.cells[i]` is the cell now at index `i` (`.box`, `.value`), `arr.swap(i, j)`
    exchanges two cells, `arr.compare(i, j)` highlights them, `arr.set(i, v)` changes a value and
    `arr.pointer("i", 2)` points at an index (calling it again moves the pointer)."""

    if TYPE_CHECKING:
        row: Row
        indices: list[Text]
        pointers: dict[str, Group]
        _pointer_slots: dict[str, Signal[float]]
        _array_opts: tuple[float, float, float]

    def __init__(self, values: Sequence[object], *, index: bool = True, cell: float = 0.8, size: float = 0.4, gap: float = 0.0, **props: Unpack[TransformKeywords]) -> None:
        cells: list[Node] = []
        for v in values:
            cells.append(ArrayCell(Square(cell, stroke_width=3.0), Text(str(v), size=size)))
        row = Row(*cells, gap=gap)
        object.__setattr__(row, "_part", "row")
        object.__setattr__(self, "row", row)
        object.__setattr__(self, "pointers", {})
        object.__setattr__(self, "_pointer_slots", {})
        object.__setattr__(self, "_array_opts", (cell, size, gap))
        numbers: list[Text] = []
        if index:
            for i in range(len(values)):
                number = Text(str(i), size=size * 0.6, x=self._slot_x(i, len(values)), y=-cell * 0.85)
                object.__setattr__(number, "_part", f".indices[{i}]")
                numbers.append(number)
        object.__setattr__(self, "indices", numbers)
        super().__init__(row, *numbers, **props)

    def _slot_x(self, i: int, count: int | None = None) -> float:
        """Center of index `i` (cells keep their slots; a swap exchanges what is in them)."""
        cell, _, gap = self._array_opts
        n = len(self.row) if count is None else count
        return (i - (n - 1) / 2) * (cell + gap)

    @property
    def cells(self) -> list[ArrayCell]:
        """The cells in index order at the cursor (after the swaps scheduled so far)."""
        return [c for c in self.row.children if isinstance(c, ArrayCell)]

    def swap(self, i: int, j: int, **kw: Unpack[ReorderTiming]) -> Animation:
        """Exchange the cells at `i` and `j` (they move along arcs)."""
        return self.row.swap(i, j, **kw)

    def compare(self, i: int, j: int, *, color: ColorLike = YELLOW, duration: float | None = None) -> Animation:
        """Highlight the cells at `i` and `j` (a temporary tint and pulse)."""
        a, b = self.cells[i], self.cells[j]
        return par(indicate(a, color=color, scale=1.08, duration=duration), indicate(b, color=color, scale=1.08, duration=duration))

    def set(self, i: int, value: object, *, duration: float | None = None) -> Animation:  # pyright: ignore[reportIncompatibleMethodOverride] - an array's set() changes a value
        """Change the value shown at `i` (the old one crossfades into the new)."""
        return self.cells[i].value.to(text=str(value), duration=duration)

    def pointer(self, name: str, i: int, *, color: ColorLike = YELLOW, duration: float | None = None) -> Animation:
        """Point `name` at index `i`: a labelled arrow under the cell fades in the first time,
        then slides to the new index. Pointers follow the array if it moves."""
        cell, size, _ = self._array_opts
        existing = self.pointers.get(name)
        if existing is not None:
            return self._pointer_slots[name].to(self._slot_x(i), duration=duration)
        slot = signal(self._slot_x(i))
        depth = len(self.pointers)
        top = -cell * (1.25 if self.indices else 0.65) - depth * size * 2.2
        arrow = Arrow(start=(0.0, top - size * 1.1), end=(0.0, top), stroke=color, fill=color, stroke_width=3.0)
        label = Text(name, size=size * 0.7, fill=color, y=top - size * 1.8)
        # A free object beside the array (not a child): its own fade never touches the array.
        mark = Group(arrow, label, x=self.world.center.x + slot, y=self.world.center.y)
        mark._rename(f"{self._label()}.pointers[{name!r}]")
        self.pointers[name] = mark
        self._pointer_slots[name] = slot
        return fade_in(mark, duration=duration)
