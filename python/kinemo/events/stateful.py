"""State with memory: `k.integrate`, `k.simulate` and `k.State`.

Their values depend on history, so they are precomputed into tables during resolve
(and recomputed when handlers change what they read); the render only reads tables."""

from __future__ import annotations

import copy
import math
import typing
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar

from .._runtime.context import current_scene
from .._runtime.spans import Span, user_span
from ..anim.animation import Animation
from ..anim.ease import Ease
from ..diagnostics import KinemoError
from ..reactive.expr import Expr, Op, Time, lift
from . import numeric
from .event import Event, EventSource

if TYPE_CHECKING:
    from typing import Self

    from ..scene.scene import Scene
    from ..values.aliases import FloatVal

#: Simulated time while a `step` function runs (signals read with `x()` use it).
sim_time: ContextVar[float | None] = ContextVar("kinemo_sim_time", default=None)


class Stateful:
    """Something whose table must be (re)computed in the resolve phase."""

    def compute(self, s: "Scene", horizon: float) -> None:
        raise NotImplementedError


@dataclass
class Integral(Stateful):
    rate: Expr
    by: Expr
    initial: float
    clamp: tuple[float, float] | None
    since: float
    table: int
    span: Span

    def compute(self, s: "Scene", horizon: float) -> None:
        dt = s._resolve_dt()
        n = max(2, int(math.ceil((horizon - self.since) / dt)) + 1)
        values = numeric.integrate(s._b, self.rate._ir(), self.by._ir(), self.initial, self.clamp, self.since, dt, n)
        s._b.set_table(self.table, self.since, dt, values)


def integrate(expr: FloatVal, d: FloatVal | None = None, *, initial: float = 0.0, clamp: tuple[float, float] | None = None) -> Expr[float]:
    """`k.integrate(power / capacity, d=hour, initial=0.2, clamp=(0, 1))`.

    Integrates with respect to the variation of `d` (default `k.time`), from the cursor."""
    s = current_scene()
    table = s._b.add_table()
    item = Integral(lift(expr), lift(d) if d is not None else Time(), float(initial), clamp, s.cursor, table, user_span())
    s._statefuls.append(item)
    s._tables_dirty = True
    return Op("table", {"table": table})


# ---- simulations ----------------------------------------------------------------------


class State:
    """Base of simulation states: plain fields (floats, bools, pairs) plus `k.Event`s.

        class Ball(k.State):
            y: float = 4.0
            v: float = 0.0
            bounce: k.Event[Impact]
    """

    _state_fields: typing.ClassVar[dict[str, Any]] = {}
    _state_events: typing.ClassVar[tuple[str, ...]] = ()

    def __init_subclass__(cls, **kw: Any) -> None:
        super().__init_subclass__(**kw)
        import inspect

        try:
            hints = inspect.get_annotations(cls, eval_str=True)
        except Exception:  # noqa: BLE001
            hints = dict(inspect.get_annotations(cls))
        fields: dict[str, Any] = dict(getattr(cls, "_state_fields", {}))
        events: list[str] = list(getattr(cls, "_state_events", ()))
        for name, tp in hints.items():
            origin = typing.get_origin(tp) or tp
            if origin is Event or (isinstance(tp, str) and "Event" in tp):
                events.append(name)
            else:
                fields[name] = cls.__dict__.get(name, 0.0)
        cls._state_fields = fields
        cls._state_events = tuple(events)

    def __init__(self, **values: object) -> None:
        unknown = set(values) - set(self._state_fields)
        if unknown:
            raise KinemoError.make("K0105", f"{type(self).__name__} has no fields {', '.join(sorted(unknown))}")
        for name, default in self._state_fields.items():
            object.__setattr__(self, name, values.get(name, default))
        object.__setattr__(self, "_emitter", None)

    def replace(self, **changes: object) -> Self:
        """A copy with some fields changed (states are values)."""
        out = copy.copy(self)
        for name, value in changes.items():
            if name not in self._state_fields:
                raise KinemoError.make("K0105", f"{type(self).__name__} has no field {name}")
            object.__setattr__(out, name, value)
        return out

    if not TYPE_CHECKING:
        # Events read as `EventSource[P]` through their `k.Event[P]` declarations (a
        # descriptor for the type checker); fields are plain annotated attributes.
        def __getattr__(self, name: str) -> Any:
            if name in type(self)._state_events:
                emitter = self.__dict__.get("_emitter")
                if emitter is None:
                    raise KinemoError.make("K0105", f"event {name} can only be emitted during the simulation")
                return emitter(name)
            raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        raise KinemoError.make("K0105", "states are values: use st.replace(field=...)", fixes=[("return a new state", "return st.replace(y=y, v=v)")])


