"""The `Animation` value and its composition (`seq`, `par`, `stagger`)."""

from __future__ import annotations

import copy
import math
import random
from typing import TYPE_CHECKING, Callable, Literal, Sequence, TypedDict

from .._runtime.spans import Span, user_span
from ..diagnostics import KinemoError
from .ease import DEFAULT, Ease, EaseLike, as_ease

if TYPE_CHECKING:
    from ..scene.scene import Scene

DEFAULT_DURATION = 1.0

#: Orders of `k.stagger` (`"random(7)"` shuffles with seed 7).
StaggerOrder = Literal["sequence", "reverse", "center", "random"] | str


class AnimationTiming(TypedDict, total=False):
    """Timing keywords forwarded to an animation (`ax.zoom_to(x=..., duration=2)`)."""

    duration: float | None
    ease: EaseLike | None
    delay: float


def check_duration(d: float, what: str = "duration") -> float:
    if not isinstance(d, int | float) or not math.isfinite(d) or d < 0:
        raise KinemoError.make("K0202", f"invalid {what}: {d!r}", fixes=[("use a finite number ≥ 0", None)])
    return float(d)


class Animation:
    """Immutable: only has an effect when passed to `s.play` or `s.start`."""

    def __init__(self, duration: float | None = None, ease: EaseLike | None = None, delay: float = 0.0, span: Span | None = None) -> None:
        self.duration = check_duration(DEFAULT_DURATION if duration is None else duration)
        self.ease: Ease = as_ease(ease) if ease is not None else DEFAULT
        self.delay = check_duration(delay, "delay")
        self.span = span or user_span()
        self._explicit_ease = ease is not None

    @property
    def total(self) -> float:
        """Natural length including the delay, before any rescaling."""
        return self.delay + self.duration

    def with_(self, *, duration: float | None = None, ease: EaseLike | None = None, delay: float | None = None) -> "Animation":
        """A copy with other parameters."""
        out = copy.copy(self)
        if duration is not None:
            out._rescale_to(check_duration(duration))
        if ease is not None:
            out.ease = as_ease(ease)
            out._explicit_ease = True
        if delay is not None:
            out.delay = check_duration(delay, "delay")
        return out

    def _rescale_to(self, duration: float) -> None:
        self.duration = duration

    def emit(self, s: "Scene", t0: float, k: float, ease: Ease | None) -> float:
        """Schedule into the scene starting at `t0`, with every duration multiplied by `k`.
        Returns the time the animation actually ends."""
        start = t0 + self.delay * k
        self._emit(s, start, self.duration * k, ease if ease is not None else self.ease)
        return start + self.duration * k

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        raise NotImplementedError

    def describe(self) -> str:
        """Short human description for `kinemo check` timelines."""
        return type(self).__name__.lower()

    def split_for_during(self, s: "Scene") -> "tuple[Animation, Animation]":
        """(apply, revert) pair for `s.during`, computed before applying. Only state changes
        and emphasis can be reverted; everything else is K0204."""
        raise KinemoError.make(
            "K0204",
            f"{type(self).__name__} is not reversible and cannot be used in s.during",
            spans=[self.span],
            fixes=[("use state changes (.to) or k.indicate inside during", None)],
        )


class Composite(Animation):
    """Children scheduled relative to each other. The natural length is computed lazily, so
    children whose length is only known by running them (clips) cost nothing until needed."""

    def __init__(self, children: Sequence[Animation], span: Span | None = None) -> None:
        for c in children:
            if not isinstance(c, Animation):
                raise not_an_animation(c)
        self.children = list(children)
        super().__init__(duration=0.0, span=span)
        self._forced_duration: float | None = None

    @property  # type: ignore[override]
    def duration(self) -> float:
        forced = getattr(self, "_forced_duration", None)
        return forced if forced is not None else self._natural()

    @duration.setter
    def duration(self, value: float) -> None:
        self._forced_duration = value

    def _natural(self) -> float:
        raise NotImplementedError

    def _rescale_to(self, duration: float) -> None:
        self._forced_duration = duration

    def emit(self, s: "Scene", t0: float, k: float, ease: Ease | None) -> float:
        inner_k = k
        if self._forced_duration is not None:
            natural = self._natural()
            inner_k = k * (self._forced_duration / natural if natural > 0 else 0.0)
        override = ease if ease is not None else (self.ease if self._explicit_ease else None)
        return self._emit_children(s, t0 + self.delay * k, inner_k, override)

    def _emit_children(self, s: "Scene", start: float, k: float, ease: Ease | None) -> float:
        raise NotImplementedError


