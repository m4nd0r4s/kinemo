"""Objects entering and leaving the scene: `s.add`, `s.remove` and entry/exit verbs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Iterable

from .._runtime.spans import Span, user_span
from ..diagnostics import KinemoError

if TYPE_CHECKING:
    from .._core import Builder
    from ..objects.node import Node


class LifecycleMixin:
    _b: "Builder"
    cursor: float

    if TYPE_CHECKING:

        def _record(self, kind: str, start: float, end: float, label: str = "", span: "Span | None" = None) -> None: ...

    def add(self, *objs: "Node") -> None:
        """Put objects in the scene instantly, at the cursor."""
        nodes = _nodes(objs, "add")
        for o in nodes:
            self._enter(o, self.cursor)
        self._record("add", self.cursor, self.cursor, ", ".join(o._label() for o in nodes))

    def remove(self, *objs: "Node") -> None:
        """Take objects out of the scene instantly, at the cursor."""
        nodes = _nodes(objs, "remove")
        for o in nodes:
            self._exit(o, self.cursor)
        self._record("remove", self.cursor, self.cursor, ", ".join(o._label() for o in nodes))

    def _enter(self, node: "Node", t: float) -> None:
        for n in [node, *node._entering_descendants(t)]:
            if not self._b.present(n._id, t):
                self._b.set_presence(n._id, t, True)
                self._raise(n)
            for companion in n.__dict__.get("_companions", ()):
                self._enter(companion, t)  # a curve's label, kept beside it in the axes
        for a in node._ancestors():
            if not self._b.present(a._id, t):
                self._b.set_presence(a._id, t, True)
                self._raise(a)

    def _raise(self, node: "Node") -> None:
        """With equal `z`, objects draw in the order they enter: `s.add(trail, dot)` puts the
        dot on top."""
        if node._parent is None:
            self._b.raise_root(node._id)

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
