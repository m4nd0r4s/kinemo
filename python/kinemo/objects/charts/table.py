"""`k.Table`: a grid of `k.Text` cells with a styled header row.

`table.to(data=...)` updates the cells: changed texts fade out and back in with the new
value, new rows fade in below, rows the new data no longer has fade out."""

from __future__ import annotations

from typing import TYPE_CHECKING, Sequence, Unpack

from ... import _core
from ..._runtime.spans import Span, user_span
from ...anim.animation import Animation
from ...anim.ease import Ease
from ...anim.prop import PropTo
from ...data.arrow import column, columns
from ..groups import Group, Reorder
from ..node import Node
from ..shapes import Line
from ..text import Text
from .data_transition import DataTransition, animate, set_at

if TYPE_CHECKING:
    from ...data.arrow import DataTable
    from ...scene.scene import Scene
    from ...values.aliases import ColorLike
    from ..keywords import ChangeKeywords, TransformKeywords, VisibilityKeywords

CELL_PADDING = 0.5
ROW_SPACING = 1.9


def read_cells(data: DataTable, names: Sequence[str] | None) -> tuple[list[str], list[list[str]]]:
    """(column names, rows of cell texts) of a table."""
    cols = columns(data)
    chosen = list(names) if names is not None else list(cols)
    texts = [column(cols, n).strings() for n in chosen]
    count = max((len(t) for t in texts), default=0)
    rows = [[t[r] if r < len(t) else "" for t in texts] for r in range(count)]
    return chosen, rows


class Table(Group):
    """`k.Table(df, columns=["pais", "gwh"], size=0.32)`. `table.cells[r][c]` are the
    body cells and `table.header[c]` the header texts."""

    if TYPE_CHECKING:
        _table_opts: tuple[list[str], float, ColorLike | None, bool, list[float]]
        _initial_rows: list[list[str]]
        _texts: list[list[str]]
        #: Body cells, by row then column.
        cells: list[list[Text]]
        #: Header texts, by column.
        header: list[Text]
        #: The line under the header (with `rule=True`).
        rule: Line

    def __init__(self, data: DataTable, columns: Sequence[str] | None = None, *, size: float = 0.32, header_color: ColorLike | None = None, rule: bool = True, **props: Unpack[TransformKeywords]) -> None:
        names, rows = read_cells(data, columns)
        widths = [
            max(_text_width(t, size) for t in [f"**{n}**", *(r[c] for r in rows)]) + CELL_PADDING
            for c, n in enumerate(names)
        ]
        object.__setattr__(self, "_table_opts", (names, size, header_color, rule, widths))
        object.__setattr__(self, "_initial_rows", rows)
        object.__setattr__(self, "cells", [])
        object.__setattr__(self, "_texts", [])
        super().__init__(**props)

    # ---- geometry --------------------------------------------------------------------
    def _column_x(self, c: int) -> float:
        widths = self._table_opts[4]
        left = -sum(widths) / 2
        return left + sum(widths[:c]) + widths[c] / 2

    def _row_y(self, r: int) -> float:
        """Row `r` of the body (the header is row -1); the header sits at y = 0."""
        size = self._table_opts[1]
        return -(r + 1) * size * ROW_SPACING

    # ---- construction ------------------------------------------------------------------
    def _parts(self) -> list[Node]:
        names, size, header_color, rule, widths = self._table_opts
        fill = header_color if header_color is not None else self._scene.theme.accent
        header = [Text(f"**{n}**", size=size, fill=fill, x=self._column_x(c), y=0.0) for c, n in enumerate(names)]
        for c, cell in enumerate(header):
            object.__setattr__(cell, "_part", f".header[{c}]")
        object.__setattr__(self, "header", header)
        parts: list[Node] = list(header)
        if rule:
            y = -size * ROW_SPACING / 2
            line = Line(start=(-sum(widths) / 2, y), end=(sum(widths) / 2, y), stroke_width=2.0)
            object.__setattr__(line, "_part", "rule")
            object.__setattr__(self, "rule", line)
            parts.append(line)
        for r, row in enumerate(self._initial_rows):
            parts += self._new_row(r, row)
        return parts

    def _new_row(self, r: int, texts: list[str], **props: Unpack[VisibilityKeywords]) -> list[Text]:
        size = self._table_opts[1]
        row = [Text(t, size=size, x=self._column_x(c), y=self._row_y(r), **props) for c, t in enumerate(texts)]
        for c, cell in enumerate(row):
            object.__setattr__(cell, "_part", f".cells[{r}][{c}]")
        self.cells.append(row)
        self._texts.append(list(texts))
        return row

    # ---- transitions ---------------------------------------------------------------------
    def to(self, *, data: DataTable | None = None, **kw: Unpack[ChangeKeywords]) -> Animation:  # pyright: ignore[reportIncompatibleMethodOverride] - `data=` is the table's own input
        """`table.to(data=df2)`: animated update of the cells (plus any other props)."""
        anim = super().to(**kw)
        if data is None:
            return anim
        assert isinstance(anim, PropTo)
        _, rows = read_cells(data, self._table_opts[0])
        apply = lambda s, t0, d, e, sp: self._transition(rows, s, t0, d, e, sp)  # noqa: E731
        anim.extra.append(DataTransition(self, apply, user_span()))
        return anim

    def _transition(self, rows: list[list[str]], s: "Scene", start: float, duration: float, ease: Ease, span: Span) -> None:
        half = duration / 2
        old = len(self.cells)
        changed: list[tuple[Text, str]] = []
        for r in range(min(old, len(rows))):
            for c, text in enumerate(rows[r]):
                if self._texts[r][c] != text:
                    changed.append((self.cells[r][c], text))
                    self._texts[r][c] = text
        entering = [cell for r in range(old, len(rows)) for cell in self._new_row(r, rows[r], opacity=0.0)]
        leaving = [cell for row in self.cells[len(rows):] for cell in row]
        if entering:
            Reorder(self, self._children_at(start) + list(entering), span, entering=entering)._emit(s, start, 0.0, ease)
        fade_out = [(cell._sig("opacity"), 0.0) for cell, _ in changed] + [(cell._sig("opacity"), 0.0) for cell in leaving]
        animate(s, fade_out, start, half, ease, span)
        set_at(s, [(cell._sig("text"), text) for cell, text in changed], start + half, span)
        fade_in = [(cell._sig("opacity"), 1.0) for cell, _ in changed]
        animate(s, fade_in, start + half, duration - half, ease, span)
        animate(s, [(cell._sig("opacity"), 1.0) for cell in entering], start, duration, ease, span)
        for cell in leaving:
            s._exit(cell, start + half)
        del self.cells[len(rows):]
        del self._texts[len(rows):]


def _text_width(text: str, size: float) -> float:
    x0, _, x1, _ = _core.measure_text(text, size)
    return x1 - x0
