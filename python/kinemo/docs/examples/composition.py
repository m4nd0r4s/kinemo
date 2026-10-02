"""Composition: `k.seq`, `k.par`, `k.stagger`, `@k.clip`, `.with_`, `k.ease`."""

from __future__ import annotations

from ..entry import DocEntry

ENTRIES = (
    DocEntry(
        "k.seq",
        "Composition",
        "Composes animations in sequence: each one starts when the previous one ends. The result "
        "is an `Animation` like any other and can be rescaled with `duration=`.",
        '''
import kinemo as k

@k.scene
def sequence(s: k.Scene):
    box = k.Square(2).place(at="center")
    label = k.Text("box").place(inside=box)
    s.play(k.seq(k.draw(box), k.write(label)), duration=2)
    s.wait(0.5)
''',
        related=("k.par", "k.stagger", "Scene.play"),
    ),
    DocEntry(
        "k.par",
        "Composition",
        "Composes animations in parallel: they all start together and the group lasts as long as "
        "the longest one. `s.play(a, b)` is defined as `s.play(k.par(a, b))`; use `k.par` when "
        "the parallel group is part of another composition.",
        '''
import kinemo as k

@k.scene
def parallel(s: k.Scene):
    a = k.Circle(r=0.7).place(at="left", margin=3)
    b = k.Circle(r=0.7).place(at="right", margin=3)
    title = k.Text("Together").place(at="top", margin=0.8)
    s.play(k.seq(k.par(k.draw(a), k.draw(b)), k.write(title)))
    s.wait(0.5)
''',
        related=("k.seq", "k.stagger", "Scene.play"),
    ),
    DocEntry(
        "k.stagger",
        "Composition",
        "Staggers a list of animations: each one starts `lag` seconds after the previous one. "
        "`order=` changes the order: `\"sequence\"` (default), `\"reverse\"`, `\"center\"` or "
        "`\"random(seed)\"`.",
        '''
import kinemo as k

@k.scene
def cascade(s: k.Scene):
    bars = [k.Bar(v) for v in [3, 5, 2, 6, 4]]
    row = k.Row(*bars, gap=0.3, align="bottom").place(at="center")
    s.play(k.stagger([k.grow(b, from_="bottom") for b in row], lag=0.1))
    s.wait(0.5)
''',
        related=("k.seq", "k.par", "k.grow"),
    ),
    DocEntry(
        "k.clip",
        "Composition",
        "Decorator that turns a function `def name(s: k.Scene, ...)` into a reusable sequence "
        "with its own cursor. Calling the clip returns an `Animation`, which composes with "
        "`s.play`, `k.seq` and `k.par` and can be rescaled with `duration=`.",
        '''
import kinemo as k

@k.clip
def present(s: k.Scene, obj: k.Node) -> None:
    s.play(k.draw(obj))
    s.play(k.indicate(obj))

@k.scene
def with_clip(s: k.Scene):
    a = k.Circle(r=0.8).place(at="left", margin=3)
    b = k.Square(1.6).place(at="right", margin=3)
    s.play(present(a), present(b))
''',
        related=("k.seq", "Scene.play", "k.Component"),
        signature="@k.clip",
    ),
    DocEntry(
        "Animation.with_",
        "Composition",
        "Returns a copy of the animation with a different duration, easing or delay. Animations "
        "are immutable values: the original does not change.",
        '''
import kinemo as k

@k.scene
def variation(s: k.Scene):
    dot = k.Dot(r=0.25, x=-4)
    s.add(dot)
    move = dot.to(x=4)
    s.play(move.with_(duration=2, ease=k.ease.out_back, delay=0.2))
''',
        related=("k.ease", "Node.to"),
    ),
    DocEntry(
        "k.ease",
        "Composition",
        "Easing curves. Every verb and every `.to()` uses `k.ease.smooth` (cubic in-out) by "
        "default. Also: `linear`, `in_`, `out`, `in_out`, `out_back`, `out_elastic`, "
        "`spring(stiffness, damping)`, `steps(n)` and `custom(fn)` for any f: [0, 1] → ℝ.",
        '''
import kinemo as k

@k.scene
def easing(s: k.Scene):
    a = k.Dot(r=0.2, x=-4, y=1)
    b = k.Dot(r=0.2, x=-4, y=-1)
    s.add(a, b)
    s.play(a.to(x=4, ease=k.ease.linear), b.to(x=4, ease=k.ease.out_elastic), duration=2)
''',
        related=("Animation.with_", "Scene.play"),
    ),
)
