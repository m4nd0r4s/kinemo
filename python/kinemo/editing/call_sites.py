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
class Variable:
    """The literal a name argument holds: `gap = 0.4` for `place(gap=gap)`. `start`/`end`
    locate the literal in the assignment; `uses` counts where the name is read."""

    name: str
    text: str
    kind: LiteralKind
    value: object
    line: int
    uses: int
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
    #: For a bare name bound once to a literal in its scope: that assignment.
    variable: Variable | None = None


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
            variable=self._variable(value) if isinstance(value, ast.Name) else None,
        )

    def _variable(self, name: ast.Name) -> Variable | None:
        """The assignment that gives `name` its value, when there is exactly one in the
        innermost function around the call (or, when that function never binds the name, at
        module level) and it assigns a literal."""
        if self.tree is None:
            return None
        function = _enclosing_function(self.tree, name)
        scope: ast.AST = self.tree
        if function is not None and (_parameters(function) & {name.id} or _bindings(function, name.id) or _declared_outside(function, name.id)):
            scope = function
        if name.id in (_parameters(scope) if not isinstance(scope, ast.Module) else set()):
            return None
        bindings = _bindings(scope, name.id)
        if len(bindings) != 1 or _declared_outside(scope, name.id):
            return None
        binding = bindings[0]
        if not isinstance(binding, (ast.Assign, ast.AnnAssign)) or binding.value is None:
            return None
        value = binding.value
        kind = literal_kind(value, self.module_aliases)
        if kind is None:
            return None
        start = self.position(value.lineno, value.col_offset)
        end = self.position(value.end_lineno or value.lineno, value.end_col_offset or 0)
        uses = sum(1 for node in ast.walk(scope) if isinstance(node, ast.Name) and node.id == name.id and isinstance(node.ctx, ast.Load))
        return Variable(name.id, self.segment(start, end), kind, literal_value(value), binding.lineno, uses, start, end)

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


_Function = ast.FunctionDef | ast.AsyncFunctionDef
_Scopes = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)


def _enclosing_function(tree: ast.Module, node: ast.AST) -> _Function | None:
    """The innermost function whose body contains `node`."""
    found: _Function | None = None
    for candidate in ast.walk(tree):
        if isinstance(candidate, (ast.FunctionDef, ast.AsyncFunctionDef)) and any(n is node for n in ast.walk(candidate)):
            if found is None or any(n is candidate for n in ast.walk(found)):
                found = candidate
    return found


def _own_nodes(scope: ast.AST) -> list[ast.AST]:
    """The nodes of `scope` outside the functions, classes and comprehensions nested in it."""
    out: list[ast.AST] = []
    pending = list(ast.iter_child_nodes(scope))
    while pending:
        node = pending.pop()
        out.append(node)
        if not isinstance(node, _Scopes):
            pending.extend(ast.iter_child_nodes(node))
    return out


def _parameters(scope: ast.AST) -> set[str]:
    if not isinstance(scope, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return set()
    a = scope.args
    names = [*a.posonlyargs, *a.args, *a.kwonlyargs, *([a.vararg] if a.vararg else []), *([a.kwarg] if a.kwarg else [])]
    return {arg.arg for arg in names}


def _bindings(scope: ast.AST, name: str) -> list[ast.stmt | ast.expr | ast.AST]:
    """Everything in `scope` that binds `name`: assignments, loop and `with` targets, imports,
    walrus targets, nested definitions."""
    out: list[ast.stmt | ast.expr | ast.AST] = []
    for node in _own_nodes(scope):
        if isinstance(node, ast.Assign) and any(_binds(t, name) for t in node.targets):
            out.append(node)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and _binds(node.target, name):
            out.append(node)
        elif isinstance(node, (ast.For, ast.AsyncFor)) and _binds(node.target, name):
            out.append(node)
        elif isinstance(node, ast.withitem) and node.optional_vars is not None and _binds(node.optional_vars, name):
            out.append(node)
        elif isinstance(node, ast.NamedExpr) and node.target.id == name:
            out.append(node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)) and any((a.asname or a.name.split(".")[0]) == name for a in node.names):
            out.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
            out.append(node)
    return out


def _binds(target: ast.expr, name: str) -> bool:
    if isinstance(target, ast.Name):
        return target.id == name
    if isinstance(target, (ast.Tuple, ast.List)):
        return any(_binds(e, name) for e in target.elts)
    if isinstance(target, ast.Starred):
        return _binds(target.value, name)
    return False


def _declared_outside(scope: ast.AST, name: str) -> bool:
    """`global name` or `nonlocal name` in `scope`: it is bound somewhere else."""
    return any(isinstance(n, (ast.Global, ast.Nonlocal)) and name in n.names for n in _own_nodes(scope))
