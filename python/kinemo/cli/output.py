"""Shared output helpers: text vs `--json`, exit codes."""

from __future__ import annotations

import json
import sys
from typing import Any

from ..diagnostics import Diagnostic

EXIT_OK = 0
EXIT_ERRORS = 1


def emit_json(payload: Any) -> None:
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


def exit_code(diags: list[Diagnostic], strict: bool) -> int:
    failing = ("error", "warning") if strict else ("error",)
    return EXIT_ERRORS if any(d.level in failing for d in diags) else EXIT_OK


def summary_word(diags: list[Diagnostic]) -> str:
    errors = sum(d.level == "error" for d in diags)
    warnings = sum(d.level == "warning" for d in diags)
    if errors:
        return f"{errors} error{'s' if errors > 1 else ''}"
    if warnings:
        return f"ok with {warnings} warning{'s' if warnings > 1 else ''}"
    return "ok"
