"""`obj.copy()`: a new identity with the same props, bound (default) or frozen."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from .._runtime.spans import user_span
from ..values.encode import decode, encode

if TYPE_CHECKING:
    from .node import Node


#: Attributes tied to one IR object (never shared between copies).
IDENTITY_ATTRS = (
    "_id", "_sigs", "_parent", "_place_log", "_binding_log", "_children_sig",
    "_lifecycle_events", "_runs", "_rest",
)


def copy_node(node: "Node", frozen: bool, descendant: bool = False) -> "Node":
    """A new node with `node`'s props (bound or frozen). The copied root starts where the
    original is in the world; its descendants keep their positions in their parent."""
    from .groups import Group
    from .node import Node

    s = node._scene
    span = user_span()
    clone = object.__new__(type(node))
    for attr, value in node.__dict__.items():
        if attr not in IDENTITY_ATTRS + ("_span", "_name"):
            object.__setattr__(clone, attr, value)
    object.__setattr__(clone, "_span", span)
    object.__setattr__(clone, "_name", None)
    object.__setattr__(clone, "_sigs", {})
    object.__setattr__(clone, "_parent", None)
    object.__setattr__(clone, "_place_log", [])
    object.__setattr__(clone, "_binding_log", {})
    object.__setattr__(clone, "_id", s._b.add_object(node.kind, json.dumps(span.ir()), None))
    s._b.add_root(clone._id)
    s._nodes.append(clone)
    # The copy starts where the original is (in world coordinates when it had a parent),
    # free of any placement; other props keep the original's bindings (or freeze).
    world = node._parent is not None and not descendant
    position = {
        axis: json.loads(s._b.derived(node._id, axis, s.cursor, world))["Float"] for axis in ("x", "y")
    }
    for name, sig in node._sigs.items():
        new = clone._create_signal(name, None)
        base = s._base_source(sig)
        if name in position and (frozen or base.get("k") != "expr" or node._place_log):
            src = {"k": "val", "v": encode(position[name], "float")}
        elif frozen or base.get("k") != "expr":
            current = decode(json.loads(s._b.eval_signal(sig._id, s.cursor)))
            src = {"k": "val", "v": encode(current, sig.kind)}
        else:
            src = base
        s._push_entry(new, {"k": "set", "t": s.cursor, "src": src, "span": span.ir()}, src)
    if isinstance(node, Group):
        assert isinstance(clone, Group)
        kids = [copy_node(c, frozen, descendant=True) for c in node.children]
        sid = s._b.add_signal(json.dumps(encode(kids, "objects")), "layout", (clone._id, "children"), json.dumps(span.ir()))
        s._b.set_children_signal(clone._id, sid)
        from ..reactive.signal import Signal

        object.__setattr__(clone, "_children_sig", Signal(s, sid, "objects", "layout"))
        for k in kids:
            clone._adopt(k)
        if "_runs" in node.__dict__:
            object.__setattr__(clone, "_runs", {})
        if "_rest" in node.__dict__ and kids:
            object.__setattr__(clone, "_rest", kids[0])
    assert isinstance(clone, Node)
    if not node.__dict__.get("_copying_child"):
        from .charts.axes import _name_from_call

        _name_from_call(clone, Node.copy)
    return clone
