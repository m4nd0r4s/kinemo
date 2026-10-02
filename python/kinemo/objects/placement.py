"""`.place(...)`: position by constraints that keep holding while things move."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Mapping, Unpack

from .._runtime.spans import Span, user_span
from ..anim.animation import Animation
from ..anim.ease import Ease
from ..diagnostics import KinemoError
from ..reactive.expr import Expr, lift

if TYPE_CHECKING:
    from typing import Self

    from ..anim.ease import EaseLike
    from ..scene.scene import Scene
    from .keywords import PlaceKeywords
    from .node import Node

SIDES = {"above": "y", "below": "y", "left_of": "x", "right_of": "x", "inside": "xy"}
ANCHORS = {
    "center", "top", "bottom", "left", "right",
    "top-left", "top-right", "bottom-left", "bottom-right",
}


def placement_ir(node: "Node", kw: Mapping[str, Any], span: Span) -> dict[str, Any]:
    sides = [k for k in SIDES if kw.get(k) is not None]
    if len(sides) > 1:
        axes = {SIDES[k] for k in sides}
        if len(axes) < len(sides):
            raise KinemoError.make(
                "K0403",
                f"conflicting constraints on the same axis: {' and '.join(sides)}",
                spans=[span],
                fixes=[("keep one; for a weak constraint use weak=True", None)],
            )
        raise KinemoError.make(
            "K0105",
            f"one relation per place call ({', '.join(sides)})",
            spans=[span],
            fixes=[("combine the relation with align=", f".place({sides[0]}=..., align=\"left\")")],
        )
    unknown = set(kw) - set(SIDES) - {"at", "gap", "margin", "align", "clamp", "weak", "by", "pad"}
    if unknown:
        raise KinemoError.make("K0105", f"unknown argument to place: {', '.join(sorted(unknown))}", spans=[span])
    p: dict[str, Any] = {"span": span.ir(), "clamp": bool(kw.get("clamp", False)), "weak": bool(kw.get("weak", False))}
    p["rotated"] = kw.get("by") == "rotated"
    if sides:
        side = sides[0]
        target = kw[side]
        from .node import Node

        if not isinstance(target, Node):
            raise KinemoError.make("K0105", f"{side}= expects an object, got {type(target).__name__}", spans=[span])
        if target is node:
            raise KinemoError.make("K0402", "an object cannot be placed relative to itself", spans=[span])
        p["side"] = side
        p["target"] = target._id
        gap = kw.get("pad" if side == "inside" and "pad" in kw else "gap")
        if gap is not None:
            p["gap"] = lift(gap)._ir()
    at = kw.get("at")
    if at is not None:
        if isinstance(at, str):
            if at not in ANCHORS:
                raise KinemoError.make(
                    "K0404", f"unknown anchor {at!r}", spans=[span],
                    fixes=[(f"use one of {', '.join(sorted(ANCHORS))}", None)],
                )
            p["at"] = at
        else:
            p["at_point"] = lift(tuple(at) if not isinstance(at, Expr) else at, "vec2")._ir()
    if kw.get("margin") is not None:
        p["margin"] = lift(kw["margin"])._ir()
    if kw.get("align") is not None:
        p["align"] = str(kw["align"])
    if not sides and at is None:
        p["at"] = "center"
    return p


class PlacementMixin:
    _scene: "Scene"
    _id: int
    _parent: "Node | None"
    _place_log: list[tuple[float, bool, Span]]

    def place(self, **kw: Unpack[PlaceKeywords]) -> Self:
        """Declare where the object is, relative to the frame or another object."""
        span = user_span()
        p = placement_ir(self, kw, span)  # type: ignore[arg-type]
        self._push_placement(self._scene.cursor, 0.0, None, p, span)
        return self

    def to_place(
        self,
        *,
        duration: float | None = None,
        ease: EaseLike | None = None,
        delay: float = 0.0,
        **place: Unpack[PlaceKeywords],
    ) -> Animation:
        """Animated change of placement: `s.play(title.to_place(right_of=tri, gap=0.4))`.
        Takes the same keywords as `.place(...)`."""
        span = user_span()
        return PlaceTo(self, placement_ir(self, place, span), span, duration=duration, ease=ease, delay=delay)  # type: ignore[arg-type]

    def unpin(self) -> None:
        """Release the placement; the object keeps its current position and becomes free."""
        self._unpin_at(self._scene.cursor, user_span())

    def _unpin_at(self, t: float, span: Span) -> None:
        s = self._scene
        x = json.loads(s._b.derived(self._id, "x", t, False))["Float"]
        y = json.loads(s._b.derived(self._id, "y", t, False))["Float"]
        self._push_placement(t, 0.0, None, None, span)
        s._push_set(self._sig("x"), x, span, t)  # type: ignore[attr-defined]
        s._push_set(self._sig("y"), y, span, t)  # type: ignore[attr-defined]

    def _push_placement(self, t: float, dur: float, ease: Ease | None, p: dict[str, Any] | None, span: Span) -> None:
        entry: dict[str, Any] = {"t": t, "dur": dur, "p": p, "span": span.ir()}
        if ease is not None:
            entry["ease"] = ease.ir()
        self._scene._b.push_place(self._id, json.dumps(entry))
        self._place_log.append((t, p is not None, span))
        self._place_log.sort(key=lambda e: e[0])

    def _place_to(self, kw: Mapping[str, Any], span: Span) -> Animation:
        return PlaceTo(self, placement_ir(self, kw, span), span)  # type: ignore[arg-type]

    def _pinned_by(self, t: float) -> tuple[str, Span] | None:
        """What holds the object's position at `t` (container or placement), if anything."""
        parent = self._parent
        if parent is not None and getattr(parent, "is_container", False):
            return (f"the container '{parent._label()}'", parent._span)
        state: tuple[str, Span] | None = None
        for when, placed, span in self._place_log:
            if when <= t + 1e-9:
                state = ("a constraint", span) if placed else None
        return state


class PlaceTo(Animation):
    """Animated change of constraint: `obj.to_place(right_of=tri)`."""

    def __init__(
        self,
        node: "Node",
        placement: dict[str, Any],
        span: Span,
        duration: float | None = None,
        ease: "EaseLike | None" = None,
        delay: float = 0.0,
    ) -> None:
        super().__init__(duration, ease, delay, span)
        self.node = node
        self.placement = placement

    def describe(self) -> str:
        return f"{self.node._label()}.to_place(...)"

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        s._check_alive(self.node, start, self.span)
        self.node._push_placement(start, duration, ease, self.placement, self.span)
        s._max_end = max(s._max_end, start + duration)


class Unpin(Animation):
    """`obj.to(..., unpin=True)`: releases the placement where the animation starts, so
    the same animation can then move `x`/`y` freely."""

    def __init__(self, node: "Node", span: Span) -> None:
        super().__init__(0.0, None, 0.0, span)
        self.node = node

    def describe(self) -> str:
        return f"{self.node._label()}.unpin()"

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        self.node._unpin_at(start, self.span)
