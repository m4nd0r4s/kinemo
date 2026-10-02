"""What the Markdown reference documents: every name in `kinemo.__all__`, the public
members of every public class, and the area page each one lives on.

Areas come from the catalog (`kinemo.docs.entry.AREAS`): a name is documented on the page
of the catalog entry it resolves to (`k.cos` → `k.sin`, `k.Scene` → `Scene.play`). Names
with no entry go to an extra "Tooling and types" page."""

from __future__ import annotations

import ast
import dataclasses
import inspect
import textwrap
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import kinemo

from .. import catalog, signatures
from ..entry import AREAS, DocEntry
from .writer import slug

#: Area for public names without a catalog entry (`k.Diagnostic`, `k.Val`, ...).
TOOLING_AREA = "Tooling and types"

#: Class attributes that describe the implementation, not the API.
_SKIPPED_ATTRIBUTES = {"kind", "is_container", "PROPS", "STYLE_BINDINGS"}


def page_file(area: str) -> str:
    return slug(area) + ".md"


@dataclass(frozen=True)
class Member:
    """A public method, property, classmethod or staticmethod of a documented class."""

    owner: str
    name: str
    kind: str
    raw: Any
    anchor: str

    @property
    def symbol(self) -> str:
        return f"{self.owner}.{self.name}"


@dataclass(frozen=True)
class Attribute:
    name: str
    type: str
    description: str


@dataclass
class Symbol:
    """One documented name: `k.Circle`, `k.morph`, `k.pi`, or a non-exported type (`Plot`)."""

    name: str
    qualified: str
    obj: Any
    kind: str
    area: str
    anchor: str
    #: The catalog entry whose symbol is exactly this name.
    entry: DocEntry | None = None
    #: The entry this name resolves through when it has none of its own (`k.cos` → `k.sin`).
    documented_by: DocEntry | None = None
    members: list[Member] = field(default_factory=list)
    #: `[(public base, [member names])]` inherited without being redefined.
    inherited: list[tuple[str, list[str]]] = field(default_factory=list)

    @property
    def page(self) -> str:
        return page_file(self.area)


def _kind(obj: Any) -> str:
    from ...reactive.expr import Expr
    from ...values.color import Color

    if inspect.isclass(obj):
        return "class"
    if inspect.isfunction(obj) or inspect.isbuiltin(obj):
        return "function"
    if isinstance(obj, Color | float | int | str | Expr):
        return "constant"
    if type(obj).__module__ == "typing" or "GenericAlias" in type(obj).__name__:
        return "type alias"
    if callable(obj):
        return "function"
    return "namespace" if type(obj).__name__.startswith("_") else "value"


@lru_cache(maxsize=1)
def public_classes() -> dict[type, str]:
    """Every documented class and the name it is documented under."""
    out: dict[type, str] = {}
    for name in kinemo.__all__:
        obj = getattr(kinemo, name)
        if inspect.isclass(obj):
            out.setdefault(obj, name)
    for name, cls in signatures._extra_types().items():
        out.setdefault(cls, name)
    return out


def _member_kind(value: Any) -> str | None:
    if isinstance(value, property):
        return "property"
    if isinstance(value, classmethod):
        return "classmethod"
    if isinstance(value, staticmethod):
        return "staticmethod"
    if inspect.isfunction(value):
        return "method"
    return None


def _own_bases(cls: type) -> tuple[list[type], list[type]]:
    """(the class plus its non-public bases, its nearest public bases) in MRO order."""
    public = public_classes()
    own: list[type] = []
    inherited: list[type] = []
    for base in cls.__mro__:
        if base is object or base.__module__ in ("typing", "builtins", "abc"):
            continue
        if base is cls:
            own.append(base)
        elif base in public:
            inherited.append(base)
        elif not any(issubclass(p, base) for p in inherited):
            own.append(base)
    return own, inherited


