"""W0311: a lambda captures a plain Python list that is mutated afterwards.

    items = [1, 2]
    label = k.Text(lambda: f"{len(items)} itens")
    items.append(3)          # kinemo never sees this change

Plain lists are not tracked: the lambda was traced with the list as it was. Fix:
`items = k.list([1, 2])`, a reactive list whose `append`/`insert`/`pop`/`swap` are
recorded at the cursor.

"Mutated afterwards" means a mutation that comes later in the source than the lambda,
or anywhere inside a loop that also contains the lambda (it runs again on the next
iteration). Mutations: calls of list methods that change it in place, item/slice
assignment or deletion, and `+=`/`*=`.
"""

from __future__ import annotations

import ast

from ..._runtime.spans import Span
from ...diagnostics import Fix
from ..source_edits import char_column, indentation, line_fix
from .scope import CodeFinding, free_names, position
from .source import FunctionSource

CODE = "W0311"

MUTATING_METHODS = {"append", "extend", "insert", "pop", "remove", "clear", "sort", "reverse"}
LOOPS = (ast.For, ast.AsyncFor, ast.While)


def _list_value(value: ast.AST) -> bool:
    if isinstance(value, (ast.List, ast.ListComp)):
        return True
    return isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "list"


def _list_assignments(fn: ast.AST) -> dict[str, list[ast.Assign]]:
    out: dict[str, list[ast.Assign]] = {}
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if _list_value(node.value):
                out.setdefault(node.targets[0].id, []).append(node)
    return out


def _subscript_of(target: ast.AST, name: str) -> bool:
    return isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == name


def _mutations(fn: ast.AST, name: str) -> list[ast.AST]:
    out: list[ast.AST] = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            owner = node.func.value
            if isinstance(owner, ast.Name) and owner.id == name and node.func.attr in MUTATING_METHODS:
                out.append(node)
        elif isinstance(node, ast.Assign) and any(_subscript_of(t, name) for t in node.targets):
            out.append(node)
        elif isinstance(node, ast.AugAssign):
            t = node.target
            if (isinstance(t, ast.Name) and t.id == name) or _subscript_of(t, name):
                out.append(node)
        elif isinstance(node, ast.Delete) and any(_subscript_of(t, name) for t in node.targets):
            out.append(node)
    return out


def _enclosing_loops(node: ast.AST, source: FunctionSource) -> set[ast.AST]:
    loops: set[ast.AST] = set()
    for a in source.module.ancestors(node):
        if a is source.node:
            break
        if isinstance(a, LOOPS):
            loops.add(a)
    return loops


def _k_list_fix(source: FunctionSource, assignment: ast.Assign, name: str) -> Fix:
    module = source.module
    alias = module.kinemo_alias
    description = "use a reactive list"
    value = assignment.value
    line = module.line(assignment.lineno)
    if value.lineno != value.end_lineno or value.end_col_offset is None:
        return Fix(description, f"{name} = {alias}.list([...])")
    start = char_column(line, value.col_offset)
    end = char_column(line, value.end_col_offset)
    inner = line[start:end]
    if isinstance(value, ast.Call) and len(value.args) == 1 and not value.keywords:
        inner = ast.get_source_segment("\n".join(module.lines), value.args[0]) or inner
    new_line = line[:start] + f"{alias}.list({inner})" + line[end:]
    return line_fix(description, module.file, assignment.lineno, indentation(line) + new_line.lstrip())


def find(source: FunctionSource) -> list[CodeFinding]:
    fn = source.node
    module = source.module
    assignments = _list_assignments(fn)
    if not assignments:
        return []
    out: list[CodeFinding] = []
    for lam in (n for n in ast.walk(fn) if isinstance(n, ast.Lambda)):
        lam_pos = position(lam)
        lam_loops = _enclosing_loops(lam, source)
        for name in sorted(free_names(lam) & assignments.keys()):
            before = [a for a in assignments[name] if position(a) < lam_pos]
            if not before:
                continue
            assignment = before[-1]
            later = [
                m for m in _mutations(fn, name)
                if position(m) > lam_pos or (lam_loops & _enclosing_loops(m, source))
            ]
            if not later:
                continue
            mutation_line = later[0].lineno  # type: ignore[attr-defined]
            message = (
                f"lambda captures the Python list '{name}', which is modified later (line {mutation_line}); "
                "plain lists are not tracked"
            )
            spans = [
                Span(module.file, lam.lineno, char_column(module.line(lam.lineno), lam.col_offset)),
                Span(module.file, assignment.lineno, 0),
            ]
            out.append(CodeFinding(CODE, message, spans, [_k_list_fix(source, assignment, name)]))
    return out
