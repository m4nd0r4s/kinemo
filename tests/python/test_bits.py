"""`k.Bits`: patterns, two's complement, flips and fields."""

from __future__ import annotations

import pytest

import kinemo as k
from conftest import build


def digits(bits: k.Bits) -> str:
    return "".join(str(cell.digit.text.now) for cell in bits.cells)


def test_value_changes_flip_only_the_changed_cells() -> None:
    seen: dict[str, object] = {}

    @build
    def scene(s: k.Scene) -> None:
        reg = k.Bits(13, width=8)
        s.add(reg)
        seen["before"] = digits(reg)
        s.play(reg.to(value=14))
        seen["after"], seen["value"] = digits(reg), reg.value
        seen["lsb"] = reg.bit(0).digit.text.now

    assert seen["before"] == "00001101" and seen["after"] == "00001110"
    assert seen["value"] == 14 and seen["lsb"] == "0"


def test_signed_registers_use_twos_complement_and_reject_overflow() -> None:
    seen: dict[str, str] = {}

    @build
    def scene(s: k.Scene) -> None:
        reg = k.Bits(-1, width=4, signed=True, place_values=True)
        s.add(reg)
        seen["bits"] = digits(reg)
        seen["msb_weight"] = reg.place_values[0].text.now

    assert seen["bits"] == "1111" and seen["msb_weight"] == "-8"
    with pytest.raises(k.KinemoError):

        @build
        def overflow(s: k.Scene) -> None:
            k.Bits(16, width=4)


def test_fields_label_ranges() -> None:
    seen: dict[str, list[str]] = {}

    @build
    def scene(s: k.Scene) -> None:
        reg = k.Bits(0, width=8, fields={"high": (0, 4), "low": (4, 8)})
        s.add(reg)
        seen["names"] = list(reg.fields)

    assert seen["names"] == ["high", "low"]
