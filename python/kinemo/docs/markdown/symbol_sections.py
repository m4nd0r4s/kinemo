"""One Markdown section per documented symbol and per class member: heading with a stable
anchor, signature with types, summary and docstring, parameters, props, example, links."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from .. import catalog, signatures
from ..entry import DocEntry
from . import class_details as details
from . import symbols as model
from .typed_signatures import ParameterRow, default_text, format_call, parameter_rows, property_type, signature_variants
from .writer import code, code_block, heading, paragraphs, table

IMPORT_LINES = ("import kinemo as k", "")


@dataclass
class PageState:
    """What a page already showed, so a repeated example becomes a link."""

    file: str
    examples: dict[str, tuple[str, str]] = field(default_factory=dict)


@dataclass(frozen=True)
class CallShape:
    signatures: list[inspect.Signature]
    skip_first: bool
    display: str
    owner: str | None = None
    returns: bool = True


def _class_shape(cls: type, display: str) -> CallShape | None:
    init = next((c.__dict__["__init__"] for c in cls.__mro__ if "__init__" in c.__dict__), None)
    variants = signature_variants(init) if init is not None and init is not object.__init__ else []
    if len(variants) > 1:
        return CallShape(variants, True, display, cls.__name__, returns=False)
    try:
        sig = inspect.signature(cls)
    except (TypeError, ValueError):
        return None
    if not sig.parameters and model.class_constants(cls):
        return None  # a namespace of constants (`k.lerp`), never instantiated
    return CallShape([sig], False, display, cls.__name__, returns=False)


def _value_line(symbol: model.Symbol) -> str:
    from ...reactive.expr import Expr
    from ...values.color import Color

    obj, name = symbol.obj, symbol.qualified
    annotation = details.value_annotation(symbol.name, obj)
    if isinstance(obj, Color):
        return f'{name}: Color = "{obj.to_hex()}"'
    if isinstance(obj, Expr):
        return f"{name}: {annotation}  # read-only signal"
    if symbol.kind == "namespace":
        return f"{name}  # namespace"
    if symbol.kind == "class":
        return f"{name}  # namespace of constants"
    if symbol.kind == "type alias":
        reason = catalog.UNDOCUMENTED_INTERNAL.get(symbol.name, "")
        alias = reason.removeprefix("type alias ").rsplit(", ", 1)[0]
        return f"{name}[T] = {alias}" if alias else name
    shown = default_text(obj)
    if shown and shown != type(obj).__name__:
        return f"{name}: {annotation} = {shown}"
    return f"{name}: {annotation}"


def symbol_signature_block(symbol: model.Symbol) -> tuple[list[str], CallShape | None]:
    """The signature code block of a top-level symbol and the shape its parameters come from."""
    obj, display = symbol.obj, symbol.qualified
    shape: CallShape | None = None
    if symbol.kind == "class":
        shape = _class_shape(obj, display)
    elif symbol.kind == "function":
        target = obj if inspect.isroutine(obj) else type(obj).__call__
        variants = signature_variants(target)
        shape = CallShape(variants, not inspect.isroutine(obj), display) if variants else None
    if shape is None or not shape.signatures:
        return code_block(_value_line(symbol)), None
    calls = [format_call(display, s, shape.skip_first, shape.owner, shape.returns) for s in shape.signatures]
    return code_block("\n".join(calls)), shape


def member_signature_block(member: model.Member) -> tuple[list[str], CallShape | None]:
    raw, owner = member.raw, member.owner
    if member.kind == "property":
        annotation = property_type(raw, owner)
        display = signatures.display_name(member.symbol)
        line = f"{display}: {annotation}" if annotation else display
        suffix = "  # read-only" if raw.fset is None else ""
        return code_block(line + suffix), None
    if member.kind == "method":
        display = signatures.display_name(member.symbol)
    else:
        display = f"{details._qualified(owner)}.{member.name}"
    variants = signature_variants(raw)
    if not variants:
        return code_block(display), None
    shape = CallShape(variants, member.kind != "staticmethod", display, owner)
    calls = [format_call(display, s, shape.skip_first, owner) for s in variants]
    return code_block("\n".join(calls)), shape


def _default_cell(default: str) -> str:
    if default in ("required", "variadic") or default.startswith("keyword"):
        return default
    return code(default)


def parameters_section(shape: CallShape | None, doc_text: str, notes: dict[str, str] | None = None) -> list[str]:
    """The parameters table; `notes` gives descriptions the docs do not contain."""
    if shape is None:
        return []
    widest = max(shape.signatures, key=lambda s: len(s.parameters))
    rows: list[ParameterRow] = parameter_rows(widest, shape.skip_first, shape.owner, doc_text)
    if not rows:
        return []
    notes = notes or {}
    cells = [
        (code(r.name), code(r.type) if r.type else "", _default_cell(r.default), r.description or notes.get(r.name, ""))
        for r in rows
    ]
    return ["**Parameters:**", "", *table(("Name", "Type", "Default", "Description"), cells)]


def _example_body(entry: DocEntry) -> str:
    lines = entry.example.rstrip("\n").splitlines()
    while lines and lines[0] in IMPORT_LINES:
        lines.pop(0)
    return "\n".join(lines)


def example_section(entry: DocEntry, anchor: str, display: str, state: PageState) -> list[str]:
    seen = state.examples.get(entry.example)
    if seen is not None:
        return [f"**Example:** same as [{code(seen[1])}](#{seen[0]}).", ""]
    state.examples[entry.example] = (anchor, display)
    return ["**Example:**", "", *code_block(_example_body(entry))]


def related_section(entry: DocEntry | None, state: PageState) -> list[str]:
    names = list(entry.related) if entry is not None else []
    links: list[str] = []
    for name in names:
        hit = catalog.entry(name)
        shown = signatures.display_name(hit.symbol) if hit is not None else name
        rendered = details.reference_link(name, shown, state.file)
        if rendered not in links:
            links.append(rendered)
    return [f"**See also:** {', '.join(links)}.", ""] if links else []


def description_section(entry: DocEntry | None, docstring: str) -> list[str]:
    """The catalog summary when there is one (it is the curated text), else the docstring."""
    if entry is not None:
        return paragraphs(entry.summary)
    return paragraphs(docstring) if docstring else []


def _usage_line(entry: DocEntry | None) -> list[str]:
    if entry is None or not entry.signature:
        return []
    return [f"Written as: {code(entry.signature)}", ""]


def member_section(member: model.Member, state: PageState) -> list[str]:
    entry = catalog.entry(member.symbol)
    entry = entry if entry is not None and entry.symbol == member.symbol else None
    docstring = model.own_docstring(member.raw)
    title = f"{code(details._qualified(member.owner) + '.' + member.name)} *({member.kind})*"
    out = heading(4, title, member.anchor)
    block, shape = member_signature_block(member)
    out += block + _usage_line(entry) + description_section(entry, docstring)
    out += parameters_section(shape, (entry.summary if entry else "") + " " + docstring)
    if entry is not None:
        out += example_section(entry, member.anchor, signatures.display_name(member.symbol), state)
        out += related_section(entry, state)
    return out


def _documented_by_line(symbol: model.Symbol, state: PageState) -> list[str]:
    entry = symbol.documented_by
    if symbol.entry is not None:
        return []
    if entry is None and symbol.name in catalog.UNDOCUMENTED_INTERNAL and not model.own_docstring(symbol.obj):
        return [model.summary_of(symbol), ""]
    if entry is None:
        return []
    shown = details.reference_link(entry.symbol, signatures.display_name(entry.symbol), state.file)
    line = f"Documented together with {shown}."
    if not model.own_docstring(symbol.obj):
        line += " " + " ".join(entry.summary.split())
    return [line, ""]


def symbol_section(symbol: model.Symbol, state: PageState) -> list[str]:
    obj, entry = symbol.obj, symbol.entry
    docstring = model.own_docstring(obj) if symbol.kind in ("class", "function") else ""
    if symbol.kind == "namespace":
        docstring = model.own_docstring(obj)
    out = heading(3, f"{code(symbol.qualified)} *({symbol.kind})*", symbol.anchor)
    block, shape = symbol_signature_block(symbol)
    out += block + _usage_line(entry) + description_section(entry, docstring) + _documented_by_line(symbol, state)
    out += parameters_section(shape, (entry.summary if entry else "") + " " + docstring, _parameter_notes(symbol))
    if inspect.isclass(obj):
        variable = signatures.OWNER_VARIABLES.get(symbol.name, symbol.name.lower())
        out += details.props_section(obj, state.file) + details.derived_props_section(obj)
        out += details.attributes_section(obj, variable) + details.constants_section(obj, symbol.qualified)
    elif symbol.kind == "namespace":
        out += details.namespace_section(obj, symbol.qualified)
    if entry is not None:
        out += example_section(entry, symbol.anchor, signatures.display_name(entry.symbol), state)
        out += related_section(entry, state)
    if symbol.members:
        out += ["**Members:**", ""]
        out += [f"- {details.reference_link(m.symbol, m.name, state.file)}: {_member_summary(m)}" for m in symbol.members]
        out.append("")
    out += details.inherited_section(symbol, state.file)
    for member in symbol.members:
        out += member_section(member, state)
    return out


def _parameter_notes(symbol: model.Symbol) -> dict[str, str]:
    if symbol.qualified == "k.scene":
        from .configuration_page import SCENE_OPTIONS

        return SCENE_OPTIONS
    return {}


def _member_summary(member: model.Member) -> str:
    entry = catalog.entry(member.symbol)
    if entry is not None and entry.symbol == member.symbol:
        return model.first_sentence(entry.summary)
    summary = model.first_sentence(model.own_docstring(member.raw))
    if summary:
        return summary
    if member.kind == "property":
        annotation = property_type(member.raw, member.owner)
        return f"property ({code(annotation)})." if annotation else "property."
    return f"{member.kind}."

