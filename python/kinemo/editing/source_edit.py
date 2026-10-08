"""Apply argument changes to a file's text: replace an argument's value, replace one number
inside a computed argument, or add a `keyword=value` argument to a call. Only those
characters change; formatting and comments stay as the author wrote them."""

from __future__ import annotations

import ast
from dataclasses import dataclass

from .call_sites import Argument, CallSite, Position, SourceFile
from .literals import is_number, is_valid_expression


class EditError(Exception):
    """An edit that cannot be applied; the message is shown to the user."""


@dataclass(frozen=True)
class Change:
    """Set the argument bound to `target` in `site` to the Python expression `value`."""

    site: CallSite
    target: str
    value: str
    #: Positional index → parameter name for the call's callable (constructors).
    params: tuple[tuple[int, str], ...] = ()
    #: Which number inside a computed argument to set (`value` is then a number), or `None`
    #: for the whole argument.
    number: int | None = None
    #: Set the literal of the variable the argument names (`gap = 0.4` for `gap=gap`).
    variable: bool = False


def bound_argument(site: CallSite, target: str, params: tuple[tuple[int, str], ...] = ()) -> Argument | None:
    """The argument that sets `target`: the keyword itself, or a positional bound to it."""
    found = site.keyword(target)
    if found is not None:
        return found
    for index, name in params:
        if name == target:
            return site.positional(index)
    return None


def apply_changes(source: SourceFile, changes: list[Change]) -> str:
    """The text of `source` with every change applied (all or nothing)."""
    replacements: list[tuple[int, int, int, str]] = []
    inserted_at: set[int] = set()
    for order, change in enumerate(changes):
        value = change.value.strip()
        if not is_valid_expression(value) or "\n" in value:
            raise EditError(f"not a valid value: {change.value!r}")
        argument = bound_argument(change.site, change.target, change.params)
        if change.number is not None:
            replacements.append(_number_replacement(source, change, argument, value, order))
        elif change.variable:
            variable = argument.variable if argument is not None else None
            if variable is None:
                raise EditError(f"{change.target}= no longer names a variable holding a value; the preview reloads")
            replacements.append((_offset(source, variable.start), _offset(source, variable.end), order, value))
        elif argument is not None:
            if argument.kind is None:
                raise EditError(f"{change.target}= is computed ({argument.text}); edit it in the code")
            start, end = _offset(source, argument.start), _offset(source, argument.end)
            replacements.append((start, end, order, value))
        else:
            at = _offset(source, change.site.insert_at)
            separator = ", " if change.site.has_arguments or at in inserted_at else ""
            inserted_at.add(at)
            replacements.append((at, at, order, f"{separator}{change.target}={value}"))
    _check_overlaps(replacements)
    text = source.text
    # From the end, so earlier offsets stay valid; insertions at one point keep their order.
    for start, end, _, replacement in sorted(replacements, key=lambda r: (r[0], r[2]), reverse=True):
        text = text[:start] + replacement + text[end:]
    return text


def _number_replacement(source: SourceFile, change: Change, argument: Argument | None, value: str, order: int) -> tuple[int, int, int, str]:
    numbers = argument.numbers if argument is not None else ()
    if change.number is None or not 0 <= change.number < len(numbers):
        raise EditError(f"{change.target}= no longer has that number; the preview reloads")
    if not is_number(ast.parse(value, mode="eval").body):
        raise EditError(f"not a number: {value!r}")
    found = numbers[change.number]
    return (_offset(source, found.start), _offset(source, found.end), order, value)


def _offset(source: SourceFile, position: Position) -> int:
    return sum(len(line) + 1 for line in source.lines[: position.line - 1]) + position.col


def _check_overlaps(replacements: list[tuple[int, int, int, str]]) -> None:
    spans = sorted((start, end) for start, end, _, _ in replacements if end > start)
    for (_, end), (next_start, _) in zip(spans, spans[1:]):
        if next_start < end:
            raise EditError("two changes touch the same argument")
