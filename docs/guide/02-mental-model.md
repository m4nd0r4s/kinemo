# The mental model

kinemo looks like an imperative script (`s.play(...)`, `s.wait(...)`), but your code does
not draw anything. It **describes a timeline**, once, and the Rust core turns that timeline
into frames. Once that clicks, every rule of the API follows from it. This guide explains
the three execution phases, the time cursor, the two ways of reading a value, and the
seven rules the whole API is built on.

## Three phases: build → resolve → render

| Phase | Who runs | How often | What happens |
| --- | --- | --- | --- |
| **Build** | Python (your scene function) | Exactly once | Each call records something in the timeline at the cursor. |
| **Resolve** | Rust core, calling back into Python only for handlers, `k.python` and `k.simulate` | Until nothing changes (at most 8 passes) | Simulations and integrals are precomputed, `k.when` edges are detected, `.on` handlers run, conflicts and lints are checked. |
| **Render** | Rust core only | Once per frame, in any order | `frame(t)` evaluates every value at instant `t`, solves the layout and draws. |

### Build

The body of your `@k.scene` function runs exactly once. There is a **cursor**, a time in
seconds that starts at 0. Every call records something *at the cursor*:

- `s.play(anim)` schedules `anim` at the cursor and moves the cursor to its end;
- `s.start(anim)` schedules `anim` at the cursor and leaves the cursor where it is;
- `s.wait(d)` moves the cursor forward by `d` seconds;
- `s.add`, `s.remove`, `obj.set(...)`, `x.set(...)` record instant changes at the cursor;
- `k.when(...)` and `@event.on` register effects that are resolved later.

Nothing is drawn during build. A `for` loop that calls `s.play` ten times simply records ten
animations one after the other.

### Resolve

With the whole timeline known, the core precomputes everything that depends on history
(integrals, simulations, trails), finds the instants at which `k.when` conditions become
true, and runs the matching `.on` handlers. A handler can schedule more animations, which
may cause new events, so resolve repeats until nothing changes. It gives up after 8 passes
with `K0501` (an event loop). Finally it checks for conflicts (two animations on the same
prop at the same time) and runs the visual lints.

### Render

`frame(t)` is a **pure function of `t`**. It never calls your Python code. That is what
makes the preview scrubbable, lets frames render in parallel and out of order, and makes
the output deterministic: the same source produces the same bytes.

A consequence: you cannot "do something every frame" in Python. Anything continuous is
expressed as a reactive value (a signal, an expression, a lambda that kinemo traces into
native code), which the core evaluates at each `t`.

## The cursor

The cursor is where the next call lands. You move it explicitly:

```python
import kinemo as k


@k.scene
def cursor(s: k.Scene):
    a = k.Circle(r=0.6, x=-3)
    b = k.Square(1.2, x=3)
    s.play(k.draw(a), k.draw(b))          # 0.0 → 1.0, cursor ends at 1.0
    s.start(b.to(rotate=90), duration=3)  # 1.0 → 4.0, cursor stays at 1.0
    s.play(a.to(color=k.RED))             # 1.0 → 2.0, alongside the rotation
    s.wait(1)                             # cursor 2.0 → 3.0
    s.play(a.to(scale=1.5))               # 3.0 → 4.0, the rotation ends at 4.0 too
```

`kinemo check` prints exactly this as the timeline summary, with the line of each entry.
The scene ends at the later of the final cursor and the end of everything started, plus the
`tail` (0.5 s by default, `@k.scene(tail=...)`).

## Two reads: `.now` and `x()`

Every value that changes over time is a **signal**: every object prop (`dot.x`,
`box.color`), every `k.signal(...)` you create, and expressions derived from them. There are
two ways to read one, and they mean different things:

| Read | Where | Meaning |
| --- | --- | --- |
| `x.now` | Scene body, a component's `build()`, `.on` handlers, clips | The value **at the cursor**, taking into account everything scheduled so far. A plain Python value. |
| `x()` | Lambdas passed to props, `k.computed`, functions given to `.map` | A **tracked** read: the expression is re-evaluated at every instant by the core. |

Use `.now` to make decisions while writing the script:

```python
import kinemo as k


@k.scene
def decide(s: k.Scene):
    bar = k.Bar(3, label=True, y=-1.5)
    s.play(k.grow(bar, from_="bottom"))
    s.play(bar.to(value=7))
    if bar.value.now > 5:          # 7 at this point of the script
        s.play(bar.to(color=k.RED))
    s.wait(0.5)
```

Use `x()` inside a lambda to make something follow a value continuously:

