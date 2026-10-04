"""Verbs: module functions that animate (`k.draw`, `k.write`, `k.fade_in`, ...).

Entry verbs put objects in the scene at their start; exit verbs take them out at their
end. Effects run on render-only props, so they never disturb layout dependents.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Sequence

from .._runtime.spans import Span, user_span
from ..diagnostics import KinemoError
from ..objects.placement import ANCHORS
from ..values.color import YELLOW, parse as parse_color
from ..values.encode import encode
from .animation import Animation, Instant
from .ease import Ease, EaseLike

if TYPE_CHECKING:
    from ..objects.node import Node
    from ..scene.scene import Scene
    from ..values.aliases import Anchor, ColorLike, VecLike

ANCHOR_UNITS = {
    "center": (0.0, 0.0), "top": (0.0, 1.0), "bottom": (0.0, -1.0), "left": (-1.0, 0.0), "right": (1.0, 0.0),
    "top-left": (-1.0, 1.0), "top-right": (1.0, 1.0), "bottom-left": (-1.0, -1.0), "bottom-right": (1.0, -1.0),
}


def _nodes(objs: Sequence[object], verb: str) -> list["Node"]:
    from ..objects.node import Node

    if not objs:
        raise KinemoError.make("K0105", f"k.{verb} needs at least one object")
    for o in objs:
        if not isinstance(o, Node):
            raise KinemoError.make("K0105", f"k.{verb} takes objects, got {type(o).__name__}")
    return [o for o in objs if isinstance(o, Node)]


def _ramp(s: "Scene", node: "Node", prop: str, start: float, duration: float, ease: Ease, a: Any, b: Any, span: Span) -> None:
    """Hidden-prop animation from `a` to `b` (explicit start value)."""
    sig = node._sig(prop)
    src_b = {"k": "val", "v": encode(b, sig.kind)}
    if duration <= 0:
        s._push_entry(sig, {"k": "set", "t": start, "src": src_b, "span": span.ir()}, src_b)
        return
    s._push_entry(
        sig,
        {
            "k": "anim",
            "t0": start,
            "t1": start + duration,
            "from": {"k": "val", "v": encode(a, sig.kind)},
            "to": src_b,
            "ease": ease.ir(),
            "span": span.ir(),
        },
        src_b,
    )


def _set(s: "Scene", node: "Node", prop: str, t: float, value: Any, span: Span) -> None:
    sig = node._sig(prop)
    src = {"k": "val", "v": encode(value, sig.kind)}
    s._push_entry(sig, {"k": "set", "t": t, "src": src, "span": span.ir()}, src)


def _protocol(node: "Node", method: str) -> Any:
    """A component's own `enter()`/`exit()`/`indicate()`, if it defines one."""
    fn = getattr(type(node), method, None)
    return getattr(node, method) if callable(fn) else None


def _emit_protocol(s: "Scene", anim: Animation, start: float, duration: float) -> float:
    natural = anim.total
    k = duration / natural if natural > 0 else 1.0
    return anim.emit(s, start, k, None)


def _enter_with_protocol(s: "Scene", node: "Node", start: float, duration: float) -> bool:
    """Runs the component's own `enter()`; returns False when it has none."""
    enter = _protocol(node, "enter")
    if enter is None:
        return False
    s._enter_shallow(node, start)
    s._enter_rest(node, _emit_protocol(s, enter(), start, duration))
    return True


class Verb(Animation):
    name = "verb"

    def describe(self) -> str:
        return f"{self.name}({', '.join(o._label() for o in self.objs)})"

    def __init__(self, objs: Sequence[Node], duration: float | None, ease: EaseLike | None, delay: float, span: Span) -> None:
        super().__init__(duration, ease, delay, span)
        self.objs = _nodes(objs, self.name)


class Draw(Verb):
    """Traces the outline, then fills."""
    enters = True

    name = "draw"
    prop = "_draw"

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        for o in self.objs:
            if _enter_with_protocol(s, o, start, duration):
                continue
            s._enter(o, start)
            for leaf in o._leaves(start):
                _ramp(s, leaf, self.prop, start, duration, ease, 0.0, 1.0, self.span)


class Write(Draw):
    """Writes character by character (text); other objects are drawn."""

    name = "write"

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        for o in self.objs:
            if _enter_with_protocol(s, o, start, duration):
                continue
            s._enter(o, start)
            from ..objects.text import TextLike

            if isinstance(o, TextLike):
                _ramp(s, o, "_write", start, duration, ease, 0.0, 1.0, self.span)
                continue
            for leaf in o._leaves(start):
                prop = "_write" if leaf.kind in ("text", "glyphs") else "_draw"
                _ramp(s, leaf, prop, start, duration, ease, 0.0, 1.0, self.span)