class _Emit:
    def __init__(self, sim: "Simulation", name: str) -> None:
        self.sim = sim
        self.name = name

    def emit(self, data: Any = None) -> None:
        t = sim_time.get()
        assert t is not None
        self.sim._pending.append((self.name, t, data))


StateT = TypeVar("StateT", bound=State)


class Simulation(Animation, Stateful, Generic[StateT]):
    """`k.simulate(step, state, dt, until)`: fixed-step Python simulation started with
    `s.start(sim)`. Every field becomes a signal (`sim.y`); events become sources."""

    def __init__(self, step: Callable[[StateT, float], StateT], state: StateT, dt: float, until: float | None, span: Span) -> None:
        s = current_scene()
        super().__init__(duration=until or 0.0, span=span)
        self.step = step
        self.state = state
        self.dt = dt
        self.until = until
        self._scene = s
        self._start: float | None = None
        self._pending: list[tuple[str, float, Any]] = []
        self._tables = {name: s._b.add_table() for name in type(state)._state_fields}
        self._sources = {name: EventSource(s, name, self, bounded=until is not None) for name in type(state)._state_events}
        #: Fires when the simulation ends (`until=`).
        self.done: EventSource[None] = EventSource(s, "done", self, bounded=True)
        s._statefuls.append(self)

    def __getattr__(self, name: str) -> Any:
        """`sim.y` (an `Expr[float]` of the field) and `sim.bounce` (an `EventSource`):
        mirrored from the state class, so typed `Any` (no static mapping of fields)."""
        tables = self.__dict__.get("_tables", {})
        if name in tables:
            return Op("table", {"table": tables[name]})
        sources = self.__dict__.get("_sources", {})
        if name in sources:
            return sources[name]
        raise AttributeError(name)

    def __hash__(self) -> int:
        return id(self)

    def _emit(self, s: "Scene", start: float, duration: float, ease: Ease) -> None:
        self._start = start
        s._tables_dirty = True

    def emit(self, s: "Scene", t0: float, k: float, ease: Ease | None) -> float:
        start = t0 + self.delay * k
        self._emit(s, start, 0.0, self.ease)
        return start + (self.until or 0.0)

    def compute(self, s: "Scene", horizon: float) -> None:
        names = list(type(self.state)._state_fields)
        start = self._start
        if start is None:
            for name in names:
                value = _as_float(getattr(self.state, name))
                s._b.set_table(self._tables[name], 0.0, 1.0, [value])
            return
        end = start + self.until if self.until is not None else horizon
        steps = max(1, int(math.ceil((end - start) / self.dt)))
        columns: dict[str, list[float]] = {n: [_as_float(getattr(self.state, n))] for n in names}
        self._pending.clear()
        state = self.state
        emitter = lambda name: _Emit(self, name)  # noqa: E731
        object.__setattr__(state, "_emitter", emitter)
        for i in range(steps):
            token = sim_time.set(start + (i + 1) * self.dt)
            try:
                state = self.step(state, self.dt)
            finally:
                sim_time.reset(token)
            if not isinstance(state, State):
                raise KinemoError.make("K0105", f"the simulation step must return a {type(self.state).__name__}", spans=[self.span])
            object.__setattr__(state, "_emitter", emitter)
            for n in names:
                columns[n].append(_as_float(getattr(state, n)))
        for n in names:
            s._b.set_table(self._tables[n], start, self.dt, columns[n])
        for name, t, data in self._pending:
            s._events.fire(self._sources[name], t, data, generated=True)
        s._events.fire(self.done, end, None, generated=True)

    def describe(self) -> str:
        return f"simulate({getattr(self.step, '__name__', 'step')})"


def _as_float(v: Any) -> float:
    return float(v) if not isinstance(v, bool) else (1.0 if v else 0.0)


def simulate(step: Callable[[StateT, float], StateT], state: StateT, dt: float = 1 / 240, until: float | None = None) -> Simulation[StateT]:
    """Fixed-step simulation: `step(state, dt) -> state`, run in Python during resolve."""
    if not isinstance(state, State):
        raise KinemoError.make("K0105", "k.simulate expects a k.State", fixes=[("declare the state", "class Ball(k.State): y: float = 4.0")])
    return Simulation(step, state, float(dt), until, user_span())