def _own_member_names(cls: type) -> list[tuple[str, str, Any]]:
    """(name, kind, raw) of the public members `cls` defines itself or through private bases."""
    own, _ = _own_bases(cls)
    out: dict[str, tuple[str, str, Any]] = {}
    for base in own:
        for name, value in base.__dict__.items():
            kind = _member_kind(value)
            if not name.startswith("_") and kind is not None and name not in out:
                out[name] = (name, kind, value)
    return list(out.values())


def class_members(cls: type, owner: str) -> tuple[list[Member], list[tuple[str, list[str]]]]:
    members = [Member(owner, name, kind, raw, f"{slug(owner)}-{slug(name)}") for name, kind, raw in _own_member_names(cls)]
    public = public_classes()
    seen = {m.name for m in members}
    inherited: list[tuple[str, list[str]]] = []
    for base in cls.__mro__[1:]:
        if base not in public:
            continue
        names = [name for name, _, _ in _own_member_names(base) if name not in seen]
        seen.update(names)
        if names:
            inherited.append((public[base], names))
    return members, inherited


def class_attributes(cls: type) -> list[Attribute]:
    """Public instance attributes assigned in `__init__` (with their `#:` comments)."""
    own, _ = _own_bases(cls)
    init = next((b.__dict__["__init__"] for b in own if "__init__" in b.__dict__), None)
    if init is None:
        return []
    try:
        source = textwrap.dedent(inspect.getsource(init))
    except (OSError, TypeError):
        return []
    lines = source.splitlines()
    out: dict[str, Attribute] = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        for target in targets:
            if not (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self"):
                continue
            if target.attr.startswith("_") or target.attr in out:
                continue
            annotation = ast.unparse(node.annotation) if isinstance(node, ast.AnnAssign) else ""
            out[target.attr] = Attribute(target.attr, annotation, _comment_above(lines, node.lineno - 1))
    return sorted(out.values(), key=lambda a: a.name)


def _comment_above(lines: list[str], index: int) -> str:
    comments: list[str] = []
    while index > 0 and lines[index - 1].strip().startswith("#:"):
        index -= 1
        comments.insert(0, lines[index].strip()[2:].strip())
    return " ".join(comments)


def class_constants(cls: type) -> list[tuple[str, Any]]:
    """Public simple class attributes that are not dataclass or named-tuple fields."""
    fields = {f.name for f in dataclasses.fields(cls)} if dataclasses.is_dataclass(cls) else set()
    fields |= set(getattr(cls, "_fields", ()))
    out = []
    for name, value in cls.__dict__.items():
        if name.startswith("_") or name in _SKIPPED_ATTRIBUTES or name in fields:
            continue
        if isinstance(value, str | int | float | bool):
            out.append((name, value))
    return out


def _resolving_entry(name: str) -> DocEntry | None:
    return catalog.lookup(f"k.{name}").entry


def _class_anchor(name: str) -> str:
    lowered = {n.lower() for n in kinemo.__all__ if n != name}
    base = "k-" + slug(name)
    if name[:1].isupper() and name.lower() in lowered:
        return base + "-class"
    return base


def _make_symbol(name: str, qualified: str, obj: Any, area: str, anchor: str) -> Symbol:
    symbol = Symbol(name, qualified, obj, _kind(obj), area, anchor)
    direct = catalog.entry(qualified)
    symbol.entry = direct if direct is not None and direct.symbol == qualified else None
    if symbol.entry is None and qualified.startswith("k."):
        symbol.documented_by = _resolving_entry(name)
    if inspect.isclass(obj):
        symbol.members, symbol.inherited = class_members(obj, name)
    return symbol


@lru_cache(maxsize=1)
def symbols_by_area() -> dict[str, list[Symbol]]:
    """Every documented symbol, grouped by area in page order."""
    remaining = list(kinemo.__all__)
    extra = dict(signatures._extra_types())
    out: dict[str, list[Symbol]] = {area: [] for area in (*AREAS, TOOLING_AREA)}
    placed: set[str] = set()

    def place(name: str, area: str) -> None:
        if name in placed:
            return
        placed.add(name)
        if name in extra:
            out[area].append(_make_symbol(name, name, extra[name], area, slug(name)))
        else:
            out[area].append(_make_symbol(name, f"k.{name}", getattr(kinemo, name), area, _class_anchor(name)))

    resolved = {name: _resolving_entry(name) for name in remaining}
    for entry in catalog.entries():
        if entry.symbol.startswith("k."):
            place(entry.symbol[2:], entry.area)
        owner = entry.symbol.partition(".")[0]
        if owner in extra:
            place(owner, entry.area)
        followers = sorted((n for n, e in resolved.items() if e is entry), key=lambda n: (n.lower(), n))
        for name in followers:
            place(name, entry.area)
    for name in sorted(remaining, key=lambda n: (n.lower(), n)):
        place(name, TOOLING_AREA)
    return {area: items for area, items in out.items() if items}


def all_symbols() -> list[Symbol]:
    return [symbol for items in symbols_by_area().values() for symbol in items]


@lru_cache(maxsize=1)
def registry() -> dict[str, tuple[str, str]]:
    """`{name: (page file, anchor)}` for symbols and members, by canonical and display name."""
    out: dict[str, tuple[str, str]] = {}
    for symbol in all_symbols():
        out.setdefault(symbol.qualified, (symbol.page, symbol.anchor))
        for member in symbol.members:
            target = (symbol.page, member.anchor)
            out.setdefault(member.symbol, target)
            out.setdefault(signatures.display_name(member.symbol), target)
    return out


def target_of(name: str) -> tuple[str, str] | None:
    """Where `name` (`k.draw`, `Scene.play`, `Row.swap`, `s.play`) is documented."""
    table = registry()
    if name in table:
        return table[name]
    owner, _, member = name.partition(".")
    cls = signatures.owner_type(owner)
    if inspect.isclass(cls) and member:
        for base in cls.__mro__:
            hit = table.get(f"{public_classes().get(base, base.__name__)}.{member}")
            if hit is not None:
                return hit
    found = catalog.lookup(name).entry
    if found is not None and found.symbol in table:
        return table[found.symbol]
    return None


def first_sentence(text: str) -> str:
    from .typed_signatures import _SENTENCE_END

    flat = " ".join(text.split())
    return _SENTENCE_END.split(flat, 1)[0] if flat else ""


def own_docstring(obj: Any) -> str:
    """The docstring written on `obj` itself (a class's inherited docstring does not count)."""
    if isinstance(obj, staticmethod | classmethod):
        obj = obj.__func__
    if isinstance(obj, property):
        obj = obj.fget
    if inspect.isclass(obj):
        doc = obj.__dict__.get("__doc__")
        if doc and dataclasses.is_dataclass(obj) and doc.startswith(f"{obj.__name__}("):
            return ""
        return inspect.cleandoc(doc) if isinstance(doc, str) else ""
    if inspect.isfunction(obj) or inspect.ismethod(obj) or inspect.isbuiltin(obj):
        return inspect.getdoc(obj) or ""
    if type(obj).__module__ in ("typing", "types", "builtins"):
        # A typing construct (`Val`, a Union since Python 3.14) carries its class's docstring,
        # which describes the construct, not this symbol.
        return ""
    doc = type(obj).__dict__.get("__doc__")
    if not isinstance(doc, str) or doc.startswith(f"{type(obj).__name__}("):
        return ""
    return inspect.cleandoc(doc)


def summary_of(symbol: Symbol) -> str:
    """One line for the index: the catalog summary, else the docstring, else the redirect."""
    if symbol.entry is not None:
        return first_sentence(symbol.entry.summary)
    doc = own_docstring(symbol.obj) if symbol.kind in ("class", "function", "namespace") else ""
    if doc:
        return first_sentence(doc)
    reason = catalog.UNDOCUMENTED_INTERNAL.get(symbol.name)
    if reason:
        return reason[:1].upper() + reason[1:] + "."
    if symbol.documented_by is not None:
        return first_sentence(symbol.documented_by.summary)
    return ""
