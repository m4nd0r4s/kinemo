"""`k.Bits`: a binary register — cells of 0/1 that flip when the value changes, with optional
place values, grouping and labelled fields (sign, exponent, mantissa)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Mapping, Unpack

from ..anim.animation import Animation, par, stagger
from ..diagnostics import KinemoError
from ..values.aliases import ColorLike
from .groups import Group
from .keywords import TransformKeywords
from .node import Node
from .shapes import Line, Square
from .text import Text


#: Fill opacity of a lit cell: the accent, light enough that the digit stays readable.
LIT = 0.45


class BitCell(Group):
    """A cell of a `k.Bits`: its `box` and its `digit`."""

    if TYPE_CHECKING:
        box: Square
        digit: Text

    def __init__(self, box: Square, digit: Text, x: float) -> None:
        object.__setattr__(self, "box", box)
        object.__setattr__(self, "digit", digit)
        object.__setattr__(box, "_part", "box")
        object.__setattr__(digit, "_part", "digit")
        super().__init__(box, digit, x=x)


class Bits(Group):
    """`k.Bits(13, width=8)`: the bits of a value, most significant first. `bits.to(value=n)`
    flips the cells that change (the lit cells are the ones), `signed=True` shows negative
    values in two's complement, `place_values=True` writes 128 64 ... 1 above the cells,
    `group=4` leaves a gap every 4 bits and `fields={"sign": (0, 1), "exponent": (1, 9)}`
    labels ranges of cells (counted from the left). `bits.bit(0)` is the least significant
    cell (`.box`, `.digit`); `bits.cells` lists them left to right."""

    if TYPE_CHECKING:
        cells: list[BitCell]
        place_values: list[Text]
        fields: dict[str, Group]
        _bits_opts: tuple[int, bool, float, ColorLike]
        _value: int

    def __init__(
        self,
        value: int = 0,
        width: int = 8,
        *,
        signed: bool = False,
        place_values: bool = False,
        group: int | None = None,
        fields: Mapping[str, tuple[int, int]] | None = None,
        size: float = 0.5,
        color: ColorLike | None = None,
        **props: Unpack[TransformKeywords],
    ) -> None:
        from .._runtime.context import current_scene

        if width < 1:
            raise KinemoError.make("K0105", f"k.Bits needs width >= 1, got {width}")
        accent = color if color is not None else current_scene().theme.accent
        object.__setattr__(self, "_bits_opts", (width, signed, size, accent))
        pattern = self._pattern(value)
        gap = size * 0.12
        spacing = size + gap
        breaks = [i // group for i in range(width)] if group else [0] * width
        extra = size * 0.35
        xs = [i * spacing + breaks[i] * extra for i in range(width)]
        center = (xs[0] + xs[-1]) / 2
        xs = [x - center for x in xs]
        # Small labels never below the readable minimum at 1080p.
        small = max(size * 0.32, 0.16)
        cells: list[BitCell] = []
        for i, bit in enumerate(pattern):
            box = Square(size, stroke_width=2.0, fill=accent, fill_opacity=LIT if bit else 0.0)
            digit = Text(str(bit), size=size * 0.6)
            cell = BitCell(box, digit, xs[i])
            object.__setattr__(cell, "_part", f".cells[{i}]")
            cells.append(cell)
        parts: list[Node] = list(cells)
        powers: list[Text] = []
        if place_values:
            for i in range(width):
                power = 2 ** (width - 1 - i)
                label = Text(str(-power if signed and i == 0 else power), size=small, x=xs[i], y=size * 0.85)
                object.__setattr__(label, "_part", f".place_values[{i}]")
                powers.append(label)
            parts += powers
        labelled: dict[str, Group] = {}
        for name, (first, last) in (fields or {}).items():
            if not 0 <= first < last <= width:
                raise KinemoError.make("K0105", f"field {name!r} spans cells {first}..{last}, outside 0..{width}")
            # A small inset keeps the lines of neighbouring fields apart.
            left, right = xs[first] - size / 2 + gap, xs[last - 1] + size / 2 - gap
            y = -size * 0.85
            bracket = Line(start=(left, y), end=(right, y), stroke=accent, stroke_width=2.0)
            label = Text(name, size=small, fill=accent, x=(left + right) / 2, y=y - size * 0.35)
            field = Group(bracket, label)
            object.__setattr__(field, "_part", f".fields[{name!r}]")
            labelled[name] = field
            parts.append(field)
        object.__setattr__(self, "cells", cells)
        object.__setattr__(self, "place_values", powers)
        object.__setattr__(self, "fields", labelled)
        object.__setattr__(self, "_value", value)
        super().__init__(*parts, **props)

    def _pattern(self, value: int) -> list[int]:
        width, signed, _, _ = self._bits_opts
        low, high = (-(2 ** (width - 1)), 2 ** (width - 1) - 1) if signed else (0, 2**width - 1)
        if not low <= value <= high:
            kind = "signed" if signed else "unsigned"
            raise KinemoError.make("K0105", f"{value} does not fit in {width} {kind} bits ({low}..{high})", fixes=[("more bits", f"width={width + 1}")])
        word = value % (2**width)
        return [(word >> (width - 1 - i)) & 1 for i in range(width)]

    @property
    def value(self) -> int:  # pyright: ignore[reportIncompatibleVariableOverride] - the register's value, not a prop
        """The value shown (after the changes scheduled so far)."""
        return self._value

    def bit(self, index: int) -> BitCell:
        """The cell of bit `index`, 0 being the least significant."""
        width = self._bits_opts[0]
        if not 0 <= index < width:
            raise KinemoError.make("K0105", f"bit {index} of a {width}-bit register")
        return self.cells[width - 1 - index]

    def to(self, *, value: int, lag: float = 0.04, duration: float | None = None) -> Animation:  # pyright: ignore[reportIncompatibleMethodOverride] - a register changes its value
        """Change the value: the cells whose bit changes flip (digit and fill), from the least
        significant up, `lag` seconds apart."""
        old, new = self._pattern(self._value), self._pattern(value)
        object.__setattr__(self, "_value", value)
        flips: list[Animation] = []
        for cell, before, after in reversed(list(zip(self.cells, old, new))):
            if before != after:
                flips.append(par(cell.digit.to(text=str(after), duration=duration), cell.box.to(fill_opacity=LIT if after else 0.0, duration=duration)))
        if not flips:
            return par()
        return stagger(flips, lag=lag)
