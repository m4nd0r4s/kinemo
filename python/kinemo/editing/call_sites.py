"""Find the call behind a span in a source file and describe its arguments.

Spans recorded by the runtime cover the user's call exactly (`k.Circle(r=0.8)`,
`c.to(x=3)`, `s.play(..., duration=0.4)`), so a call is identified by its full range even
when several calls share a line or are chained.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import cached_property

from .._runtime.spans import Span
from .literals import LiteralKind, literal_kind, literal_value, numbers_inside


@dataclass(frozen=True, order=True)
class Position:
    """A place in the text: 1-based line, 0-based character column."""

    line: int
    col: int


@dataclass(frozen=True)
class NumberInside:
    """A number written inside a computed argument (`1.2` in `title.x + 1.2`). `offset` is
    where it starts in the argument's text."""

    text: str
    value: int | float
    offset: int
    start: Position
    end: Position


@dataclass(frozen=True)
class Argument:
    """One argument of a call. Positional arguments have an `index`, keywords a `keyword`."""

    keyword: str | None
    index: int | None
    text: str
    kind: LiteralKind | None
    value: object
    start: Position
    end: Position
    #: The numbers inside a computed argument, editable one by one (none for a literal).
    numbers: tuple[NumberInside, ...] = ()


@dataclass(frozen=True)
class CallSite:
    callee: str
    arguments: tuple[Argument, ...]
    #: Where a new `keyword=value` goes: after the last argument, or inside empty parentheses.
    insert_at: Position
    has_arguments: bool
    start: Position
    end: Position

    def keyword(self, name: str) -> Argument | None:
        return next((a for a in self.arguments if a.keyword == name), None)

    def positional(self, index: int) -> Argument | None:
        return next((a for a in self.arguments if a.index == index), None)


class SourceFile:
    """Parsed text of one file, with call lookup by span."""

    def __init__(self, path: str, text: str) -> None:
        self.path = path
        self.text = text
        self.lines = text.split("\n")

    @cached_property
    def tree(self) -> ast.Module | None:
        try:
            return ast.parse(self.text, filename=self.path)
        except SyntaxError:
            return None

    @cached_property
    def module_aliases(self) -> frozenset[str]:
        """Names kinemo is imported as (`k` for `import kinemo as k`)."""
        names: set[str] = set()
        for node in ast.walk(self.tree) if self.tree else ():
            if isinstance(node, ast.Import):
                names.update(a.asname or a.name for a in node.names if a.name == "kinemo")
        return frozenset(names)

    @cached_property
    def _calls(self) -> dict[tuple[Position, Position], ast.Call]:
        out: dict[tuple[Position, Position], ast.Call] = {}
        for node in ast.walk(self.tree) if self.tree else ():
            if isinstance(node, ast.Call) and node.end_lineno is not None and node.end_col_offset is not None:
                out[(self.position(node.lineno, node.col_offset), self.position(node.end_lineno, node.end_col_offset))] = node
        return out

    def position(self, line: int, byte_col: int) -> Position:
        """`ast` columns are UTF-8 byte offsets; positions use characters."""
        text = self.lines[line - 1] if 0 < line <= len(self.lines) else ""
        return Position(line, len(text.encode("utf-8")[:byte_col].decode("utf-8", errors="ignore")))

    def segment(self, start: Position, end: Position) -> str:
        if start.line == end.line:
            return self.lines[start.line - 1][start.col : end.col]
        parts = [self.lines[start.line - 1][start.col :]]
        parts += self.lines[start.line : end.line - 1]
        parts.append(self.lines[end.line - 1][: end.col])
        return "\n".join(parts)

    def call_at(self, span: Span) -> CallSite | None:
        """The call a span covers, or `None` when the span has no range or the text changed."""
        if not span.end_line:
            return None
        node = self._calls.get((Position(span.line, span.col), Position(span.end_line, span.end_col)))
        return self._describe(node) if node is not None else None

    def _describe(self, node: ast.Call) -> CallSite:
        arguments: list[Argument] = []
        for index, arg in enumerate(node.args):
            arguments.append(self._argument(arg, None, index))
        for kw in node.keywords:
            if kw.arg is not None:
                arguments.append(self._argument(kw.value, kw.arg, None))
        start = self.position(node.lineno, node.col_offset)
        end = self.position(node.end_lineno or node.lineno, node.end_col_offset or 0)
        ends = [self.position(a.end_lineno or a.lineno, a.end_col_offset or 0) for a in [*node.args, *(k.value for k in node.keywords)]]
        insert_at = max(ends) if ends else Position(end.line, end.col - 1)
        return CallSite(
            callee=self.segment(self.position(node.func.lineno, node.func.col_offset), self.position(node.func.end_lineno or 0, node.func.end_col_offset or 0)),
            arguments=tuple(arguments),
            insert_at=insert_at,
            has_arguments=bool(ends),
            start=start,
            end=end,
        )

    def _argument(self, value: ast.expr, keyword: str | None, index: int | None) -> Argument:
        start = self.position(value.lineno, value.col_offset)
        end = self.position(value.end_lineno or value.lineno, value.end_col_offset or 0)
        kind = None if isinstance(value, ast.Starred) else literal_kind(value, self.module_aliases)
        return Argument(
            keyword=keyword,
            index=index,
            text=self.segment(start, end),
            kind=kind,
            value=literal_value(value) if kind is not None else None,
            start=start,
            end=end,
            numbers=self._numbers(value, start) if kind is None else (),
        )

    def _numbers(self, value: ast.expr, argument_start: Position) -> tuple[NumberInside, ...]:
        out: list[NumberInside] = []
        for node in numbers_inside(value):
            start = self.position(node.lineno, node.col_offset)
            end = self.position(node.end_lineno or node.lineno, node.end_col_offset or 0)
            text = self.segment(start, end)
            # Positions inside f-strings are unreliable before Python 3.12: keep a number
            # only where the text really is that number.
            try:
                written = ast.literal_eval(text)
            except (ValueError, SyntaxError):
                continue
            number = ast.literal_eval(node)
            if written != number or isinstance(written, bool):
                continue
            out.append(NumberInside(text, number, len(self.segment(argument_start, start)), start, end))
        return tuple(out)
