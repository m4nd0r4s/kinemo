"""Scene side of events: handlers with their own cursor, `s.wait_for`, table refresh."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from .._runtime.spans import user_span
from ..diagnostics import KinemoError
from ..events.event import EventInfo, EventSource

if TYPE_CHECKING:
    from .._core import Builder
    from ..events.event import P
    from ..events.registry import EventRegistry

#: Integrals and edge searches sample at this rate (s).
RESOLVE_DT = 1.0 / 240.0


class EventsMixin:
    _b: "Builder"
    cursor: float

    if TYPE_CHECKING:

        def _record(self, kind: str, start: float, end: float, label: str = "", span: Any = None) -> None: ...
    _speed: float
    _max_end: float
    _events: "EventRegistry"
    _statefuls: list[Any]
    _tables_dirty: bool
    _component_stack: list[Any]
    _handler_nodes: list[Any]

    def _resolve_dt(self) -> float:
        return RESOLVE_DT

    def _building_component(self) -> Any:
        return self._component_stack[-1] if self._component_stack else None

    def _horizon(self) -> float:
        return max(self.cursor, self._max_end) + self.config.tail  # type: ignore[attr-defined]

    def _refresh_tables(self) -> None:
        """Before reading state with memory at the cursor, make sure its tables exist."""
        if self._tables_dirty and self._statefuls:
            from ..events.resolve import compute_tables

            compute_tables(self, self._horizon())  # type: ignore[arg-type]

    def _run_handler(self, fn: Callable[..., object], e: EventInfo[Any]) -> None:
        cursor, speed = self.cursor, self._speed
        before = len(self._nodes)  # type: ignore[attr-defined]
        self.cursor, self._speed = e.time, 1.0
        try:
            fn(self, e)
        finally:
            self.cursor, self._speed = cursor, speed
        self._handler_nodes.extend(self._nodes[before:])  # type: ignore[attr-defined]

    def wait_for(self, event: EventSource[P], count: int = 1, timeout: float | None = None) -> EventInfo[P]:
        """Move the cursor to the `count`-th firing of `event` after it (what is scheduled so far)."""
        from ..events.resolve import firings_of

        span = user_span()
        if not isinstance(event, EventSource):
            raise KinemoError.make("K0105", f"s.wait_for expects an event, got {type(event).__name__}", spans=[span])
        if timeout is None and not event.bounded:
            raise KinemoError.make(
                "K0702",
                f"'{event!r}' is not guaranteed to end: s.wait_for needs timeout=",
                spans=[span],
                fixes=[("set a limit", f"s.wait_for({event.name}, timeout=20)")],
            )
        horizon = self.cursor + timeout if timeout is not None else self._horizon()
        firings = firings_of(self, event, horizon)  # type: ignore[arg-type]
        after = [f for f in firings if f.t > self.cursor + 1e-9 and f.t <= horizon + 1e-9]
        if len(after) >= count:
            f = after[count - 1]
            index = firings.index(f) + 1
            self._record("wait_for", self.cursor, f.t, f"wait_for({event!r})")
            self.cursor = f.t
            return EventInfo(f.t, f.data, index, self)
        before = [f for f in firings if f.t <= self.cursor + 1e-9]
        if before and not after:
            raise KinemoError.make(
                "K0703",
                f"'{event!r}' already happened at t = {before[-1].t:.2f} s, before the cursor ({self.cursor:.2f} s)",
                spans=[span],
                time=self.cursor,
                fixes=[("start the earlier animation without blocking the cursor", "s.start(...)  # instead of s.play(...)")],
            )
        detail = self._why_not_fired(event, horizon)
        raise KinemoError.make(
            "K0702",
            f"'{event!r}' did not fire {count}× by t = {horizon:.2f} s{detail}",
            spans=[span],
            time=horizon,
            fixes=[("increase the timeout or check the condition", None)],
        )

    def _why_not_fired(self, event: EventSource[Any], horizon: float) -> str:
        from ..events import numeric

        from ..reactive.expr import Op

        for effect in self._events.effects:
            if effect.action is not event:
                continue
            cond = effect.cond
            # For a comparison, report the measured side: "x >= 1" → the peak of x.
            if isinstance(cond, Op) and cond.op == "bin" and cond.fields.get("f") in ("ge", "gt", "le", "lt"):
                side = cond.fields["a"]
                peak, when = numeric.extreme(self._b, side._ir(), self.cursor, horizon, 1 / 30)
                if cond.fields["f"] in ("le", "lt"):
                    low, at = numeric.extreme(self._b, (-side)._ir(), self.cursor, horizon, 1 / 30)
                    return f" (minimum {-low:.3g} at t = {at:.2f} s)"
                return f" (maximum {peak:.3g} at t = {when:.2f} s)"
            return " (the condition never became true)"
        return ""
