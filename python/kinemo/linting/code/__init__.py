"""W03xx code lints, found in the scene function's AST without running it.

Each rule is a module with `CODE` and `find(source) -> list[CodeFinding]`:

- `late_binding` — W0310 lambda in a loop capturing the loop variable;
- `captured_list` — W0311 lambda capturing a Python list mutated later;
- `eased_clock` — W0312 clock signal (`d=` of `k.integrate`) animated with easing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Iterable

from ...diagnostics import Collector, Diagnostic
from . import captured_list, eased_clock, late_binding
from .scope import CodeFinding
from .source import FunctionSource, function_source, functions_at_lines

if TYPE_CHECKING:
    from ...scene.scene import Scene

RULES = (late_binding, captured_list, eased_clock)


def code_findings(sources: Iterable[FunctionSource]) -> list[CodeFinding]:
    out: list[CodeFinding] = []
    for source in sources:
        for rule in RULES:
            out.extend(rule.find(source))
    return out


def scene_sources(s: "Scene | None", scene_fn: Callable[..., Any] | None) -> list[FunctionSource]:
    """The function(s) to lint: `scene_fn` (or a `SceneDef`) when given; otherwise the
    scene functions that created the scene's objects, found from their spans."""
    if scene_fn is not None:
        source = function_source(scene_fn)
        return [source] if source is not None else []
    if s is None:
        return []
    lines_by_file: dict[str, list[int]] = {}
    for node in s._nodes:
        span = node._span
        if span.line > 0:
            lines_by_file.setdefault(span.file, []).append(span.line)
    out: list[FunctionSource] = []
    for file, lines in lines_by_file.items():
        out.extend(functions_at_lines(file, lines))
    return out


def code_diagnostics(
    s: "Scene | None" = None,
    scene_fn: Callable[..., Any] | None = None,
    collector: Collector | None = None,
) -> list[Diagnostic]:
    """W03xx diagnostics for the scene function (inline allows respected)."""
    out = collector if collector is not None else Collector()
    for f in code_findings(scene_sources(s, scene_fn)):
        out.warn(f.code, f.message, fixes=f.fixes, spans=f.spans)
    return out.items


__all__ = ["CodeFinding", "code_diagnostics", "code_findings", "scene_sources"]
