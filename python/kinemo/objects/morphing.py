"""The transient node that draws a morph in progress."""

from __future__ import annotations

from typing import Any

from .node import Node
from .props import PropSpec


class MorphNode(Node):
    kind = "morph"
    PROPS = {
        "a": PropSpec("object", None, "step_end"),
        "b": PropSpec("object", None, "step_end"),
        "progress": PropSpec("float", 0.0),
        "pairs": PropSpec("points", [], "step_end"),
    }

    def __init__(self, a: Node, b: Node, pairs: list[tuple[int, int]], **props: Any) -> None:
        super().__init__(a=a, b=b, pairs=[(float(i), float(j)) for i, j in pairs], name=f"morph({a._label()}→{b._label()})", **props)
