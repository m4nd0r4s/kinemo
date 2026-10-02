"""Resolve documented symbols to live objects and extract signatures and docstrings with
`inspect`, formatted the way an author writes the call (`s.play(...)`, `ax.plot(...)`)."""

from __future__ import annotations

import enum
import inspect
import re
from typing import Any

import kinemo

#: Variable an author uses for an instance of each documented owner type.
OWNER_VARIABLES = {
    "Scene": "s",
    "Axes": "ax",
    "Node": "obj",
    "Group": "group",
    "Plot": "curve",
    "Signal": "x",
    "Expr": "x",
    "Animation": "anim",
    "EventSource": "event",
    "EventInfo": "e",
    "Code": "code",
}


class Missing(enum.Enum):
    """Marker for a symbol that does not exist (yet) in this version of kinemo."""

    MISSING = "missing"


MISSING = Missing.MISSING


def _extra_types() -> dict[str, Any]:
    """Owner types that are documented but not exported as `k.*`."""
    from ..objects.charts.plot import Plot

    return {"Plot": Plot}


def owner_type(name: str) -> Any:
    if name in kinemo.__all__:
        return getattr(kinemo, name)
    return _extra_types().get(name)


def resolve(symbol: str) -> Any:
    """The live object for `k.draw` / `Scene.play` / `Axes.plot`, or `MISSING`."""
    if symbol.startswith("k."):
        name = symbol[2:]
        if name not in kinemo.__all__:
            return MISSING
        return getattr(kinemo, name)
    owner_name, _, member = symbol.partition(".")
    owner = owner_type(owner_name)
    if owner is None or not member:
        return MISSING
    try:
        return inspect.getattr_static(owner, member)
    except AttributeError:
        return MISSING


def exists(symbol: str) -> bool:
    return resolve(symbol) is not MISSING


def display_name(symbol: str) -> str:
    """`Scene.play` → `s.play`, `Axes.plot` → `ax.plot`; `k.*` names are unchanged."""
    if symbol.startswith("k."):
        return symbol
    owner, _, member = symbol.partition(".")
    return f"{OWNER_VARIABLES.get(owner, owner.lower())}.{member}"


# ---- formatting --------------------------------------------------------------------------

def _default_repr(value: Any) -> str:
    from ..values.color import PALETTE, Color

    if isinstance(value, Color):
        for name, color in PALETTE.items():
            if color == value:
                return f"k.{name}"
        return f'k.rgb({value.r:g}, {value.g:g}, {value.b:g})'
    if isinstance(value, str):
        return '"' + value.replace('"', '\\"') + '"'
    if isinstance(value, float) and len(repr(value)) > 8:
        return f"{value:.6g}"
    if callable(value) and hasattr(value, "__name__"):
        return value.__name__
    return repr(value)


#: `[T]`-style arguments that name a type variable (`EventInfo[P]` reads as `EventInfo`).
_TYPE_VARIABLE_ARGUMENT = re.compile(r"\[(?:T|U|P|ChildT|StateT)\]")


def _annotation(annotation: Any, owner: str | None = None) -> str:
    if annotation is inspect.Signature.empty:
        return ""
    text = annotation if isinstance(annotation, str) else getattr(annotation, "__name__", str(annotation))
    text = text.strip("'\"").replace("[Any]", "")
    text = _TYPE_VARIABLE_ARGUMENT.sub("", text)
    if text == "Self" and owner:
        return owner
    return "" if text in ("Any", "None", "") else text


def format_parameters(sig: inspect.Signature, skip_first: bool = False) -> str:
    params = list(sig.parameters.values())
    if skip_first and params:
        params = params[1:]
    out: list[str] = []
    keyword_marker_done = False
    for p in params:
        if p.name.startswith("_"):
            continue
        if p.kind is p.VAR_POSITIONAL:
            out.append(f"*{p.name}")
            keyword_marker_done = True
            continue
        if p.kind is p.VAR_KEYWORD:
            out.append(f"**{p.name}")
            continue
        if p.kind is p.KEYWORD_ONLY and not keyword_marker_done:
            out.append("*")
            keyword_marker_done = True
        out.append(p.name if p.default is p.empty else f"{p.name}={_default_repr(p.default)}")
    return ", ".join(out)


def _callable_signature(display: str, fn: Any, skip_first: bool, returns: bool = True, owner: str | None = None) -> str:
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return display
    returns_text = _annotation(sig.return_annotation, owner) if returns else ""
    call = f"{display}({format_parameters(sig, skip_first)})"
    if returns_text.startswith("Iterator"):
        return f"with {call}:"  # a context manager
    return f"{call} -> {returns_text}" if returns_text else call


def _namespace_signature(display: str, obj: Any) -> str:
    """`k.ease`: the public members of a namespace object."""
    members: list[str] = []
    for name, value in vars(type(obj)).items():
        if name.startswith("_"):
            continue
        if isinstance(value, staticmethod):
            members.append(_callable_signature(name, value.__func__, False, returns=False))
        else:
            members.append(name)
    return " | ".join(f"{display}.{m}" for m in members) if members else display


def signature(symbol: str) -> str:
    """How a call to `symbol` is written, with defaults (annotations omitted)."""
    from ..reactive.expr import Expr
    from ..values.color import Color

    display = display_name(symbol)
    obj = resolve(symbol)
    if obj is MISSING:
        return display
    if isinstance(obj, staticmethod | classmethod):
        return _callable_signature(display, obj.__func__, isinstance(obj, classmethod))
    if isinstance(obj, property):
        return display
    if isinstance(obj, Color):
        return f"{display}  # {obj.to_hex()}"
    if isinstance(obj, Expr):
        return f"{display}  # read-only signal"
    if isinstance(obj, float | int):
        return f"{display} = {obj:.6g}"
    if inspect.isclass(obj):
        init = obj.__dict__.get("__init__") or next(
            (c.__dict__["__init__"] for c in obj.__mro__ if "__init__" in c.__dict__), None
        )
        if init is None or init is object.__init__:
            return f"{display}()"
        return _callable_signature(display, init, True)
    if inspect.isfunction(obj) or inspect.ismethod(obj) or inspect.isbuiltin(obj):
        owner = None if symbol.startswith("k.") else symbol.partition(".")[0]
        return _callable_signature(display, obj, skip_first=not symbol.startswith("k."), owner=owner)
    if callable(obj):
        return _callable_signature(display, obj, False)
    return _namespace_signature(display, obj)


def docstring_summary(obj: Any) -> str:
    """First paragraph of the docstring, on one line."""
    if isinstance(obj, staticmethod | classmethod):
        obj = obj.__func__
    doc = inspect.getdoc(obj) or ""
    return " ".join(doc.split("\n\n", 1)[0].split())


def own_methods(symbol: str) -> list[tuple[str, str]]:
    """(name, signature) of the public methods a class defines itself (`k.Axes` → plot, ...)."""
    obj = resolve(symbol)
    if not inspect.isclass(obj):
        return []
    display = OWNER_VARIABLES.get(obj.__name__, obj.__name__.lower())
    out: list[tuple[str, str]] = []
    for name, value in obj.__dict__.items():
        if name.startswith("_") or name == "build":
            continue
        if inspect.isfunction(value):
            out.append((name, _callable_signature(f"{display}.{name}", value, True, owner=obj.__name__)))
        elif isinstance(value, classmethod | staticmethod):
            fn = value.__func__
            out.append((name, _callable_signature(f"{symbol}.{name}", fn, isinstance(value, classmethod))))
    return out
