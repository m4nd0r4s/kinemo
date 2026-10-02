"""W0901: a loop created more than 1000 individual leaf objects from one source line.

Each object is a node with its own signals, layout and draw item; thousands of them
make the build, the IR and every frame slow. The vectorized types (`k.Points`,
`k.VectorField`, `k.StreamLines`) hold all marks in one object and evaluate per-point
functions natively.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING, Any

from .._runtime.spans import Span
from ..diagnostics import Collector, Diagnostic

if TYPE_CHECKING:
    from ..scene.scene import Scene

CODE = "W0901"
#: More than this many leaves from one line triggers the lint.
MAX_OBJECTS_PER_LINE = 1000

_MASS_KINDS = ("points", "vector_field", "stream_lines")
_ARROW_KINDS = ("arrow", "line")


def _is_user_leaf(node: Any) -> bool:
    """A leaf the user constructed (not a part a component or text made for itself)."""
    from ..objects.node import Node

    return (
        getattr(node, "_part", None) is None
        and type(node)._children_at is Node._children_at
        and node.kind not in _MASS_KINDS
        and node._span.line > 0
    )


def _suggestion(kind: str) -> tuple[str, str]:
    if kind in _ARROW_KINDS:
        return ("a field of arrows is a single object", "k.VectorField(lambda x, y: (vx, vy), density=30)")
    return ("a mass of points is a single object", "k.Points(xy, radius=0.02, color=lambda p: ...)")


def mass_object_diagnostics(s: "Scene", collector: Collector | None = None) -> list[Diagnostic]:
    """W0901 for every source line that created more than 1000 leaf objects."""
    out = collector if collector is not None else Collector()
    counts: Counter[tuple[str, int]] = Counter()
    kinds: dict[tuple[str, int], Counter[str]] = {}
    for node in s._nodes:
        if not _is_user_leaf(node):
            continue
        key = (node._span.file, node._span.line)
        counts[key] += 1
        kinds.setdefault(key, Counter())[type(node).__name__ + ":" + node.kind] += 1
    for (file, line), n in sorted(counts.items()):
        if n <= MAX_OBJECTS_PER_LINE:
            continue
        name, kind = kinds[(file, line)].most_common(1)[0][0].split(":", 1)
        description, code = _suggestion(kind)
        out.warn(
            CODE,
            f"{n} {name} objects created on this line: use a vectorized type",
            fixes=[(description, code)],
            spans=[Span(file, line)],
        )
    return out.items
