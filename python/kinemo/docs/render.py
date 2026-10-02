"""Terminal text for `kinemo docs`: one symbol, the list of symbols, or "not found"."""

from __future__ import annotations

import textwrap
from typing import Any

from . import catalog, signatures
from .entry import DocEntry

WIDTH = 88


def entry_signature(entry: DocEntry) -> str:
    return entry.signature or signatures.signature(entry.symbol)


def related_names(entry: DocEntry) -> list[str]:
    """Display names of related symbols that exist in this version."""
    out = []
    for symbol in entry.related:
        hit = catalog.entry(symbol)
        if hit is not None:
            out.append(signatures.display_name(hit.symbol))
    return out


def _wrap(text: str, indent: str = "") -> str:
    return textwrap.fill(text, WIDTH, initial_indent=indent, subsequent_indent=indent)


def render_entry(entry: DocEntry) -> str:
    lines = [entry_signature(entry), "", _wrap(entry.summary), "", "example:"]
    lines += ["    " + line if line else "" for line in entry.example.rstrip("\n").splitlines()]
    methods = signatures.own_methods(entry.symbol)
    if methods:
        lines += ["", "methods:"]
        lines += [f"    {sig}" for _, sig in methods]
    related = related_names(entry)
    if related:
        lines += ["", "see also: " + ", ".join(related)]
    return "\n".join(lines)


def render_index() -> str:
    lines = ["kinemo docs <symbol> — documented symbols:", ""]
    for area, items in catalog.by_area().items():
        names = ", ".join(signatures.display_name(e.symbol) for e in items)
        lines.append(textwrap.fill(f"{area}: {names}", WIDTH, subsequent_indent="    "))
    return "\n".join(lines)


def render_not_found(query: str, suggestions: list[str]) -> str:
    lines = [f"kinemo: '{query}' is not documented."]
    if suggestions:
        lines.append("did you mean: " + ", ".join(suggestions) + "?")
    lines.append("full list: kinemo docs")
    return "\n".join(lines)


def entry_json(entry: DocEntry) -> dict[str, Any]:
    return {
        "symbol": signatures.display_name(entry.symbol),
        "canonical": entry.symbol,
        "area": entry.area,
        "signature": entry_signature(entry),
        "summary": entry.summary,
        "example": entry.example,
        "methods": [sig for _, sig in signatures.own_methods(entry.symbol)],
        "related": related_names(entry),
    }
