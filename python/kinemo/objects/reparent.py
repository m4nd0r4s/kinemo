"""`k.reparent(obj, new)`: move an object to another group keeping its global position.

The IR keeps one parent per node, so from the instant of the move the object is drawn
by a fresh node under the new parent; the Python object keeps its identity and every
later call addresses the new node."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from .._runtime.spans import Span, user_span
from ..anim.animation import Animation
from ..anim.ease import Ease
from ..diagnostics import KinemoError
from .copying import IDENTITY_ATTRS, copy_node

if TYPE_CHECKING:
    from ..scene.scene import Scene
    from .groups import Group
    from .node import Node


def _swap_identity(a: "Node", b: "Node") -> None:
    """Exchange which IR objects two Python nodes stand for (subtrees included)."""
    kids_a, kids_b = a._children_at(a._scene.cursor), b._children_at(b._scene.cursor)
    for attr in IDENTITY_ATTRS:
        va, vb = a.__dict__.get(attr), b.__dict__.get(attr)
        object.__setattr__(a, attr, vb)
        object.__setattr__(b, attr, va)
    for node in (a, b):
        for sig in node._sigs.values():
            object.__setattr__(sig, "_node", node)
    for ka, kb in zip(kids_a, kids_b):
        _swap_identity(ka, kb)
        object.__setattr__(ka, "_parent", a)
        object.__setattr__(kb, "_parent", b)


def _world_to_local(s: "Scene", parent: "Node | None", t: float, point: tuple[float, float]) -> tuple[float, float]:
    if parent is None:
        return point

    def to_world(x: float, y: float) -> tuple[float, float]:
        expr = {"op": "to_world", "obj": parent._id, "p": {"op": "const", "v": {"Vec2": [x, y]}}}
        return tuple(json.loads(s._b.eval_expr(json.dumps(expr), t))["Vec2"])  # type: ignore[return-value]

    ox, oy = to_world(0.0, 0.0)
    ax, ay = to_world(1.0, 0.0)
    bx, by = to_world(0.0, 1.0)
    m00, m10, m01, m11 = ax - ox, ay - oy, bx - ox, by - oy
    det = m00 * m11 - m01 * m10
    if abs(det) < 1e-12:
        raise KinemoError.make("K0105", "the new parent has zero scale; the position cannot be kept")
    dx, dy = point[0] - ox, point[1] - oy
    return ((m11 * dx - m01 * dy) / det, (-m10 * dx + m00 * dy) / det)


def _keep_world_position(s: "Scene", obj: "Node", parent: "Node", t: float, world: tuple[float, float], span: Span) -> None:
    """Solve the local position that lands `obj` at `world`. The parent's scale pivots on
    its bounding box, which contains `obj` itself, so solve with Newton steps on a
    numerically estimated Jacobian."""

    def place(x: float, y: float) -> tuple[float, float]:
        s._push_set(obj._sig("x"), x, span)
        s._push_set(obj._sig("y"), y, span)
        wx, wy = json.loads(s._b.derived(obj._id, "position", t, True))["Vec2"]
        return wx, wy

    x, y = _world_to_local(s, parent, t, world)
    h = 1e-3
    for _ in range(8):
        wx, wy = place(x, y)
        ex, ey = world[0] - wx, world[1] - wy
        if abs(ex) + abs(ey) < 1e-9:
            return
        ax, ay = place(x + h, y)
        bx, by = place(x, y + h)
        j00, j10, j01, j11 = (ax - wx) / h, (ay - wy) / h, (bx - wx) / h, (by - wy) / h
        det = j00 * j11 - j01 * j10
        if abs(det) < 1e-12:
            break
        x += (j11 * ex - j01 * ey) / det
        y += (-j10 * ex + j00 * ey) / det
    place(x, y)


class Reparent(Animation):
    def __init__(self, obj: "Node", parent: "Group", span: Span) -> None:
        super().__init__(duration=0.0, span=span)
        self.obj = obj
        self.parent = parent

    def describe(self) -> str:
        return f"reparent({self.obj._label()}, {self.parent._label()})"

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        obj, new_parent = self.obj, self.parent
        if obj is new_parent or obj in new_parent._ancestors_or_self():
            raise KinemoError.make("K0103", "an object cannot be its own child", spans=[self.span])
        cursor = s.cursor
        s.cursor = start
        try:
            present = s._b.present(obj._id, start)
            world = tuple(json.loads(s._b.derived(obj._id, "position", start, True))["Vec2"])
            old_parent = obj._parent
            if old_parent is not None:
                old_parent._children_sig.set([c for c in old_parent.children if c is not obj])  # type: ignore[attr-defined]
            retired = copy_node(obj, frozen=False)
            _swap_identity(obj, retired)  # `obj` now stands for the fresh node
            object.__setattr__(obj, "_parent", None)
            if present:
                s._exit(retired, start)
            new_parent._add_child(obj)
            if not getattr(new_parent, "is_container", False):
                _keep_world_position(s, obj, new_parent, start, world, self.span)  # type: ignore[arg-type]
            if present:
                s._enter(obj, start)
        finally:
            s.cursor = cursor


def reparent(obj: "Node", new_parent: "Group") -> Animation:
    """Instant move of `obj` into `new_parent` at the scheduled instant, keeping its world
    position (inside a container it takes its slot in the flow)."""
    from .groups import Group
    from .node import Node

    if not isinstance(obj, Node) or not isinstance(new_parent, Group):
        raise KinemoError.make("K0105", "k.reparent(obj, group) takes an object and a group")
    return Reparent(obj, new_parent, user_span())
