"""Groups and layout containers (`Row`, `Column`, `Grid`, `Stack`)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Generic, Iterator, Mapping, Sequence, TypedDict, TypeVar, Unpack, cast

from .._runtime.spans import Span, user_span
from ..anim.animation import Animation
from ..anim.prop import PropTo
from ..diagnostics import KinemoError
from ..reactive.signal import Signal
from ..values.aliases import ALIGNMENTS
from ..values.encode import encode
from .node import Node
from .props import PropSpec

if TYPE_CHECKING:
    from typing import Self

    from ..anim.ease import Ease, EaseLike
    from ..scene.frame import Rect as FrameRect
    from ..scene.scene import Scene
    from ..values.aliases import Align, FloatVal
    from ..reactive.signal import Blend
    from .keywords import GroupKeywords, PlaceKeywords, PropChanges, TransformKeywords
    from .props import PropAccessor

    # `k.Group` without a type argument is `k.Group[k.Node]` (PEP 696 default). The
    # children's type is what construction gave (covariant: a `Row[Square]` is a
    # `Group[Node]`); `insert` and `to(children=...)` accept any object.
    from typing_extensions import TypeVar as TypeVarWithDefault

    ChildT = TypeVarWithDefault("ChildT", bound=Node, default=Node, covariant=True)
else:
    ChildT = TypeVar("ChildT", bound=Node, covariant=True)


class Group(Node, Generic[ChildT]):
    """Groups compose transforms; opacity multiplies. A node has exactly one parent.

    `k.Row(*bars)` is a `Row[Bar]`: indexing and iterating give the children's type."""

    kind = "group"
    is_container = False

    if TYPE_CHECKING:
        _children_sig: Signal[list[Node]]

    def __init__(self, *children: ChildT | Sequence[ChildT], **props: Unpack[GroupKeywords]) -> None:
        if len(children) == 1 and isinstance(children[0], list | tuple):
            children = tuple(children[0])
        super().__init__(**props)
        # One list argument holds the children; otherwise each argument is a child.
        members = (*cast("tuple[Node, ...]", children), *self._parts())
        for c in members:
            self._adopt(c)
        s = self._scene
        sid = s._b.add_signal(json.dumps(encode(list(members), "objects")), "layout", (self._id, "children"), json.dumps(self._span.ir()))
        s._b.set_children_signal(self._id, sid)
        object.__setattr__(self, "_children_sig", Signal(s, sid, "objects", "layout"))

    def _adopt(self, child: Node) -> None:
        if not isinstance(child, Node):
            raise KinemoError.make("K0105", f"groups contain objects, got {type(child).__name__}")
        if child._parent is not None and child._parent is not self:
            raise KinemoError.make(
                "K0103",
                f"'{child._label()}' already belongs to '{child._parent._label()}'",
                fixes=[("use a copy", f"{child._label()}.copy()"), ("or change parents while keeping the position", f"k.reparent({child._label()}, new_parent)")],
            )
        if child is self or self in child._ancestors_or_self():
            raise KinemoError.make("K0103", "a group cannot contain itself")
        object.__setattr__(child, "_parent", self)
        self._scene._b.set_parent(child._id, self._id)
        if child._name is not None and child._name == self._name and child._span == self._span:
            # `group = k.Group(k.Group(...))`: the name belongs to the outer object.
            object.__setattr__(child, "_name", None)

    def _parts(self) -> list[Node]:
        """Children a subclass builds itself (after its props exist)."""
        return []

    def _add_child(self, node: Node, enter_with_parent: bool = True) -> None:
        """Append a child at the cursor (parts created after construction). With
        `enter_with_parent=False` it stays hidden until a verb or `s.add` brings it in."""
        self._adopt(node)
        if not enter_with_parent:
            object.__setattr__(node, "_enters_on_its_own", True)
        self._children_sig.set(self._children_at(self._scene.cursor) + [node])
        s = self._scene
        if enter_with_parent and s._b.present(self._id, s.cursor):
            s._enter(node, s.cursor)

    # ---- children at the cursor --------------------------------------------------
    def _children_at(self, t: float) -> list[Node]:
        ids = [v["Object"] for v in json.loads(self._scene._b.eval_signal(self._children_sig._id, t))["List"]]
        by_id = {n._id: n for n in self._scene._nodes}
        return [by_id[i] for i in ids]

    @property
    def children(self) -> list[ChildT]:
        """Children at the cursor, in order (reflects reorders already scheduled)."""
        return cast("list[ChildT]", self._children_at(self._scene.cursor))

    def __iter__(self) -> Iterator[ChildT]:
        return iter(self.children)

    def __len__(self) -> int:
        return len(self.children)

    def __getitem__(self, i: int) -> ChildT:
        return self.children[i]

    def _color_targets(self) -> list[tuple[Node, str]]:
        return [t for c in self.children for t in c._color_targets()]

    def _color_props(self) -> tuple[str, ...]:
        return ()

    # ---- reordering --------------------------------------------------------------
    def to(  # pyright: ignore[reportIncompatibleMethodOverride] - `children=` is the group's own prop
        self,
        *,
        duration: float | None = None,
        ease: EaseLike | None = None,
        delay: float = 0.0,
        blend: Blend = "replace",
        place: PlaceKeywords | Mapping[str, object] | None = None,
        children: Sequence[Node] | None = None,
        **props: Unpack[PropChanges],
    ) -> Animation:
        """Animated change of state; `children=` reorders, inserts or removes children
        with an animated reflow."""
        anim = super().to(duration=duration, ease=ease, delay=delay, blend=blend, place=place, **props)
        if children is not None:
            assert isinstance(anim, PropTo)
            anim.extra.append(Reorder(self, list(children), user_span()))
        return anim

    def _reorder(self, new: Sequence[Node], **kw: Unpack[ReorderKeywords]) -> Animation:
        return Reorder(self, new, user_span(2), **kw)

    def swap(self, i: int, j: int, **kw: Unpack[ReorderTiming]) -> Animation:
        """Exchange two children. ≡ `.to(children=...)` with `i` and `j` swapped."""
        kids = self.children
        kids[i], kids[j] = kids[j], kids[i]
        return self._reorder(kids, **kw)

    def insert(self, i: int, obj: Node, **kw: Unpack[ReorderTiming]) -> Animation:
        """Insert a child (it enters with the reflow). ≡ `.to(children=...)`."""
        kids: list[Node] = list(self.children)
        kids.insert(i, obj)
        return self._reorder(kids, entering=[obj], **kw)

    def pop(self, i: int = -1, **kw: Unpack[ReorderTiming]) -> Animation:
        """Remove a child (it leaves with the reflow). ≡ `.to(children=...)`."""
        kids = self.children
        gone = kids.pop(i)
        return self._reorder(kids, leaving=[gone], **kw)

    def fit(self, area: FrameRect, margin: float = 0.0) -> Self:
        """Scale (once, at the cursor) so the group fits inside `area` (e.g. `s.frame.safe`)."""
        w = self.width.now
        h = self.height.now
        if w > 0 and h > 0:
            k = min((area.width - 2 * margin) / w, (area.height - 2 * margin) / h)
            self.set(scale=self.scale.now * k)
        return self



