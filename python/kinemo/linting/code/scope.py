"""AST helpers shared by the code lints: free names of lambdas, positions, findings."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field

from ..._runtime.spans import Span
from ...diagnostics import Fix

COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)


@dataclass
class CodeFinding:
    code: str
    message: str
    spans: list[Span]
    fixes: list[Fix] = field(default_factory=list)


def target_names(target: ast.AST) -> set[str]:
    """Names bound by an assignment/loop target (`i`, `(i, x)`, `[a, *rest]`)."""
    return {n.id for n in ast.walk(target) if isinstance(n, ast.Name)}


def parameter_names(args: ast.arguments) -> set[str]:
    names = {a.arg for a in args.posonlyargs + args.args + args.kwonlyargs}
    if args.vararg:
        names.add(args.vararg.arg)
    if args.kwarg:
        names.add(args.kwarg.arg)
    return names


def free_names(node: ast.AST, bound: frozenset[str] = frozenset()) -> set[str]:
    """Names read in `node` that are not bound inside it (lambda parameters,
    comprehension targets, nested lambdas)."""
    if isinstance(node, ast.Lambda):
        inner = bound | parameter_names(node.args)
        out: set[str] = set()
        for default in node.args.defaults + [d for d in node.args.kw_defaults if d is not None]:
            out |= free_names(default, bound)
        return out | free_names(node.body, inner)
    if isinstance(node, COMPREHENSIONS):
        inner = set(bound)
        out = set()
        for gen in node.generators:
            out |= free_names(gen.iter, frozenset(inner))
            inner |= target_names(gen.target)
            for cond in gen.ifs:
                out |= free_names(cond, frozenset(inner))
        parts = [node.key, node.value] if isinstance(node, ast.DictComp) else [node.elt]
        for part in parts:
            out |= free_names(part, frozenset(inner))
        return out
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        return set() if node.id in bound else {node.id}
    out = set()
    for child in ast.iter_child_nodes(node):
        out |= free_names(child, bound)
    return out


def position(node: ast.AST) -> tuple[int, int]:
    return (getattr(node, "lineno", 0), getattr(node, "col_offset", 0))

