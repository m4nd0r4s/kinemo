"""Insert and remove statements of a scene function: what the preview's editor mode writes.

The code stays the only source of truth: adding an object from the preview writes a line into
the scene function, as an author would. A statement goes after the one at a given line (the
statement at the playhead), with its indentation, or at the end of the function. Places where
one statement stands for several runs (a loop) or for another scene's code (a clip or helper
defined inside) are refused with the reason, and every result must still parse.
"""

from __future__ import annotations

import ast
import keyword
import re

from .call_sites import SourceFile
from .source_edit import EditError

_LOOPS = (ast.For, ast.AsyncFor, ast.While)
_NESTED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
#: Statements whose body holds statements the editor may write between.
_BLOCKS = (ast.With, ast.AsyncWith, ast.If, ast.Try)


def scene_function(source: SourceFile, name: str) -> ast.FunctionDef:
    """The function `name` of the file (the scene the preview shows)."""
    for node in ast.walk(source.tree) if source.tree else ():
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise EditError(f"the scene function {name}() is no longer in {source.path}; the preview reloads")


def _bodies(node: ast.stmt) -> list[list[ast.stmt]]:
    if isinstance(node, ast.Try):
        return [node.body, *(h.body for h in node.handlers), node.orelse, node.finalbody]
    if isinstance(node, ast.If):
        return [node.body, node.orelse]
    return [node.body] if isinstance(node, (ast.With, ast.AsyncWith)) else []


def _statement_at(body: list[ast.stmt], line: int) -> tuple[list[ast.stmt], int] | None:
    """The innermost block and index of the statement that covers `line`, going into `with`,
    `if` and `try` blocks; loops and nested definitions are refused."""
    for index, stmt in enumerate(body):
        if not (stmt.lineno <= line <= (stmt.end_lineno or stmt.lineno)):
            continue
        if isinstance(stmt, _LOOPS) and line > stmt.lineno:
            raise EditError("that line is inside a loop: a statement there would run on every pass; add it after the loop")
        if isinstance(stmt, _NESTED) and line > stmt.lineno:
            raise EditError("that line is inside a function defined in the scene (a clip or a helper); add it in the scene itself")
        if isinstance(stmt, _BLOCKS):
            for inner in _bodies(stmt):
                found = _statement_at(inner, line)
                if found is not None:
                    return found
        return body, index
    return None


def _lines_of(text: str) -> list[str]:
    return text.split("\n")


def _checked(text: str, path: str) -> str:
    try:
        ast.parse(text, filename=path)
    except SyntaxError as e:
        raise EditError(f"the edit would not parse ({e.msg}); nothing was written") from None
    return text


def insert_statement(source: SourceFile, function: str, after_line: int | None, code: str) -> str:
    """The text of `source` with `code` (one or more statements) inserted in `function`: after
    the statement covering `after_line` (same indentation), or at the end of the function."""
    try:
        new = ast.parse(code)
    except SyntaxError as e:
        raise EditError(f"not a statement: {code!r} ({e.msg})") from None
    if not new.body:
        raise EditError("nothing to insert")
    fn = scene_function(source, function)
    if after_line is None:
        anchor = fn.body[-1]
    else:
        found = _statement_at(fn.body, after_line)
        if found is None:
            raise EditError(f"line {after_line} is not a statement of {function}()")
        body, index = found
        anchor = body[index]
    indent = " " * anchor.col_offset
    lines = _lines_of(source.text)
    end = anchor.end_lineno or anchor.lineno
    block = [indent + line if line.strip() else "" for line in code.strip("\n").split("\n")]
    return _checked("\n".join(lines[:end] + block + lines[end:]), source.path)


def remove_statement(source: SourceFile, function: str, line: int) -> str:
    """The text of `source` without the statement of `function` that starts at `line`; a block
    left empty gets `pass`."""
    fn = scene_function(source, function)
    found = _statement_at(fn.body, line)
    if found is None:
        raise EditError(f"line {line} is not a statement of {function}()")
    body, index = found
    stmt = body[index]
    if stmt.lineno != line:
        raise EditError(f"line {line} is inside a statement that starts on line {stmt.lineno}")
    lines = _lines_of(source.text)
    start, end = stmt.lineno - 1, stmt.end_lineno or stmt.lineno
    replacement = [" " * stmt.col_offset + "pass"] if len(body) == 1 else []
    return _checked("\n".join(lines[:start] + replacement + lines[end:]), source.path)


