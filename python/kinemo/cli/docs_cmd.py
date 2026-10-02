"""`kinemo docs <symbol>`: short offline doc with the canonical example.

Accepts `k.morph`, `morph`, `Scene.play`, `s.play`, `Axes.plot`, `ax.plot`. Without a symbol,
lists every documented symbol by area; `--check` builds every canonical example.
"""

from __future__ import annotations

import argparse

from .output import EXIT_ERRORS, EXIT_OK, emit_json


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Arguments of `kinemo docs` (registered by `cli/main.py`)."""
    parser.add_argument("symbol", nargs="?", help="symbol: k.draw, draw, s.play, Scene.play, ax.plot")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--check", action="store_true", help="build every canonical example (like check --strict)")


def run(args: argparse.Namespace) -> int:
    from ..docs import catalog, render

    if getattr(args, "check", False):
        return _check_examples(getattr(args, "json", False))
    symbol = getattr(args, "symbol", None)
    if not symbol:
        if args.json:
            emit_json({"symbols": [render.entry_json(e)["symbol"] for e in catalog.entries()]})
        else:
            print(render.render_index())
        return EXIT_OK
    found = catalog.lookup(symbol)
    if found.entry is None:
        if args.json:
            emit_json({"query": symbol, "found": False, "suggestions": found.suggestions})
        else:
            print(render.render_not_found(symbol, found.suggestions))
        return EXIT_ERRORS
    if args.json:
        emit_json({"query": symbol, "found": True, **render.entry_json(found.entry)})
    else:
        print(render.render_entry(found.entry))
    return EXIT_OK


def _check_examples(as_json: bool) -> int:
    from ..docs import catalog
    from ..docs.validation import check_example

    reports = [check_example(e) for e in catalog.entries()]
    failed = [r for r in reports if not r.ok]
    if as_json:
        emit_json(
            {
                "examples": len(reports),
                "failed": [
                    {"symbol": r.entry.symbol, "problems": r.problems, "diagnostics": [d.json() for d in r.diagnostics]}
                    for r in failed
                ],
            }
        )
    else:
        for r in failed:
            print(r.render())
        print(f"kinemo docs: {len(reports) - len(failed)}/{len(reports)} examples ok")
    return EXIT_ERRORS if failed else EXIT_OK
