"""Docs lookups for the `docs` tool: `kinemo.docs` when available, docstrings otherwise."""

from __future__ import annotations

import dataclasses
import difflib
import importlib
import inspect as python_inspect
from typing import Any

#: Functions `kinemo.docs` may expose for a single-symbol lookup, tried in order.
DOCS_LOOKUP_FUNCTIONS = ("lookup", "docs_for", "render", "get", "describe", "show", "docs")
SYMBOL_PREFIXES = ("kinemo.", "k.")


class SymbolNotFound(LookupError):
    def __init__(self, symbol: str, suggestions: list[str]) -> None:
        super().__init__(f"unknown symbol: {symbol}")
        self.symbol = symbol
        self.suggestions = suggestions


def lookup_documentation(symbol: str) -> dict[str, Any]:
    """`{"symbol", "source", "text", ...}` for `symbol` (`k.morph`, `Text`, `Scene.play`).

    Raises `SymbolNotFound` with close matches when nothing documents it."""
    from_docs_package = _from_docs_package(symbol)
    if from_docs_package is not None:
        return from_docs_package
    return _from_docstring(symbol)


def _from_docs_package(symbol: str) -> dict[str, Any] | None:
    """Ask `kinemo.docs` (built separately) — `None` when it is missing or has no lookup function."""
    try:
        module = importlib.import_module("kinemo.docs")
    except ImportError:
        return None
    for function_name in DOCS_LOOKUP_FUNCTIONS:
        function = getattr(module, function_name, None)
        if not callable(function):
            continue
        try:
            found = function(symbol)
        except (KeyError, LookupError):
            raise SymbolNotFound(symbol, _suggestions(symbol)) from None
        except Exception:  # noqa: BLE001 - a different signature or a half-built module
            continue
        if found is None:
            raise SymbolNotFound(symbol, _suggestions(symbol))
        return {"symbol": symbol, "source": "kinemo.docs", **_as_fields(module, found)}
    return None


def _as_fields(module: Any, found: Any) -> dict[str, Any]:
    """Normalize what `kinemo.docs` returned (text, dict or a `DocEntry`-like dataclass)."""
    if isinstance(found, str):
        return {"text": found}
    if isinstance(found, dict):
        return dict(found)
    fields: dict[str, Any] = {}
    if dataclasses.is_dataclass(found) and not isinstance(found, type):
        fields = {k: list(v) if isinstance(v, tuple) else v for k, v in dataclasses.asdict(found).items()}
    renderer = getattr(module, "render", None)
    try:
        text = renderer(found) if callable(renderer) else None
    except Exception:  # noqa: BLE001
        text = None
    fields.setdefault("text", text if isinstance(text, str) else str(found))
    return fields


def _from_docstring(symbol: str) -> dict[str, Any]:
    import kinemo

    target: Any = kinemo
    path = _strip_prefix(symbol)
    for part in path.split(".") if path else []:
        if not hasattr(target, part):
            raise SymbolNotFound(symbol, _suggestions(symbol))
        target = getattr(target, part)
    if target is kinemo and path:
        raise SymbolNotFound(symbol, _suggestions(symbol))
    return {
        "symbol": symbol,
        "source": "docstring",
        "kind": _kind(target),
        "signature": _signature(path or "kinemo", target),
        "text": python_inspect.getdoc(target) or "(no documentation)",
    }


def _strip_prefix(symbol: str) -> str:
    symbol = symbol.strip()
    for prefix in SYMBOL_PREFIXES:
        if symbol.startswith(prefix):
            return symbol[len(prefix) :]
    return "" if symbol in ("k", "kinemo") else symbol


def _kind(target: Any) -> str:
    if python_inspect.isclass(target):
        return "class"
    if python_inspect.ismodule(target):
        return "module"
    if callable(target):
        return "function"
    return type(target).__name__


def _signature(path: str, target: Any) -> str | None:
    if python_inspect.ismodule(target):
        return None
    try:
        return f"k.{path}{python_inspect.signature(target)}"
    except (TypeError, ValueError):
        return f"k.{path}"


def _suggestions(symbol: str) -> list[str]:
    import kinemo

    names = [n for n in dir(kinemo) if not n.startswith("_")]
    leaf = _strip_prefix(symbol).split(".")[-1]
    return [f"k.{n}" for n in difflib.get_close_matches(leaf, names, n=5, cutoff=0.6)]
