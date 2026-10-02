"""Signals: values with a timeline. Every object prop is a signal too."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any, Callable, Final, Literal, TypeVar, overload

from .._runtime.context import current_scene, tracing
from .._runtime.spans import user_span
from ..values.encode import encode, infer_kind
from ..values.vec import Vec
from .expr import IR, Expr, Val, is_reactive, lift

if TYPE_CHECKING:
    from ..anim.animation import Animation
    from ..anim.ease import EaseLike
    from ..scene.scene import Scene

T = TypeVar("T")

#: How a signal moves between two values (`k.lerp.*`).
LerpMode = Literal["linear", "round", "step_end", "step_start", "pointwise", "layout"]
#: How an animation combines with the value it starts from.
Blend = Literal["replace", "add"]


class lerp:
    """Interpolation modes for `k.signal(..., lerp=)`."""

    linear: Final = "linear"
    round: Final = "round"
    step: Final = "step_end"
    step_start: Final = "step_start"
    pointwise: Final = "pointwise"
    layout: Final = "layout"


def source_ir(value: object, kind: str) -> IR:
    """A timeline source: a constant value or a live expression (binding)."""
    if is_reactive(value):
        return {"k": "expr", "e": lift(value, kind)._ir()}
    return {"k": "val", "v": encode(value, kind)}


class Signal(Expr[T]):
    """A value that changes over the timeline: `.set` (instant), `.to` (animated), `.now`.

    `k.Signal[float]` in annotations (scene params, component code)."""

    __slots__ = ("_scene", "_id", "kind", "lerp")

    def __init__(self, scene: "Scene", sid: int, kind: str, lerp_mode: str = "linear") -> None:
        self._scene = scene
        self._id = sid
        self.kind = kind
        self.lerp = lerp_mode

    def _ir(self) -> IR:
        return {"op": "sig", "id": self._id}

    @property
    def now(self) -> T:
        """Value at the build cursor."""
        if tracing():
            return super().now
        from ..values.encode import decode

        self._scene._refresh_tables()
        return decode(json.loads(self._scene._b.eval_signal(self._id, self._scene.cursor)))

    def set(self, value: Val[T]) -> None:
        """Instant change at the cursor. Passing a signal or lambda creates a binding."""
        self._scene._push_set(self, value, user_span())

    def to(
        self,
        value: Val[T],
        *,
        duration: float | None = None,
        ease: EaseLike | None = None,
        delay: float = 0.0,
        blend: Blend = "replace",
    ) -> Animation:
        """Animated change from the value at the cursor to `value`."""
        from ..anim.prop import PropTo

        return PropTo([(self, value)], duration=duration, ease=ease, delay=delay, blend=blend, span=user_span())

    def unbind(self) -> None:
        """Drop a reactive binding, keeping the current value."""
        self._scene._push_set(self, self.now, user_span())

    def __repr__(self) -> str:
        names: dict[int, str] = getattr(self._scene, "_signal_names", {})
        return names.get(self._id) or f"Signal#{self._id}({self.kind})"


@overload
def signal(initial: bool, *, lerp: LerpMode | None = "linear", kind: str | None = None) -> Signal[bool]: ...  # pyright: ignore[reportOverlappingOverload] - bool before float
@overload
def signal(initial: float, *, lerp: LerpMode | None = "linear", kind: str | None = None) -> Signal[float]: ...
@overload
def signal(initial: tuple[float, float], *, lerp: LerpMode | None = "linear", kind: str | None = None) -> Signal[Vec]: ...
@overload
def signal(initial: T, *, lerp: LerpMode | None = "linear", kind: str | None = None) -> Signal[T]: ...
def signal(initial: object, *, lerp: LerpMode | None = "linear", kind: str | None = None) -> Signal[Any]:
    """`k.signal(1.0)`: a free signal. `lerp=None` switches values in steps."""
    s = current_scene()
    k = kind or infer_kind(initial)
    mode = "step_end" if lerp is None else lerp
    if k in ("str", "bool") and lerp == "linear":
        mode = "step_end"
    span = user_span()
    sid = s._b.add_signal(json.dumps(encode(initial, k)), mode, None, json.dumps(span.ir()))
    match = re.match(r"^\s*([A-Za-z_]\w*)\s*=\s*(?:\w+\.)?signal\(", span.source_line())
    if match:
        s.__dict__.setdefault("_signal_names", {})[sid] = match.group(1)
    return Signal(s, sid, k, mode)


@overload
def computed(fn: Callable[[], Expr[T]]) -> Expr[T]: ...
@overload
def computed(fn: Callable[[], T]) -> Expr[T]: ...
def computed(fn: Callable[[], object]) -> Expr[Any]:
    """`k.computed(lambda: f(a(), b()))`: a derived value with several dependencies."""
    from .tracer import trace

    return trace(fn)
