"""Lints run after the build: layout problems found by the core, collected warnings,
visual lints (W10xx, sampled by the core) and code lints (W03xx, from the AST)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Callable

from ._runtime.spans import Span
from .diagnostics import Collector, Diagnostic
from .linting import code_diagnostics, visual_diagnostics
from .linting.mass_objects import mass_object_diagnostics

if TYPE_CHECKING:
    from .scene.scene import Scene

#: Sampling step of the visual lints, in seconds (timeline boundaries are always sampled).
VISUAL_SAMPLE_STEP = 0.1


def sample_times(s: "Scene", step: float = 0.25) -> list[float]:
    n = max(1, int(s.duration / step))
    return [i * step for i in range(n + 1)]


def layout_diagnostics(s: "Scene") -> list[Diagnostic]:
    out: list[Diagnostic] = []
    issues = json.loads(s._b.layout_issues(sample_times(s, 0.5)))
    by_id = {n._id: n for n in s._nodes}
    for issue in issues:
        nodes = [by_id[i] for i in issue["objects"] if i in by_id]
        names = [n._label() for n in nodes]
        spans: list[Span] = [n._place_log[-1][2] if n._place_log else n._span for n in nodes]
        if issue["code"] == "K0402":
            message = "constraint cycle: " + " → ".join(names + names[:1])
        else:
            message = "conflicting constraints: " + ", ".join(names)
        out.append(Diagnostic(issue["code"], "error", message, spans, [], issue["t"], names, []))
    return out


def _collector_like(s: "Scene") -> Collector:
    """A fresh collector honoring the codes the scene allowed (`kinemo.toml`)."""
    c = Collector()
    c.allow(sorted(s.lints._allowed))
    return c


from .linting.component_ranges import range_diagnostics


def run_lints(
    s: "Scene",
    scene_fn: Callable[..., Any] | None = None,
    *,
    visual_step: float = VISUAL_SAMPLE_STEP,
) -> list[Diagnostic]:
    """Every post-build diagnostic of `s`.

    `scene_fn` (the scene function or its `SceneDef`) is the source the code lints read;
    without it they lint the scene functions that created the scene's objects.
    """
    return (
        layout_diagnostics(s)
        + list(s.lints.items)
        + visual_diagnostics(s, _collector_like(s), visual_step)
        + code_diagnostics(s, scene_fn, _collector_like(s))
        + mass_object_diagnostics(s, _collector_like(s))
        + range_diagnostics(s)
    )
