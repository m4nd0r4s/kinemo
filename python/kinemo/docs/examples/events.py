"""State with memory and events: `k.when`, `k.integrate`, `k.simulate`, `k.trace`, `.on`."""

from __future__ import annotations

from ..entry import DocEntry

ENTRIES = (
    DocEntry(
        "k.when",
        "Stateful systems",
        "Edge-triggered effect: when `cond` goes from false to true, it fires an animation or "
        "emits an event. It does not move the cursor. Without `rearm=`, the condition must become "
        "false again before it fires again; `once=True` fires only the first time.",
        '''
import kinemo as k

@k.scene
def trigger(s: k.Scene):
    x = k.signal(-4.0)
    dot = k.Dot(r=0.25, x=x)
    s.add(dot)
    k.when(x >= 2, k.flash(dot, color=k.YELLOW))
    s.play(x.to(4), duration=3, ease=k.ease.linear)
''',
        related=("EventSource.on", "Scene.wait_for", "k.integrate"),
    ),
    DocEntry(
        "k.integrate",
        "Stateful systems",
        "Integral of an expression with respect to the change in `d=` (default `k.time`), starting "
        "at the cursor, with `initial=` and `clamp=(lo, hi)`. It is precomputed during resolve; the "
        "result is a read-only signal. A clock used as `d=` must advance linearly.",
        '''
import kinemo as k

@k.scene
def tank(s: k.Scene):
    flow = k.signal(0.5)
    level = k.integrate(flow, initial=0.0, clamp=(0, 3))
    water = k.Rect(w=2, h=level + 0.01, fill=k.BLUE, fill_opacity=0.8).place(at="center")
    s.add(water)
    s.wait(2)
    s.play(flow.to(-1), duration=1)
    s.wait(2)
''',
        related=("k.when", "k.time", "k.Component"),
    ),
    DocEntry(
        "k.simulate",
        "Stateful systems",
        "Fixed-step simulation: `step(state, dt) -> state`, run in Python during resolve. "
        "The state is a subclass of `k.State` (float, bool or pair fields with defaults, plus "
        "`k.Event[P]` events); states are values, so the step returns "
        "`st.replace(field=...)` and emits events with `st.event.emit(payload)` — an immediate effect at "
        "the simulated instant, not part of the returned value (event without payload: `bounce: k.Event`, "
        "`st.bounce.emit()`). The step is plain Python (`if`, `min`, `math` all work). Each field becomes "
        "a signal (`sim.y`) and each event a source (`sim.bounce`). Start it with `s.start(sim)`; "
        "`sim.done` fires at the end (`until=`).",
        '''
import kinemo as k

class Fall(k.State):
    y: float = 3.0
    v: float = 0.0

def step(st: Fall, dt: float) -> Fall:
    return st.replace(y=st.y + st.v * dt, v=st.v - 9.8 * dt)

@k.scene
def fall(s: k.Scene):
    sim = k.simulate(step, Fall(), dt=1 / 240, until=1)
    s.add(k.Circle(r=0.3, y=sim.y))
    s.start(sim)
    s.wait_for(sim.done)
''',
        related=("EventSource.on", "Scene.wait_for", "k.Event"),
        aliases=("k.State",),
    ),
    DocEntry(
        "k.trace",
        "Stateful systems",
        "Trail: the last `length` seconds of the path of a moving point "
        "(usually `obj.world.position`), drawn as a stroke. It is sampled from the timeline, "
        "so rendering stays pure.",
        '''
import kinemo as k

@k.scene
def trail(s: k.Scene):
    dot = k.Dot(r=0.15, x=k.cos(k.time * 2) * 3, y=k.sin(k.time * 3) * 2)
    trail = k.trace(dot.world.position, length=1.5, stroke=k.TEAL)
    s.add(trail, dot)
    s.wait(4)
''',
        related=("k.follow", "k.time"),
    ),
    DocEntry(
        "EventSource.on",
        "Events",
        "Decorator that reacts to every firing of an event: `@source.on` registers "
        "`def handler(s, e)`, run during resolve with its own `s` whose cursor starts at "
        "`e.time` (the main cursor does not change). `.on(once=True)` reacts only to the first one. "
        "Objects created in the handler must leave the scene (lint W0701).",
        '''
import kinemo as k

@k.scene
def reaction(s: k.Scene):
    box = k.Square(1.5).place(at="center")
    h = s.play(k.draw(box))

    @h.done.on
    def notify(s: k.Scene, e: k.EventInfo) -> None:
        note = k.Text("done").place(above=box, gap=0.3)
        s.play(k.fade_in(note))
        s.play(k.fade_out(note))
''',
        related=("Scene.wait_for", "k.when", "k.EventInfo"),
        aliases=("EventSource.emit",),
        signature="@event.on  ·  @event.on(once=True)",
    ),
    DocEntry(
        "k.EventInfo",
        "Events",
        "One firing of an event, received by `.on` handlers and returned by `s.wait_for`: "
        "`e.time` (instant), `e.data` (typed payload), `e.count` (n-th firing) and "
        "`e.value(sig)` (value of any signal at the instant of the event).",
        '''
import kinemo as k

@k.scene
def instant(s: k.Scene):
    x = k.signal(0.0)
    dot = k.Dot(r=0.2, x=x)
    s.add(dot)
    h = s.start(x.to(4), duration=2)
    e = s.wait_for(h.done)
    label = k.Text(f"x = {e.value(x):.0f} at t = {e.time:.0f} s").place(at="top", margin=0.8)
    s.play(k.write(label))
''',
        related=("EventSource.on", "Scene.wait_for"),
        aliases=("EventInfo.value", "EventInfo.time", "EventInfo.data", "EventInfo.count"),
        signature="e.time · e.data · e.count · e.value(sig)",
    ),
)
