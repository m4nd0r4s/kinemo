"""Registry of documented symbols and lookup by any name an author might type.

To document a new symbol, add one `DocEntry` to the module of its area in
`kinemo/docs/examples/`. Entries whose symbol does not exist in this version of kinemo
(e.g. written ahead of an implementation) are skipped automatically.
"""

from __future__ import annotations

import difflib
import inspect
from dataclasses import dataclass, field
from functools import lru_cache

import kinemo

from . import signatures
from .entry import AREAS, DocEntry
from .examples import (
    charts,
    components,
    composition,
    events,
    layout,
    mass,
    media,
    native,
    objects,
    output,
    params,
    reactive,
    scene,
    text,
    verbs,
)

EXAMPLE_MODULES = (
    scene, objects, media, mass, verbs, composition, text, layout, charts, reactive, native, events, components, params, output,
)

#: Public names documented through the entry of what an author actually calls.
DOCUMENTED_BY: dict[str, str] = {
    "Scene": "Scene.play",
    "SceneDef": "k.scene",
    "TimeSpan": "Scene.start",
    "Animation": "Animation.with_",
    "Node": "Node.to",
    "Signal": "k.signal",
    "ListSignal": "k.list",
    "Expr": "Expr.map",
    "Trail": "k.trace",
    "EventSource": "EventSource.on",
    "Context": "k.context",
    "Theme": "k.themes",
    "Color": "k.rgb",
    "Vec": "k.vec",
    "Movie": "k.movie",
}

#: Public names that are not part of what a scene author writes, and why.
UNDOCUMENTED_INTERNAL: dict[str, str] = {
    "IR_VERSION": "IR format version, for tools",
    "Val": "type alias T | Signal[T] | Callable[[], T], for annotations only",
    "Diagnostic": "diagnostics are read with `kinemo check` and `kinemo explain <code>`",
    "KinemoError": "exception that carries a Diagnostic; see `kinemo explain <code>`",
}


@dataclass(frozen=True)
class Lookup:
    entry: DocEntry | None
    suggestions: list[str] = field(default_factory=list)
    #: The name the query resolved through (`k.Signal` → documented by `k.signal`).
    via: str | None = None


@lru_cache(maxsize=1)
def entries() -> tuple[DocEntry, ...]:
    """Every documented symbol available in this version, in area order."""
    found = [e for module in EXAMPLE_MODULES for e in module.ENTRIES if signatures.exists(e.symbol)]
    return tuple(sorted(found, key=lambda e: AREAS.index(e.area)))


def by_area() -> dict[str, list[DocEntry]]:
    out: dict[str, list[DocEntry]] = {area: [] for area in AREAS}
    for e in entries():
        out[e.area].append(e)
    return {area: items for area, items in out.items() if items}


def entry(symbol: str) -> DocEntry | None:
    return _index().get(symbol)


@lru_cache(maxsize=1)
def _index() -> dict[str, DocEntry]:
    """Every name that answers with an entry: canonical, display form and aliases."""
    index: dict[str, DocEntry] = {}
    for e in entries():
        for name in (e.symbol, signatures.display_name(e.symbol), *e.aliases):
            index.setdefault(name, e)
            index.setdefault(signatures.display_name(name), e)
    for name, target in DOCUMENTED_BY.items():
        if target in index:
            index.setdefault(f"k.{name}", index[target])
    return index


def documented_names() -> set[str]:
    """`k.*` names (without the prefix) covered by an entry, an alias or a redirect."""
    return {name[2:] for name in _index() if name.startswith("k.") and "." not in name[2:]}


def _candidates(query: str) -> list[str]:
    """Spellings of `query` to try against the index, most literal first."""
    q = query.strip().lstrip("@").removesuffix("()").removesuffix(":").strip()
    if q.startswith("with "):
        q = q[5:].strip()
    if q.startswith("kinemo."):
        q = "k." + q[len("kinemo."):]
    q = q.split("(", 1)[0]
    out = [q]
    head, _, rest = q.partition(".")
    variables = {v: owner for owner, v in signatures.OWNER_VARIABLES.items()}
    if not rest:
        out.append(f"k.{q}")
    elif head == "k" and "." in rest:
        owner, _, member = rest.partition(".")  # k.Axes.plot → Axes.plot, else k.Axes
        out += [f"{owner}.{member}", f"k.{owner}"]
    elif head in variables:
        out.append(f"{variables[head]}.{rest}")
    elif head[:1].isupper():
        out.append(f"k.{head}")  # Polygon.regular → k.Polygon
    return out


def _inherited(symbol: str, index: dict[str, DocEntry]) -> DocEntry | None:
    """`Row.swap` → `Group.swap`, `Circle.to` → `Node.to` (documented on a base class)."""
    owner, _, member = symbol.partition(".")
    if owner == "k" or not member:
        return None
    cls = signatures.owner_type(owner)
    if not inspect.isclass(cls):
        return None
    for base in cls.__mro__:
        hit = index.get(f"{base.__name__}.{member}")
        if hit is not None:
            return hit
    return None


def lookup(query: str) -> Lookup:
    index = _index()
    candidates = _candidates(query)
    for name in candidates:
        hit = index.get(name) or _inherited(name, index)
        if hit is not None:
            return Lookup(hit, via=name)
    member = candidates[0].rsplit(".", 1)[-1]
    by_member = {e.symbol: e for n, e in index.items() if n.rsplit(".", 1)[-1] == member}
    if len(by_member) == 1:
        return Lookup(next(iter(by_member.values())), via=candidates[0])
    lowered = {n.lower(): e for n, e in index.items()}
    for name in candidates:
        if name.lower() in lowered:
            return Lookup(lowered[name.lower()], via=name)
    return Lookup(None, suggestions(query))


def suggestions(query: str, limit: int = 5) -> list[str]:
    names = sorted({signatures.display_name(e.symbol) for e in entries()})
    names += sorted(n for n in _index() if n not in names)
    tried = _candidates(query)
    out: list[str] = []
    for q in tried:
        for match in difflib.get_close_matches(q, names, n=limit, cutoff=0.6):
            if match not in out:
                out.append(match)
    needle = tried[0].rsplit(".", 1)[-1].lower()
    if len(needle) >= 3:
        out += [n for n in names if needle in n.lower() and n not in out]
    canonical = []
    for name in out:
        shown = signatures.display_name(_index()[name].symbol) if name in _index() else name
        if shown not in canonical:
            canonical.append(shown)
    return canonical[:limit]


def coverage_gaps() -> list[str]:
    """Names in `kinemo.__all__` neither documented nor listed as internal."""
    covered = documented_names() | set(UNDOCUMENTED_INTERNAL)
    return sorted(n for n in kinemo.__all__ if n not in covered)
