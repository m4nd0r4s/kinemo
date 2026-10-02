"""`k.Event` declarations and the event sources components, states and objects expose."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar, overload

if TYPE_CHECKING:
    from typing import Self

    # `k.Event` without a payload type means `k.Event[None]` (PEP 696 default).
    from typing_extensions import TypeVar as TypeVarWithDefault

    from ..reactive.expr import Val
    from ..scene.scene import Scene

    P = TypeVarWithDefault("P", default=None)
    P_co = TypeVarWithDefault("P_co", covariant=True, default=None)
else:
    P = TypeVar("P")
    P_co = TypeVar("P_co", covariant=True)

T = TypeVar("T")


class Event(Generic[P]):
    """Declaration in a component or state class body: `full: k.Event`, `bounce: k.Event[Impact]`.

    For the type checker the declaration is a descriptor: on an instance it reads as the
    concrete `EventSource[P]` the component (or simulation state) creates."""

    if TYPE_CHECKING:

        @overload
        def __get__(self, instance: None, owner: type[object]) -> Self: ...
        @overload
        def __get__(self, instance: object, owner: type[object]) -> EventSource[P]: ...
        def __get__(self, instance: object, owner: type[object]) -> EventSource[P] | Self: ...


@dataclass(frozen=True)
class EventInfo(Generic[P_co]):
    """One firing: `e.time`, `e.data` (typed payload), `e.count` (1-based), `e.value(sig)`."""

    time: float
    data: P_co
    count: int
    _scene: Any = None

    def value(self, sig: Val[T]) -> T:
        """Value of any signal or expression at the instant of the event."""
        from ..reactive.expr import lift
        from ..values.encode import decode

        s = self._scene
        return decode(json.loads(s._b.eval_expr(json.dumps(lift(sig)._ir()), self.time)))


#: `fn(s, e)`: what `@src.on` registers; it runs with its own cursor at `e.time`.
EventHandler = Callable[["Scene", EventInfo[P]], object]
HandlerT = TypeVar("HandlerT", bound=Callable[..., object])


class EventSource(Generic[P]):
    """A concrete event of one owner. React with `@src.on`, wait with `s.wait_for(src)`.

    Firings come from explicit `emit()` calls, from `k.when` conditions, from simulations
    and from computed sources (object lifecycle, end of an animation)."""

    def __init__(
        self,
        scene: "Scene",
        name: str,
        owner: Any = None,
        computed: Callable[[], list[tuple[float, Any]]] | None = None,
        bounded: bool = False,
    ) -> None:
        self._scene = scene
        self.name = name
        self.owner = owner
        #: Firings derived from the timeline itself (recomputed at every resolve pass).
        self.computed = computed
        #: Whether the source is guaranteed to stop firing (so `wait_for` needs no timeout).
        self.bounded = bounded or computed is not None
        self._id = scene._events.register(self)

    @overload
    def emit(self: EventSource[None]) -> None: ...
    @overload
    def emit(self, data: P) -> None: ...
    def emit(self, data: Any = None) -> None:
        """Fire at the cursor (in a build, clip or handler)."""
        self._scene._events.fire(self, self._scene.cursor, data)

    @overload
    def on(self, fn: EventHandler[P], *, once: bool = False) -> EventHandler[P]: ...
    @overload
    def on(self, fn: None = None, *, once: bool = False) -> Callable[[HandlerT], HandlerT]: ...
    def on(self, fn: Callable[..., object] | None = None, *, once: bool = False) -> Any:
        """`@src.on`: run `fn(s, e)` at each firing, with its own cursor at `e.time`."""

        def register(f: Callable[..., object]) -> Callable[..., object]:
            self._scene._events.handle(self, f, once)
            return f

        return register(fn) if fn is not None else register

    def __repr__(self) -> str:
        label = getattr(self.owner, "_label", None)
        owner = label() if callable(label) else ""
        return f"{owner}.{self.name}" if owner else self.name
