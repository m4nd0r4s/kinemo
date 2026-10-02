# Reactive values

In kinemo, everything that varies is a **signal**, and anything computed from signals is a
**derived value** that the core keeps up to date by itself. You never write updaters: you
pass a signal or a lambda where a value is expected, and the binding holds at every frame.
Derived values are compiled to native expressions by *tracing*, so the render never calls
Python. This guide explains signals, the five ways to derive values, the tracing rules,
`k.python` for opaque code, list signals, time, and the errors you will meet.

Reference: [reactive](../reference/reactive.md) ([`k.signal`](../reference/reactive.md#k-signal),
[`k.computed`](../reference/reactive.md#k-computed), [`k.python`](../reference/reactive.md#k-python),
[`k.list`](../reference/reactive.md#k-list)), [native blocks](../reference/native-blocks.md),
[stateful systems](../reference/stateful-systems.md).

## Signals

```python
x = k.signal(1.0)                              # Signal[float]
name = k.signal("a", lerp=None)                # no interpolation: .to() switches in one step
pts = k.signal([(0, 0)], lerp=k.lerp.pointwise)  # lists need a lerp mode

x.set(5)                     # instant change at the cursor
s.play(x.to(3), duration=2)  # animated change
x.now                        # value at the cursor (build phase)
x()                          # tracked read (inside lambdas, k.computed, .map)
```

A signal has a timeline: `set` and `to` record changes at the cursor, just like object
props. In fact **every object prop is a signal with the same API**: `dot.x.now`,
`dot.x.set(2)`, and `s.play(dot.x.to(3))` is the same as `s.play(dot.to(x=3))`.

Interpolation modes (`lerp=`): `k.lerp.linear` (default), `k.lerp.round` (integers),
`k.lerp.step` (switch at the end, the same as `lerp=None`), `k.lerp.step_start` and
`k.lerp.pointwise` (lists of points).

```python
import kinemo as k


@k.scene
def signal_demo(s: k.Scene):
    r = k.signal(0.5)
    steps = k.signal(0, lerp=k.lerp.round)
    c = k.Circle(r=r).place(at="center")
    label = k.Text(lambda: f"r = {r():.2f}, {steps():.0f} steps").place(at="top", margin=0.8)
    s.add(c, label)
    s.play(r.to(2), steps.to(10), duration=2)
    r.set(1)
    s.wait(0.5)
```

### Lifting: every prop accepts `T`, a signal or a lambda

Wherever the API takes a `T`, it also accepts a `Signal[T]` and a `Callable[[], T]`. The
public type is `k.Val[T]`. That includes constructor arguments: `k.Circle(r=r)` binds the
radius to `r`; `k.Polygon.regular(n)` with a signal `n` changes the number of sides.

## Deriving values

There are five forms, each with its role. All but the last run natively in Rust.

| Form | Use it for | Example |
| --- | --- | --- |
| Operators | Arithmetic and comparisons | `a.x + 1.5`, `solar - load`, `soc >= 1` |
| `k` functions | Math, conditions, tables | `k.sin(x)`, `k.clamp(v, 0, 1)`, `k.where(c, a, b)`, `k.interp(h, xs, ys)` |
| `.map(fn)` | A function of one signal | `hour.map(solar_curve)` |
| `k.computed(fn)` | Logic with several dependencies | `k.computed(lambda: w() * h())` |
| `k.python(fn)` | Opaque Python, cost accepted explicitly | `hour.map(k.python(optimize))` |

A lambda passed directly to a prop is an implicit `k.computed`.

```python
import kinemo as k


def solar_curve(h: float) -> float:
    return k.max(0, 6 * k.sin(k.pi * (h - 6) / 12))


@k.scene
def derived(s: k.Scene):
    w = k.signal(2.0)
    h = k.signal(1.0)
    area = k.computed(lambda: w() * h())                    # several dependencies
    box = k.Rect(w=w, h=h, fill=k.mix(k.BLUE, k.RED, h - 1), fill_opacity=0.5).place(at="center")
    label = k.Text(lambda: f"area = {area():.1f}").place(at="top", margin=0.8)
    hour = k.time.map(lambda t: t * 4)                      # one signal
    sun = k.Circle(r=hour.map(solar_curve) * 0.1 + 0.1, fill=k.YELLOW, fill_opacity=1)
    sun.place(at="top-right", margin=1.2)
    s.add(box, label, sun)
    s.play(w.to(4), h.to(2), duration=2)
    s.wait(1)
```

Derived values are read-only, lazy and memoized: the core recomputes them only when a
dependency changes. `.set()` or `.to()` on a derived value is `K0303`: animate the source.

The `k` functions are polymorphic: they accept floats, signals, symbolic values and arrays.
The same `solar_curve` works with floats in `ax.plot(solar_curve)` and with a signal in
`hour.map(solar_curve)`.

## Lambdas in props

A lambda in a prop is how you write "this value, computed from those signals, at every
instant". Read the signals with `x()`:

```python
import kinemo as k


@k.scene
def readout(s: k.Scene):
    x = k.signal(0.0)
    dot = k.Dot(r=0.2, x=x, y=lambda: k.sin(x() * 2) * 1.5)
    value = k.Text(lambda: f"x = {x():+.2f}  y = {k.sin(x() * 2) * 1.5:+.2f}", size=0.45)
    value.place(at="top", margin=0.8)
    s.add(dot, value)
    s.play(x.to(4), duration=2)
    s.play(x.to(-4), duration=3)
```

Reactive text is laid out again only when the string changes, and digits use tabular widths
so numbers do not jitter.

## Tracing: what can go in a lambda

To compile a function, kinemo calls it **once** with symbolic values in place of the
signals. Every operation on them becomes a node of a native expression. If the function
touches something that cannot be represented, tracing fails with `K0310`, never with a
silent fallback.

| Construct | Traceable | Alternative |
| --- | --- | --- |
| Arithmetic, comparisons, `&` `\|` `~`, `abs()`, `round()` | Yes | — |
| `k` functions: `k.sin`, `k.cos`, `k.exp`, `k.sqrt`, `k.min`, `k.max`, `k.floor`, `k.ceil`, `k.clamp`, `k.where`, `k.piecewise`, `k.interp`, `k.spline`, `k.smoothstep`, `k.noise`, `k.mix`, `k.vec` | Yes | — |
| f-strings with format specs (`f"{x():.1f}"`) | Yes | — |
| Helper functions, constants, loops with a fixed count | Yes (unrolled) | — |
| `if` / `while` / `and` / `or` / ternaries on a symbolic value | No | `k.where`, `k.piecewise`, `&` `\|` `~` |
| `math.*`, `int()`, `float()`, built-in `min()` / `max()` | No | `k.sin`, `k.floor`, `k.min`, `k.max` |
| numpy functions applied to a signal | No | `k` functions, or `k.python` |
| External libraries, I/O, mutable state | No | `k.python(fn)` |

Conditions, written natively:

```python
import kinemo as k


def tariff(h: float) -> float:
    return k.where((h >= 18) & (h < 21), 1.8, 0.6)


def band(v: float) -> k.Color:
    return k.piecewise((v < 1, k.GREEN), (v < 2, k.YELLOW), default=k.RED)


@k.scene
def conditions(s: k.Scene):
    hour = k.time * 6
    price = k.Text(lambda: f"{hour():.0f} h: {tariff(hour()):.2f} per kWh").place(at="top", margin=0.8)
    v = k.signal(0.0)
    lamp = k.Circle(r=1, fill=v.map(band), fill_opacity=1).place(at="center")
    word = k.Text(k.where(v > 2, "high", "normal"), size=0.5).place(below=lamp, gap=0.3)
    s.add(price, lamp, word)
    s.play(v.to(3), duration=3)
```

A helper function with a fixed loop is unrolled into the expression:

```python
import kinemo as k


def series(x: float) -> float:
    total = 0.0
    for n in range(1, 6):
        total = total + k.sin(n * x) / n
    return total


@k.scene
def fourier(s: k.Scene):
    ax = k.Axes(x=(0, 6.3, 1), y=(-2, 2, 1)).place(at="center")
    ax.plot(series, color=k.YELLOW)
    t = k.signal(0.0)
    dot = k.Dot(r=0.1, fill=k.RED).place(at=ax.point(t, t.map(series)))
    s.play(k.draw(ax), k.fade_in(dot))
    s.play(t.to(6.2), duration=3, ease=k.ease.linear)
```

## `k.python`: opaque Python, explicitly

`k.python(fn)` is the only door to code that cannot be traced. The function is called during
**resolve**, once per frame, batched; the render only reads the precomputed table:

```python
import math

import numpy as np

import kinemo as k


def opaque(t: float) -> float:
    return 1 + 0.5 * math.sin(t) ** 2


def wobble(ts: np.ndarray) -> np.ndarray:
    return 0.6 + 0.2 * np.sin(ts * 3)


@k.scene
def explicit_cost(s: k.Scene):
    a = k.Circle(r=k.time.map(k.python(opaque))).place(at="left", margin=3)
    b = k.Circle(r=k.time.map(k.python(wobble, vectorized=True))).place(at="right", margin=3)
    s.add(a, b)
    s.wait(3)
```

- `k.python(fn)` wraps a function of **one** argument; use it with `.map`.
- `vectorized=True` makes a single call that receives the whole timeline as a numpy array.
- The result must be numeric. For text that depends on a condition, use `k.where` with
  strings (as in the example above) or an f-string.
- If the function depends on a scene parameter, it cannot be precomputed for interactive
  output: lint `W1302`.

Prefer the `k` functions whenever you can: they run natively, at no cost.

## List signals: `k.list`

Plain Python lists are not tracked. If a lambda captures a list that you modify later, the
lambda will not see the change (and lint `W0311` warns you). `k.list([...])` is a list signal
whose `append`, `insert`, `pop` and `swap` are recorded at the cursor:

```python
import kinemo as k


@k.scene
def queue_demo(s: k.Scene):
    queue = k.list(["ann", "bea"])
    label = k.Text(lambda: f"queue: {queue()}").place(at="center")
    s.add(label)
    s.wait(1)
    queue.append("cal")
    s.wait(1)
    queue.pop(0)
    s.wait(1)
```

In the scene body, `len(queue)`, `queue[0]`, iteration and `queue.now` read the list at the
cursor. Inside a lambda, `queue()` is a tracked read that you can format into a string;
Python operations on it such as `len(queue())` are not traceable.

## Time

`k.time` is the global scene time, a read-only signal in seconds. It advances linearly and
is never eased, which makes it the right base for clocks and continuous motion:

```python
import kinemo as k


@k.scene
def clocks(s: k.Scene):
    star = k.Polygon.regular(5, r=1).place(at="left", margin=3)
    star.set(rotate=k.time * 90)                         # 90 degrees per second, forever
    hour = k.time.map(lambda t: k.min(t * 6, 24))        # 1 s of video = 6 h, capped at 24
    clock = k.Text(lambda: f"{k.floor(hour()):02.0f}:00", size=0.9).place(at="right", margin=3)
    s.add(star, clock)
    s.wait(4)
```

- Inside components, `self.age` is the time since the component entered the scene.
- `s.tempo` does not affect `k.time`.
- A signal animated with easing and used as a clock (for example `d=` of `k.integrate`)
  makes everything that depends on it speed up and slow down: lint `W0312` suggests
  `ease=k.ease.linear` or `k.time.map(...)`.

## Effects: reacting during playback

Because the render is pure, "when the value crosses a threshold, do something" is an
effect resolved before rendering. `k.when(cond, action)` fires an animation or emits an event
on each false → true edge of `cond`:

```python
import kinemo as k


@k.scene
def trigger(s: k.Scene):
    x = k.signal(-4.0)
    dot = k.Dot(r=0.25, x=x)
    s.add(dot)
    k.when(x >= 2, k.flash(dot, color=k.YELLOW))
    s.play(x.to(4), duration=3, ease=k.ease.linear)
```

`once=True` fires only the first time; `rearm=cond` sets a separate condition to re-arm it
(hysteresis). Whatever is fired does not move the main cursor.

> **Common mistakes**
>
> | You see | Why | Fix |
> | --- | --- | --- |
> | `K0301 x() is a tracked read and only works inside lambdas, k.computed or .map` | `x()` in the scene body. | `x.now`. |
> | `K0302 '.now' inside a reactive function would freeze the value` | `x.now` inside a lambda or `.map`. | `x()`. |
> | `K0303 a derived value is read-only` | `.to()` / `.set()` on `x * 2`, a `.map`, a `k.computed`, or a layout prop. | Animate the source signal. |
> | `K0304 a signal has no single boolean value` | `if x > 2:` in the scene body. | `if x.now > 2:` (decide now) or `k.when(x > 2, ...)` (react during playback). |
> | `K0305 a signal cannot become a number` | `math.sin(x)`, `float(x)` in the scene body. | `k.sin(x)`. For any other function, `x.map(k.python(fn))`. |
> | `K0310 ... uses if/and/or on a symbolic value` | `if`, ternary, `and`/`or` inside a lambda (this message also appears for built-in `min()`/`max()`). | `k.where(cond, a, b)`, `k.piecewise(...)`, `&` `\|` `~`, `k.min`, `k.max`. |
> | `K0310 ... uses math.* or int()/float() on a symbolic value` | `math.sin`, `int()` inside a traced function. | `k.sin`, `k.floor`; or `x.map(k.python(fn))`. |
> | `K0310 ... it failed with symbolic values` | A library call (numpy, ...) on a signal inside a lambda. | Native `k` functions, or `k.python(fn)` (with `vectorized=True` for numpy). |
> | `K0205 this list does not know how to interpolate` | `.to()` on a list signal created without `lerp=`. | `lerp=k.lerp.pointwise` or `lerp=None`. |
> | `W0310 lambda in a loop captures 'i' by reference` | A lambda created in a `for` loop reads the loop variable; every lambda would see the last value. | `lambda i=i: ...`, or derive from a signal with `.map`. |
> | `W0311 lambda captures the Python list 'names'` | The list is modified after the lambda captured it. | `names = k.list([...])`. |
> | `W0312 'hour' is used as a clock ... non-linear easing` | A clock signal animated with the default `smooth` easing. | `ease=k.ease.linear`, or derive the clock from `k.time`. |
> | `K0001 ValueError: could not convert string to float` | A `k.python` function returned a string. | Return numbers; build strings with `k.where` or an f-string lambda. |
