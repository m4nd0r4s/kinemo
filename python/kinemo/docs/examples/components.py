"""Components: `k.Component`, `k.Prop`, `k.Out`, `k.Event`, `k.field`, `k.prop`, context."""

from __future__ import annotations

from ..entry import DocEntry

_CONTEXT_EXAMPLE = '''
import kinemo as k

Scale = k.context("scale", default=1.0)

class Point(k.Component):
    r: k.Prop[float] = k.from_context(Scale)

    def build(self) -> k.Node:
        return k.Dot(r=self.r * 0.2)

@k.scene
def context(s: k.Scene):
    with k.provide(Scale, 2.0):
        p = Point().place(at="center")
    s.play(k.fade_in(p))
'''

ENTRIES = (
    DocEntry(
        "k.Component",
        "Components",
        "The only kind of reusable object: a subclass with props (`k.Prop[T]`, inputs), "
        "static fields (`name: T = default`), outs (`k.Out[T]`, outputs as signals) and events "
        "(`k.Event`), plus a `build()` that runs once and returns the visual. Parts stored "
        "on `self.*` are addressable from outside. Verbs use `enter()`/`exit()`/`indicate()` "
        "when the component defines them.",
        '''
import kinemo as k

class Tag(k.Component):
    text: str = "kinemo"

    def build(self) -> k.Node:
        self.box = k.RoundedRect(w=3, h=1)
        self.label = k.Text(self.text).place(inside=self.box)
        return k.Group(self.box, self.label)

@k.scene
def component(s: k.Scene):
    tag = Tag(text="Hello").place(at="center")
    s.play(k.draw(tag))
    s.play(tag.box.to(color=k.BLUE))
''',
        related=("k.Prop", "k.Out", "k.Event", "k.clip"),
        signature="class Name(k.Component)",
    ),
    DocEntry(
        "k.Prop",
        "Components",
        "Declares a reactive component prop: `power: k.Prop[float] = k.prop(0.0)`. Inside "
        "the component it is always a signal (`Signal[float]`), even if the author passed "
        "a constant; from outside, it accepts a value, signal or lambda and animates with "
        "`comp.to(power=...)`. The default via `k.prop` is what passes Pyright strict.",
        '''
import kinemo as k

class Gauge(k.Component):
    value: k.Prop[float] = k.prop(0.0)

    def build(self) -> k.Node:
        return k.Rect(w=0.6, h=self.value + 0.01, fill=k.GREEN, fill_opacity=1)

@k.scene
def gauge(s: k.Scene):
    m = Gauge(value=1.0).place(at="center")
    s.add(m)
    s.play(m.to(value=3))
''',
        related=("k.Component", "k.prop", "k.field"),
        signature="name: k.Prop[T] = default",
    ),
    DocEntry(
        "k.Out",
        "Components",
        "Declares a continuous component output: `soc: k.Out[float]`. It must be assigned in "
        "`build()` (error K0602) and is read from outside as a read-only signal (`bat.soc`).",
        '''
import kinemo as k

class Counter(k.Component):
    total: k.Out[float]

    def build(self) -> k.Node:
        self.total = k.integrate(0.5)
        return k.Text(lambda: f"{self.total():.1f}")

@k.scene
def output(s: k.Scene):
    c = Counter().place(at="center")
    bar = k.Rect(w=0.5, h=c.total + 0.01).place(below=c, gap=0.3)
    s.add(c, bar)
    s.wait(3)
''',
        related=("k.Component", "k.integrate"),
        signature="name: k.Out[T]",
    ),
    DocEntry(
        "k.Event",
        "Components",
        "Declares an event on a component or a `k.State`: `full: k.Event` or, with a typed "
        "payload, `bounce: k.Event[Impact]`. Fire it with `k.when(cond, self.full)` or "
        "`self.full.emit()`; react with `@obj.full.on` or `s.wait_for(obj.full)`. String-based "
        "events do not exist.",
        '''
import kinemo as k

class Alarm(k.Component):
    rang: k.Event

    def build(self) -> k.Node:
        k.when(k.time >= 2, self.rang)
        return k.Circle(r=0.5, fill=k.RED, fill_opacity=1)

@k.scene
def event(s: k.Scene):
    alarm = Alarm().place(at="center")
    s.add(alarm)
    s.wait_for(alarm.rang, timeout=5)
    s.play(k.flash(alarm))
''',
        related=("EventSource.on", "k.when", "Scene.wait_for"),
        signature="name: k.Event  ·  name: k.Event[Payload]",
    ),
    DocEntry(
        "k.field",
        "Components",
        "Validated default for a static component field: "
        "`k.field(0.2, range=(0, 1))` or `k.field(\"a\", choices=[...])`. Out-of-range values "
        "are an error at construction; static fields reject signals (K0601).",
        '''
import kinemo as k

class Ring(k.Component):
    thickness: float = k.field(0.2, range=(0.05, 1))

    def build(self) -> k.Node:
        return k.Circle(r=1, stroke_width=self.thickness * 20)

@k.scene
def ring(s: k.Scene):
    r = Ring(thickness=0.4).place(at="center")
    s.play(k.draw(r))
''',
        related=("k.prop", "k.Component"),
    ),
    DocEntry(
        "k.prop",
        "Components",
        "Validated default for a reactive prop: `k.prop(0.0, range=(-5, 5))`. Constants "
        "are validated at construction; for reactive values, lint W0602 samples the timeline.",
        '''
import kinemo as k

class Needle(k.Component):
    angle: k.Prop[float] = k.prop(0.0, range=(0, 360))

    def build(self) -> k.Node:
        return k.Line(start=(0, 0), end=(2, 0), rotate=self.angle)

@k.scene
def needle(s: k.Scene):
    p = Needle(angle=30)
    s.add(p)
    s.play(p.to(angle=150))
''',
        related=("k.Prop", "k.field"),
    ),
    DocEntry(
        "k.context",
        "Components",
        "Declares a context (at module level): a value that many components need "
        "(clock, scale, unit), supplied with `k.provide` instead of passed down prop by prop. "
        "The theme is a built-in context.",
        _CONTEXT_EXAMPLE,
        related=("k.provide", "k.from_context"),
    ),
    DocEntry(
        "k.provide",
        "Components",
        "`with` block that supplies a context value to the components constructed inside it. "
        "It is resolved at construction (lexical scope of the build phase); passing the prop "
        "explicitly always wins over the context.",
        _CONTEXT_EXAMPLE,
        related=("k.context", "k.from_context"),
    ),
    DocEntry(
        "k.from_context",
        "Components",
        "Prop or field default that reads a context: "
        "`time: k.Prop[float] = k.from_context(Clock)`. Without `k.provide`, the context's "
        "`default=` applies.",
        _CONTEXT_EXAMPLE,
        related=("k.context", "k.provide"),
    ),
)
