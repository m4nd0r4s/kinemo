"""Offline documentation: the catalog of documented symbols with canonical examples,
`kinemo docs <symbol>` rendering and `llms.txt` generation.

`docs_for(symbol)` is the single-symbol entry point for tools (the MCP `docs` tool):
it returns a JSON-ready dict or raises `SymbolNotDocumented` with suggestions.
"""

from __future__ import annotations

from typing import Any

from .catalog import DOCUMENTED_BY, UNDOCUMENTED_INTERNAL, by_area, coverage_gaps, entries, entry
from .entry import AREAS, DocEntry


class SymbolNotDocumented(LookupError):
    def __init__(self, symbol: str, suggestions: list[str]) -> None:
        super().__init__(f"'{symbol}' is not documented")
        self.symbol = symbol
        self.suggestions = suggestions


def docs_for(symbol: str) -> dict[str, Any]:
    """Signature, summary, example and related symbols of `symbol`, plus the terminal `text`.

    Accepts `k.morph`, `morph`, `Scene.play`, `s.play`, `Axes.plot`, `ax.plot`."""
    from . import catalog, render

    found = catalog.lookup(symbol)
    if found.entry is None:
        raise SymbolNotDocumented(symbol, found.suggestions)
    return {**render.entry_json(found.entry), "text": render.render_entry(found.entry)}


__all__ = [
    "AREAS",
    "DOCUMENTED_BY",
    "DocEntry",
    "SymbolNotDocumented",
    "UNDOCUMENTED_INTERNAL",
    "by_area",
    "coverage_gaps",
    "docs_for",
    "entries",
    "entry",
]
