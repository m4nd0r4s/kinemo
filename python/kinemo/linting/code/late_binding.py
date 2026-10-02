"""W0310: a lambda inside a loop reads the loop variable (late binding).

    for i in range(5):
        dots.append(k.Dot(x=lambda: t() + i))   # every lambda sees the last i

Python closures capture variables, not values, and kinemo evaluates prop lambdas
during playback, long after the loop ended. Fix: bind the value as a default argument,
`lambda i=i: ...`. Lambdas consumed on the spot (`sorted(key=lambda ...)`, `map`,
`filter`, ...) are not reported.
"""

from __future__ import annotations

import ast

from ..._runtime.spans import Span
from ...diagnostics import Fix
from ..source_edits import char_column, line_fix
from .scope import CodeFinding, free_names, parameter_names, target_names
from .source import FunctionSource

CODE = "W0310"

#: Callables that run a lambda argument immediately.
IMMEDIATE_CALLS = {"sorted", "min", "max", "map", "filter", "sum", "any", "all", "list", "tuple", "set", "reduce"}
IMMEDIATE_METHODS = {"sort"}


def _consumed_immediately(lam: ast.Lambda, source: FunctionSource) -> bool:
    parent = source.module.parent(lam)
    if isinstance(parent, ast.keyword):
        parent = source.module.parent(parent)
    if not isinstance(parent, ast.Call):
        return False
    func = parent.func
    if isinstance(func, ast.Name):
        return func.id in IMMEDIATE_CALLS
    return isinstance(func, ast.Attribute) and func.attr in IMMEDIATE_METHODS


class _LoopLambdaVisitor(ast.NodeVisitor):
    def __init__(self, source: FunctionSource) -> None:
        self.source = source
        self.loop_variables: list[set[str]] = []
        self.found: list[tuple[ast.Lambda, list[str]]] = []

    def _visit_loop(self, node: ast.For | ast.AsyncFor) -> None:
        self.visit(node.iter)
        self.loop_variables.append(target_names(node.target))
        for stmt in node.body:
            self.visit(stmt)
        self.loop_variables.pop()
        for stmt in node.orelse:
            self.visit(stmt)

    visit_For = _visit_loop
    visit_AsyncFor = _visit_loop

    def _visit_comprehension(self, node: ast.AST) -> None:
        generators: list[ast.comprehension] = node.generators  # type: ignore[attr-defined]
        pushed = 0
        for gen in generators:
            self.visit(gen.iter)
            self.loop_variables.append(target_names(gen.target))
            pushed += 1
            for cond in gen.ifs:
                self.visit(cond)
        parts = [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]  # type: ignore[attr-defined]
        for part in parts:
            self.visit(part)
        del self.loop_variables[len(self.loop_variables) - pushed :]

    visit_ListComp = _visit_comprehension
    visit_SetComp = _visit_comprehension
    visit_GeneratorExp = _visit_comprehension
    visit_DictComp = _visit_comprehension

    def visit_Lambda(self, node: ast.Lambda) -> None:
        in_loop = set().union(*self.loop_variables) if self.loop_variables else set()
        # Defaults are evaluated when the lambda is created: only the body binds late.
        body_names = free_names(node.body, frozenset(parameter_names(node.args)))
        captured = sorted(body_names & in_loop)
        if captured and not _consumed_immediately(node, self.source):
            self.found.append((node, captured))
            return
        self.generic_visit(node)


def _default_argument_line(line: str, lam: ast.Lambda, captured: list[str]) -> str | None:
    """`line` with the lambda's header rewritten to bind `captured` as defaults."""
    if lam.body.lineno != lam.lineno:
        return None
    start = char_column(line, lam.col_offset)
    body_start = char_column(line, lam.body.col_offset)
    header = line[start:body_start]
    if not header.startswith("lambda") or ":" not in header:
        return None
    existing = ast.unparse(lam.args)
    defaults = ", ".join(f"{n}={n}" for n in captured)
    params = f"{existing}, {defaults}" if existing else defaults
    return line[:start] + f"lambda {params}: " + line[body_start:]


def find(source: FunctionSource) -> list[CodeFinding]:
    visitor = _LoopLambdaVisitor(source)
    for stmt in source.node.body:
        visitor.visit(stmt)
    module = source.module
    out: list[CodeFinding] = []
    for lam, captured in visitor.found:
        names = ", ".join(f"'{n}'" for n in captured)
        message = (
            f"lambda in a loop captures {names} by reference (late binding): "
            "every lambda will see the loop's last value"
        )
        span = Span(module.file, lam.lineno, char_column(module.line(lam.lineno), lam.col_offset))
        new_line = _default_argument_line(module.line(lam.lineno), lam, captured)
        description = "capture the current value with a default argument (or use .map)"
        if new_line is not None:
            fix = line_fix(description, module.file, lam.lineno, new_line)
        else:
            fix = Fix(description, "lambda " + ", ".join(f"{n}={n}" for n in captured) + ": ...")
        out.append(CodeFinding(CODE, message, [span], [fix]))
    return out
