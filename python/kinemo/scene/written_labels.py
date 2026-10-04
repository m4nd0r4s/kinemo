"""Timeline labels as the user wrote them: `chart.bar("IT").to(color=k.RED)` rather than a
description rebuilt from the objects (`chart.bars["IT"].to(fill)`).

The label is the source of the animations passed to `s.play(...)`/`s.start(...)`. A call
that runs several times (in a loop) reads the same each time, so its entries keep the
generated description, which tells the iterations apart."""

from __future__ import annotations

import ast
import linecache
from collections import Counter
from typing import TYPE_CHECKING, Sequence

if TYPE_CHECKING:
    from .._runtime.spans import Span
    from .timeline import LogEntry

#: Longer labels are cut with an ellipsis.
MAX_LABEL = 72


def written_labels(log: Sequence["LogEntry"]) -> list[str]:
    """One label per entry of `log`, in the same order."""
    runs = Counter(_key(e.call) for e in log if e.call is not None)
    labels: list[str] = []
    for entry in log:
        written = _arguments_text(entry.call) if entry.call is not None and runs[_key(entry.call)] == 1 else None
        labels.append(written or entry.label)
    return labels


def _key(span: "Span") -> tuple[str, int, int, int, int]:
    return (span.file, span.line, span.col, span.end_line, span.end_col)


def _arguments_text(call: "Span") -> str | None:
    """The positional arguments of the call at `call`, as written."""
    if not call.end_line or call.line <= 0:
        return None
    lines = [linecache.getline(call.file, n) for n in range(call.line, call.end_line + 1)]
    if not all(lines):
        return None
    lines[-1] = lines[-1][: call.end_col]
    lines[0] = lines[0][call.col :]
    source = "".join(lines)
    try:
        node = ast.parse(source, mode="eval").body
    except SyntaxError:
        return None
    if not isinstance(node, ast.Call) or not node.args or any(isinstance(a, ast.Starred) for a in node.args):
        return None
    parts = [ast.get_source_segment(source, a) for a in node.args]
    if any(p is None for p in parts):
        return None
    text = " ".join(", ".join(p for p in parts if p).split())
    return text if len(text) <= MAX_LABEL else text[: MAX_LABEL - 1] + "…"
