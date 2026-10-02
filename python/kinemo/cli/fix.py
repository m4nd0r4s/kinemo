"""`kinemo check --fix`: apply the single safe fix of each diagnostic."""

from __future__ import annotations

from collections import defaultdict

from ..diagnostics import Diagnostic, Edit


def apply_fixes(diags: list[Diagnostic]) -> int:
    edits: dict[str, dict[int, Edit]] = defaultdict(dict)
    for d in diags:
        safe = [f for f in d.fixes if f.edits]
        if len(safe) != 1:
            continue
        for e in safe[0].edits:
            edits[e.file].setdefault(e.line, e)
    applied = 0
    for path, by_line in edits.items():
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()
        for line, e in by_line.items():
            if 0 < line <= len(lines):
                ending = "\n" if lines[line - 1].endswith("\n") else ""
                lines[line - 1] = e.replacement + ending
                applied += 1
        with open(path, "w", encoding="utf-8") as fh:
            fh.writelines(lines)
    return applied
