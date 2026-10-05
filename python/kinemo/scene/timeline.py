"""Timeline methods: the only way time passes in a scene."""

from __future__ import annotations

import math
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Iterator, Literal, cast

from .._runtime.spans import Span, user_span
from ..anim.animation import Animation, Par, check_duration, not_an_animation
from ..anim.ease import Ease, EaseLike, as_ease
from ..diagnostics import Collector, KinemoError
from .timespan import TimeSpan

if TYPE_CHECKING:
    from .._core import Builder
    from .scene import Scene


@dataclass(frozen=True)
class LogEntry:
    """One scheduled `play`/`start`, for timeline summaries."""

    start: float
    end: float
    label: str
    span: Span
    position: int
    #: The `s.play(...)`/`s.start(...)` call (where `duration=` and `ease=` are written).
    call: Span | None = None

    def warped(self, warp: Callable[[float], float]) -> "LogEntry":
        return LogEntry(warp(self.start), warp(self.end), self.label, self.span, self.position, self.call)


@dataclass(frozen=True)
class Statement:
    """A run of a statement that schedules time or acts at the cursor (`play`, `start`, `wait`,
    `wait_for`, `voice`, `add`, `remove`, `mark`), for the dev editor's code view. A statement
    in a loop has one run per iteration."""

    kind: str
    start: float
    end: float
    label: str
    span: Span
    position: int

    def warped(self, warp: Callable[[float], float]) -> "Statement":
        return Statement(self.kind, warp(self.start), warp(self.end), self.label, self.span, self.position)


class TimelineMixin:
    _b: "Builder"
    cursor: float
    _speed: float
    _max_end: float
    _marks: list[tuple[str | None, float, bool, int]]
    lints: Collector
    _log: list[LogEntry]
    _statements: list[Statement]

    # ---- scheduling ----------------------------------------------------------------
    def _as_animation(self, anims: tuple[object, ...]) -> Animation:
        if not anims:
            raise KinemoError.make("K0203", "nothing to animate", fixes=[("pass at least one animation", "s.play(k.draw(obj))")])
        checked: list[Animation] = []
        for a in anims:
            if not isinstance(a, Animation):
                raise not_an_animation(a)
            checked.append(a)
        return checked[0] if len(checked) == 1 else Par(checked, span=user_span(2))

    def _record(self, kind: str, start: float, end: float, label: str = "", span: Span | None = None) -> None:
        """Note a statement run for the code view."""
        self._statements.append(Statement(kind, start, end, label, span or user_span(), self._b.log_position()))

    def _schedule(self, anims: tuple[object, ...], duration: float | None, ease: EaseLike | None, at: float | None, kind: str = "start") -> TimeSpan:
        anim = self._as_animation(anims)
        k = self._speed
        if duration is not None:
            d = check_duration(duration)
            natural = anim.total
            k = (d / natural) * self._speed if natural > 0 else self._speed
        call = user_span()
        start = self.cursor if at is None else float(at)
        end = anim.emit(cast("Scene", self), start, k, as_ease(ease) if ease is not None else None)
        self._max_end = max(self._max_end, end)
        self._log.append(LogEntry(start, end, anim.describe(), anim.span, self._b.log_position(), call))
        self._record(kind, start, end, anim.describe(), call)
        return TimeSpan(start, end, cast("Scene", self))

    def play(self, *anims: Animation, duration: float | None = None, ease: EaseLike | None = None, at: float | None = None) -> TimeSpan:
        """Schedule at the cursor and advance it to the end. Several animations run in parallel."""
        if at is not None:
            self.lints.warn(
                "W0110",
                "play(..., at=) does not move the cursor",
                fixes=[("make the intent explicit", "s.start(..., at=...)")],
            )
            return self._schedule(anims, duration, ease, at, "play")
        span = self._schedule(anims, duration, ease, None, "play")
        self.cursor = span.end
        return span

    def start(self, *anims: Animation, duration: float | None = None, ease: EaseLike | None = None, at: float | None = None) -> TimeSpan:
        """Schedule without moving the cursor (background animation)."""
        return self._schedule(anims, duration, ease, at)

    def wait(self, d: float = 1.0) -> TimeSpan:
        """Advance the cursor by `d` seconds."""
        start = self.cursor
        self.cursor += check_duration(d, "wait") * self._speed
        self._record("wait", start, self.cursor, f"wait({d:g})")
        return TimeSpan(start, self.cursor, cast("Scene", self))

    def mark(self, name: str | None = None, slide: bool = False) -> float:
        """Time anchor at the cursor; `slide=True` makes it a slide break."""
        self._b.add_mark(self.cursor, name, slide)
        self._marks.append((name, self.cursor, slide, self._b.log_position()))
        self._record("mark", self.cursor, self.cursor, name or "mark")
        return self.cursor

    @property
    def marks(self) -> dict[str, float]:
        """Named marks: name → time in seconds."""
        return {n: t for n, t, _, _ in self._marks if n is not None}

    # ---- blocks ----------------------------------------------------------------------
    @contextmanager
    def during(
        self,
        *anims: Animation,
        duration: float | None = None,
        ease: EaseLike | None = None,
        revert: Literal["instant"] | float | Ease | None = None,
    ) -> Iterator[None]:
        """Apply state changes on entry and revert them, animated, on exit."""
        anim = self._as_animation(anims)
        apply, undo = anim.split_for_during(cast("Scene", self))
        self.play(apply, duration=duration, ease=ease)
        try:
            yield
        finally:
            if revert == "instant":
                self.play(undo, duration=0.0)
            elif isinstance(revert, int | float) and not isinstance(revert, bool):
                self.play(undo, duration=float(revert), ease=ease)
            elif isinstance(revert, Ease):
                self.play(undo, duration=duration, ease=revert)
            else:
                self.play(undo, duration=duration, ease=ease)

    @contextmanager
    def tempo(self, factor: float, to: float | None = None) -> Iterator[None]:
        """Multiply the speed of everything inside; `to=` ramps the speed across the block."""
        f0 = float(factor)
        if not math.isfinite(f0) or f0 <= 0:
            raise KinemoError.make("K0105", f"invalid tempo: {factor!r}", fixes=[("use a factor > 0", "s.tempo(2)")])
        if to is None:
            outer = self._speed
            self._speed = outer / f0
            try:
                yield
            finally:
                self._speed = outer
            return
        f1 = float(to)
        since, t0 = self._b.log_position(), self.cursor
        max_before = self._max_end
        try:
            yield
        finally:
            length = self.cursor - t0
            new_end = self._b.remap(since, t0, length, f0, f1)
            warp = lambda t: self._b.warp_time(t, t0, length, f0, f1)  # noqa: E731
            if self._max_end > max_before:
                self._max_end = max(max_before, warp(self._max_end))
            self._marks = [(n, warp(t) if pos >= since else t, sl, pos) for n, t, sl, pos in self._marks]
            self._log = [e.warped(warp) if e.position >= since else e for e in self._log]
            self._statements = [e.warped(warp) if e.position >= since else e for e in self._statements]
            self.cursor = new_end