class FadeIn(Verb):
    enters = True

    name = "fade_in"

    def __init__(self, objs: Sequence[Node], shift: VecLike | None, duration: float | None, ease: EaseLike | None, delay: float, span: Span) -> None:
        super().__init__(objs, duration, ease, delay, span)
        self.shift = shift

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        for o in self.objs:
            if _enter_with_protocol(s, o, start, duration):
                continue
            s._enter(o, start)
            _ramp(s, o, "_fade", start, duration, ease, 0.0, 1.0, self.span)
            if self.shift is not None:
                dx, dy = self.shift
                _ramp(s, o, "_shift", start, duration, ease, (-dx, -dy), (0.0, 0.0), self.span)


class FadeOut(Verb):
    name = "fade_out"

    def __init__(self, objs: Sequence[Node], shift: VecLike | None, duration: float | None, ease: EaseLike | None, delay: float, span: Span) -> None:
        super().__init__(objs, duration, ease, delay, span)
        self.shift = shift

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        end = start + duration
        for o in self.objs:
            s._check_alive(o, start, self.span)
            if (leave := _protocol(o, "exit")) is not None:
                s._exit(o, _emit_protocol(s, leave(), start, duration))
                continue
            _ramp(s, o, "_fade", start, duration, ease, 1.0, 0.0, self.span)
            if self.shift is not None:
                _ramp(s, o, "_shift", start, duration, ease, (0.0, 0.0), tuple(self.shift), self.span)
            s._exit(o, end)
            _set(s, o, "_fade", end, 1.0, self.span)
            if self.shift is not None:
                _set(s, o, "_shift", end, (0.0, 0.0), self.span)


def _anchor(name: str) -> tuple[float, float]:
    if name not in ANCHORS:
        raise KinemoError.make("K0404", f"unknown anchor {name!r}", fixes=[(f"use one of {', '.join(sorted(ANCHORS))}", None)])
    return ANCHOR_UNITS[name]


class Grow(Verb):
    @property
    def enters(self) -> bool:  # type: ignore[override]
        return bool(getattr(self, "entering", False))

    name = "grow"

    def __init__(self, objs: Sequence[Node], origin: str, entering: bool, duration: float | None, ease: EaseLike | None, delay: float, span: Span) -> None:
        super().__init__(objs, duration, ease, delay, span)
        self.origin = _anchor(origin)
        self.entering = entering
        self.name = "grow" if entering else "shrink"

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        end = start + duration
        a, b = (0.0, 1.0) if self.entering else (1.0, 0.0)
        for o in self.objs:
            if self.entering:
                if _enter_with_protocol(s, o, start, duration):
                    continue
                s._enter(o, start)
            else:
                s._check_alive(o, start, self.span)
                if (leave := _protocol(o, "exit")) is not None:
                    s._exit(o, _emit_protocol(s, leave(), start, duration))
                    continue
            scaled, faded = o._grow_parts()
            for n in scaled:
                _set(s, n, "_grow_from", start, self.origin, self.span)
                _ramp(s, n, "_grow", start, duration, ease, a, b, self.span)
            for n in faded:
                _ramp(s, n, "_fade", start, duration, ease, a, b, self.span)
            if not self.entering:
                s._exit(o, end)
                for n in scaled:
                    _set(s, n, "_grow", end, 1.0, self.span)
                for n in faded:
                    _set(s, n, "_fade", end, 1.0, self.span)


