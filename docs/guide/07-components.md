# Components

A component is kinemo's one form of reusable object: a subclass of `k.Component` that
declares its inputs and outputs in the class body and builds its visual in `build()`. Every
built-in object with structure (`k.Axes`, `k.Bar`, `k.BarChart`...) is written this way,
with the same public API you use. This guide shows how to declare props, outputs and
events, how the verb protocol (`enter`, `exit`, `indicate`) works, how to share values
through context, and how to keep the whole thing type-checked.

Reference: [components](../reference/components.md) ([`k.Component`](../reference/components.md#k-component),
[`k.prop`](../reference/components.md#k-prop), [`k.context`](../reference/components.md#k-context)),
[events](../reference/events.md).

## Anatomy

A component has three channels:

| Channel | Direction | Declaration | Used from outside as |
| --- | --- | --- | --- |
| Reactive prop | In | `name: k.Prop[T] = k.prop(default)` | `Gauge(value=signal)`, `g.to(value=5)` |
| Static field | In | `name: T = default` or `k.field(default, ...)` | `Gauge(thickness=0.9)` |
| Out | Out (continuous) | `name: k.Out[T]` | `bat.soc`, `bat.soc.now` |
| Event | Out (discrete) | `name: k.Event` or `name: k.Event[Payload]` | `@bat.full.on`, `s.wait_for(bat.full)` |

The smallest useful component:

```python
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
```

- Arguments are passed by keyword: `Tag(text="Hello")`. Transform props (`x`, `scale`,
  `opacity`...) and `name=` are accepted too.
- `build()` runs **once, at construction**, and returns the visual (usually a `k.Group`).
  Inside it, `.now` and the whole object API are valid.
- **Parts are attributes.** Objects stored on `self.*` are public and addressable from
  outside (`tag.box.to(...)`). A `_` prefix makes a part private for `inspect` and
  autocomplete.
- **A component is a group.** It accepts `.place`, `.to()`, every verb, `copy()` (which
  rebuilds it with the same arguments) and can be a child of a container.

## Reactive props

A reactive prop accepts a constant, a signal or a lambda from the outside, and **inside the
component it is always a signal**, so the internal code is uniform:

```python
import kinemo as k


class Gauge(k.Component):
    value: k.Prop[float] = k.prop(0.0, range=(0, 5))
    thickness: float = k.field(0.6, range=(0.2, 2))

    def build(self) -> k.Node:
        self.track = k.Rect(w=self.thickness, h=5.2, fill_opacity=0)
        self.bar = k.Rect(w=self.thickness - 0.1, h=self.value + 0.01, fill=k.GREEN, fill_opacity=1, stroke_width=0)
        self.bar.place(inside=self.track, align="bottom", pad=0.1)
        self.label = k.Text(lambda: f"{self.value():.1f}", size=0.4).place(below=self.track, gap=0.25)
        return k.Group(self.track, self.bar, self.label)


@k.scene
def gauges(s: k.Scene):
    level = k.signal(1.0)
    a = Gauge(value=2.0)                    # a constant
    b = Gauge(value=level, thickness=0.9)       # a signal: b follows it
    c = Gauge(value=lambda: 5 - level())    # a lambda
    row = k.Row(a, b, c, gap=1.2, align="bottom").place(at="center")
    s.play(k.fade_in(row))
    s.play(a.to(value=4), level.to(3), duration=2)
    s.wait(0.5)
```

- `self.value` is a `Signal[float]`: use it directly (`h=self.value + 0.01`) or read it
  with `self.value()` inside lambdas.
- From outside, animate it like any prop: `a.to(value=4)`.
- `k.prop(default, range=(lo, hi))` validates constants at construction (an out-of-range
  value is `K0105`).

## Static fields

A field without `k.Prop` is **static**: a plain value fixed at construction (`self.thickness`
is a `float`). Use it for structure that does not animate: sizes, counts, labels, options.

- `k.field(default, range=(lo, hi))` or `k.field(default, choices=[...])` validates the
  value at construction (`K0105` when it is out of range or not one of the choices).
- Static fields reject signals: passing one is `K0601`, whose fix is to declare the field as
  `k.Prop[T]`.
- They cannot be reassigned after construction.
- Do not reuse the names of built-in props (`x`, `y`, `scale`, `opacity`, `width`,
  `height`, `left`, `center`...). A field called `width` silently hides the layout-derived
  `width` of the component; Pyright strict reports it as an incompatible override, but
  `kinemo check` does not.

## Outs

An out is a continuous output: a read-only signal that the component computes in
`build()` and the outside world can read or bind to.

```python
import kinemo as k


class Tank(k.Component):
    flow: k.Prop[float] = k.prop(0.5)
    capacity: float = 3.0

    level: k.Out[float]
    full: k.Event

    def build(self) -> k.Node:
        self.level = k.integrate(self.flow, initial=0.0, clamp=(0, self.capacity))
        k.when(self.level >= self.capacity, self.full)
        self.body = k.Rect(w=2, h=self.capacity + 0.2, fill_opacity=0)
        self.water = k.Rect(w=1.8, h=self.level + 0.01, fill=k.BLUE, fill_opacity=0.8, stroke_width=0)
        self.water.place(inside=self.body, align="bottom", pad=0.1)
        return k.Group(self.body, self.water)


@k.scene
def tank(s: k.Scene):
    t = Tank(flow=1.0).place(at="center")
    gauge = k.Text(lambda: f"{t.level():.1f} L", size=0.45).place(above=t, gap=0.3)
    s.add(t, gauge)
    e = s.wait_for(t.full, timeout=10)
    s.play(k.flash(t.body, color=k.BLUE))
    s.play(t.to(flow=-1.0))
    s.wait(1)
    s.play(k.write(k.Text(f"full at {e.time:.1f} s", size=0.4).place(below=t, gap=0.3)))
```

Every `k.Out` must be assigned by the end of `build()`; otherwise `K0602`.

## Events

An event is an instant on the timeline with an optional typed payload. Declare it with
`name: k.Event` (no payload) or `name: k.Event[Payload]`, and fire it in one of two ways:

- `k.when(cond, self.event)` in `build()`: fires on every false → true edge of `cond`;
- `self.event.emit(payload)` in a clip or `build()`: fires at the cursor.

From outside, react with `@obj.event.on` (also do this, with its own cursor) or continue
the script with `s.wait_for(obj.event)`. Handlers receive `e: k.EventInfo` with `e.time`,
`e.data` (the typed payload), `e.count` and `e.value(signal)`. String-based events do not
exist.

Component effects are active **while the component is in the scene**: a `k.when` registered
in `build()` does nothing before the entrance or after the exit. Because `k.when` reacts to
edges, a condition that is already true when the component enters does not fire.

## The verb protocol: `enter`, `exit`, `indicate`

A component can define how it enters, leaves and is emphasized. The `k` verbs call these
methods when they exist and fall back to the default behavior on the group otherwise:

| Method | Used by |
| --- | --- |
| `enter(self) -> k.Animation` | `k.draw`, `k.write`, `k.fade_in`, `k.grow` |
| `exit(self) -> k.Animation` | `k.fade_out`, `k.shrink` |
| `indicate(self) -> k.Animation` | `k.indicate` |

The animation you return is rescaled to the verb's duration, so `k.draw(comp, duration=2)`
still lasts 2 s.

## Named transitions and clips

Methods that return an `Animation` are **named transitions**. Document each one as the
`.to()` it stands for. Methods decorated with `@k.clip` receive their own `s` and can use
the whole timeline API, including emitting events:

```python
from dataclasses import dataclass

import kinemo as k

Unit = k.context("unit", default="kWh")


@dataclass
class Reading:
    value: float


class Meter(k.Component):
    level: k.Prop[float] = k.prop(0.0, range=(0, 1))
    unit: str = k.from_context(Unit)
    track_width: float = k.field(1.0, range=(0.5, 3))

    filled: k.Out[float]
    full: k.Event
    read: k.Event[Reading]

    def build(self) -> k.Node:
        self.filled = k.clamp(self.level, 0, 1)
        k.when(self.filled >= 1, self.full)
        self.track = k.RoundedRect(w=self.track_width, h=3, radius=0.1)
        self.bar = k.Rect(w=self.track_width - 0.2, h=self.filled * 2.8 + 0.01, fill=k.GREEN, fill_opacity=0.9, stroke_width=0)
        self.bar.place(inside=self.track, align="bottom", pad=0.1)
        self.label = k.Text(lambda: f"{self.filled() * 100:.0f} {self.unit}", size=0.35)
        self.label.place(below=self.track, gap=0.25)
        return k.Group(self.track, self.bar, self.label)

    def enter(self) -> k.Animation:
        return k.seq(k.draw(self.track), k.grow(self.bar, from_="bottom"), k.fade_in(self.label))

    def exit(self) -> k.Animation:
        return k.fade_out(self.track, self.bar, self.label)

    def indicate(self) -> k.Animation:
        return k.flash(self.track, color=k.GREEN)

    def highlight(self, color: k.Color = k.YELLOW) -> k.Animation:
        """Named transition: equivalent to self.track.to(stroke=color)."""
        return self.track.to(stroke=color)

    @k.clip
    def fill_up(self, s: k.Scene) -> None:
        s.play(self.to(level=1), duration=2)
        s.play(k.indicate(self))
        self.read.emit(Reading(self.filled.now))


@k.scene
def meter(s: k.Scene):
    with k.provide(Unit, "%"):
        m = Meter(level=0.2, track_width=1.5).place(at="center")

    @m.read.on
    def _(s: k.Scene, e: k.EventInfo[Reading]) -> None:
        note = k.Text(f"read {e.data.value:.0%}", size=0.35).place(right_of=m, gap=0.4)
        s.play(k.fade_in(note))
        s.play(k.fade_out(note))

    s.play(k.draw(m))              # uses Meter.enter
    s.play(m.highlight(k.TEAL))
    s.play(m.fill_up())
    s.wait(2)
    s.play(k.fade_out(m))          # uses Meter.exit
```

## Context: `k.context`, `k.provide`, `k.from_context`

Some values are needed by many components: a clock, a unit, a scale. Instead of passing
them down prop by prop, declare a **context** at module level and provide it around the
construction of the components:

```python
import kinemo as k

Clock = k.context("clock", default=k.time)


class Hand(k.Component):
    time: k.Prop[float] = k.from_context(Clock)
    length: float = 1.2

    def build(self) -> k.Node:
        dial = k.Circle(r=self.length, stroke_width=2, opacity=0.4)
        # The hand turns about its start (anchor at the bottom of its box), in the dial's center.
        hand = k.Line(start=(0, 0), end=(0, self.length), anchor=(0, -1), rotate=-self.time * 30, stroke_width=4)
        return k.Group(dial, hand)


@k.scene
def clocks(s: k.Scene):
    hour = k.time.map(lambda t: t * 4)
    slow = Hand().place(at="left", margin=4)                 # context default: k.time
    with k.provide(Clock, hour):
        fast = Hand().place(at="center")                     # time = hour, via context
        explicit = Hand(time=k.time * 2).place(at="right", margin=4)   # an argument wins
    s.add(slow, fast, explicit)
    s.wait(3)
```

- Context is resolved **at the component's construction**, in the lexical scope of the
  build phase, not dynamically: what matters is which `with k.provide(...)` block was open
  when the constructor ran.
- An explicit argument always wins over the context; without any `provide`, the context's
  `default=` applies.
- `k.from_context(ctx)` works as the default of a reactive prop or of a static field.
- The theme is a built-in context: `@k.scene(theme=k.themes.blueprint)` and the
  `k.theme.*` tokens.
- `kinemo inspect` shows where each prop value came from.

## Content as a prop

A component that wraps other objects declares a static field of type `k.Node` and places
it in `build()`. The child then belongs to the component (one parent per object):

```python
import kinemo as k


class Card(k.Component):
    content: k.Node
    title: str = "Card"

    def build(self) -> k.Node:
        self.frame = k.RoundedRect(w=4, h=2.5, radius=0.2)
        self.heading = k.Text(self.title, size=0.4).place(inside=self.frame, align="top", pad=0.25)
        self.content.place(inside=self.frame, align="bottom", pad=0.4)
        return k.Group(self.frame, self.heading, self.content)


@k.scene
def cards(s: k.Scene):
    a = Card(content=k.Text("42 kWh", size=0.6), title="Today")
    b = Card(content=k.Circle(r=0.5, fill=k.YELLOW, fill_opacity=1), title="Sun")
    row = k.Row(a, b, gap=0.8).place(at="center")
    s.play(k.stagger([k.fade_in(c) for c in row], lag=0.2))
    s.play(k.indicate(a.content))
```

## Typing with `k.prop`

Components are designed to pass Pyright in strict mode (the configuration `kinemo new`
writes). The declarations are descriptors for the type checker:

| Declaration | In the class body | On the instance |
| --- | --- | --- |
| `power: k.Prop[float] = k.prop(0.0)` | `Prop[float]` | `Signal[float]` |
| `capacity: float = 10.0` | `float` | `float` |
| `initial: float = k.field(0.2, range=(0, 1))` | `float` | `float` |
| `soc: k.Out[float]` | — | `Expr[float]`; `self.soc = expr` type-checks in `build()` |
| `full: k.Event` / `k.Event[P]` | — | an event source (`.on`, `.emit`) |
| `time: k.Prop[float] = k.from_context(Clock)` | `Any` on purpose | `Signal[float]` |

Write prop defaults as `k.prop(default)`. A bare `power: k.Prop[float] = 0.0` works at
runtime, but no descriptor type can accept a plain `float` in the class body while reading
as `Signal[float]` on instances, so Pyright reports that assignment.

> **Common mistakes**
>
> | You see | Why | Fix |
> | --- | --- | --- |
> | `K0601 Ring.thickness is a static field and does not accept reactive values` | A signal or lambda passed to a field declared as `T`. | Declare it `thickness: k.Prop[float] = k.prop(0.2)`. |
> | `K0602 Counter.build() did not assign total` | A `k.Out` was declared but not assigned in `build()`. | Assign it: `self.total = ...` before returning. |
> | `K0105 Gauge.value = 9 is outside the range [0, 5]` | A constant out of the `range=` of `k.prop` / `k.field`. | Pass a valid value or widen the range. |
> | `K0105 static fields cannot change after construction` | Reassigning a static field outside `build()`. | Make it a `k.Prop[T]` and animate it with `.to()`. |
> | `K0105 ... is an output, not an argument` | Passing an out or event to the constructor. | Outs are computed inside; read them from outside. |
> | `K0105 ... build() must return a k.Node` | `build()` returned `None` or a list. | Return the visual: `return k.Group(...)`. |
> | `K0103` when building | The same object used in two components (or in a component and a group). | Create one object per component, or use `copy()`. |
> | `K0702` waiting for a component event | The `k.when` condition never had a false → true edge while the component was in the scene (for example, already true at entrance). | Add the component earlier, or fire the event with `self.event.emit()` from a clip. |
> | Pyright: "`width` overrides symbol of same name in class `Node`" | A field named like a built-in prop. | Rename it (`thickness`, `track_width`...). |
> | Pyright: "`float` is not assignable to `Prop[float]`" | A bare default on a reactive prop. | `k.prop(0.0)`. |
