"""`k.Table(widths=, reserve=)`: columns sized for data shown later keep their width."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build


def column_xs(table: k.Table) -> list[float]:
    return [float(cell.x.now) for cell in table.header]


def test_reserve_sizes_columns_for_later_rows() -> None:
    seen: dict[str, list[float]] = {}
    first = {"name": ["a"], "value": ["1"]}
    later = {"name": ["a", "a much longer name"], "value": ["1", "2"]}

    @build
    def scene(s: k.Scene) -> None:
        plain = k.Table(first)
        roomy = k.Table(first, reserve=[later])
        s.add(plain, roomy)
        seen["plain"], seen["roomy"] = column_xs(plain), column_xs(roomy)

    plain_gap = seen["plain"][1] - seen["plain"][0]
    roomy_gap = seen["roomy"][1] - seen["roomy"][0]
    assert roomy_gap > plain_gap + 1.0


def test_widths_are_minimums() -> None:
    seen: dict[str, list[float]] = {}

    @build
    def scene(s: k.Scene) -> None:
        table = k.Table({"x": ["1"], "y": ["2"]}, widths=[3.0, None])
        s.add(table)
        seen["xs"] = column_xs(table)

    assert seen["xs"][1] - seen["xs"][0] >= 1.5


def test_widths_must_match_the_columns() -> None:
    with pytest.raises(k.KinemoError):

        @build
        def scene(s: k.Scene) -> None:
            k.Table({"x": ["1"], "y": ["2"]}, widths=[1.0])
