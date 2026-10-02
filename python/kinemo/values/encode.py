"""Encoding of Python values into IR values (externally tagged, full names)."""

from __future__ import annotations

from typing import Any

from ..theme.tokens import ThemeToken
from .color import Color, parse as parse_color

Kind = str  # "float" | "int" | "bool" | "str" | "vec2" | "color" | "list" | "points" | "object" | "objects"


def resolve(value: Any) -> Any:
    return value.resolve() if isinstance(value, ThemeToken) else value


def encode(value: Any, kind: Kind) -> dict[str, Any] | str:
    value = resolve(value)
    if value is None:
        return "None"
    if kind == "float":
        return {"Float": float(value)}
    if kind == "int":
        return {"Int": int(value)}
    if kind == "bool":
        return {"Bool": bool(value)}
    if kind == "str":
        return {"Str": str(value)}
    if kind == "vec2":
        x, y = value
        return {"Vec2": [float(x), float(y)]}
    if kind == "color":
        return {"Color": parse_color(value).components()}
    if kind == "points":
        return {"List": [{"Vec2": [float(x), float(y)]} for x, y in value]}
    if kind == "segments":
        return {"List": [{"List": [{"Vec2": [float(x), float(y)]} for x, y in seg]} for seg in value]}
    if kind == "floats":
        return {"List": [{"Float": float(v)} for v in value]}
    if kind == "object":
        return {"Object": value._id}
    if kind == "objects":
        return {"List": [{"Object": o._id} for o in value]}
    if kind == "list":
        return {"List": [encode(v, infer_kind(v)) for v in value]}
    raise TypeError(f"unknown value kind {kind}")


def infer_kind(value: Any) -> Kind:
    value = resolve(value)
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int | float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, Color):
        return "color"
    if isinstance(value, tuple) and len(value) == 2 and all(isinstance(v, int | float) for v in value):
        return "vec2"
    if isinstance(value, list | tuple):
        return "list"
    if hasattr(value, "_id"):
        return "object"
    raise TypeError(f"unsupported value {value!r}")


def decode(v: Any) -> Any:
    """IR value (as parsed JSON) → Python value."""
    if v == "None" or v is None:
        return None
    (tag, payload), = v.items()
    if tag in ("Float", "Int", "Bool", "Str", "Object"):
        return payload
    if tag == "Vec2":
        from .vec import Vec

        return Vec(*payload)
    if tag == "Color":
        return Color(*payload)
    if tag == "List":
        return [decode(x) for x in payload]
    raise ValueError(f"unknown IR value {v!r}")
