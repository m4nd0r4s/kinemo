"""What kind of value a call argument takes, for choosing an editor widget.

Read from the API's own annotations (`align: Align` is a choice, `at: Anchor | VecVal` a
choice or a point, `fill: ColorVal` a color) and, for props passed through `**props`, from
the prop's declared kind. Annotations are strings (`from __future__ import annotations`)
and some names exist only for the type checker, so they are evaluated leniently: an unknown
name just contributes nothing.
"""

from __future__ import annotations

import ast
import builtins
import inspect
import sys
import types
import typing
from typing import Any, Callable, Literal, Mapping, Union

from ..anim.ease import Ease
from ..objects.props import PropSpec
from ..theme.tokens import ThemeToken
from ..values.color import Color
from ..values.vec import Vec

ValueType = dict[str, Any]
"""`{"type": "number" | "string" | "bool" | "color" | "vector" | "choice" | "ease", ...}`;
a choice has `choices`, and `vector: true` when a point is accepted too; a number may have
`range: [low, high]`."""

#: Props whose value is a fraction.
_FRACTIONS = {"opacity", "fill_opacity", "stroke_opacity"}

_PROP_KINDS = {"float": "number", "color": "color", "vec2": "vector", "bool": "bool", "str": "string"}


class _Unknown:
    """Stands for a name the annotation's module does not define at runtime."""

    def __or__(self, other: object) -> object:
        return other

    def __ror__(self, other: object) -> object:
        return other

    def __getitem__(self, item: object) -> "_Unknown":
        return self


_UNKNOWN = _Unknown()


def _fallback_scopes() -> list[Mapping[str, object]]:
    from ..anim import ease
    from ..objects import keywords
    from ..values import aliases

    return [vars(keywords), vars(aliases), vars(ease), vars(typing), vars(builtins)]


def _lookup(name: str, scopes: list[Mapping[str, object]]) -> object:
    for scope in scopes:
        if name in scope:
            return scope[name]
    return _UNKNOWN


def evaluate(annotation: object, module_globals: Mapping[str, object]) -> object:
    """An annotation string evaluated with its module's names, then kinemo's public types.

    Every name is resolved up front into a plain dict (an unknown one becomes a placeholder),
    rather than through a mapping with `__missing__`, which `eval` does not consult on every
    Python version."""
    if not isinstance(annotation, str):
        return annotation
    try:
        tree = ast.parse(annotation, mode="eval")
    except SyntaxError:
        return _UNKNOWN
    scopes = [module_globals, *_fallback_scopes()]
    names = {node.id: _lookup(node.id, scopes) for node in ast.walk(tree) if isinstance(node, ast.Name)}
    try:
        # Real builtins: on some versions `Union | None` imports internally.
        return eval(compile(tree, "<annotation>", "eval"), {"__builtins__": builtins}, names)  # noqa: S307 - kinemo's own annotations
    except Exception:  # noqa: BLE001 - an annotation the runtime cannot evaluate is just unknown
        return _UNKNOWN


def classify(tp: object) -> ValueType | None:
    """Widget type of an evaluated annotation, or `None` when no literal editor fits."""
    found = _kinds(tp)
    if "color" in found:
        return {"type": "color"}
    if found.get("choice"):
        return {"type": "choice", "choices": found["choice"], "vector": "vector" in found}
    for kind in ("ease", "vector", "number", "bool", "string"):
        if kind in found:
            return {"type": kind}
    return None


def _kinds(tp: object) -> dict[str, Any]:
    out: dict[str, Any] = {}
    origin = typing.get_origin(tp)
    if origin in (Union, types.UnionType):
        for arg in typing.get_args(tp):
            for kind, value in _kinds(arg).items():
                if kind == "choice":
                    out.setdefault("choice", []).extend(c for c in value if c not in out.get("choice", []))
                else:
                    out[kind] = value
    elif origin is Literal:
        values = [v for v in typing.get_args(tp) if isinstance(v, str)]
        if values:
            out["choice"] = values
    elif origin is tuple or tp is Vec:
        out["vector"] = True
    elif tp in (Color, ThemeToken):
        out["color"] = True
    elif tp is Ease:
        out["ease"] = True
    elif tp is bool:
        out["bool"] = True
    elif tp in (int, float):
        out["number"] = True
    elif tp is str:
        out["string"] = True
    return out


def from_prop_spec(name: str, spec: PropSpec) -> ValueType | None:
    if spec.kind == "str" and spec.choices:
        return {"type": "choice", "choices": list(spec.choices), "vector": False}
    kind = _PROP_KINDS.get(spec.kind)
    if kind is None:
        return None
    out: ValueType = {"type": kind}
    if name in _FRACTIONS:
        out["range"] = [0, 1]
    return out


def parameter_types(fn: Callable[..., Any] | None) -> dict[str, ValueType]:
    """Widget types of a callable's parameters, `**props: Unpack[Keywords]` expanded."""
    if fn is None:
        return {}
    target = inspect.unwrap(fn)
    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError):
        return {}
    module_globals = getattr(target, "__globals__", {})
    out: dict[str, ValueType] = {}
    for parameter in signature.parameters.values():
        if parameter.annotation is inspect.Parameter.empty:
            continue
        annotation = evaluate(parameter.annotation, module_globals)
        if parameter.kind is inspect.Parameter.VAR_KEYWORD:
            out.update(_keyword_types(annotation))
        elif parameter.kind is not inspect.Parameter.VAR_POSITIONAL:
            kind = classify(annotation)
            if kind is not None:
                out[parameter.name] = kind
    return out


def _keyword_types(annotation: object) -> dict[str, ValueType]:
    """`Unpack[SomeKeywords]` → the TypedDict's keys and their types."""
    args = typing.get_args(annotation)
    keywords = args[0] if typing.get_origin(annotation) is typing.Unpack and args else None
    hints = getattr(keywords, "__annotations__", None)
    if not isinstance(hints, dict):
        return {}
    module = sys.modules.get(getattr(keywords, "__module__", ""), None)
    module_globals = vars(module) if module is not None else {}
    out: dict[str, ValueType] = {}
    for name, hint in hints.items():
        text = hint.__forward_arg__ if isinstance(hint, typing.ForwardRef) else hint
        kind = classify(evaluate(text, module_globals))
        if kind is not None:
            out[str(name)] = kind
    return out
