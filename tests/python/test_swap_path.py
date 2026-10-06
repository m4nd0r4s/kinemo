"""`row.swap(i, j, path=...)`: children that pass each other on arcs (default) or straight."""

from __future__ import annotations

import json

import pytest

import kinemo as k
from conftest import build
from kinemo.values.encode import decode


def mid_swap_y(path: str) -> float:
    seen: dict[str, float] = {}

    @build
    def scene(s: k.Scene) -> None:
        row = k.Row(k.Square(0.6), k.Square(0.6), k.Square(0.6), gap=0.4)
        s.add(row)
        s.play(row.swap(0, 2, path=path), duration=1)  # type: ignore[arg-type]
        first = row.children[2]
        seen["y"] = decode(json.loads(s._b.derived(first._id, "y", 0.5, True)))  # pyright: ignore[reportPrivateUsage]

    return float(seen["y"])


def test_swaps_pass_on_arcs_by_default_and_straight_on_request() -> None:
    assert abs(mid_swap_y("arc")) > 0.1
    assert abs(mid_swap_y("straight")) < 1e-9


def test_unknown_path_is_an_error() -> None:
    with pytest.raises(k.KinemoError):

        @build
        def scene(s: k.Scene) -> None:
            row = k.Row(k.Square(0.6), k.Square(0.6))
            s.add(row)
            s.play(row.swap(0, 1, path="zigzag"))  # type: ignore[arg-type]
