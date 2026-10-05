"""Speculative runs and checkpoints: execute build code, then roll the scene back.

Used to measure clips (`_probe`) and by the resolve phase, which re-runs event handlers
from the same starting point until the timeline stops changing (`_checkpoint`)."""

from __future__ import annotations

import copy
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Callable, Iterator

if TYPE_CHECKING:
    from .._core import Builder

_SCALARS = ("cursor", "_speed", "_max_end", "_tables_dirty")
_CONTAINERS = ("_base", "_marks", "_tables", "_log", "_statements", "_statefuls", "_exits")


class ProbeMixin:
    _b: "Builder"
    _nodes: list[Any]

    def _capture(self) -> dict[str, Any]:
        state: dict[str, Any] = {n: getattr(self, n) for n in _SCALARS if hasattr(self, n)}
        state.update({n: copy.copy(getattr(self, n)) for n in _CONTAINERS if hasattr(self, n)})
        state["_events"] = self._events.copy()  # type: ignore[attr-defined]
        state["#nodes"] = len(self._nodes)
        state["#lints"] = len(self.lints.items)  # type: ignore[attr-defined]
        state["#node_state"] = [
            (n, list(n._place_log), dict(n._sigs), n._parent, {k: list(v) for k, v in n._binding_log.items()})
            for n in self._nodes
        ]
        return state

    def _restore(self, state: dict[str, Any]) -> None:
        for name, value in state.items():
            if not name.startswith("#"):
                setattr(self, name, copy.copy(value) if name in _CONTAINERS else value)
        self._events = state["_events"].copy()  # type: ignore[attr-defined]
        del self._nodes[state["#nodes"] :]
        del self.lints.items[state["#lints"] :]  # type: ignore[attr-defined]
        for node, place_log, sigs, parent, bindings in state["#node_state"]:
            object.__setattr__(node, "_place_log", list(place_log))
            object.__setattr__(node, "_sigs", dict(sigs))
            object.__setattr__(node, "_parent", parent)
            object.__setattr__(node, "_binding_log", {k: list(v) for k, v in bindings.items()})

    @contextmanager
    def _probe(self) -> Iterator[None]:
        """Run the block, then undo everything it did."""
        snapshot = self._b.snapshot()
        state = self._capture()
        try:
            yield
        finally:
            self._b.restore(snapshot)
            self._b.drop_snapshot(snapshot)
            self._restore(state)

    @contextmanager
    def _checkpoint(self) -> Iterator[Callable[[], None]]:
        """Yields `rollback()`, which returns to the state at entry; the final state is kept."""
        snapshot = self._b.snapshot()
        state = self._capture()

        def rollback() -> None:
            self._b.restore(snapshot)
            self._restore(state)

        try:
            yield rollback
        finally:
            self._b.drop_snapshot(snapshot)
