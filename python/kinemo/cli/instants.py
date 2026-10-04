"""Instants given on the command line (`--at`): seconds, `end`, a mark, a mark shifted by
seconds (`B03+1.5`, `intro-0.5`), or a fraction of the stretch between a mark and its
`.end` mark (`B03+65%`)."""

from __future__ import annotations

import re

#: `name+12`, `name-0.5`, `name+65%` (the name may contain dots: `B03.end+1`).
_SHIFTED = re.compile(r"^(?P<mark>.+?)\s*(?P<sign>[+-])\s*(?P<amount>\d+(?:\.\d*)?|\.\d+)\s*(?P<unit>%|s)?$")


class InstantError(ValueError):
    """An instant that cannot be read; the message says what is accepted."""


def parse_time(text: str, duration: float, marks: dict[str, float]) -> float:
    """Seconds into the scene for `text`, clamped to the scene."""
    text = text.strip()
    if text == "end":
        return max(0.0, duration - 1e-6)
    if text in marks:
        return marks[text]
    shifted = _SHIFTED.match(text)
    if shifted and shifted["mark"] in marks:
        base = marks[shifted["mark"]]
        amount = float(shifted["amount"])
        if shifted["unit"] == "%":
            end_name = f"{shifted['mark']}.end"
            if end_name not in marks:
                raise InstantError(f"{text!r}: a percentage needs a mark {end_name!r} where {shifted['mark']!r} ends")
            when = base + (marks[end_name] - base) * amount / 100.0 * (1 if shifted["sign"] == "+" else -1)
        else:
            when = base + amount if shifted["sign"] == "+" else base - amount
        return min(max(0.0, when), duration)
    try:
        return min(max(0.0, float(text)), duration)
    except ValueError:
        names = ", ".join(sorted(marks)) or "none"
        raise InstantError(f"unknown instant {text!r}: use seconds, 'end', a mark, 'mark+1.5' or 'mark+50%' (marks: {names})") from None


def instants_of(at: str, marks: dict[str, float]) -> list[str]:
    """The `--at` list, with `marks` standing for every mark of the scene in time order."""
    out: list[str] = []
    for text in (t.strip() for t in at.split(",")):
        out += sorted(marks, key=lambda name: marks[name]) if text == "marks" else [text]
    return out
