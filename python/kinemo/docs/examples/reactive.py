"""Reactive system: signals, derived values and `k.python`."""

from __future__ import annotations

from ..entry import DocEntry

ENTRIES = (
    DocEntry(
        "k.signal",
        "Reactive",
        "A value with a timeline. `x.set(v)` changes it at the cursor, `s.play(x.to(v))` animates it, "
        "`x.now` reads the value at the cursor (build phase) and `x()` does a tracked read inside "
        "lambdas. Passing the signal to a prop creates a reactive binding. `lerp=None` switches "
        "in a single step. Every object prop is a signal with the same API.",
        '''
import kinemo as k

@k.scene
def signal_demo(s: k.Scene):
    r = k.signal(0.5)
    c = k.Circle(r=r).place(at="center")
    label = k.Text(lambda: f"r = {r():.2f}").place(at="top", margin=0.8)
    s.add(c, label)
    s.play(r.to(2), duration=2)
    r.set(1)
    s.wait(0.5)
''',
        related=("k.computed", "Expr.map", "Node.set"),
        aliases=("Signal.to", "Signal.set", "Signal.now"),
    ),
    DocEntry(
        "k.computed",
        "Reactive",
        "Derived value with several dependencies: `k.computed(lambda: f(a(), b()))`. The function is "
        "traced to native code (error K0310 if it is not traceable); derived values are read-only "
        "(animate the sources). For a single signal, use `x.map(fn)`.",
        '''
import kinemo as k

@k.scene
def derived(s: k.Scene):
    w = k.signal(2.0)
    h = k.signal(1.0)
    area = k.computed(lambda: w() * h())
    box = k.Rect(w=w, h=h).place(at="center")
    label = k.Text(lambda: f"area = {area():.1f}").place(at="top", margin=0.8)
    s.add(box, label)
    s.play(w.to(4), h.to(2), duration=2)
''',
        related=("Expr.map", "k.signal", "k.python"),
    ),
    DocEntry(
        "Expr.map",
        "Reactive",
        "Applies a function to a signal: `hour.map(solar_curve)`. The function is traced to "
        "native code, so use `k` functions (`k.sin`, `k.where`...), not `math` or `if`; "
        "for opaque Python, `x.map(k.python(fn))`.",
        '''
import kinemo as k

def solar_curve(h: float) -> float:
    return k.max(0, 6 * k.sin(k.pi * (h - 6) / 12))

@k.scene
def mapping(s: k.Scene):
    hour = k.time.map(lambda t: t * 4)
    radius = hour.map(solar_curve) * 0.2 + 0.1
    sun = k.Circle(r=radius, fill=k.YELLOW, fill_opacity=1).place(at="center")
    s.add(sun)
    s.wait(5)
''',
        related=("k.computed", "k.python", "k.time"),
        aliases=("Signal.map",),
    ),
    DocEntry(
        "k.list",
        "Reactive",
        "List signal. Plain Python lists are not tracked; `k.list([...])` records "
        "`append`, `insert`, `pop` and `swap` at the cursor, and lambdas that read it with `items()` "
        "follow the changes.",
        '''
import kinemo as k

@k.scene
def queue_demo(s: k.Scene):
    queue = k.list(["ann", "bea"])
    label = k.Text(lambda: f"queue: {queue()}").place(at="center")
    s.add(label)
    s.wait(1)
    queue.append("cal")
    s.wait(1)
''',
        related=("k.signal",),
    ),
    DocEntry(
        "k.python",
        "Reactive",
        "Marks an opaque Python function (external libraries, `math`, untraceable logic). It "
        "is precomputed in the resolve phase, one call per frame, and the render only reads the table. "
        "`vectorized=True` receives the whole timeline as a numpy array. Prefer `k` functions: "
        "they run natively at no extra cost.",
        '''
import math

import kinemo as k

def opaque(t: float) -> float:
    return 1 + 0.5 * math.sin(t) ** 2

@k.scene
def explicit_cost(s: k.Scene):
    c = k.Circle(r=k.time.map(k.python(opaque))).place(at="center")
    s.add(c)
    s.wait(3)
''',
        related=("Expr.map", "k.computed"),
    ),
    DocEntry(
        "k.lerp",
        "Reactive",
        "Interpolation modes of a signal, passed as `k.signal(..., lerp=)`: `linear` "
        "(default), `round` (integers), `step` (switches at the end), `step_start` (switches at the "
        "start) and `pointwise` (lists of points, point by point).",
        '''
import kinemo as k

@k.scene
def counter(s: k.Scene):
    n = k.signal(0, lerp=k.lerp.round)
    label = k.Text(lambda: f"{n():.0f} steps", size=0.8).place(at="center")
    s.add(label)
    s.play(n.to(10), duration=2)
''',
        related=("k.signal",),
        signature="k.lerp.linear | k.lerp.round | k.lerp.step | k.lerp.step_start | k.lerp.pointwise",
    ),
)
