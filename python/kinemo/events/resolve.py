"""The resolve phase: precompute state with memory, detect events, run handlers, repeat
until nothing changes (at most 8 passes, then K0501)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..diagnostics import KinemoError
from . import numeric
from .event import EventInfo, EventSource
from .registry import Firing

if TYPE_CHECKING:
    from ..scene.scene import Scene

MAX_PASSES = 8

Firings = dict[int, list[Firing]]


def compute_tables(s: "Scene", horizon: float) -> None:
    s._events.generated.clear()
    for item in s._statefuls:
        item.compute(s, horizon)
    s._tables_dirty = False


def effect_firings(s: "Scene", horizon: float) -> Firings:
    """Edges of every `k.when`, as firings of its target source."""
    out: Firings = {}
    dt = 1.0 / s.config.fps
    for effect in s._events.effects:
        times = numeric.edges(
            s._b, effect.cond._ir(), effect.since, horizon, dt,
            effect.rearm._ir() if effect.rearm is not None else None, effect.once,
        )
        if effect.owner is not None:
            times = [t for t in times if s._b.present(effect.owner._id, t)]
        out.setdefault(effect.action._id, []).extend(Firing(t) for t in times)
    return out


def collect(s: "Scene", horizon: float) -> Firings:
    """All firings known now: explicit, generated, conditions and computed sources."""
    out: Firings = {}
    for table in (s._events.explicit, s._events.generated):
        for sid, firings in table.items():
            out.setdefault(sid, []).extend(firings)
    for sid, firings in effect_firings(s, horizon).items():
        out.setdefault(sid, []).extend(firings)
    for src in list(s._events.sources):
        if src.computed is not None:
            out.setdefault(src._id, []).extend(Firing(t, d) for t, d in src.computed())
    for firings in out.values():
        firings.sort(key=lambda f: f.t)
    return out


def _signature(firings: Firings) -> list[tuple[int, float]]:
    return sorted((sid, round(f.t, 6)) for sid, fs in firings.items() for f in fs)


def run_handlers(s: "Scene", firings: Firings) -> None:
    queue: list[tuple[float, int, int, Firing]] = []
    for sid, fs in firings.items():
        for count, f in enumerate(fs, 1):
            queue.append((f.t, sid, count, f))
    queue.sort(key=lambda q: (q[0], q[1], q[2]))
    for t, sid, count, f in queue:
        for h in s._events.handlers.get(sid, []):
            if h.once and count > 1:
                continue
            s._run_handler(h.fn, EventInfo(t, f.data, count, s))


def resolve(s: "Scene") -> None:
    """Fixed point of tables, events and handlers. Leaves the scene in the converged state."""
    if not (s._statefuls or s._events.effects or s._events.handlers):
        return
    horizon_of = lambda: max(s.cursor, s._max_end) + s.config.tail  # noqa: E731
    with s._checkpoint() as rollback:
        compute_tables(s, horizon_of())
        firings = collect(s, horizon_of())
        history = [_signature(firings)]
        for _ in range(MAX_PASSES):
            rollback()
            run_handlers(s, firings)
            compute_tables(s, horizon_of())
            new = collect(s, horizon_of())
            signature = _signature(new)
            if signature == history[-1]:
                return
            history.append(signature)
            firings = new
        raise _loop_error(s, history)


def _loop_error(s: "Scene", history: list[list[tuple[int, float]]]) -> KinemoError:
    last, before = set(history[-1]), set(history[-2])
    changed = sorted({sid for sid, _ in last ^ before})
    names = [repr(s._events.sources[sid]) for sid in changed][:4]
    spans = []
    for sid in changed:
        for h in s._events.handlers.get(sid, []):
            code = getattr(h.fn, "__code__", None)
            if code is not None:
                from .._runtime.spans import Span

                spans.append(Span(code.co_filename, code.co_firstlineno))
    return KinemoError.make(
        "K0501",
        f"events did not converge within {MAX_PASSES} passes: " + " → ".join(names + names[:1]),
        spans=spans[:2],
        fixes=[("break the event → handler → signal → event cycle (use once=True or rearm=)", None)],
    )


def firings_of(s: "Scene", src: EventSource[Any], horizon: float) -> list[Firing]:
    """Firings of one source with what is scheduled so far (for `s.wait_for`)."""
    compute_tables(s, horizon)
    return collect(s, horizon).get(src._id, [])
