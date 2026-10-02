# Events and simulation

Most scenes are a script: play this, then that. Some are better described as rules:
*when the tank is full, flash the lamp*; *every time the ball hits the floor, squash it*;
*continue the explanation once the battery is empty*. kinemo expresses these with events,
effects and stateful systems, and it still keeps the frame at time `t` a pure function of
`t`. It does this by resolving everything before rendering.

This guide covers:

- `k.when`, which fires an animation or an event when a condition becomes true;
- event sources (`k.EventSource`, component and simulation events, `h.done`, `obj.entered`);
- `@src.on` handlers, which run with their own cursor;
- `s.wait_for`, which continues the script from an event, and its timeouts;
- `k.integrate`, `k.simulate` with `k.State`, and `k.trace`;
- the resolve fixed point and the `K0501` event loop error.

It assumes you know the timeline (`s.play` blocks the cursor, `s.start` does not) from
[The timeline](03-timeline.md) and signals from [Reactive values](06-reactive.md).

## Where events are resolved

A scene goes through three phases (see [The mental model](02-mental-model.md)):

1. **Build.** Your function runs once. `k.when`, `.on`, `k.integrate` and `k.simulate`
   *record* effects and states. They do not run yet.
2. **Resolve.** With the whole timeline known, the core samples conditions every frame,
   precomputes integrals and simulations into tables, finds the instants where events fire,
   and runs your handlers. Handlers may schedule more animations, so this repeats until
   nothing changes.
3. **Render.** Frames only read the tables. Python is never called while rendering.

Because of this, an event is always *an instant on the timeline* with an optional payload.
There are two ways to react to one, and they mean different things:

| Form | Meaning | Main cursor |
| --- | --- | --- |
| `@src.on` | "Also do this, every time it happens." | Unchanged. The handler gets its own cursor at `e.time`. |
| `s.wait_for(src)` | "Wait for it, then continue the script from there." | Jumps to the event. |

## `k.when`: react to a condition

`k.when(cond, action)` watches a boolean expression. When `cond` goes from false to true
(an *edge*), it starts `action`, which can be an animation or an event to emit. It never
moves the cursor.

```python
import kinemo as k


@k.scene
def thermostat(s: k.Scene):
    temp = k.signal(20.0)
    gauge = k.Text(lambda: f"{temp():.0f} °C", size=0.9).place(at="center")
    lamp = k.Circle(r=0.4, fill=k.GRAY, fill_opacity=1).place(below=gauge, gap=0.5)
    s.add(gauge, lamp)

    k.when(temp > 80, k.flash(lamp, color=k.RED), once=True)
    k.when(temp > 60, k.indicate(gauge, color=k.ORANGE), rearm=temp < 40)

    s.play(temp.to(90), duration=3)
    s.play(temp.to(30), duration=2)
    s.play(temp.to(70), duration=2)
    s.wait(1)
```

`kinemo check` shows where the effects landed. The `indicate` fires twice (around 1.6 s and
6.2 s), and the `flash` fires once:

```
   0.00– 3.00  Signal#0(float).to(value)                thermostat.py:14
   1.58– 2.58  indicate(gauge)                          :12
   2.01– 2.61  flash(lamp)                              :11
   ...
   6.21– 7.21  indicate(gauge)                          :12
```

How `k.when` behaves:

- **Edges only.** The condition is sampled once per frame and each false → true edge is
  refined by bisection to 1 ms. A condition that stays true fires once, not once per frame.
- **Rearming.** Without `rearm=`, the condition must become false again before it can fire
  again. With `rearm=cond2`, `cond2` must become true first (hysteresis), which avoids
  repeated firing when a value hovers around a threshold.
- **`once=True`** fires only the first time.
- **From the cursor on.** The effect applies from the cursor where you registered it. If
  the condition is already true at that point, it is not armed: it has to become false and
  then true again.
- **In components**, a `k.when` registered in `build()` is active only while the component
  is in the scene (see [Components](07-components.md)).
- **Conditions are expressions.** Combine them with `&`, `|` and `~`, never with
  `and`/`or`/`if` (see [Reactive values](06-reactive.md)).

## Event sources

Every event is a `k.EventSource`. You react to one with `@src.on`, or wait for it with
`s.wait_for(src)`. Sources come from several places:

| Source | Example | Fires |
| --- | --- | --- |
| A named source of the scene | `full = k.EventSource(s, "full")` | Whenever you emit it, or when a `k.when` targets it |
| `k.when` with an event as action | `k.when(level >= 1, full)` | On each edge of the condition |
| Explicit emission | `full.emit()` or `ping.emit("hello")` | At the cursor (in the build, a clip or a handler) |
| A component event | `full: k.Event` → `bat.full` | When the component emits it (see [Components](07-components.md)) |
| A simulation event | `bounce: k.Event[Impact]` → `sim.bounce` | When `step` calls `st.bounce.emit(...)` |
| End of an animation | `h = s.start(anim)` → `h.done` | At `h.end` |
| End of a simulation | `sim.done` | At `until=` |
| Object lifecycle | `obj.entered`, `obj.exited` | When the object enters or leaves the scene |