def unique_name(source: SourceFile, function: str, base: str) -> str:
    """`base`, or `base_2`, `base_3`... : the first name not bound anywhere in `function`."""
    fn = scene_function(source, function)
    taken = {a.arg for a in ast.walk(fn.args) if isinstance(a, ast.arg)}
    taken |= {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    stem = re.sub(r"\W+", "_", base).strip("_").lower() or "item"
    if stem[0].isdigit() or keyword.iskeyword(stem):
        stem = f"{stem}_"
    name, n = stem, 2
    while name in taken:
        name, n = f"{stem}_{n}", n + 1
    return name


#: What the preview's palette adds: the constructor (placed at a point unless it says where it
#: is itself) and the verb it enters with.
OBJECT_KINDS: dict[str, tuple[str, str, str]] = {
    # kind: (base name, constructor with {k}, {x}, {y}, entrance verb)
    "text": ("label", '{k}.Text("Text", size=0.5).place(at=({x}, {y}))', "write"),
    "math": ("formula", '{k}.Math(r"x^2").place(at=({x}, {y}))', "write"),
    "circle": ("circle", "{k}.Circle(r=0.5).place(at=({x}, {y}))", "draw"),
    "square": ("square", "{k}.Square(1).place(at=({x}, {y}))", "draw"),
    "arrow": ("arrow", "{k}.Arrow(start=({x0}, {y}), end=({x1}, {y}))", "draw"),
    "axes": ("axes", "{k}.Axes(x=(-3, 3, 1), y=(-2, 2, 1), width=6, height=4).place(at=({x}, {y}))", "draw"),
}


def _number(v: float) -> str:
    text = f"{round(v, 2):.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def object_statements(source: SourceFile, function: str, kind: str, at: tuple[float, float], alias: str | None) -> str:
    """The lines that add a `kind` object at `at` and bring it in: `circle = k.Circle(...)`
    and `s.play(k.draw(circle))`, with a name the function does not use yet."""
    if kind not in OBJECT_KINDS:
        raise EditError(f"unknown object {kind!r} (objects: {', '.join(OBJECT_KINDS)})")
    if alias is None:
        raise EditError("the scene file does not import kinemo as a module (import kinemo as k)")
    fn = scene_function(source, function)
    if not fn.args.args:
        raise EditError(f"{function}() takes no scene parameter")
    scene_param = fn.args.args[0].arg
    base, constructor, verb = OBJECT_KINDS[kind]
    name = unique_name(source, function, base)
    x, y = at
    made = constructor.format(k=alias, x=_number(x), y=_number(y), x0=_number(x - 0.75), x1=_number(x + 0.75))
    return f"{name} = {made}\n{scene_param}.play({alias}.{verb}({name}))"


#: Animations the preview adds for a selected object at the playhead: entrances, emphasis,
#: exits (verbs of `k` that take the object).
ANIMATION_VERBS: tuple[str, ...] = ("fade_in", "draw", "write", "grow", "indicate", "fade_out", "shrink")


def animation_statement(source: SourceFile, function: str, name: str, verb: str, alias: str | None) -> str:
    """`s.play(k.<verb>(<name>))` for an object the scene function (or the module) names."""
    if verb not in ANIMATION_VERBS:
        raise EditError(f"unknown animation {verb!r} (animations: {', '.join(ANIMATION_VERBS)})")
    if alias is None:
        raise EditError("the scene file does not import kinemo as a module (import kinemo as k)")
    if not name.isidentifier() or keyword.iskeyword(name):
        raise EditError(f"{name} is not a variable of the scene (a part or an unnamed object); animate it in the code")
    fn = scene_function(source, function)
    bound = {n.id for n in ast.walk(source.tree or fn) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    if name not in bound:
        raise EditError(f"{name} is not a variable of the scene; animate it in the code")
    if not fn.args.args:
        raise EditError(f"{function}() takes no scene parameter")
    return f"{fn.args.args[0].arg}.play({alias}.{verb}({name}))"


def definition_line(source: SourceFile, function: str, name: str) -> int | None:
    """The line where `function` first assigns `name` (None: defined outside the function)."""
    fn = scene_function(source, function)
    lines = [n.lineno for n in ast.walk(fn) if isinstance(n, ast.Name) and n.id == name and isinstance(n.ctx, ast.Store)]
    return min(lines) if lines else None
