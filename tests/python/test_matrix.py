"""`k.Matrix`: grid layout, addressing, product and the row-by-column animation."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build


def test_entries_are_addressable_and_laid_out_in_a_grid() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        m = k.Matrix([[1, 22], [333, 4]])
        s.add(m)
        seen["shape"] = m.shape
        seen["entry"] = m[1, 0].text.now  # type: ignore[attr-defined]
        seen["same_column_x"] = float(m[0, 1].x.now) == float(m[1, 1].x.now)
        seen["same_row_y"] = float(m[0, 0].y.now) == float(m[0, 1].y.now)
        seen["column"] = [n.text.now for n in m.column(0)]  # type: ignore[attr-defined]

    assert seen["shape"] == (2, 2) and seen["entry"] == "333"
    assert seen["same_column_x"] is True and seen["same_row_y"] is True
    assert seen["column"] == ["1", "333"]


def test_product_and_its_animation() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        a, b = k.Matrix([[1, 2], [3, 4]]), k.Matrix([[5, 6], [7, 8]])
        c = a @ b
        s.add(a, b)
        start = s.mark()
        s.play(k.matrix_product(a, b, c, step=0.5))
        seen["values"] = [[n.text.now for n in c.row(i)] for i in range(2)]  # type: ignore[attr-defined]
        seen["took"] = s.mark() - start

    assert seen["values"] == [["19", "22"], ["43", "50"]]
    assert seen["took"] == pytest.approx(0.5 + 4 * 0.5)


def test_mismatched_shapes_are_errors() -> None:
    with pytest.raises(k.KinemoError):

        @build
        def ragged(s: k.Scene) -> None:
            k.Matrix([[1, 2], [3]])

    with pytest.raises(k.KinemoError):

        @build
        def product(s: k.Scene) -> None:
            _ = k.Matrix([[1, 2]]) @ k.Matrix([[1, 2]])
