"""Signatures with types for the Markdown reference, and their parameter tables.

`kinemo.docs.signatures` writes calls the way an author types them (no annotations); the
reference also shows each parameter's type, and expands `**kw: Unpack[SomeKeywords]` into
the keywords of that `TypedDict`."""

from __future__ import annotations

import importlib
import inspect
import re
import typing
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from .. import signatures
from .writer import SIGNATURE_WIDTH

_QUOTED_NAME = re.compile(r"""['"]([A-Za-z_][\w.]*)['"]""")
_WRAPPERS = re.compile(r"^(?:NotRequired|Required|ReadOnly)\[(.*)\]$")
_UNPACK = re.compile(r"^Unpack\[(\w+)\]$")
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z`(])")


@dataclass(frozen=True)
class ParameterRow:
    name: str
    type: str
    default: str
    description: str


def clean_annotation(annotation: Any, owner: str | None = None) -> str:
    """Readable annotation text: quotes removed, `Self` replaced by the owner class."""
    if annotation is inspect.Signature.empty:
        return ""
    if isinstance(annotation, str):
        text = annotation
    elif isinstance(annotation, typing.ForwardRef):
        text = annotation.__forward_arg__
    elif isinstance(annotation, type):
        text = annotation.__name__
    else:
        text = str(annotation).replace("typing.", "")
    text = text.strip()
    while len(text) >= 2 and text[0] == text[-1] and text[0] in "'\"":
        text = text[1:-1].strip()
    if "Literal" not in text:
        text = _QUOTED_NAME.sub(r"\1", text)
    if owner:
        text = re.sub(r"\bSelf\b", owner, text)
    return text


def default_text(value: Any) -> str:
    """A default value as source text, never with a memory address."""
    if value is inspect.Parameter.empty:
        return ""
    text = signatures._default_repr(value)
    if text == "<factory>" or type(value).__name__ == "_HAS_DEFAULT_FACTORY_CLASS":
        return "<factory>"
    if " at 0x" in text or text.startswith("<"):
        return type(value).__name__
    return text


def signature_variants(fn: Any) -> list[inspect.Signature]:
    """The `@overload` signatures of `fn` when it has any, otherwise its signature."""
    target = fn.__func__ if isinstance(fn, staticmethod | classmethod) else fn
    try:
        overloads = typing.get_overloads(target)
    except (AttributeError, TypeError):
        overloads = []
    variants = []
    for candidate in overloads or [target]:
        try:
            variants.append(inspect.signature(candidate))
        except (TypeError, ValueError):
            continue
    return variants


def _visible_parameters(sig: inspect.Signature, skip_first: bool) -> list[inspect.Parameter]:
    params = list(sig.parameters.values())
    if skip_first and params:
        params = params[1:]
    return [p for p in params if not p.name.startswith("_")]


def _parameter_text(p: inspect.Parameter, owner: str | None) -> str:
    prefix = {p.VAR_POSITIONAL: "*", p.VAR_KEYWORD: "**"}.get(p.kind, "")
    annotation = clean_annotation(p.annotation, owner)
    text = f"{prefix}{p.name}: {annotation}" if annotation else f"{prefix}{p.name}"
    if p.default is not p.empty:
        text += f" = {default_text(p.default)}" if annotation else f"={default_text(p.default)}"
    return text


def format_call(
    display: str, sig: inspect.Signature, skip_first: bool, owner: str | None = None, returns: bool = True
) -> str:
    """`display(a: T = 1, *, b: U) -> R`, one parameter per line when it gets long."""
    parts: list[str] = []
    keyword_marker_done = False
    positional_only_open = False
    for p in _visible_parameters(sig, skip_first):
        if p.kind is p.POSITIONAL_ONLY:
            positional_only_open = True
        elif positional_only_open:
            parts.append("/")
            positional_only_open = False
        if p.kind is p.VAR_POSITIONAL:
            keyword_marker_done = True
        if p.kind is p.KEYWORD_ONLY and not keyword_marker_done:
            parts.append("*")
            keyword_marker_done = True
        parts.append(_parameter_text(p, owner))
    if positional_only_open:
        parts.append("/")
    return_text = clean_annotation(sig.return_annotation, owner) if returns else ""
    tail = f" -> {return_text}" if return_text and return_text != "None" else ""
    one_line = f"{display}({', '.join(parts)}){tail}"
    if len(one_line) <= SIGNATURE_WIDTH or not parts:
        return one_line
    body = "".join(f"    {part},\n" for part in parts)
    return f"{display}(\n{body}){tail}"


@lru_cache(maxsize=None)
def keywords_typed_dict(name: str) -> type | None:
    """The `TypedDict` called `name` in kinemo (for `Unpack[...]`), imported on demand: keyword
    `TypedDict`s are often imported only under `TYPE_CHECKING`."""
    package_root = Path(__file__).resolve().parents[2]
    definition = re.compile(rf"^class {re.escape(name)}\b", re.MULTILINE)
    for path in sorted(package_root.rglob("*.py")):
        if not definition.search(path.read_text(encoding="utf-8")):
            continue
        relative = path.relative_to(package_root.parent).with_suffix("")
        module = importlib.import_module(".".join(relative.parts))
        candidate = getattr(module, name, None)
        if isinstance(candidate, type) and typing.is_typeddict(candidate):
            return candidate
    return None


def _typed_dict_keys(typed_dict: type) -> list[tuple[str, str]]:
    keys: dict[str, str] = {}
    for base in reversed(typed_dict.__mro__):
        for key, annotation in getattr(base, "__annotations__", {}).items():
            keys[key] = annotation
    out = []
    for key, annotation in keys.items():
        text = clean_annotation(annotation)
        while (match := _WRAPPERS.match(text)) is not None:
            text = match.group(1)
        out.append((key, text))
    return out


def describe(name: str, text: str) -> str:
    """The first sentence of `text` that names the parameter (`` `name=` `` or `` `name` ``)."""
    if not text:
        return ""
    pattern = re.compile(rf"`[^`]*\b{re.escape(name)}=|`{re.escape(name)}`")
    for sentence in _SENTENCE_END.split(" ".join(text.split())):
        if pattern.search(sentence):
            return sentence.strip()
    return ""


def parameter_rows(
    sig: inspect.Signature, skip_first: bool, owner: str | None = None, doc_text: str = ""
) -> list[ParameterRow]:
    rows: list[ParameterRow] = []
    for p in _visible_parameters(sig, skip_first):
        annotation = clean_annotation(p.annotation, owner)
        unpacked = _UNPACK.match(annotation)
        if p.kind is p.VAR_KEYWORD and unpacked is not None:
            typed_dict = keywords_typed_dict(unpacked.group(1))
            if typed_dict is not None:
                keys = ", ".join(f"`{key}: {key_type}`" for key, key_type in _typed_dict_keys(typed_dict))
                description = f"Keyword arguments (`{unpacked.group(1)}`): {keys}."
                rows.append(ParameterRow("**" + p.name, annotation, "variadic", description))
                continue
        prefix = {p.VAR_POSITIONAL: "*", p.VAR_KEYWORD: "**"}.get(p.kind, "")
        if p.default is not p.empty:
            default = default_text(p.default)
        elif p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            default = "variadic"
        else:
            default = "required"
        rows.append(ParameterRow(prefix + p.name, annotation, default, describe(p.name, doc_text)))
    return rows


def property_type(prop: property, owner: str | None = None) -> str:
    getter = prop.fget
    if getter is None:
        return ""
    try:
        return clean_annotation(inspect.signature(getter).return_annotation, owner)
    except (TypeError, ValueError):
        return ""
