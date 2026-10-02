"""Emphasis and motion verbs built on the core verbs: `k.flash`, `k.squash`, `k.follow`."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Sequence, Union

from .._runtime.spans import Span, user_span
from ..diagnostics import KinemoError
from ..reactive.native import interp
from ..values.color import YELLOW, parse as parse_color
from .animation import Animation
from .ease import Ease, EaseLike, ease as eases
from .verbs import _nodes, _ramp, _set

if TYPE_CHECKING:
    from ..objects.node import Node
    from ..scene.scene import Scene
    from ..values.aliases import ColorLike, VecLike

#: What `k.follow` travels along: an object's outline or a list of points.
FollowPath = Union["Node", Sequence["VecLike"]]


class Squash(Animation):
    def __init__(self, obj: "Node", amount: float, duration: float | None, ease: EaseLike | None, delay: float, span: Span) -> None:
        super().__init__(0.4 if duration is None else duration, ease if ease is not None else eases.out, delay, span)
        self.obj = _nodes([obj], "squash")[0]
        self.amount = float(amount)

    def describe(self) -> str:
        return f"squash({self.obj._label()})"

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        s._check_alive(self.obj, start, self.span)
        half = duration / 2
        _ramp(s, self.obj, "_squash", start, half, ease, 0.0, self.amount, self.span)
        _ramp(s, self.obj, "_squash", start + half, half, eases.out_back, self.amount, 0.0, self.span)


def squash(obj: "Node", amount: float = 0.3, *, duration: float | None = None, ease: EaseLike | None = None, delay: float = 0.0) -> Animation:
    """Emphasis: elastic squash on the object's base (state returns to the initial one)."""
    return Squash(obj, amount, duration, ease, delay, user_span())


class Flash(Animation):
    def __init__(self, obj: "Node", color: ColorLike, duration: float | None, ease: EaseLike | None, delay: float, span: Span) -> None:
        super().__init__(0.6 if duration is None else duration, ease if ease is not None else eases.out, delay, span)
        self.obj = _nodes([obj], "flash")[0]
        self.color = parse_color(color)

    def describe(self) -> str:
        return f"flash({self.obj._label()})"

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        from ..objects.shapes import Circle

        o = self.obj
        s._check_alive(o, start, self.span)
        cursor = s.cursor
        s.cursor = start
        try:
            w, h = o.world.width.now, o.world.height.now
            r0 = max(w, h) / 2 * 1.05 + 0.05
            ring = Circle(r=r0, stroke=self.color, stroke_width=6.0, fill_opacity=0.0, position=o.world.center)
        finally:
            s.cursor = cursor
        s._enter(ring, start)
        _ramp(s, ring, "_grow", start, duration, ease, 1.0, 1.6, self.span)
        _ramp(s, ring, "_fade", start, duration, ease, 1.0, 0.0, self.span)
        s._exit(ring, start + duration)


def flash(obj: "Node", color: ColorLike = YELLOW, *, duration: float | None = None, ease: EaseLike | None = None, delay: float = 0.0) -> Animation:
    """Emphasis: a ring of light expanding from the object's border."""
    return Flash(obj, color, duration, ease, delay, user_span())


class Follow(Animation):
    def __init__(self, obj: "Node", path: FollowPath, rotate: bool, duration: float | None, ease: EaseLike | None, delay: float, span: Span) -> None:
        super().__init__(duration, ease, delay, span)
        self.obj = _nodes([obj], "follow")[0]
        self.path = path
        self.rotate = rotate

    def describe(self) -> str:
        return f"follow({self.obj._label()})"

    def _points(self, s: "Scene", t: float) -> list[tuple[float, float]]:
        from ..objects.node import Node

        if isinstance(self.path, Node):
            return [(p[0], p[1]) for p in s._b.outline_points(self.path._id, t, 256)]
        pts = [(float(x), float(y)) for x, y in self.path]
        if len(pts) < 2:
            raise KinemoError.make("K0105", "k.follow needs a path with at least two points", spans=[self.span])
        return pts

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        from ..reactive.signal import signal

        o = self.obj
        s._check_alive(o, start, self.span)
        pts = self._points(s, start)
        lengths = [0.0]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            lengths.append(lengths[-1] + math.hypot(x1 - x0, y1 - y0))
        total = lengths[-1] or 1.0
        fractions = [l / total for l in lengths]
        cursor = s.cursor
        s.cursor = start
        angles: list[float] = []
        try:
            progress = signal(0.0)
            parent = o._parent
            if parent is not None:
                raise KinemoError.make("K0105", "k.follow only moves objects without a parent (the path is in world coordinates)", spans=[self.span])
            o._check_animatable_prop("x", start, self.span)
            s._push_set(o._sig("x"), interp(progress, fractions, [p[0] for p in pts]), self.span)
            s._push_set(o._sig("y"), interp(progress, fractions, [p[1] for p in pts]), self.span)
            if self.rotate:
                angles = _unwrapped([math.degrees(math.atan2(y1 - y0, x1 - x0)) for (x0, y0), (x1, y1) in zip(pts, pts[1:])])
                s._push_set(o._sig("rotate"), interp(progress, fractions[:-1], angles), self.span)
        finally:
            s.cursor = cursor
        _set(s, o, "_draw", start, 1.0, self.span)
        progress_anim = progress.to(1.0)
        progress_anim.emit(s, start, duration / progress_anim.total if progress_anim.total else 1.0, ease)
        # When the path ends the object is free again, resting at the last point.
        end = start + duration
        s._push_set(o._sig("x"), pts[-1][0], self.span, t=end)
        s._push_set(o._sig("y"), pts[-1][1], self.span, t=end)
        if self.rotate:
            s._push_set(o._sig("rotate"), angles[-1], self.span, t=end)


def _unwrapped(angles: Sequence[float]) -> list[float]:
    out: list[float] = []
    for a in angles:
        if out:
            while a - out[-1] > 180:
                a -= 360
            while a - out[-1] < -180:
                a += 360
        out.append(a)
    return out


def follow(obj: "Node", path: FollowPath, *, rotate: bool = False, duration: float | None = None, ease: EaseLike | None = None, delay: float = 0.0) -> Animation:
    """Move along a path (an object's outline or a list of points); `rotate=True` aligns
    the object with the tangent."""
    return Follow(obj, path, rotate, duration, ease, delay, user_span())