```python
import kinemo as k


@k.scene
def follow_value(s: k.Scene):
    x = k.signal(0.0)
    label = k.Text(lambda: f"x = {x():.2f}").place(at="top", margin=0.8)
    dot = k.Dot(r=0.2, x=x)
    s.add(label, dot)
    s.play(x.to(4), duration=2)
    s.play(x.to(-4), duration=2)
```

Here `dot` gets `x=x` (a signal passed directly) and the label gets a lambda. Both create a
**reactive binding**: the core evaluates them at every instant. The lambda is called once
during build with symbolic values and compiled ("traced") into a native expression; it is
never called during render. See [reactive values](06-reactive.md) for the details.

Mixing the two reads is always an error, never silent:

- `x()` in the scene body → `K0301`, use `x.now`;
- `x.now` inside a lambda → `K0302`, it would freeze the value at build time; use `x()`;
- `if x > 2:` on a signal → `K0304`, use `x.now > 2` (decide now) or `k.when(x > 2, ...)`
  (react during playback).

## The seven rules

The whole API derives from these rules. When you are unsure how to do something, one of
them usually answers it.

1. **Scene code runs once and produces a timeline.** The frame at instant `t` is a pure
   function of `t`. Ordinary Python (`if`, `for`, functions) is fine in the scene body; it
   runs once.
2. **Objects are values.** Creating an object does not put it in the scene; it enters with
   `s.add(obj)` (instant) or with an entrance verb (`k.draw`, `k.write`, `k.fade_in`,
   `k.grow`).
3. **Whatever takes time goes through `s.play` (blocks the cursor) or `s.start` (does not
   block).** Whatever is instant is a direct call: `s.add`, `s.remove`, `obj.set`, `x.set`.
4. **A state change is `obj.to(...)`.** Components may expose *named transitions*
   (`row.swap(i, j)`, `ax.zoom_to(...)`), which are documented as sugar for a `.to()`.
5. **Position comes from constraints, not coordinates.** Use `.place(...)`, `k.Row`,
   `k.Column`, `k.Grid`. Coordinates (`x=`, `y=`) exist, but they are the rare case.
6. **Passing a signal or a lambda creates a reactive binding.** There are no updaters.
7. **Two reads, two names.** `x.now` reads at the cursor during construction; `x()` reads in
   a tracked way inside reactive contexts.

Some consequences you will meet early:

- An animation is a value. `move = dot.to(x=4)` does nothing until you pass `move` to
  `s.play` or `s.start`. You can store it, reuse it with `move.with_(duration=2)`, or
  compose it with `k.seq` and `k.par`.
- There is one name per concept and no aliases: `k.draw`, not `create`; `obj.to`, not
  `animate`. Manim names are recognized and answered with the kinemo form (`K11xx`).
- Because the render is pure, effects are not I/O. "When the battery is full, flash it" is
  `k.when(bat.soc >= 1, k.flash(bat))`: the core finds the instant during resolve and puts
  the flash on the timeline.

## Handlers run in resolve, with their own cursor

Event handlers are the one place where Python code runs after the build. They receive their
own `s`, whose cursor starts at the event's time; the main cursor is not affected:

```python
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

    s.wait(2)
```

`h` is the `TimeSpan` returned by `s.play`; `h.done` is an event at its end. Objects created
in a handler should leave the scene before it ends (lint `W0701`).

> **Common mistakes**
>
> | You see | Why | Fix |
> | --- | --- | --- |
> | `K0301 x() is a tracked read and only works inside lambdas, k.computed or .map` | You called a signal in the scene body. | Read it at the cursor: `x.now`. |
> | `K0302 '.now' inside a reactive function would freeze the value` | You used `.now` inside a lambda or `.map` function. | Use the tracked read `x()`. |
> | `K0304 a signal has no single boolean value` | `if x > 2:` (or `and`/`or`) on a signal. | `if x.now > 2:` to decide in the script, `k.when(x > 2, ...)` to react during playback, `k.where(...)` inside expressions. |
> | `K0305 a signal cannot become a number` | `math.sin(x)`, `float(x)` on a signal. | `k.sin(x)`, or `x.map(fn)` for a function of the signal. |
> | `K0101` / `K0102` | You animated an object before it entered, or after it left. | Enter it first (`s.add` / a verb); bring it back with an entrance verb. |
> | `K0501 event loop` | Handlers keep triggering each other and resolve did not converge in 8 passes. | Break the chain: use `once=True`, a `rearm=` condition, or do not let the handler change what the condition reads. |
> | A value printed in the scene body looks "stale" | `.now` is a snapshot at the cursor. Anything scheduled later is not included. | Read it after the `s.play` that changes it, or bind it reactively instead. |