class ReorderTiming(TypedDict, total=False):
    """`row.swap(i, j, duration=, ease=)` (and `insert`, `pop`)."""

    duration: float | None
    ease: EaseLike | None


class ReorderKeywords(ReorderTiming, total=False):
    entering: Sequence[Node]
    leaving: Sequence[Node]


class Reorder(Animation):
    """Animated change of a group's children; containers reflow during the transition."""

    def __init__(self, group: Group[Any], children: Sequence[Node], span: Span, entering: Sequence[Node] = (), leaving: Sequence[Node] = (), duration: float | None = None, ease: EaseLike | None = None) -> None:
        super().__init__(duration, ease, 0.0, span)
        self.group = group
        self.new = children
        self.entering = list(entering)
        self.leaving = list(leaving)

    def describe(self) -> str:
        return f"{self.group._label()}.reorder"

    def _emit(self, s: Scene, start: float, duration: float, ease: Ease) -> None:
        g = self.group
        s._check_alive(g, start, self.span)
        for c in self.new:
            if c._parent is not g:
                g._adopt(c)
        from ..anim.verbs import _ramp, _set  # pyright: ignore[reportPrivateUsage]

        for c in self.entering:
            s._enter(c, start)
            if duration > 0:
                # Grows in while its neighbours make room.
                _ramp(s, c, "_fade", start, duration, ease, 0.0, 1.0, self.span)
                _ramp(s, c, "_grow", start, duration, ease, 0.0, 1.0, self.span)
        sig = g._children_sig
        src = {"k": "val", "v": encode(self.new, "objects")}
        if duration <= 0:
            s._push_entry(sig, {"k": "set", "t": start, "src": src, "span": self.span.ir()}, src)
        else:
            s._check_conflict(sig, start, start + duration, self.span)
            s._push_entry(sig, {"k": "anim", "t0": start, "t1": start + duration, "to": src, "ease": ease.ir(), "span": self.span.ir()}, src)
        for c in self.leaving:
            if duration > 0:
                # Shrinks away in its old slot while the others close the gap.
                _ramp(s, c, "_fade", start, duration, ease, 1.0, 0.0, self.span)
                _ramp(s, c, "_grow", start, duration, ease, 1.0, 0.0, self.span)
                _set(s, c, "_fade", start + duration, 1.0, self.span)
                _set(s, c, "_grow", start + duration, 1.0, self.span)
            s._exit(c, start + duration)


