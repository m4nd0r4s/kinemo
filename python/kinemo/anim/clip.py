"""`@k.clip`: a sequence written with its own cursor, packaged as an animation."""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING, Any, Callable, Concatenate, Generic, ParamSpec, TypeVar, overload

from .._runtime.context import current_scene
from .._runtime.spans import Span, user_span
from .animation import Animation
from .ease import Ease

if TYPE_CHECKING:
    from ..scene.scene import Scene

P = ParamSpec("P")
Owner = TypeVar("Owner")


class Clip(Animation):
    """Runs its function at scheduling time with the cursor starting at the clip's start.
    Its length is where the inner cursor ends; it rescales like any animation."""

    def __init__(self, fn: Callable[..., None], args: tuple[Any, ...], kwargs: dict[str, Any], span: Span) -> None:
        super().__init__(duration=0.0, span=span)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self._natural: float | None = None
        self._forced: float | None = None

    @property  # type: ignore[override]
    def duration(self) -> float:
        if getattr(self, "_forced", None) is not None:
            return self._forced  # type: ignore[return-value]
        return self._measure()

    @duration.setter
    def duration(self, value: float) -> None:
        if hasattr(self, "_natural"):
            self._forced = value

    def _measure(self) -> float:
        """Natural length, measured by running the clip and rolling the scene back."""
        if self._natural is None:
            s = current_scene()
            with s._probe():
                start = s.cursor
                self._natural = self._run(s, start, 1.0) - start
        return self._natural

    def _rescale_to(self, duration: float) -> None:
        self._forced = duration

    def _run(self, s: "Scene", start: float, k: float) -> float:
        cursor, speed = s.cursor, s._speed
        s.cursor, s._speed = start, speed * k
        try:
            self.fn(s, *self.args, **self.kwargs)
            return s.cursor
        finally:
            s.cursor, s._speed = cursor, speed

    def emit(self, s: "Scene", t0: float, k: float, ease: Ease | None) -> float:
        if self._forced is not None:
            natural = self._measure()
            k = k * (self._forced / natural if natural > 0 else 0.0)
        return self._run(s, t0 + self.delay * k, k)

    def describe(self) -> str:
        return f"{getattr(self.fn, '__name__', 'clip')}(...)"


class ClipFunction(Generic[P]):
    """What `@k.clip` returns for a function `def name(s, ...)`: calling it with the
    remaining arguments builds a `Clip`, so `present(obj)` is checked against `obj`'s type."""

    def __init__(self, fn: Callable[..., None], bound: object = None) -> None:
        self.fn = fn
        self.bound = bound
        functools.update_wrapper(self, fn)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Clip:
        span = user_span()
        if self.bound is not None:
            target = self.bound
            fn = lambda s, *a, **kw: self.fn(target, s, *a, **kw)  # noqa: E731
            fn.__name__ = self.fn.__name__  # type: ignore[attr-defined]
            return Clip(fn, args, kwargs, span)
        return Clip(self.fn, args, kwargs, span)


class ClipMethod(ClipFunction[P], Generic[Owner, P]):
    """What `@k.clip` returns for a method `def name(self, s, ...)`: reading it from an
    instance gives the clip bound to that instance (`self.fill_up()`)."""

    @overload
    def __get__(self, obj: None, owner: object = None) -> "ClipMethod[Owner, P]": ...
    @overload
    def __get__(self, obj: Owner, owner: object = None) -> ClipFunction[P]: ...
    def __get__(self, obj: Owner | None, owner: object = None) -> "ClipMethod[Owner, P] | ClipFunction[P]":
        return self if obj is None else ClipFunction(self.fn, obj)


@overload
def clip(fn: Callable[Concatenate["Scene", P], None]) -> ClipFunction[P]: ...
@overload
def clip(fn: Callable[Concatenate[Owner, "Scene", P], None]) -> ClipMethod[Owner, P]: ...
def clip(fn: Callable[..., None]) -> Any:
    """`@k.clip def proof(s, tri): ...` → `s.play(proof(tri))`."""
    return ClipMethod(fn)