Events are typed: `k.EventInfo[str]` in a handler means `e.data` is a `str`. String-based
event names (`"full"` as an argument to `k.when`) do not exist.

## `@src.on`: handlers with their own cursor

A handler is a function `def handler(s: k.Scene, e: k.EventInfo) -> None` registered with
`@src.on`. It runs during resolve, once per firing. It receives its **own** `s` whose
cursor starts at `e.time`, so `s.play`, `s.wait` and `s.start` inside it are relative to
the event. The main script's cursor is not affected.

```python
import kinemo as k


@k.scene
def sources(s: k.Scene):
    box = k.Square(1.5).place(at="center")
    ping = k.EventSource(s, "ping")

    @box.entered.on
    def arrived(s: k.Scene, e: k.EventInfo) -> None:
        s.play(k.flash(box))

    @ping.on
    def answer(s: k.Scene, e: k.EventInfo[str]) -> None:
        note = k.Text(e.data, size=0.5).place(above=box, gap=0.4)
        s.play(k.fade_in(note), duration=0.5)
        s.play(k.fade_out(note), duration=0.5)

    s.play(k.draw(box))
    s.wait(1)
    ping.emit("hello")
    s.wait(2)
```

What a handler receives:

| Field | Meaning |
| --- | --- |
| `e.time` | Instant of the firing, in seconds |
| `e.data` | Typed payload (`None` for events without one) |
| `e.count` | Which firing this is (1-based) |
| `e.value(sig)` | Value of any signal or expression at `e.time` |

Rules for handlers:

- **`.on(once=True)`** reacts only to the first firing.
- **Objects created in a handler must leave the scene**, usually with `k.fade_out`.
  Otherwise every firing adds a new object that stays forever, and lint `W0701` warns.
- **Handlers are plain Python.** `if`, `min()` and `math.*` work. Only lambdas, `.map` and
  `k.computed` are traced.