class Seq(Composite):
    def describe(self) -> str:
        return "seq(" + ", ".join(c.describe() for c in self.children) + ")"

    def _natural(self) -> float:
        return sum(c.total for c in self.children)

    def _emit_children(self, s: "Scene", start: float, k: float, ease: Ease | None) -> float:
        t = start
        for c in self.children:
            t = c.emit(s, t, k, ease)
        return t


class Par(Composite):
    def describe(self) -> str:
        return ", ".join(c.describe() for c in self.children)

    def _natural(self) -> float:
        return max((c.total for c in self.children), default=0.0)

    def _emit_children(self, s: "Scene", start: float, k: float, ease: Ease | None) -> float:
        # Parallel means "at the same instant": entries go first so `s.play(obj.to(...),
        # k.fade_in(obj))` works in any argument order.
        ordered = sorted(self.children, key=lambda c: not getattr(c, "enters", False))
        return max((c.emit(s, start, k, ease) for c in ordered), default=start)

    def split_for_during(self, s: "Scene") -> "tuple[Animation, Animation]":
        pairs = [c.split_for_during(s) for c in self.children]
        return Par([a for a, _ in pairs], span=self.span), Par([r for _, r in pairs], span=self.span)


class Stagger(Composite):
    def __init__(self, children: Sequence[Animation], lag: float, order: str = "sequence", span: Span | None = None) -> None:
        self.lag = check_duration(lag, "lag")
        self.order = order
        super().__init__(children, span=span)
        rank = {child: r for r, child in enumerate(self._order())}
        self._offsets = [rank[i] * self.lag for i in range(len(self.children))]

    def _order(self) -> list[int]:
        n = len(self.children)
        idx = list(range(n))
        if self.order == "sequence" or n == 0:
            return idx
        if self.order == "reverse":
            return idx[::-1]
        if self.order == "center":
            mid = (n - 1) / 2
            return sorted(idx, key=lambda i: (abs(i - mid), i))
        if self.order.startswith("random"):
            seed = int(self.order[7:-1]) if self.order.startswith("random(") else 0
            random.Random(seed).shuffle(idx)
            return idx
        raise KinemoError.make("K0105", f"unknown stagger order: {self.order!r}",
                               fixes=[("use 'sequence', 'reverse', 'center' or 'random(seed)'", None)])

    def describe(self) -> str:
        labels = list(dict.fromkeys(c.describe() for c in self.children))
        if len(labels) <= 3:
            return f"stagger({', '.join(labels)})"
        return f"stagger({len(self.children)} × {labels[0]}, ...)"

    def _natural(self) -> float:
        return max((o + c.total for o, c in zip(self._offsets, self.children)), default=0.0)

    def _emit_children(self, s: "Scene", start: float, k: float, ease: Ease | None) -> float:
        ends = [c.emit(s, start + off * k, k, ease) for off, c in zip(self._offsets, self.children)]
        return max(ends, default=start)


class Instant(Animation):
    """A zero-length action (used for `k.sound`, `s.add` inside compositions)."""

    def __init__(self, action: Callable[["Scene", float], object], span: Span | None = None) -> None:
        super().__init__(duration=0.0, span=span)
        self.action = action

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        self.action(s, start)


def not_an_animation(value: object) -> KinemoError:
    from ..diagnostics.manim import manim_hint

    hint = manim_hint(value)
    if hint is not None:
        return hint
    return KinemoError.make(
        "K0203",
        f"expected an animation, got {type(value).__name__}",
        fixes=[("use a k verb or .to()", "s.play(k.draw(obj))")],
    )


def seq(*anims: Animation) -> Animation:
    """In sequence."""
    return Seq(anims, span=user_span())


def par(*anims: Animation) -> Animation:
    """In parallel. `s.play(a, b)` is defined as `s.play(k.par(a, b))`."""
    return Par(anims, span=user_span())


def stagger(anims: Sequence[Animation], lag: float = 0.1, order: StaggerOrder = "sequence") -> Animation:
    """Each animation starts `lag` seconds after the previous (spatial orders: center, random(seed))."""
    return Stagger(list(anims), lag, order, span=user_span())
