"""Locating and parsing the source of scene functions for AST lints."""

from __future__ import annotations

import ast
import inspect
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass
class ParsedModule:
    """A whole source file, parsed once. Line numbers and columns are the file's own."""

    file: str
    lines: list[str]
    tree: ast.Module
    #: Name the module imports kinemo as (`import kinemo as k` → "k").
    kinemo_alias: str = "k"
    parents: dict[ast.AST, ast.AST] = field(default_factory=dict)

    def line(self, number: int) -> str:
        return self.lines[number - 1] if 0 < number <= len(self.lines) else ""

    def parent(self, node: ast.AST) -> ast.AST | None:
        return self.parents.get(node)

    def ancestors(self, node: ast.AST) -> Iterable[ast.AST]:
        cur = self.parents.get(node)
        while cur is not None:
            yield cur
            cur = self.parents.get(cur)


@dataclass
class FunctionSource:
    """One function to lint, inside its parsed module."""

    module: ParsedModule
    node: FunctionNode


_MODULE_CACHE: dict[tuple[str, float], ParsedModule] = {}


def parse_file(file: str) -> ParsedModule | None:
    import os

    try:
        key = (file, os.path.getmtime(file))
    except OSError:
        return None
    cached = _MODULE_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        with open(file, encoding="utf-8") as fh:
            text = fh.read()
        tree = ast.parse(text, filename=file)
    except (OSError, SyntaxError, ValueError):
        return None
    module = ParsedModule(file, text.splitlines(), tree, _kinemo_alias(tree))
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            module.parents[child] = parent
    _MODULE_CACHE[key] = module
    return module


def _kinemo_alias(tree: ast.Module) -> str:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "kinemo":
                    return alias.asname or "kinemo"
    return "k"


def _functions(tree: ast.AST) -> list[FunctionNode]:
    return [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _first_line(node: FunctionNode) -> int:
    return min([node.lineno] + [d.lineno for d in node.decorator_list])


def function_source(fn: Callable[..., Any]) -> FunctionSource | None:
    """Source of `fn` (a scene function, or a `SceneDef` holding one)."""
    fn = getattr(fn, "fn", fn)
    fn = inspect.unwrap(fn)
    try:
        file = inspect.getsourcefile(fn)
        _, start = inspect.getsourcelines(fn)
    except (OSError, TypeError):
        return None
    if file is None:
        return None
    module = parse_file(file)
    if module is None:
        return None
    name = getattr(fn, "__name__", None)
    candidates = [f for f in _functions(module.tree) if f.name == name]
    exact = [f for f in candidates if _first_line(f) == start or f.lineno == start]
    chosen = (exact or candidates or [None])[0]
    return FunctionSource(module, chosen) if chosen is not None else None


def _is_scene_function(node: FunctionNode) -> bool:
    for d in node.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        if isinstance(target, ast.Attribute) and target.attr == "scene":
            return True
        if isinstance(target, ast.Name) and target.id == "scene":
            return True
    args = node.args.posonlyargs + node.args.args
    return bool(args) and args[0].arg == "s"


def functions_at_lines(file: str, lines: Iterable[int]) -> list[FunctionSource]:
    """Scene functions of `file` containing any of `lines` (used when the scene function
    itself is unknown: lines come from the spans of the scene's objects).

    For each line, the innermost enclosing function that looks like a scene function
    (decorated with `scene`, or whose first parameter is `s`) is chosen; failing that,
    the outermost enclosing function.
    """
    module = parse_file(file)
    if module is None:
        return []
    functions = _functions(module.tree)
    chosen: list[FunctionNode] = []
    for line in sorted(set(lines)):
        enclosing = [f for f in functions if _first_line(f) <= line <= (f.end_lineno or f.lineno)]
        if not enclosing:
            continue
        enclosing.sort(key=lambda f: _first_line(f))
        scene_like = [f for f in enclosing if _is_scene_function(f)]
        pick = scene_like[-1] if scene_like else enclosing[0]
        if pick not in chosen:
            chosen.append(pick)
    return [FunctionSource(module, f) for f in chosen]