class Indicate(Animation):
    """Temporary emphasis: tint and pulse, back to the initial state at the end."""

    def describe(self) -> str:
        return f"indicate({self.obj._label()})"

    def __init__(self, obj: "Node", color: ColorLike, scale: float, phase: str, duration: float | None, ease: EaseLike | None, delay: float, span: Span) -> None:
        super().__init__(duration, ease, delay, span)
        self.obj = _nodes([obj], "indicate")[0]
        self.color = parse_color(color)
        self.scale = float(scale)
        self.phase = phase

    def split_for_during(self, s: "Scene") -> tuple[Animation, Animation]:
        mk = lambda phase: Indicate(self.obj, self.color, self.scale, phase, self.duration, self.ease, 0.0, self.span)  # noqa: E731
        return mk("in"), mk("out")

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        o = self.obj
        s._check_alive(o, start, self.span)
        # An object can hand the emphasis to one of its parts (a chart bar to its rectangle).
        from ..objects.node import Node

        target = getattr(o, "_indicate_target", None)
        if callable(target) and isinstance(part := target(), Node):
            o = part
        if self.phase == "full" and (custom := _protocol(o, "indicate")) is not None:
            _emit_protocol(s, custom(), start, duration)
            return
        _set(s, o, "_tint", start, self.color, self.span)
        if self.phase == "full":
            half = duration / 2
            _ramp(s, o, "_tint_amount", start, half, ease, 0.0, 1.0, self.span)
            _ramp(s, o, "_pulse", start, half, ease, 1.0, self.scale, self.span)
            _ramp(s, o, "_tint_amount", start + half, half, ease, 1.0, 0.0, self.span)
            _ramp(s, o, "_pulse", start + half, half, ease, self.scale, 1.0, self.span)
        elif self.phase == "in":
            _ramp(s, o, "_tint_amount", start, duration, ease, 0.0, 1.0, self.span)
            _ramp(s, o, "_pulse", start, duration, ease, 1.0, self.scale, self.span)
        else:
            _ramp(s, o, "_tint_amount", start, duration, ease, 1.0, 0.0, self.span)
            _ramp(s, o, "_pulse", start, duration, ease, self.scale, 1.0, self.span)


# ---- public verbs ------------------------------------------------------------------

def draw(*objs: "Node", duration: float | None = None, ease: EaseLike | None = None, delay: float = 0.0) -> Animation:
    """Entry: trace the outline, then fill."""
    return Draw(objs, duration, ease, delay, user_span())


def write(*objs: "Node", duration: float | None = None, ease: EaseLike | None = None, delay: float = 0.0) -> Animation:
    """Entry: write text character by character (math and code too)."""
    return Write(objs, duration, ease, delay, user_span())


def fade_in(*objs: "Node", shift: VecLike | None = None, duration: float | None = None, ease: EaseLike | None = None, delay: float = 0.0) -> Animation:
    """Entry: opacity 0 → 1, optionally arriving from `-shift`."""
    return FadeIn(objs, shift, duration, ease, delay, user_span())


def fade_out(*objs: "Node", shift: VecLike | None = None, duration: float | None = None, ease: EaseLike | None = None, delay: float = 0.0) -> Animation:
    """Exit: opacity 1 → 0, then the objects leave the scene."""
    return FadeOut(objs, shift, duration, ease, delay, user_span())


def grow(obj: "Node", from_: Anchor = "center", *, duration: float | None = None, ease: EaseLike | None = None, delay: float = 0.0) -> Animation:
    """Entry: scale up from a side or the center."""
    return Grow([obj], from_, True, duration, ease, delay, user_span())


def shrink(obj: "Node", to: Anchor = "center", *, duration: float | None = None, ease: EaseLike | None = None, delay: float = 0.0) -> Animation:
    """Exit: scale down towards a side or the center, then leave."""
    return Grow([obj], to, False, duration, ease, delay, user_span())


def indicate(obj: "Node", color: ColorLike = YELLOW, scale: float = 1.2, *, duration: float | None = None, ease: EaseLike | None = None, delay: float = 0.0) -> Animation:
    """Emphasis: temporary tint and pulse; the final state equals the initial one."""
    return Indicate(obj, color, scale, "full", duration, ease, delay, user_span())


def sound(path: str, gain: float = 1.0) -> Animation:
    """Play an audio file at the scheduled instant (relative paths start next to the scene)."""
    from ..objects.media_paths import resolve_media_path

    resolved = resolve_media_path(path, "k.sound")
    return Instant(lambda s, t: s._b.add_audio(resolved, t, float(gain), "sound"), span=user_span())


def music(path: str, gain: float = 0.3, duck: float = 0.25, fade: float = 1.0) -> Animation:
    """Background music from the scheduled instant: `duck` is its level while a voice speaks
    (0.25 = a quarter, 1 = no ducking), and it fades in over `fade` seconds and out at the end
    of the scene."""
    from ..objects.media_paths import resolve_media_path

    resolved = resolve_media_path(path, "k.music")
    level = float(duck)
    ducking = level if 0.0 < level < 1.0 else 0.0  # 1 (or more) keeps the music at its level
    return Instant(lambda s, t: s._b.add_audio(resolved, t, float(gain), "music", ducking, max(0.0, float(fade))), span=user_span())