- **Handlers must be deterministic.** Resolve may run a handler several times while the
  firing times settle (see [The resolve fixed point](#the-resolve-fixed-point)). Do not
  keep counters in globals or read the wall clock. `kinemo dev` warns when two builds of
  the same source differ.

## `s.wait_for`: continue the script from an event

`s.wait_for(src)` moves the **main** cursor to the next firing of `src` after the cursor
and returns its `EventInfo`. It only sees what is already scheduled, so the usual pattern
is `s.start(...)` (which does not block), followed by `s.wait_for(...)`:

```python
import kinemo as k


@k.scene
def tank(s: k.Scene):
    level = k.signal(0.0)
    water = k.Rect(w=2, h=level * 3 + 0.01, fill=k.BLUE, fill_opacity=0.8).place(at="center")
    full = k.EventSource(s, "full")
    k.when(level >= 1, full)
    s.add(water)

    @full.on
    def overflow(s: k.Scene, e: k.EventInfo) -> None:
        note = k.Text("Full!", size=0.6).place(at="top", margin=0.8)
        s.play(k.fade_in(note))
        s.wait(0.5)
        s.play(k.fade_out(note))

    s.start(level.to(1), duration=4, ease=k.ease.linear)
    e = s.wait_for(full, timeout=6)
    label = k.Text(f"full at t = {e.time:.1f} s", size=0.4).place(at="bottom", margin=0.8)
    s.play(k.write(label))
    s.wait(1)
```

Details:

- **`count=n`** waits for the n-th firing after the cursor: `s.wait_for(sim.bounce, count=3, timeout=6)`.
- **`timeout=` is relative to the cursor**, and it is required when the source has no
  guaranteed end: a `k.when` condition, a named `k.EventSource`, or a simulation without
  `until=`. Sources with a known end (`h.done`, `sim.done`, events of a simulation with
  `until=`) do not need one. Without the timeout you get `K0702`, with the fix
  `s.wait_for(full, timeout=20)`.
- **If the event does not happen before the timeout**, `K0702` reports how close the
  condition got:

  ```
  K0702 error: 'full' did not fire 1× by t = 3.00 s (maximum 0.6 at t = 2.00 s)
  ```

- **If the event already happened**, for example because a `s.play` moved the cursor past
  it, you get `K0703`. The fix is to replace the preceding `s.play(...)` with
  `s.start(...)`:

  ```
  K0703 error: 'full' already happened at t = 2.00 s, before the cursor (2.00 s)
    fix: start the earlier animation without blocking the cursor
           s.start(...)  # instead of s.play(...)
  ```

- **Handlers are not visible to `wait_for`.** It resolves only the part of the timeline
  known up to that line, so an event that only a handler would emit later cannot be
  waited for.

## `k.integrate`: quantities with memory

`k.integrate(expr, d=clock, initial=, clamp=)` is the integral of `expr` with respect to the
change in `d` (default `k.time`), starting at the cursor. It is precomputed during resolve
(trapezoidal, 240 samples per second) and returns a read-only signal. With `clamp=(lo, hi)`,
the value stays in range, and the integral is path-dependent (a full tank stays full while
the inflow continues).

```python
import kinemo as k


@k.scene
def charging(s: k.Scene):
    hour = k.time.map(lambda t: t * 2)
    power = k.signal(2.0)
    soc = k.integrate(power / 10, d=hour, initial=0.2, clamp=(0, 1))
    body = k.RoundedRect(w=1.2, h=2.4).place(at="center")
    level = k.Rect(w=1.0, h=soc * 2.2 + 0.01, fill=k.GREEN, fill_opacity=0.9).place(inside=body, align="bottom", pad=0.1)
    label = k.Text(lambda: f"{soc() * 100:.0f} %", size=0.5).place(below=body, gap=0.3)
    s.add(body, level, label)

    full = k.EventSource(s, "full")
    k.when(soc >= 1, full)
    e = s.wait_for(full, timeout=10)
    note = k.Text(f"full after {e.value(hour):.1f} h", size=0.45).place(above=body, gap=0.3)
    s.play(k.write(note))
    s.play(power.to(-4), duration=0.5)
    s.wait(2)
```

The clock passed as `d=` must advance **linearly**. Use `k.time.map(...)`, or animate it with
`ease=k.ease.linear`. A clock animated with the default `smooth` easing makes the integral
speed up and slow down along with it, and lint `W0312` suggests the linear version.

## `k.simulate`: fixed-step systems in Python

When the rule is easier to write as code than as an expression, use a simulation. You
define:

- a **state** class, a subclass of `k.State` whose fields (floats, bools or pairs) have
  defaults, plus `k.Event` declarations;
- a **step** function `step(state, dt) -> state` in plain Python, where `if`, `min()` and
  `math` all work.

States are values. The step returns `st.replace(field=...)` and never assigns attributes.
Events are emitted with `st.event.emit(payload)`: that is an immediate effect at the
simulated instant, not part of the returned value.

```python
from dataclasses import dataclass

import kinemo as k


@dataclass
class Impact:
    speed: float


class Ball(k.State):
    y: float = 4.0
    v: float = 0.0
    bounce: k.Event[Impact]


def step(st: Ball, dt: float) -> Ball:
    v = st.v - 9.8 * dt
    y = st.y + v * dt
    if y < 0:
        y, v = -y, -v * 0.8
        if abs(v) < 0.5:
            y, v = 0.0, 0.0
        else:
            st.bounce.emit(Impact(speed=abs(v)))
    return st.replace(y=y, v=v)


@k.scene
def bounce(s: k.Scene):
    floor = k.Line(length=10).place(at="bottom", margin=1)
    sim = k.simulate(step, Ball(), dt=1 / 240, until=6)
    ball = k.Circle(r=0.3, fill=k.theme.accent, fill_opacity=1).place(above=floor, gap=sim.y)
    s.add(floor, ball)

    @sim.bounce.on
    def squash(s: k.Scene, e: k.EventInfo[Impact]) -> None:
        s.play(k.squash(ball, amount=min(e.data.speed / 20, 0.5)), duration=0.15)

    s.start(sim)
    e = s.wait_for(sim.bounce, count=3, timeout=6)
    title = k.Text(f"3rd bounce at {e.time:.2f} s", size=0.5).place(at="top", margin=0.6)
    s.play(k.write(title))
    s.wait_for(sim.done)
```

What you get from `k.simulate(step, state, dt=1/240, until=None)`:

- **A field signal per state field**: `sim.y`, `sim.v`. Use them in props like any signal
  (`gap=sim.y` above).
- **An event source per declared event**: `sim.bounce`. A `k.Event` without a type has no
  payload (`st.bounce.emit()`); `k.Event[Impact]` carries an `Impact` in `e.data`.
- **`sim.done`**, which fires at `until=`.
- **An animation**: nothing runs until you `s.start(sim)`. The simulation starts at that
  cursor, and the fields hold their initial values before that.

Without `until=`, the simulation runs to the end of the scene and its events have no
guaranteed end, so `s.wait_for` on them needs `timeout=`.

### Reading signals from a step

A step can read signals with a tracked read, `sig()`. It sees the value at the simulated
instant. Declare such signals inside the scene function: objects and signals can only be
created while a scene is being built (`K0104` at module level), so the step becomes a
closure:

```python
import kinemo as k


class Ball(k.State):
    y: float = 2.0
    v: float = 0.0
    bounce: k.Event


@k.scene
def moon(s: k.Scene):
    gravity = k.signal(9.8)

    def step(st: Ball, dt: float) -> Ball:
        v = st.v - gravity() * dt
        y = st.y + v * dt
        if y < 0:
            y, v = -y, -v * 0.9
            st.bounce.emit()
        return st.replace(y=y, v=v)

    floor = k.Line(length=10).place(at="bottom", margin=1)
    sim = k.simulate(step, Ball(), until=8)
    ball = k.Circle(r=0.3, fill=k.BLUE, fill_opacity=1).place(above=floor, gap=sim.y)
    s.add(floor, ball)

    @sim.bounce.on(once=True)
    def to_the_moon(s: k.Scene, e: k.EventInfo) -> None:
        s.play(gravity.to(5.0), duration=0.5)

    s.start(sim)
    s.wait_for(sim.done)
```

This scene closes a loop: the first bounce changes gravity, gravity changes the simulation,
and the simulation decides when the bounces happen. The next section explains how kinemo
settles that.

## `k.trace`: the path a point took

`k.trace(point, length=2.0, **style)` draws the last `length` seconds of a moving point,
usually `obj.world.position`, as a stroke. It is sampled from the timeline, so dragging the
preview backwards shows the right trail.

```python
import kinemo as k


@k.scene
def lissajous(s: k.Scene):
    dot = k.Dot(r=0.15, x=k.cos(k.time * 2) * 3, y=k.sin(k.time * 3) * 2)
    trail = k.trace(dot.world.position, length=1.5, stroke=k.TEAL)
    s.add(trail, dot)
    s.wait(4)
    s.play(k.fade_out(dot, trail))
```

## The resolve fixed point

Handlers can schedule animations that change signals feeding conditions or simulations.
The `moon` scene above does that. Resolve handles it by iterating:

1. compute every table (integrals, simulations) and collect every firing (explicit
   emissions, `k.when` edges, simulation events, lifecycle and `done` events);
2. roll back what the previous pass scheduled from handlers, then run the handlers for the
   current firings;
3. recompute the tables and collect the firings again;
4. stop when the set of firings (source and instant) is the same as in the previous pass.

Most scenes converge in one or two passes. After **8 passes** without convergence, resolve
stops with `K0501` and names the sources that kept changing. A typical cause is a handler
that always schedules the next firing of its own event at a new instant:

```python
target = k.signal(1.0)
tick = k.EventSource(s, "tick")
k.when(k.time >= target, tick)

@tick.on
def again(s: k.Scene, e: k.EventInfo) -> None:
    target.set(e.time + 0.1)  # each firing moves the next one: no fixed point
```

```
K0501 error: events did not converge within 8 passes: tick → tick
  fix: break the event → handler → signal → event cycle (use once=True or rearm=)
```

Ways out: `once=True` on the handler or the `k.when`, a `rearm=` condition that the loop
cannot satisfy, or, for a genuinely periodic process, a simulation (a step function can
emit as many events as it needs in a single pass).

## Common mistakes

> | Diagnostic | What happened | Fix |
> | --- | --- | --- |
> | `K0304` | `if x > 2:` on a signal in the scene body. A signal has no single boolean value. | Decide at the cursor with `if x.now > 2:`, or react during playback with `k.when(x > 2, ...)`. |
> | `K0105` | `k.when(cond, "flash")`: the action is neither an animation nor an event. | Pass an animation (`k.flash(dot)`) or an event source (`full`). |
> | `K0702` | `s.wait_for(src)` on a condition or a simulation without `until=`. | Add `timeout=`, which is relative to the cursor. |
> | `K0702` | The event never fired before the timeout. The message gives the maximum (or minimum) the condition reached. | Check the threshold, or start the animation that drives it. |
> | `K0703` | The event already happened, usually because a `s.play` blocked past it. | Use `s.start(...)` for the animation that leads to the event, then `s.wait_for`. |
> | `W0701` | A handler created an object that never leaves the scene. | End the handler with `s.play(k.fade_out(obj))`. |
> | `W0312` | The `d=` clock of `k.integrate` is animated with easing. | `k.time.map(...)`, or `ease=k.ease.linear`. |
> | `K0105` | `st.v = ...` inside a step: states are values. | `return st.replace(y=y, v=v)`. |
> | `K0104` | A signal read by a step was created at module level. | Create it inside the scene function and define the step there as a closure. |
> | `K0501` | Events did not converge within 8 passes. | Break the cycle with `once=True`, `rearm=`, or move the logic into a simulation. |

See also: [Stateful systems reference](../reference/stateful-systems.md),
[Events reference](../reference/events.md), [`s.wait_for`](../reference/scene.md#scene-wait_for),
[Diagnostics](../reference/diagnostics.md#range-07).