class Container(Group[ChildT]):
    is_container = True


class Row(Container[ChildT]):
    kind = "row"
    PROPS = {"gap": PropSpec("float", 0.25), "align": PropSpec("str", "center", "step_end", ALIGNMENTS)}

    if TYPE_CHECKING:
        gap: PropAccessor[float]
        align: PropAccessor[str]

    def __init__(self, *children: ChildT | Sequence[ChildT], gap: FloatVal = 0.25, align: Align = "center", **props: Unpack[TransformKeywords]) -> None:
        super().__init__(*children, gap=gap, align=align, **props)


class Column(Container[ChildT]):
    kind = "column"
    PROPS = {"gap": PropSpec("float", 0.25), "align": PropSpec("str", "center", "step_end", ALIGNMENTS)}

    if TYPE_CHECKING:
        gap: PropAccessor[float]
        align: PropAccessor[str]

    def __init__(self, *children: ChildT | Sequence[ChildT], gap: FloatVal = 0.25, align: Align = "center", **props: Unpack[TransformKeywords]) -> None:
        super().__init__(*children, gap=gap, align=align, **props)


class Grid(Container[ChildT]):
    kind = "grid"
    PROPS = {"gap": PropSpec("float", 0.25), "cols": PropSpec("float", 3.0, "step_end")}

    if TYPE_CHECKING:
        gap: PropAccessor[float]
        cols: PropAccessor[float]

    def __init__(self, *children: ChildT | Sequence[ChildT], cols: int = 3, gap: FloatVal = 0.25, **props: Unpack[TransformKeywords]) -> None:
        super().__init__(*children, cols=float(cols), gap=gap, **props)


class Stack(Container[ChildT]):
    kind = "stack"
    PROPS = {"align": PropSpec("str", "center", "step_end", ALIGNMENTS)}

    if TYPE_CHECKING:
        align: PropAccessor[str]

    def __init__(self, *children: ChildT | Sequence[ChildT], align: Align = "center", **props: Unpack[TransformKeywords]) -> None:
        super().__init__(*children, align=align, **props)
