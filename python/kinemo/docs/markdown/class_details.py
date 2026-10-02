"""Tables that only classes have: props (from `PROPS`), instance attributes, class
constants, namespace members and the "inherited from" lines."""

from __future__ import annotations

import inspect
from typing import Any

from . import symbols as model
from .typed_signatures import clean_annotation, default_text, format_call, signature_variants
from .writer import code, link, table


def reference_link(name: str, text: str | None = None, page: str | None = None) -> str:
    """`[`k.draw`](verbs.md#k-draw)`, relative to `page`; plain code when undocumented."""
    target = model.target_of(name)
    label = code(text or name)
    if target is None:
        return label
    file, anchor = target
    return link(label, f"#{anchor}" if file == page else f"{file}#{anchor}")


# ---- props -----------------------------------------------------------------------------------

def _prop_default(value: Any) -> str:
    from ...theme.tokens import ThemeToken
    from ...values.color import Color

    if isinstance(value, ThemeToken):
        return f"theme.{value.name}"
    if isinstance(value, Color):
        return value.to_hex()
    if callable(value) and getattr(value, "__name__", "<lambda>") == "<lambda>":
        return "from the theme"
    if callable(value):
        return f"theme.{value.__name__}"
    return default_text(value)


def _own_props(cls: type) -> dict[str, Any]:
    own, _ = model._own_bases(cls)
    merged: dict[str, Any] = {}
    for base in reversed(own):
        if "PROPS" in base.__dict__:
            merged.update(base.__dict__["PROPS"])
    return merged


def props_section(cls: type, page: str) -> list[str]:
    """The props table of an object class and the line naming the props it inherits."""
    if not hasattr(cls, "_all_props"):
        return []
    own = _own_props(cls)
    rows = [(code(name), spec.kind, code(_prop_default(spec.default)), spec.lerp) for name, spec in own.items()]
    out: list[str] = []
    if rows:
        out += ["**Props** (animatable with `.to()`, settable with `.set()` or in the constructor):", ""]
        out += table(("Prop", "Kind", "Default", "Interpolation"), rows)
    public = model.public_classes()
    seen = set(own)
    for base in cls.__mro__[1:]:
        if base not in public or not hasattr(base, "_all_props"):
            continue
        names = [n for n in _own_props(base) if n not in seen]
        seen.update(names)
        if names:
            shown = ", ".join(code(n) for n in names)
            out += [f"Props inherited from {reference_link('k.' + public[base], page=page)}: {shown}.", ""]
    return out


def derived_props_section(cls: type) -> list[str]:
    """`Node` only: the read-only, layout-derived props every object has."""
    from ...objects.node import Node
    from ...objects.props import DERIVED

    if cls is not Node:
        return []
    names = ", ".join(code(f"obj.{name}") for name in DERIVED)
    return [
        f"**Layout-derived props** (read-only, reactive, in the parent's coordinates): {names}; "
        "`obj.world.position` and `obj.world.center` give global coordinates.",
        "",
    ]


# ---- attributes, constants, namespaces ---------------------------------------------------------

def attributes_section(cls: type, variable: str) -> list[str]:
    rows = [(code(f"{variable}.{a.name}"), a.type, a.description) for a in model.class_attributes(cls)]
    if not rows:
        return []
    return ["**Attributes:**", "", *table(("Attribute", "Type", "Description"), rows)]


def constants_section(cls: type, display: str) -> list[str]:
    rows = [(code(f"{display}.{name}"), code(default_text(value))) for name, value in model.class_constants(cls)]
    if not rows:
        return []
    return ["**Values:**", "", *table(("Name", "Value"), rows)]


def namespace_section(obj: Any, display: str) -> list[str]:
    """Members of a namespace object (`k.ease`, `k.themes`): name, signature or type, summary."""
    rows = []
    for name, value in vars(type(obj)).items():
        if name.startswith("_"):
            continue
        if isinstance(value, staticmethod):
            variants = signature_variants(value)
            shown = format_call(f"{display}.{name}", variants[0], False) if variants else f"{display}.{name}"
            rows.append((code(shown), model.first_sentence(model.own_docstring(value))))
        elif not callable(value) or not inspect.isroutine(value):
            rows.append((code(f"{display}.{name}"), type(value).__name__))
    if not rows:
        return []
    return ["**Members:**", "", *table(("Member", "Description or type"), rows)]


def inherited_section(symbol: model.Symbol, page: str) -> list[str]:
    out = []
    for base, names in symbol.inherited:
        shown = ", ".join(reference_link(f"{base}.{n}", n, page) for n in names)
        out.append(f"Inherited from {reference_link(_qualified(base), page=page)}: {shown}.")
    return [*out, ""] if out else []


def _qualified(name: str) -> str:
    import kinemo

    return f"k.{name}" if name in kinemo.__all__ else name


def value_annotation(name: str, obj: Any) -> str:
    import kinemo

    annotation = getattr(kinemo, "__annotations__", {}).get(name)
    return clean_annotation(annotation) if annotation else type(obj).__name__
