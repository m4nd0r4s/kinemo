"""W0602: a reactive component prop leaves the `range=` it declares during the timeline."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..component.declarations import FieldSpec
from ..diagnostics import Diagnostic

if TYPE_CHECKING:
    from ..scene.scene import Scene

STEP = 0.1


def range_diagnostics(s: "Scene") -> list[Diagnostic]:
    from ..component.component import Component

    out: list[Diagnostic] = []
    n = max(2, int(s.duration / STEP) + 1)
    for node in s._nodes:
        if not isinstance(node, Component):
            continue
        for name, (_, default) in type(node)._component_props.items():
            if not isinstance(default, FieldSpec) or default.range is None:
                continue
            lo, hi = default.range
            sig = node._sigs.get(name)
            if sig is None:
                continue
            values = s._b.eval_expr_grid(json.dumps(sig._ir()), 0.0, STEP, n)
            bad = next(((i * STEP, v) for i, v in enumerate(values) if not lo <= v <= hi), None)
            if bad is None:
                continue
            t, v = bad
            d = Diagnostic(
                "W0602", "warning",
                f"{node._label()}.{name} = {v:.3g} at t = {t:.2f} s is outside its range [{lo:g}, {hi:g}]",
                [node._span], [], t, [node._label()], [],
            )
            if not s.lints.is_allowed(d):
                out.append(d)
    return out
