"""Objects entering and leaving the scene: `s.add`, `s.remove` and entry/exit verbs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable

from .._runtime.spans import user_span
from ..diagnostics import KinemoError

if TYPE_CHECKING:
    from .._core import Builder
    from ..objects.node import Node


class LifecycleMixin:
    _b: "Builder"
    cursor: float

    def add(self, *objs: "Node") -> None:
        """Put objects in the scene instantly, at the cursor."""
        for o in _nodes(objs, "add"):
            self._enter(o, self.cursor)

    def remove(self, *objs: "Node") -> None:
        """Take objects out of the scene instantly, at the cursor."""
        for o in _nodes(objs, "remove"):
            self._exit(o, self.cursor)

    def _enter(self, node: "Node", t: float) -> None:
        for n in [node, *node._entering_descendants(t)]:
            if not self._b.present(n._id, t):
                self._b.set_presence(n._id, t, True)
            for companion in n.__dict__.get("_companions", ()):
                self._enter(companion, t)  # a curve's label, kept beside it in the axes
        for a in node._ancestors():
            if not self._b.present(a._id, t):
                self._b.set_presence(a._id, t, True)

    def _enter_shallow(self, node: "Node", t: float) -> None:
        """Enter only the node and its ancestors (its parts enter through its own animation)."""
        for n in [node, *node._ancestors()]:
            if not self._b.present(n._id, t):
                self._b.set_presence(n._id, t, True)

    def _enter_rest(self, node: "Node", t: float) -> None:
        """Parts a component's `enter()` did not bring in appear when it ends."""
        for n in node._entering_descendants(t):
            if not self._b.present(n._id, t):
                self._b.set_presence(n._id, t, True)

    def _exit(self, node: "Node", t: float) -> None:
        exits: dict[int, list[Any]] = self.__dict__.setdefault("_exits", {})
        span = user_span()
        for n in [node, *node._descendants(t)]:
            exits.setdefault(n._id, []).append((t, span))
            if self._b.present(n._id, t):
                self._b.set_presence(n._id, t, False)


def _nodes(objs: Iterable[object], verb: str) -> list["Node"]:
    from ..objects.node import Node

    out = []
    for o in objs:
        if not isinstance(o, Node):
            raise KinemoError.make(
                "K0105",
                f"s.{verb} takes scene objects, got {type(o).__name__}",
                spans=[user_span()],
                fixes=[("for animations use s.play", "s.play(anim)")] if hasattr(o, "emit") else [],
            )
        out.append(o)
    return out
