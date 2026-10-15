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


def _wait_seconds(stmt: ast.stmt, scene_param: str) -> float | None:
    """The seconds of `s.wait(1.5)` (a literal), else None."""
    if not (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call)):
        return None
    call = stmt.value
    if not (isinstance(call.func, ast.Attribute) and call.func.attr == "wait" and isinstance(call.func.value, ast.Name) and call.func.value.id == scene_param):
        return None
    if len(call.args) != 1 or call.keywords:
        return None
    arg = call.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, (int, float)) and not isinstance(arg.value, bool):
        return float(arg.value)
    return None


def _uses_scene(stmt: ast.stmt, scene_param: str) -> bool:
    """Whether `stmt` calls a method of the scene (`s.play`, `s.wait`, `s.voice`...): only those
    take time."""
    return any(isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == scene_param for n in ast.walk(stmt))


def shift_statement(source: SourceFile, function: str, line: int, by: float) -> str:
    """Start the statement on `line` `by` seconds later (earlier when negative): the literal
    `s.wait(...)` right before it changes, or one is added before it."""
    fn = scene_function(source, function)
    if not fn.args.args:
        raise EditError(f"{function}() takes no scene parameter")
    scene_param = fn.args.args[0].arg
    found = _statement_at(fn.body, line)
    if found is None:
        raise EditError(f"line {line} is not a statement of {function}()")
    body, index = found
    stmt = body[index]
    # The wait that sets its start: the nearest statement before it that uses the scene
    # (making `circle = k.Circle()` between them takes no time).
    previous = next((body[i] for i in range(index - 1, -1, -1) if _uses_scene(body[i], scene_param)), None)
    seconds = _wait_seconds(previous, scene_param) if previous is not None else None
    lines = _lines_of(source.text)
    if previous is not None and seconds is not None:
        new = round(seconds + by, 2)
        if new <= 0.005:
            start, end = previous.lineno - 1, previous.end_lineno or previous.lineno
            return _checked("\n".join(lines[:start] + lines[end:]), source.path)
        start, end = previous.lineno - 1, previous.end_lineno or previous.lineno
        indent = " " * previous.col_offset
        return _checked("\n".join(lines[:start] + [f"{indent}{scene_param}.wait({_number(new)})"] + lines[end:]), source.path)
    if by <= 0:
        raise EditError("nothing waits before it to shorten; move the statement before it later instead")
    indent = " " * stmt.col_offset
    at = stmt.lineno - 1
    return _checked("\n".join(lines[:at] + [f"{indent}{scene_param}.wait({_number(by)})"] + lines[at:]), source.path)


def swap_statement(source: SourceFile, function: str, line: int, direction: int) -> str:
    """Swap the statement on `line` with the one before (`direction` -1) or after (+1) it in
    the same block, refused when the later one uses a name the earlier one assigns."""
    fn = scene_function(source, function)
    found = _statement_at(fn.body, line)
    if found is None:
        raise EditError(f"line {line} is not a statement of {function}()")
    body, index = found
    other = index + (1 if direction > 0 else -1)
    if not 0 <= other < len(body):
        raise EditError("it is already the " + ("last" if direction > 0 else "first") + " statement of its block")
    first, second = sorted((index, other))
    a, b = body[first], body[second]
    assigned = {n.id for n in ast.walk(a) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
    used = {n.id for n in ast.walk(b) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    if assigned & used:
        names = ", ".join(sorted(assigned & used))
        raise EditError(f"line {b.lineno} uses {names}, made on line {a.lineno}: they can't swap")
    lines = _lines_of(source.text)
    a_lines = lines[a.lineno - 1 : a.end_lineno or a.lineno]
    b_lines = lines[b.lineno - 1 : b.end_lineno or b.lineno]
    between = lines[(a.end_lineno or a.lineno) : b.lineno - 1]
    start, end = a.lineno - 1, b.end_lineno or b.lineno
    return _checked("\n".join(lines[:start] + b_lines + between + a_lines + lines[end:]), source.path)
