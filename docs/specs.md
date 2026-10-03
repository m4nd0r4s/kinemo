# kinemo — Specification v1.0

Sep 30, 2026 · @m4nd0r4s

## Summary

kinemo is a Python library for creating explanatory animations (math, algorithms, engineering, data) with the visual quality of Manim, live preview, and an API designed to be written by people and by AI without errors. The author writes 100% Python; the engine that evaluates, lays out, and renders is a Rust core.

What changes compared to Manim:

| Problem in Manim | kinemo's answer |
| --- | --- |
| Write → render video → watch loop | `kinemo dev`: preview with hot reload and a draggable timeline; frame = pure function of t |
| Position by coordinates (`shift(UP*0.3)`) | Constraint-based layout (`above=`, `Row`, `Grid`) that follows motion |
| Queued `self.play`, hard composition | `play`/`start`, `seq`/`par`/`stagger`, `during`, `tempo`, reusable clips |
| ValueTracker + manual updaters | Reactive signals with automatic derivation |
| Dependency on a LaTeX installation | LaTeX syntax, built-in typesetting engine |
| Two forks with incompatible APIs | One package, strict semver, migration codemods |
| Only produces video | Video, GIF, frames, slides and (later) interactive web from the same source |
| Hard for AI (mixed APIs, opaque errors) | One form per concept, full typing, errors with fixes, machine-readable `check`/`inspect`/`snap` |

Audience: educational content creators, engineers and scientists who explain systems, and AI agents that generate videos from a description. The name `kinemo` was available on PyPI and crates.io on October 1, 2026; it still needs to be registered, and GitHub, domain, and trademark need to be checked.

## Core principles and rules

The whole API derives from seven rules. A feature that does not fit them does not go in, or the rules change explicitly in this spec.

1. **Scene code runs once and produces a timeline.** The frame at instant t is a pure function of t.
2. **Objects are values.** Creating an object does not put it in the scene; it enters with `s.add()` (instant) or with a verb (`k.draw`, `k.write`, …).
3. **Whatever takes time goes through `s.play` (blocks the cursor) or `s.start` (does not block).** Whatever is instant is a direct call: `s.add`, `s.remove`, `obj.set`, `x.set`.
4. **A state change is `obj.to(...)`.** Components may expose *named transitions* (`row.swap(i, j)`), always documented as sugar for a `.to()`.
5. **Position comes from constraints, not coordinates.** Coordinates exist, but they are the rare case.
6. **Passing a signal or a lambda creates a reactive binding.** There are no updaters.
7. **Two reads, two names.** `x.now` reads the value at the cursor during construction; `x()` reads in a tracked way inside reactive contexts.

Principles that guide the detailed decisions:

- **One name per concept.** No aliases. Sugar is only accepted when it is literally the definition of another form (`s.play(a, b)` ≡ `s.play(k.par(a, b))`).
- **Errors, never silent magic.** Every error comes with the fix in code; `kinemo check --fix` applies it. There is no lenient mode.
- **Full typing.** Pyright in strict mode passes with no `Any` in the public API; every kwarg has a type.
- **Verbs are module functions** (`k.draw`), state is an object method (`.to`, `.set`, `.place`). Autocomplete on `k.` lists everything that animates.
- **Determinism.** Same source + same assets = same output bytes.
- **The library uses its own system.** Every built-in object (`Axes`, `Math`, `Bar`) is a `k.Component` written with the public API.

## Architecture

The author only sees Python; everything below the IR is Rust, built on existing libraries whenever possible. The package is published as a single wheel (`pip install kinemo`), compiled with maturin + PyO3.

Layers:

1. **`kinemo` (pure Python, typed).** Public API, scene execution (build phase), event handlers, user lambdas.
2. **IR (Intermediate Representation).** Serializable scene graph: objects, props, bindings, expressions, constraints, animations, effects, and simulations. Binary format (MessagePack) with a JSON mirror for `inspect`. Versioned.
3. **`kinemo-core` (Rust).** Resolve, reactive graph evaluation, layout, interpolation, typesetting, tessellation, rasterization, encoding, caching.
4. **Outputs.** Video encoder, preview server, slide exporter; interactive web (WASM) on the roadmap.

&#91;embedded content: architecture · 4 layers\]

The IR is the boundary: everything above it is Python; everything below it can switch libraries without changing the API.

**Expression evaluation.** Every derived value is compiled to the IR by tracing whenever possible and evaluated in Rust, in parallel and without the GIL. Opaque Python functions only come in when the author explicitly marks them with `k.python(fn)`. They are precomputed in the resolve phase (one call per frame, batched, in-process) and the render only reads the resulting table. **The render never calls Python.** Details in Reactive system › Tracing.

**Data.** The data contract is Apache Arrow: the core accepts, zero-copy, any object that implements the Arrow PyCapsule Interface (`__arrow_c_stream__` / `__arrow_c_array__`). Polars is the reference library in the docs and examples; pandas ≥ 2.2, pyarrow, and duckdb work the same way. N-dimensional arrays (geometry, grids, images) come in through the buffer protocol, also zero-copy, which covers numpy. kinemo does not import any of these libraries; optional extras: `kinemo[polars]`, `kinemo[numpy]`.

Candidate libraries (to be validated in a prototype):

| Responsibility | Candidate | Note |
| --- | --- | --- |
| Python ↔ Rust bindings | PyO3 + maturin | Single wheel per platform |
| 2D rasterization (GPU) | Vello | Vector renderer using compute shaders |
| 2D rasterization (CPU / CI) | tiny-skia | GPU-less fallback, identical output in tests |
| Curve geometry | kurbo, lyon | Paths, offsets, tessellation |
| Boolean operations | i\_overlay | Union, intersection, difference of shapes |
| Text and fonts | parley + swash (or cosmic-text) | Shaping, line breaking, outlines |
| Math | typst (layout crates) + mitex | LaTeX syntax converted and typeset without TeX |
| Code highlighting | tree-sitter | Stable tokens for code morphs |
| Container layout | taffy | Flexbox/grid for `Row`, `Column`, `Grid` |
| Relative constraints | cassowary | `above=`, `left_of=`, alignments |
| SVG input | usvg | Import illustrations with addressable parts |
| 3D | wgpu | Same device as Vello |
| Video encoding | ffmpeg (bindings or pipe) | MP4/H.264, WebM/VP9 with alpha, GIF |
| Preview server | axum + WebSocket | On-demand frames for the browser |
| Data interop | arrow-rs + pyo3-arrow | Arrow PyCapsule Interface: polars, pandas, duckdb zero-copy |

Nothing in this table leaks into the API: swapping a component (e.g. Vello for another renderer) does not change a single line of user code.

## Execution model

A scene goes through three phases: build (Python, once), resolve (core, until stable), and render (core, per frame). Understanding these phases is understanding kinemo.

&#91;embedded content: three execution phases\]

If a handler schedules something that changes a condition, resolve runs again until nothing changes.

**Phase 1 — Build.** The body of the function decorated with `@k.scene` runs exactly once. There is a time **cursor**, starting at 0. Each call records something in the IR at the cursor position:

- `s.play(anim)` schedules and advances the cursor to the end of the animation;
- `s.start(anim)` schedules and does not advance;
- `s.wait(d)` advances `d` seconds;
- `s.add`, `s.remove`, `.set` record instant changes at the cursor;
- `k.when`, `.on`, `k.simulate`, `k.integrate` record effects and states to be resolved later.

In this phase, `x.now` returns the value of `x` at the cursor, taking into account everything already scheduled. This makes `if`, `for`, and ordinary Python logic valid in the script.

**Phase 2 — Resolve.** With the whole timeline known, the core:

1. precomputes simulations, integrals, and trails, sampling from start to end;
2. detects the instants at which `k.when` conditions go from false to true;
3. runs the `.on` handlers (in Python), which may schedule more animations;
4. repeats 1–3 until nothing changes, with a limit of 8 passes (beyond that: error `K0501`, event loop);
5. validates conflicts (two animations on the same prop, contradictory constraints) and runs the lints.

**Phase 3 — Render.** `frame(t)` evaluates the reactive graph at instant t, resolves the layout, interpolates, and draws. It is pure and memoized by dependency, so it can run out of order, in parallel, and while dragging the timeline. In this phase only tracked reads (`x()`) exist; writing to any signal is an error.

**Read contexts.**

| Read | Valid in | Meaning | Outside the context |
| --- | --- | --- | --- |
| `x.now` | Scene body, component `build()`, `.on` handlers | Snapshot at the cursor | Inside a lambda/computed: error `K0302` (would freeze the value) |
| `x()` | Lambdas in props, `k.computed`, functions passed to `.map` | Tracked read, re-evaluated when the dependency changes | In the scene body: error `K0301` with suggestion `x.now` |

**End of the scene.** The duration is the greater of the final cursor and the end of everything started with `start` or fired by events, plus `tail` (default 0.5 s, configurable in `@k.scene(tail=...)`).

## Scene and timeline

A scene is a decorated function that receives `s: k.Scene`; time is controlled only by the methods below.

```python
import kinemo as k

@k.scene(size="1080p", fps=60, background=k.theme.bg, seed=0, tail=0.5)
def hello(s: k.Scene):
    title = k.Text("Hello, kinemo").place(at="center")
    s.play(k.write(title))
    s.play(title.to(color=k.BLUE, scale=1.5))
    s.wait(1)
```

**Time methods.**

| Call | Cursor | Returns | Use |
| --- | --- | --- | --- |
| `s.play(*anims, duration=, ease=, at=)` | Advances to the end | `TimeSpan` | Script step; several args = parallel |
| `s.start(*anims, ...)` | Does not advance | `TimeSpan` | Background animation, clock, simulation |
| `s.wait(d=1.0)` | Advances `d` | `TimeSpan` | Pause |
| `s.wait_for(event, count=1, timeout=)` | Jumps to the event | `EventInfo` | Continue the script when something happens |
| `s.mark(name=None, slide=False)` | Does not advance | `float` | Time anchor, audio sync, slide break |
| `with s.during(*anims, duration=, ease=, revert=):` | Block | — | Applies on entry, reverts on exit |
| `with s.tempo(f, to=None):` | Block | — | Multiplies the speed of everything inside |
| `with s.voice(text_or_audio):` | Block | — | Block lasts at least as long as the audio |

**Duration rules.**

- Every verb and every `.to()` has a default duration of 1 s and default easing `k.ease.smooth` (cubic in-out). Both accept `duration=`, `ease=`, and `delay=`.
- `duration=` in `s.play` sets the **total duration** of the set; the content is rescaled proportionally. `s.play(a, b, duration=2)` makes both last 2 s; `s.play(k.seq(a, b), duration=2)` makes each last 1 s if they had the same duration.
- `at=` schedules at an absolute instant (`at=s.marks["x"] + 0.5` or `at=h.end`) and does not move the cursor. In that case `play` behaves like `start`, and lint `W0110` suggests switching to `start` to make the intent explicit.

**`s.during`.** Applies the state animations on entering the block and reverts them, animated, on exiting. The reversion uses the same duration and easing as the entry; `revert="instant"`, `revert=0.3` (another duration), or `revert=k.ease.out` (another easing) change that. Only reversible animations are accepted (`.to`, `k.indicate`); entry/exit verbs are error `K0204`.

```python
with s.during(a.to(color=k.YELLOW), b.to(color=k.YELLOW)):
    s.wait(0.2)
    if a.value.now > b.value.now:
        s.play(row.swap(j, j + 1))
```

**`s.tempo`.** `with s.tempo(4):` divides all durations and waits inside the block by 4. `s.tempo(1, to=8)` progressively speeds up from 1× to 8× over the block. Nested tempos multiply. Signals derived from `k.time` are not affected (wall-clock time does not change).

**`s.voice`.** Takes text (TTS through the provider configured in `kinemo.toml`) or an audio file. The block lasts `max(audio, content)`. Marked words become time marks: `s.voice("This is the [leg]{c1} and this is the [other]{c2}")` creates `s.marks["c1"]` and `s.marks["c2"]` at the instant the word is spoken.

**TTS providers.** `k.TTSProvider` is an interface; each provider is a separate package (`kinemo-tts-<name>`), chosen in `kinemo.toml`. The default is a local, offline TTS (candidate: Piper, to be validated) when installed. Without a provider, `s.voice` uses silence with a duration estimated from the text (150 words/min) and emits lint `W1401`, so that the scene can be timed and `dev` works without a network. Generated audio is cached by a hash of text + voice + provider.

**Time as a signal.** `k.time` is the global scene time (read-only). Inside components, `self.age` is the time since the component entered the scene.

## Objects and scene graph

Every visible object is a node in a tree; every public property of a node is a signal.

**Lifecycle.** An object goes through three states, always in order:

| State | Entered via | Can receive `.to()` | Exited via |
| --- | --- | --- | --- |
| Created (outside the scene) | Constructor `k.Circle()` | No (error `K0101`) | `s.add` or entry verb |
| In the scene | `s.add(obj)`, `k.draw`, `k.write`, `k.fade_in`, `k.grow` | Yes | `s.remove` or exit verb |
| Removed | `s.remove(obj)`, `k.fade_out`, `k.shrink` | No (error `K0102`, with the line and instant of the exit) | Entry verb again |

**State changes.**

```python
obj.set(color=k.RED)                 # instant, at the cursor
s.play(obj.to(color=k.RED, scale=2)) # animated
obj.set(x=other.x)                   # reactive binding from the cursor on
obj.unbind("x")                      # removes the binding; current value is kept
```

`.set` and `.to` accept any public prop of the type, typed via overloads. Reserved names that are never props: `duration`, `ease`, `delay`, `place`.

**Props common to every object.**

| Group | Props |
| --- | --- |
| Transform | `x`, `y`, `position`, `rotate` (degrees), `scale`, `scale_x`, `scale_y`, `anchor` (pivot point, default `"center"`) |
| Style | `color` (shorthand for stroke and fill), `fill`, `fill_opacity`, `stroke`, `stroke_width`, `dash`, `opacity` |
| Composition | `z` (draw order; with equal `z`, later entrances draw on top), `visible`, `clip` |
| Read-only (derived) | `width`, `height`, `bbox`, `left`, `right`, `top`, `bottom`, `center` |

**Coordinates.** The default frame measures 16 × 9 units, origin at the center, y pointing up (math convention, as in Manim). `s.frame` exposes `left`, `right`, `top`, `bottom`, `center`, and `safe` (safe area with a 0.5 u margin). Every position prop is **local to the parent**; `obj.world.position` gives the global position.

**Groups.** `k.Group(a, b, c)` groups; transforms compose, `opacity` multiplies. An object has exactly one parent: adding it to a second parent is error `K0103`, with the suggestion `obj.copy()` or `k.reparent(obj, new_parent)` (an animation that keeps the global position). Groups are iterable and indexable (`g[0]`, `for o in g`); indices reflect the order **at the cursor**.

**Copies.** `obj.copy()` creates a new identity with the same reactive bindings; `obj.copy(frozen=True)` copies the values at the cursor, without bindings.

**Identity.** An object's identity is its Python identity. `key=` is only needed to match **different** objects in a morph or across the scenes of a movie (`k.Circle(key="sun")`).

**Theme.** Default colors, fonts, stroke widths, and durations come from a `k.Theme`, provided via context (see Components). `k.theme.accent`, `k.theme.fg`, `k.theme.bg` are tokens; `k.RED`, `k.BLUE`, etc. are the fixed palette. Changing the theme changes the entire scene without touching the code.

## Constraint-based layout

Position is declared as a relation to the frame or to another object, and the relation keeps holding while the objects move.

**`.place(...)`** — returns the object itself (chains with the constructor).

| Argument | Example | Effect |
| --- | --- | --- |
| `at=` | `at="center"`, `"top-left"`, `(2, 1)`, `ax.point(3, 9)` | Anchor on the frame, at a point, or at a point of another object |
| `above=` `below=` `left_of=` `right_of=` | `below=tri` | Side relative to another object |
| `inside=` | `inside=box, align="bottom", pad=0.1` | Inside another object, aligned; `pad=` is the inner distance |
| `gap=` | `gap=0.5` or `gap=sim.y` | Distance; accepts a signal |
| `margin=` | `margin=0.5` | Distance from the frame edge (with `at=`) |
| `align=` | `align="left"` | Alignment on the perpendicular axis |
| `clamp=` | `clamp=True` | Keeps it inside `s.frame.safe` |

**`.to_place(...)`** — the `.to` of `.place`: the same arguments plus `duration=`, `ease=`, `delay=`; returns an animation from the current placement to the new one.

**Containers** — flexbox and grid (via taffy):

```python
k.Row(a, b, c, gap=0.4, align="bottom")
k.Column(title, body, gap=0.2, align="left")
k.Grid(cards, cols=3, gap=0.3)
k.Stack(background, icon)             # overlapping, center-aligned
k.Grid(cards, cols=3).fit(s.frame.safe)  # scales until it fits
```

Containers are groups: changing children (inserting, removing, reordering) animates the reflow automatically when done with container transitions (`row.swap(i, j)`, `row.insert(i, obj)`, `row.pop(i)`), all sugar for `row.to(children=[...])`.

**Resolution.** Containers are resolved first (inside out); then the relative constraints between objects (cassowary). The result is memoized: it is only recomputed when an input changes (text size, a signal in a `gap`, the position of a reference object).

**Constraint vs. animation.** An axis pinned by a constraint cannot be animated directly:

```python
title.place(above=tri)
s.play(title.to(x=3))                       # error K0401: x is pinned to tri
s.play(title.to_place(right_of=tri))        # OK: constraint change, animated
s.play(title.to(x=3, unpin=True))           # OK: release and animate
```

**Conflicts and cycles.** `a.place(below=b)` + `b.place(below=a)` is error `K0402`, showing the cycle and the lines. Contradictory constraints on the same axis (`left_of=x` and `right_of=x`) are error `K0403`. There are no hidden priorities: if the author wants a weak constraint, they declare `weak=True`.

**Transforms and constraints.** Constraints between siblings use the parent's local coordinates; between objects with different parents, global coordinates. Scaling a group preserves the internal relations. A constraint applies to the object's **unrotated** bounding box; `place(..., by="rotated")` uses the rotated box.

## Animations

A `k.Animation` is an immutable value with a duration, easing, and target; it only takes effect when passed to `s.play` or `s.start`.

**Verbs (functions of `k`).**

| Verb | Category | What it does |
| --- | --- | --- |
| `k.draw(obj)` | Entry | Traces the outline, then fills |
| `k.write(text)` | Entry | Character-by-character writing (text, math, code) |
| `k.fade_in(*objs, shift=)` | Entry | Opacity 0 → 1, optional offset |
| `k.grow(obj, from_=)` | Entry | Scales from a side or point |
| `k.fade_out(*objs)` / `k.shrink(obj)` | Exit | Inverse of the entries; removes from the scene |
| `k.morph(a, b, match=)` | Swap | `a` exits, `b` enters, matching parts travel |
| `k.indicate(obj, color=, scale=)` | Emphasis | Temporary highlight; final state = initial state |
| `k.flash(obj, color=)` | Emphasis | Pulse of light on the edge |
| `k.squash(obj, amount=)` | Emphasis | Elastic squash |
| `k.follow(obj, path)` | Motion | Travels along a path; `rotate=True` aligns to the tangent |
| `k.sound(file)` | Audio | Plays a sound at the scheduled instant |

Every entry/exit consults the component protocol: if the object defines `enter()`/`exit()`, the verb uses that implementation (see Components).

**State change.** `obj.to(**props)` interpolates from the value at the cursor to the target. Interpolable types:

| Type | Interpolation |
| --- | --- |
| `float`, `int`, vectors | Linear in easing space (`int` rounds) |
| `Color` | In OKLab (avoids gray in the middle) |
| Path / shape | Point correspondence with resampling |
| `str` (in `Text`) | Glyph morph |
| `bool`, enums | Step at the end (`step="start"` for the start) |
| `list`, custom types | Requires `lerp=` on the signal; otherwise error `K0205` |

**Composition.**

```python
k.seq(a, b, c)                  # in sequence
k.par(a, b, c)                  # in parallel; s.play(a, b) ≡ s.play(k.par(a, b))
k.stagger(anims, lag=0.1)       # each one starts lag s after the previous
k.stagger(anims, lag=0.1, order="center")  # spatial order: center, left, random(seed)
a.with_(duration=2, ease=k.ease.out_back, delay=0.2)  # copy with other parameters
```

**Easing.** `k.ease.linear`, `smooth` (default), `in_`, `out`, `in_out`, `out_back`, `out_elastic`, `spring(stiffness, damping)`, `steps(n)`, and `k.ease.custom(fn)` for any `f: [0,1] → ℝ`.

**Clips.** A sequence written with its own cursor and packaged as an animation:

```python
@k.clip
def squares_proof(s: k.Scene, tri: k.Triangle) -> None:
    squares = [k.Square.on(side, outward=True) for side in tri.sides]
    s.play(k.stagger([k.grow(q) for q in squares], lag=0.2))
    s.play(k.indicate(squares[2]))

s.play(squares_proof(tri), k.write(title))   # composes like any Animation
```

A clip is executed in the build phase at the moment it is scheduled, with the cursor starting at its beginning. Its duration is that of the internal cursor at the end. It can be rescaled with `duration=` like any animation.

**Named transitions.** Component methods that return an `Animation` (`row.swap`, `axes.zoom_to`, `code.highlight`). Rule: the docs of each one state the equivalent `.to()`, and its conflict behavior is that of this `.to()`.

**Conflicts.** Two animations writing the same prop of the same object in overlapping intervals are error `K0201`, citing both lines. Intentional combination is explicit: `a.to(x=2, blend="add")` adds to the value of the other animation (e.g. a shake on top of motion).

## Reactive system

All variable state is a signal; derived values are recomputed only when a dependency changes; effects and stateful systems are resolved before the render.

### Signals

```python
x = k.signal(1.0)                      # Signal[float]
name = k.signal("a", lerp=None)        # no interpolation: .to() switches as a step
pts = k.signal([(0, 0)], lerp=k.lerp.pointwise)

s.play(x.to(3), duration=2)            # animation
x.set(5)                               # instant at the cursor
x.now                                  # 5 (build phase)
```

Every object prop is a signal with the same API: `dot.x.now`, `dot.x.set(2)`, `s.play(dot.x.to(3))` ≡ `s.play(dot.to(x=3))`.

### Derived values

Five forms, each with a role:

| Form | When to use | Example | Evaluated in |
| --- | --- | --- | --- |
| Operators | Arithmetic and comparison | `a.x + 1.5`, `solar - load`, `soc >= 1` | Rust |
| Functions of `k` | Math, conditions, tables | `k.sin(x)`, `k.clamp(v, 0, 1)`, `k.where(c, a, b)`, `k.interp(h, xs, ys)` | Rust |
| `.map(fn)` | Applying a function to a signal | `hour.map(solar_curve)` | Rust, via tracing; if not traceable, error `K0310` |
| `k.computed(lambda: ...)` | Logic with several dependencies | `k.computed(lambda: f(a(), b()))` | Rust, via tracing; if not traceable, error `K0310` |
| `k.python(fn)` | Non-traceable function, cost explicitly accepted | `hour.map(k.python(optimize_dispatch))` | Python, precomputed in resolve |

Lambdas passed directly to props are implicit `computed` values and follow the same rule: `k.Text(lambda: f"{x():.2f} kWh")` is traced and runs natively. Derived values are read-only, lazy, and memoized. `.to()` or `.set()` on a derived value is error `K0303` ("animate the source").

**Lifting.** Wherever the API accepts `T`, it also accepts `Signal[T]` and `Callable[[], T]`. The public type is `k.Val[T] = T | Signal[T] | Callable[[], T]`.

**Guards against classic mistakes.**

| Author's code | What kinemo does |
| --- | --- |
| `if x > 2:` | `Signal.__bool__` raises `K0304`: use `x.now > 2` (at the cursor) or `k.when(x > 2, ...)` (during playback) |
| `math.sin(x)` | `Signal.__float__` raises `K0305`: use `k.sin(x)` or `x.map(math.sin)` |
| `x()` in the scene body | `K0301`: use `x.now` |
| `x.now` inside a lambda | `K0302`: would freeze the value; use `x()` |
| Writing to a signal inside `computed` | `K0306`: derived values are pure |

### Tracing and `k.python`

To compile a function to the IR, kinemo calls it once with symbolic values in place of the signals. Each operation on these values becomes an expression node. If the function completes, the expression goes into the IR; if it touches something that cannot be represented, tracing fails.

| Construct | Traceable | Alternative |
| --- | --- | --- |
| Arithmetic, comparison, `&` `\|` `~`, `abs()`, `round()` | Yes | — |
| Functions of `k` (`k.sin`, `k.exp`, `k.min`, `k.max`, `k.floor`, `k.where`, `k.piecewise`, `k.interp`, `k.spline`, `k.smoothstep`, `k.noise`, `k.mix`) | Yes | — |
| numpy ufuncs (`np.sin(h)`) | Yes, via `__array_ufunc__` | — |
| f-strings with format specs (`f"{x():.1f}"`) | Yes, via `__format__` | — |
| Fixed-count loops, helper functions, constants | Yes (unrolled) | — |
| `if` / `while` / `and` / `or` on a symbolic value | No | `k.where`, `k.piecewise`, `&` `\|` |
| `math.*`, `int()`, `float()`, built-in `min()` / `max()` | No | `k.sin`, `k.floor`, `k.min`, `k.max` |
| External libraries, I/O, mutable state | No | `k.python(fn)` |

The functions of `k` are polymorphic: they accept `float`, signal, symbolic value, and arrays. The same `solar_curve` works for `ax.plot` (evaluated with floats) and for `hour.map` (traced).

```python
def solar_curve(h):
    return k.max(0, 6 * k.sin(k.pi * (h - 6) / 12))       # native

def tariff(h):
    return k.where((h >= 18) & (h < 21), 1.8, 0.6)          # native

load = hour.map(lambda h: k.interp(h, profile["hour"], profile["kw"]))  # polars, zero-copy
```

**A tracing failure is an error, never a silent fallback.**

```
K0310 'curve' is not traceable: uses math.sin (curve.py:3)
  fix 1: replace with k.sin(...) to run natively
  fix 2: accept the cost explicitly: hour.map(k.python(curve))
```

**`k.python(fn)`** is the only door to opaque Python:

- it is precomputed in the resolve phase, one call per frame, batched, in-process; with `k.python(fn, vectorized=True)`, a single call receives the entire timeline as an array;
- the render only reads the resulting table;
- the measured cost shows up in `kinemo check`; a worker pool only kicks in above a threshold configurable in `kinemo.toml` (default 2 s of computation);
- if it depends on a scene parameter, it cannot be precomputed for the interactive web: lint `W1302`.

`k.simulate` and event handlers are Python by definition and follow the same model: they run in resolve, never in render.

### Time

`k.time` (global) and `self.age` (component) are read-only signals. They are the right way to express clocks and continuous motion, because they advance linearly and are not subject to easing:

```python
star.set(rotate=k.time * 90)           # rotates 90°/s forever
hour = k.time.map(lambda t: t * 2)     # 1 s of video = 2 h of simulation
```

### Effects

Because the render is pure, an effect in kinemo means "when a condition becomes true, something enters the timeline". Never I/O.

```python
k.when(x >= 2, k.flash(dot))                        # fires an animation
k.when(bat.soc >= 1, bat.full)                      # emits an event
k.when(temp > 80, alarm, once=True)                 # only the first time
k.when(level > 0.95, beep, rearm=level < 0.8)       # hysteresis
```

- **Edge** detection (false → true), resolved in phase 2 by sampling at every frame, with bisection refinement down to 1 ms.
- Without `rearm`, the condition must become false again before it fires again.
- Whatever is fired does not move the main cursor.
- `k.when` can be called in the scene body or in a component's `build()`; it applies from the cursor at which it was registered.

### Stateful systems

Quantities that depend on history, not only on the current instant. All of them are precomputed in phase 2 and stored in a table, which keeps the render pure and the timeline draggable.

```python
soc = k.integrate(power / capacity, d=hour, initial=0.2, clamp=(0, 1))
trail = k.trace(dot.position, length=2.0)           # last 2 s of path
sim = k.simulate(step, Ball(y=4, v=0), dt=1/240, until=12)
```

- `k.integrate(expr, d=var)` integrates with respect to the variation of `var` (default `d=k.time`). With `clamp`, the integral is path-dependent, so it is always computed from the start.
- `k.simulate(step, state, dt, until)` runs `step(state, dt) -> state` in Python with a fixed step. The state is a `k.State` (a dataclass with `k.Event` support). Each field becomes a signal: `sim.y`, `sim.v`.
- Simulations can read signals (wind, animated gravity). If an event handler changes something the simulation reads, phase 2 recomputes (see Events).

### Reactive collections

Ordinary Python lists are not tracked. For collections that change, `k.list([...])` is a list signal with `append`, `insert`, `pop`, and `swap` recorded at the cursor. Lint `W0311` warns when a lambda captures a Python list that is modified later.

## Components

A component is a subclass of `k.Component` with three channels: props (in), outs (out, as a continuous value) and events (out, as a discrete occurrence). Functions that return `k.Group` remain valid, but they are just Python helpers, not a library concept.

| Channel | Direction | Nature | Declaration | External use |
| --- | --- | --- | --- | --- |
| Reactive prop | In | Value, static or reactive | `name: k.Prop[T] = k.prop(default)` | `Battery(power=balance)`, `bat.to(power=5)` |
| Static field | In | Value fixed at construction | `name: T = default` | `Battery(capacity=10)` |
| Out | Out | Read-only signal | `name: k.Out[T]` | `bat.soc`, `bat.soc.now` |
| Event | Out | Instant + payload | `name: k.Event` or `k.Event[P]` | `@bat.full.on`, `s.wait_for(bat.full)` |

### Example

```python
class Battery(k.Component):
    power:    k.Prop[float] = k.prop(0.0)          # kW; + charges, − discharges
    time:     k.Prop[float] = k.from_context(Clock) # hours
    capacity: float = 10.0                          # kWh, static
    initial:  float = k.field(0.2, range=(0, 1))

    soc:   k.Out[float]
    full:  k.Event
    empty: k.Event

    def build(self) -> k.Node:
        self.soc = k.integrate(self.power / self.capacity,
                               d=self.time, initial=self.initial, clamp=(0, 1))
        k.when(self.soc >= 1, self.full, rearm=self.soc < 0.95)
        k.when(self.soc <= 0, self.empty, rearm=self.soc > 0.05)

        self.body = k.RoundedRect(w=1.2, h=2.4, stroke=k.theme.fg)
        self.level = k.Rect(w=1.0, h=self.soc * 2.2,
                            fill=self.soc.map(lambda v: k.mix(k.RED, k.GREEN, v))) \
                        .place(inside=self.body, align="bottom", pad=0.1)
        self.label = k.Text(lambda: f"{self.soc() * self.capacity:.1f} kWh") \
                        .place(below=self.body, gap=0.2)
        return k.Group(self.body, self.level, self.label)

    def enter(self) -> k.Animation:
        return k.seq(k.draw(self.body), k.grow(self.level, from_="bottom"),
                     k.fade_in(self.label))
```

### Rules

- **Prop defaults use `k.prop(...)`** (`k.Prop[float] = k.prop(0.0)`), so that Pyright strict accepts the value in the class body and sees `Signal[float]` on the instance.
- **Reactive props always arrive as a signal.** Inside the component, `self.power` is `Signal[float]`, even if the author passed `3.0`. The internal code stays uniform.
- **Static fields reject signals.** Passing a signal to `capacity` is error `K0601`: declare it as `k.Prop[float]`.
- **Validation.** `k.field(default, range=, choices=)` and `k.prop(default, range=)` validate at construction. For reactive props, the lint `W0602` samples the timeline and warns if the value goes out of range.
- **`build()` runs once, at construction.** Inside it, `.now` and the entire object API are valid. Outs not assigned by the end of `build()` are error `K0602`.
- **Parts are attributes.** Subobjects stored in `self.*` are public and addressable from outside (`bat.level.to(opacity=0.5)`). A `_` prefix makes them private for `inspect` and autocomplete.
- **Component effects apply while it is in the scene.** A `k.when` registered in `build()` is inactive before the entrance and after the exit. `self.age` starts at 0 on entrance.
- **A component is a `Group`.** It accepts `place`, `.to()`, verbs, copying. `bat.copy()` rebuilds the component with the same arguments.
- **Verb protocol.** Optional methods: `enter()`, `exit()`, `indicate()`. The `k` verbs call these methods when they exist; otherwise, they use the default behavior on the group.
- **Named transitions and clips.** Methods that return `Animation`, or are decorated with `@k.clip` (they receive an `s` with its own cursor):

```python
    @k.clip
    def discharge(self, s: k.Scene, to: float = 0.0) -> None:
        s.play(self.to(power=-3))
        s.wait_for(self.empty, timeout=30)
```

- **Children as a prop.** A component that receives content declares `content: k.Node` (static) and positions it in `build()`. The child then belongs to the component (one parent per object).

### Context

Values that many components need (theme, clock, unit) are provided through context, instead of being passed down prop by prop.

```python
Clock = k.context("clock", default=k.time)      # declaration, at module level

@k.scene(theme=k.themes.blueprint)               # theme is built-in context
def solar_day(s: k.Scene):
    hour = k.time.map(lambda t: t * 2)
    with k.provide(Clock, hour):
        bat = Battery(power=balance)             # time = hour, via context
```

Context is resolved **at the component's construction** (lexical scope of the build phase), not dynamically. Passing the prop explicitly always wins over context. `kinemo inspect` shows where each prop came from (`arg`, `context:clock`, `default`).

## Events and callbacks

An event is an instant on the timeline with an optional payload; there are two ways to react to it, with different semantics: `on` (also do this) and `wait_for` (wait and continue from here).

**Event sources.**

| Source | Example |
| --- | --- |
| Condition | `k.when(soc >= 1, self.full)` |
| Explicit emission in build or in a clip | `self.full.emit()` (at the cursor) |
| Simulation | `st.bounce.emit(abs(v))` inside `step` |
| Object lifecycle | `obj.entered`, `obj.exited` (built-in) |
| End of animation or simulation | `h = s.start(anim)` → `h.done`; `sim.done` |

**`on`: overlapping reaction.**

```python
@bat.full.on
def celebrate(s: k.Scene, e: k.EventInfo) -> None:
    notice = k.Text("Battery full").place(above=bat)
    s.play(k.fade_in(notice), k.indicate(bat, color=k.GREEN))
    s.wait(1.5)
    s.play(k.fade_out(notice))
```

- The handler runs in phase 2, once per firing, in Python.
- It receives its own `s` with the cursor at `e.time`. The main cursor is not affected.
- `e.time` (instant), `e.data` (typed payload), `e.count` (n-th firing), `e.value(sig)` (value of any signal at that instant).
- `.on(once=True)` reacts only to the first firing.
- Objects created in the handler and never removed trigger the lint `W0701`.

**`wait_for`: continuing the script.**

```python
s.start(hour.to(24), duration=12, ease=k.ease.linear)
e = s.wait_for(bat.full, timeout=20)
s.play(k.write(k.Text(f"Full at {e.value(hour):.0f}h").place(at="top")))
```

- Moves the main cursor to the instant of the event (or of the `count`-th one, with `count=n`).
- Searches only **after the cursor**, and only sees what has been scheduled up to that point. That is why the pattern is `s.start(...)` + `s.wait_for(...)`.
- Resolves immediately: the core performs a partial resolve of the timeline known up to that point.
- `timeout` is mandatory when the source has no guaranteed end (condition, simulation without `until`). When it runs out: error `K0702`, with the maximum value the condition reached and at what instant.
- If the event already happened before the cursor: error `K0703`, saying when it occurred and suggesting `start` instead of the preceding `play`.

**Typed payload.**

```python
@dataclass
class Impact:
    force: float
    point: k.Vec

class Ball(k.State):
    y: float = 4.0
    v: float = 0.0
    bounce: k.Event[Impact]
```

`e.data.force` has autocomplete and is checked by Pyright. String-based events do not exist.

**Resolution and cycles.** Handlers can schedule animations that change signals feeding conditions or simulations. Phase 2 iterates (recomputes simulations, re-detects events, re-runs affected handlers) until a fixed point. Handlers must be deterministic; kinemo re-runs each one whenever the firing moves to a different instant. Above 8 passes: error `K0501`, showing the chain event → handler → signal → event.

## Text, math and code

Three kinds of text, all with addressable parts and morphing between versions: `k.Text`, `k.Math` and `k.Code`.

**`k.Text`.**

```python
k.Text("Hello **world**, see $x^2$", size=0.6, width=6, align="left")
```

- Minimal inline markup: `**bold**`, `*italic*`, `` `code` ``, `$math$`. Nothing beyond that.
- `width=` wraps lines; without `width`, a single line. Default font, size and color come from the theme.
- Parts: `txt["world"]` (first occurrence), `txt.find_all("a")`, `txt.chars[3:7]`, `txt.words[1]`, `txt.lines[0]`. Each part is an object with its own props (`txt["world"].to(color=k.RED)`).
- Reactive text: `k.Text(lambda: f"{x():.1f} kWh")`. Layout is redone only when the string changes; digits use tabular widths by default so they do not "jitter".

**`k.Math`.**

```python
eq = k.Math(r"\id{lhs}{a^2 + b^2} = c^2")
eq["lhs"].to(color=k.RED)      # named part
eq["c^2"]                        # lookup by TeX subexpression
```

- LaTeX syntax (AI knows it well). The engine converts it to the typst model and typesets it without a TeX installation, in milliseconds.
- `\id{name}{...}` names a subexpression. TeX lookup (`eq["c^2"]`) matches by syntax tree, not by string: `c^2` and `c^{2}` are the same.
- `engine="tex"` uses a real LaTeX installation, for packages the built-in engine does not cover (TikZ, for example). Error `K0801` (unsupported command) suggests this option.

**Equation morph.** `k.morph(eq1, eq2)` matches parts in this order of priority:

1. explicit `match=` from the author (`match={"a^2": "a^2"}`);
2. `\id{...}` with the same name;
3. identical TeX subtrees, preferring the largest;
4. identical glyphs, by relative position (breaks ties between repeated terms);
5. whatever remains: fades out in `eq1`, fades in in `eq2`.

`kinemo dev --debug morph` draws the matches. With no matches at all, the morph does warp + crossfade and emits the lint `W0801`.

**`k.Code`.**

```python
code = k.Code(src, lang="python", theme="auto", line_numbers=True)
s.play(code.highlight(lines=[3, 4]))            # named transition
s.play(k.morph(code, k.Code(src_v2, lang="python")))  # animated diff
```

Highlighting via tree-sitter. The code morph matches tokens by a line diff followed by a token diff: identical lines slide, inserted ones enter, removed ones exit.

## Charts, data, bulk objects and 3D

The built-in library covers what technical explanations use most often; everything is written as `k.Component` and follows the same rules.

**Basic shapes.** `Circle`, `Dot`, `Ellipse`, `Rect`, `RoundedRect`, `Square`, `Polygon` (`.regular(n)`), `Triangle` (`.right(a, b)`), `Line` (`start`/`end` or `length=`), `Arrow`, `Arc`, `Path` (SVG commands or points), `Brace`, `Image`, `SVG` (parts by SVG id: `svg["#motor"]`). Booleans: `k.union`, `k.intersect`, `k.subtract`. `k.Bar(value, label=)` is a bar that grows from its base, used in algorithms and charts.

**Axes and functions.**

```python
ax = k.Axes(x=(0, 24, 6), y=(0, 7), labels=("h", "kW"), grid=True)
f = ax.plot(solar_curve, until=hour, color=k.YELLOW, label="Solar")
ax.area(f, between=g, fill=k.GREEN, fill_opacity=0.2)
ax.vline(at=hour, style="dashed")
dot = k.Dot().place(at=f.point_at(x))       # point on the curve, reactive
tan = f.tangent_at(x, length=3)
s.play(ax.zoom_to(x=(4, 8)))                # named transition
```

- `plot` uses adaptive sampling (more points where curvature is high) and handles discontinuities (`1/x`) without drawing the asymptote.
- `until=` and `from_=` accept a signal: the curve grows as the signal advances.
- Also: `NumberLine`, `PolarAxes`, `ax.parametric`, `ax.scatter`, `ax.bars`.

**Data.** `k.BarChart`, `k.LineChart`, `k.Table` and `k.interp` accept any Arrow source without copying: polars (reference), pandas ≥ 2.2, pyarrow, duckdb. Lists and dicts also work for small cases. Swapping the data animates the transition (bars grow, reorder, enter and exit by key):

```python
chart = k.BarChart(df_2020, x="country", y="gwh", key="country")
s.play(chart.to(data=df_2025))
```

**Bulk objects.** No creating 10,000 Python objects. Vectorized types store arrays and draw via GPU instancing:

```python
pts = k.Points(xy, radius=0.02, color=lambda t, p: k.mix(k.BLUE, k.RED, p.x))
field = k.VectorField(lambda x, y: (-y, x), density=30)
lines = k.StreamLines(field, seeds=200)
```

The input data (`xy`) is a numpy array of shape `(n, 2)` or Arrow columns. Per-point functions are traced like any derived value (`p` is the symbolic point, with `p.x`, `p.y`, `p.index`) and vectorized in Rust over all points. Only with `k.python(fn, vectorized=True)` does the function receive actual numpy arrays. The lint `W0901` warns when a loop creates more than 1000 individual objects and suggests the vectorized type.

**3D.**

```python
@k.scene(camera="3d")
def surface(s: k.Scene):
    surf = k.Surface(lambda u, v: (u, v, k.sin(u) * k.cos(v)), u=(-3, 3), v=(-3, 3))
    s.play(k.draw(surf))
    s.play(s.camera.to(orbit=(30, 60), distance=12), duration=3)
    s.hud.add(k.Text("z = sin(u) cos(v)").place(at="top", margin=0.4))
```

- `s.camera` is an object with animatable props (`orbit`, `distance`, `target`, `fov`).
- `s.hud` is a fixed 2D layer over the 3D one, with the same constraint-based layout.
- Shapes: `Surface`, `Sphere`, `Cube`, `Prism`, `Axes3D`, `Line3D`, `Arrow3D`, `Mesh` (glTF/OBJ file). Simple lighting from the theme.
- 3D comes after 2D on the roadmap (see Decisions).

## Parameters, movies and output formats

The same source produces video, GIF, frames and slides; scene parameters become fixed values in video and controls in interactive output.

**Parameters.**

```python
@k.scene(params={"n": k.Int(3, 12, default=5), "color": k.Choice([k.BLUE, k.RED])})
def polygon(s: k.Scene, n: k.Signal[int], color: k.Signal[k.Color]):
    s.play(k.draw(k.Polygon.regular(n, color=color)))
```

- Parameters arrive as signals. In video they use the `default` (or `--param n=7` on the CLI); on the interactive web they become controls.
- Types: `k.Int`, `k.Float`, `k.Bool`, `k.Choice`, `k.Str` (`k.Text` is the text object; one name per concept).
- A parameter read with `.now` in the build becomes fixed and cannot become a live control. The lint `W1301` warns, because this breaks the interactive export.

**Movies.** Several scenes composed into a single output:

```python
movie = k.movie(
    [intro, pythagoras, solar_day],
    transitions=[k.cut, k.crossfade(0.5)],
)
```

Objects with the same `key=` in adjacent scenes can morph during the transition (`k.morph_cut`).

**Slides.** `s.mark(slide=True)` defines each break; the mark name is optional (`s.mark("proof", slide=True)`). `kinemo render --format slides` generates an HTML presentation: each section plays until the next break and waits for a key press. Looping animations (`s.start` with `loop=True`) keep running while the slide is paused.

**Formats.**

| Format | Flag | Notes |
| --- | --- | --- |
| MP4 (H.264) | `--format mp4` | Default |
| WebM (VP9) | `--format webm` | Supports transparent background (`--transparent`) |
| MOV (ProRes 4444) | `--format mov` | With alpha, for video editing |
| GIF | `--format gif` | Palette optimized per scene |
| PNG | `--format png --at 2.5` or `--frames` | A single frame or the whole sequence |
| SVG | `--format svg --at 2.5` | A single vector frame, for documents |
| Slides | `--format slides` | HTML with one video per section |
| Interactive web | `--format web` | Roadmap: core in WASM; requires everything that depends on a parameter to be native (no Pyodide) |

**Quality.** `--quality draft` (540p, 30 fps, no extra antialiasing; it is the `dev` default) and `--quality final` (the scene's resolution and fps). Sizes: `"720p"`, `"1080p"`, `"4k"`, `"square"`, `"vertical"` (9:16) or `(w, h)`. In vertical and square, the frame keeps 9 units on the shorter side.

**Project configuration.** `kinemo.toml` defines fps, size, theme, fonts, TTS provider, cache directory and active lints. What is in the `@k.scene` decorator takes precedence over `kinemo.toml`, and the CLI takes precedence over both.

## Tooling

The `kinemo` CLI is half the product: it closes the edit → view → fix loop, for people and agents alike.

| Command | Purpose |
| --- | --- |
| `kinemo new <name>` | Project with `kinemo.toml`, example scene, Pyright configuration |
| `kinemo dev <file>` | Browser preview with hot reload and a draggable timeline |
| `kinemo check <file> [--json] [--strict] [--fix]` | Build + resolve without rendering: errors, lints, timeline summary |
| `kinemo inspect <file> --at <t> [--json]` | Scene graph at instant t: position, bbox, color, origin of each prop and line of code |
| `kinemo snap <file> --at 0,2.5,end` | PNGs of the requested instants |
| `kinemo render <file> [--scene] [--format] [--quality]` | Final output |
| `kinemo docs <symbol>` | Short offline doc with a canonical example (`kinemo docs k.morph`) |
| `kinemo explain <code>` | Long explanation of an error or lint (`kinemo explain K0401`) |
| `kinemo upgrade` | Codemods between major versions |
| `kinemo mcp` | MCP server that exposes `check`, `inspect`, `snap` and `docs` as tools for agents |

**Preview (`kinemo dev`).**

- The browser shows the current frame, the timeline with each animation as a bar (with the verb name and the line), the marks and the fired events.
- Dragging the timeline requests frames from the core over WebSocket. Frames are cached by segment hash.
- When the file is saved, the scene is rebuilt and the preview returns to the same instant.
- Clicking an object shows its props, where each one came from (constraint, binding, animation) and opens the line in the editor (`vscode://`, `idea://` or the command in `kinemo.toml`).
- If the build fails, the preview keeps the last good version and shows the error as an overlay, with line and instant.
- Debug overlays: `--debug layout` (boxes and constraints), `--debug morph` (matches), `--debug safe` (safe area), `--debug trace` (what was traced and the cost of each k.python).

**`kinemo check` output** (text; with `--json`, the same in stable JSON):

```
derivative.py — scene 'derivative' — 8.4 s — ok with 1 warning
timeline
  0.00–1.00  draw(ax), draw(f)            derivative.py:9
  1.00–1.50  fade_in(dot, tangent, label) :10
  1.50–4.50  x.to(3)                      :11
events
  —
lints
  W1001 3.80 s  label leaves the safe area (top, 0.4 u)   :7
        fix: .place(above=dot, gap=0.3, clamp=True)
```

**`kinemo inspect --at 2.5` output** (excerpt):

```
dot: Dot                        derivative.py:6
  position = (1.62, 2.62)       ← place(at=f.point_at(x))   x=1.62
  radius   = 0.08               ← theme
  color    = #F5C542            ← arg
label: Math "f'(1.6) = 3.2"      derivative.py:8
  bbox     = [0.9, 2.9 → 2.4, 3.3]
  position ← place(above=dot, gap=0.3)
```

## Diagnostics

Every problem is a diagnostic with a stable code, a location in the code, an instant on the timeline and, whenever possible, an applicable fix.

**Anatomy.**

```
K0401 error: 'title' cannot animate x: the axis is held by a constraint
  --> pythagoras.py:14   s.play(title.to(x=3))
  --> pythagoras.py:9    title.place(above=tri)   ← constraint here
   t = 3.20 s
  fix 1: change the constraint in an animated way
         s.play(title.to_place(right_of=tri))
  fix 2: release and animate freely
         s.play(title.to(x=3, unpin=True))
  more: kinemo explain K0401
```

In JSON: `code`, `level`, `message`, `spans` (file, line, column), `time`, `objects`, `fixes` (exact text edits). `kinemo check --fix` applies the first fix of each diagnostic that has exactly one safe fix.

**Levels.** `error` halts the build. `warning` (lint) does not halt it; with `--strict` it becomes an error (the default in CI and in the MCP server). `hint` is a style suggestion and never becomes an error.

**Code ranges.**

| Range | Area |
| --- | --- |
| K01xx | Object lifecycle |
| K02xx / W02xx | Animations, conflicts, interpolation |
| K03xx / W03xx | Reactive system |
| K04xx | Layout and constraints |
| K05xx | Resolution (loops, convergence) |
| K06xx / W06xx | Components |
| K07xx / W07xx | Events |
| K08xx / W08xx | Text and math |
| W09xx | Performance |
| W10xx | Visual legibility |
| K11xx | Names from other libraries (Manim) |
| W13xx | Parameters and export |
| K12xx | Data and interoperability (Arrow, arrays) |
| W14xx | Audio and voice |

**Visual lints (W10xx).** They are computed by sampling the timeline, and each one points to the instant and the object:

- `W1001` object leaves the safe area;
- `W1002` text over text (bbox overlap above 10%);
- `W1003` contrast below 4.5:1 between text and background;
- `W1004` text smaller than 18 px at the final resolution;
- `W1005` object invisible in the scene for more than 3 s (opacity 0 or outside the frame) and never removed;
- `W1006` more than 12 simultaneous animations with duration under 0.3 s (visual noise);
- `W1007` more than 8 s without any visual change.

**Code lints.** Analyzed from the AST, without executing:

- `W0310` lambda in a loop capturing the loop variable (late binding) — fix: `lambda i=i:` or `.map`;
- `W0311` lambda capturing a Python list modified later — fix: `k.list`;
- `W0312` signal used as a clock (`d=` of an integral) animated with non-linear easing — fix: `k.time.map(...)` or `ease=k.ease.linear`.

Lints can be turned off per line (`# kinemo: allow W1002`) or in `kinemo.toml`, always explicitly.

## Designed for AI

The goal is for a model to generate a correct scene within two `check` iterations, without needing vision. This rests on five mechanisms.

1. **Small, regular surface.** One name per concept, verbs in `k.`, state in `.to()`. Fewer possible forms means less hallucination. The entire public API fits in an `llms.txt` of a few pages, generated from the types at each release.
2. **Errors that teach.** Every error comes with the fix in code. The model does not need to understand the architecture to fix it; it only has to apply the suggestion.
3. **Built-in Manim translation (K11xx).** Models were trained on a lot of Manim code and will write `Create`, `self.play`, `.animate`. kinemo recognizes these names and responds with the equivalent form:

```
K1101 'Create' is from Manim. In kinemo: k.draw(tri)
K1102 'x.animate.shift(UP)' → s.play(x.to(y=x.y.now + 1))
K1103 'self.play' → the scene receives 's'; use s.play(...)
K1104 'ValueTracker' → k.signal(...)
K1105 'add_updater' → pass a signal or lambda to the prop: obj.set(x=other.x)
```

4. **Seeing without vision.** `kinemo check --json` gives the timeline and the lints; `kinemo inspect --json` gives positions, sizes and the origin of each value. The visual lints (safe area, overlap, contrast, text size) cover the mistakes a human would see in the video. For models with vision, `kinemo snap` completes the loop.
5. **Native tools for agents.** `kinemo mcp` exposes `check`, `inspect`, `snap`, `docs` and `explain` as MCP tools, always with `--strict`.

**Recommended loop for an agent.**

1. Read `llms.txt` (or call `docs` for the symbols it will use).
2. Write the scene.
3. `check --json --strict`. If there are errors, apply the fixes and repeat.
4. `inspect --at` at the key instants (end of each `play`) to confirm positions.
5. Optional: `snap` and visual review.
6. `render`.

**Content for models.** One canonical example per verb and per component, short (fewer than 15 lines) and tested in CI. The Manim → kinemo table (appendix) is published alongside `llms.txt`. The docs avoid showing alternative forms, because contradictory examples are the main cause of mixed code.

## Defined behavior in edge cases

Each row is a contract: the behavior below is tested and does not change without a major version.

| # | Situation | Behavior |
| --- | --- | --- |
| 1 | `.to()` on an object not in the scene | `K0101`, fix: `k.draw(obj)` or `s.add(obj)` |
| 2 | `.to()` on an already removed object | `K0102`, with the line and instant of the exit |
| 3 | Two animations on the same prop at the same time | `K0201` with both lines; `blend="add"` to sum them |
| 4 | Entrance verb inside `s.during` | `K0204`: reversible animations only |
| 5 | `.to()` on a list without `lerp=` | `K0205`, fix: declare `lerp=` on the signal |
| 6 | `x()` in the scene body / `x.now` in a lambda | `K0301` / `K0302` |
| 7 | `if signal:` or `math.sin(signal)` | `K0304` / `K0305` with the correct form |
| 8 | `.to()` on a derived value | `K0303`: animate the source |
| 9 | Animating an axis held by a constraint or binding | `K0401`, fixes: `.to_place(...)`, `.to(..., unpin=True)`, `unbind()` |
| 10 | Constraint cycle | `K0402` showing the cycle |
| 11 | Contradictory constraints | `K0403`; `weak=True` for weak constraints |
| 12 | Loop event → handler → signal → event | Iterates up to 8 passes, then `K0501` with the chain |
| 13 | Signal passed to a static field | `K0601`: declare `k.Prop[T]` |
| 14 | Out not assigned in `build()` | `K0602` |
| 15 | `wait_for` with no event before the timeout | `K0702` with the maximum value reached |
| 16 | `wait_for` on an event already past | `K0703`, suggests `start` on the preceding `play` |
| 17 | `k.when` condition oscillating at the threshold | Fires only on the edge; without `rearm`, it must go back to false |
| 18 | Morph between shapes with nothing in common | Warp + crossfade, lint `W0801` |
| 19 | Equation morph with repeated terms | Tie broken by relative position; `match=` to force |
| 20 | Unsupported LaTeX command | `K0801`, suggests `engine="tex"` |
| 21 | Loop creating thousands of objects | `W0901`, suggests `k.Points` or `k.VectorField` |
| 22 | Non-traceable function in \`.map\` or lambda | `K0310 with native fix or k.python(fn); cost of k.python measured in check` |
| 23 | Object added to a second parent | `K0103`, fixes: `.copy()` or `k.reparent` |
| 24 | Object created in a handler and never removed | `W0701` |
| 25 | Clock animated with easing | `W0312`, fix: `k.time.map` |
| 26 | Manim name (`Create`, `.animate`, `self.play`) | `K11xx` with the translation |
| 27 | `random` / `numpy.random` without a seed | Automatic seed per scene; always the same result |
| 28 | Python exception in the build during `dev` | Preview keeps the last good version, shows an overlay with the error |
| 29 | An animation's duration changes mid-scene | Everything after is pushed back; what is anchored to `mark`/`voice` stays in place; a new overlap becomes a lint |
| 30 | Simulation handler changes what the simulation reads | Resolve recomputes the simulation from the affected instant |
| 31 | `play(..., at=)` | Behaves like `start`; lint `W0110` suggests `start` |
| 32 | Parameter read with `.now` | Fixed at build; lint `W1301` (does not become an interactive control) |
| 33 | Built-in if, math.\*, int() or min() inside a traced function | K0310 pointing to the line and the equivalent native construct (k.where, k.sin, k.floor, k.min) |
| 34 | Parameter-dependent k.python in an interactive web export | W1302, which becomes an error with --format web: it cannot be precomputed; rewrite with native blocks |
| 35 | DataFrame without Arrow PyCapsule support | K1201 with the received type and the suggested conversion (e.g.: pl.from\_pandas) |

## Determinism, caching, performance and versioning

Same source, same assets and same kinemo version produce the same bytes; caching and parallel rendering depend on this.

**Determinism.**

- `random` and `numpy.random` are seeded per scene (`@k.scene(seed=)`, default 0) before the build.
- Simulations use a fixed step; integrals and event detection use the same sampling grid on every machine.
- The CPU renderer (tiny-skia) is the reference for snapshot tests; the GPU one has a documented pixel tolerance.
- Handlers and `.map` functions must be pure. kinemo cannot prove this; `dev` warns when the same handler produces different results in two consecutive builds.

**Cache.** The timeline is divided into segments (intervals between changes in the set of active animations). Each segment has a hash of its IR, its assets and the core version. A frame is only rendered if its segment's hash changed. Changing a line at the end of the scene does not re-render the beginning.

**Performance targets** (typical scene: up to 200 objects, 1080p, recent laptop):

| Operation | Target |
| --- | --- |
| `kinemo check` | < 300 ms |
| Rebuild in `dev` after saving | < 500 ms |
| Preview frame (draft, GPU) | < 30 ms |
| Final render | ≥ real time (1 s of video in ≤ 1 s) |
| Package import | < 150 ms |

**Tests for users.** `kinemo.testing` exposes `build(scene)`, `inspect(scene, t)` and `assert_snapshot(scene, t)` for pytest. Physics, components and scripts can be tested without rendering video.

**Versioning.**

- Strict semver for the Python API and for the IR format (which has its own version).
- Nothing is removed without spending an entire major version as deprecated. The deprecation warning comes with the fix, and `kinemo upgrade` applies it via codemod (libcst).
- Diagnostic codes never change meaning; retired codes are not reused.
- A single package and a single name. Third-party extensions use the `kinemo_<name>` namespace and the same `k.Component` API.

## Complete examples

Four scenes that together use almost the entire API; all of them must pass `kinemo check --strict` with no warnings, and they are part of the test suite.

### 1. Pythagorean theorem — layout, clips, equation morph

```python
import kinemo as k

@k.clip
def squares(s: k.Scene, tri: k.Triangle) -> None:
    sq = [k.Square.on(side, outward=True, fill_opacity=0.2) for side in tri.sides]
    s.play(k.stagger([k.grow(q) for q in sq], lag=0.2))
    with s.during(sq[0].to(color=k.YELLOW), sq[1].to(color=k.YELLOW)):
        s.play(k.indicate(sq[2], color=k.GREEN))

@k.scene
def pythagoras(s: k.Scene):
    tri = k.Triangle.right(3, 4, scale=0.6).place(at="center")
    eq1 = k.Math(r"a^2 + b^2 = c^2").place(at="top", margin=0.6)
    eq2 = k.Math(r"c = \sqrt{a^2 + b^2}").place(at="top", margin=0.6)

    with s.voice("Every right triangle hides a relation between its sides."):
        s.play(k.draw(tri))
    s.play(squares(tri))
    s.play(k.write(eq1))
    s.mark(slide=True)                         # slide break
    s.play(k.morph(eq1, eq2))
    s.wait(1)
```

### 2. Bubble sort — logic in the build, reflow, `during`, `tempo`

```python
@k.scene
def bubble_sort(s: k.Scene):
    row = k.Row(*[k.Bar(v, label=True) for v in [5, 2, 8, 1, 9, 3, 7, 4]],
                gap=0.2, align="bottom").place(at="center")
    s.play(k.stagger([k.grow(b, from_="bottom") for b in row], lag=0.05))

    n = len(row)
    with s.tempo(1, to=4):                     # speeds up over the course of the algorithm
        for i in range(n):
            for j in range(n - 1 - i):
                a, b = row[j], row[j + 1]       # positions at the cursor
                with s.during(a.to(color=k.YELLOW), b.to(color=k.YELLOW), duration=0.2):
                    if a.value.now > b.value.now:
                        s.play(row.swap(j, j + 1), duration=0.4)
                    else:
                        s.wait(0.2)
            s.play(row[n - 1 - i].to(color=k.GREEN), duration=0.2)
```

### 3. A day with solar + battery — signals, component, context, events

Uses the `Battery` component defined in the Components section.

```python
import polars as pl

Clock = k.context("clock", default=k.time)
profile = pl.read_csv("typical_load.csv")           # columns: hour, kw

def solar_curve(h):
    return k.max(0, 6 * k.sin(k.pi * (h - 6) / 12))  # traceable → native

def load_curve(h):
    return k.interp(h, profile["hour"], profile["kw"])  # Arrow, zero-copy → native

@k.scene(tail=1.0)
def solar_day(s: k.Scene):
    hour = k.time.map(lambda t: k.min(t * 2, 24))     # 12 s of video = 24 h
    solar, load = hour.map(solar_curve), hour.map(load_curve)

    ax = k.Axes(x=(0, 24, 6), y=(0, 7), labels=("h", "kW")).place(at="left", margin=0.8)
    ax.plot(solar_curve, until=hour, color=k.YELLOW, label="Solar")
    ax.plot(load_curve, until=hour, color=k.RED, label="Load")
    ax.vline(at=hour, style="dashed")
    clock = k.Text(lambda: f"{k.floor(hour()):02.0f}:00").place(above=ax, align="right")

    with k.provide(Clock, hour):
        bat = Battery(power=solar - load, capacity=10).place(right_of=ax, gap=1.2)

    @bat.full.on
    def _(s: k.Scene, e: k.EventInfo) -> None:
        s.play(k.indicate(bat, color=k.GREEN))

    @bat.empty.on
    def _(s: k.Scene, e: k.EventInfo) -> None:
        notice = k.Text("Buying from the grid").place(above=bat)
        s.play(k.fade_in(notice))
        s.wait(1)
        s.play(k.fade_out(notice))

    s.add(ax, clock, bat)
    s.wait(12)
```

No function in this scene goes through Python at render time: the curves, the clock, and the battery's color and level are all traced into the IR.

### 4. Bouncing ball — simulation, typed events, `wait_for`

```python
@dataclass
class Impact:
    force: float

class Ball(k.State):
    y: float = 4.0
    v: float = 0.0
    bounce: k.Event[Impact]

def step(st: Ball, dt: float) -> Ball:
    v = st.v - 9.8 * dt
    y = st.y + v * dt
    if y < 0:
        y, v = -y, -v * 0.8
        if abs(v) < 0.5:                      # at rest: no infinitesimal bounces
            y, v = 0.0, 0.0
        else:
            st.bounce.emit(Impact(force=abs(v)))
    return st.replace(y=y, v=v)

@k.scene
def bounce(s: k.Scene):
    floor = k.Line(length=10).place(at="bottom", margin=1)
    sim = k.simulate(step, Ball(), dt=1/240, until=12)
    ball = k.Circle(r=0.3, fill=k.theme.accent).place(above=floor, gap=sim.y)
    s.add(floor, ball)

    @sim.bounce.on
    def _(s: k.Scene, e: k.EventInfo[Impact]) -> None:
        s.play(k.squash(ball, amount=e.data.force / 20), duration=0.15)

    s.start(sim)
    s.wait_for(sim.bounce, count=3, timeout=12)
    s.play(k.write(k.Text("3 bounces").place(at="top", margin=0.6)))
    s.wait_for(sim.done)
```

## Decisions and open questions

The decisions below close the discussions from the brainstorming rounds; nothing blocks the implementation of v1.0.

**Decisions made.**

| Topic | Decision | Reason |
| --- | --- | --- |
| Author language | 100% Python | Largest training base for AI, scientific ecosystem |
| Engine | Rust core via PyO3, on top of existing libraries | Performance, robustness, parallelism without the GIL |
| Execution | Build once → resolve → pure render | Scrubbable preview, caching, determinism |
| Reading values | `.now` in the build, `()` in reactive code | One read, one meaning |
| Time | `play` blocks, `start` does not | Sequential script + background, no ambiguity |
| Errors | Always an error with a fix; no lenient mode | A single dialect; `--fix` eases things for experienced users |
| Parallel | `k.par` exists; `play(a, b)` is its definition | Defining sugar is not an alias; implicit lists are forbidden |
| State | Generic `.to()` + documented named transitions | Readability (`row.swap`) without losing the rule |
| `during` | Reverts animated, same duration; `revert=` changes it | Common case of temporary highlighting |
| Context | Exists (`k.context`, `k.provide`) | The theme already needed it; solves shared clocks |
| Components | One form: subclass of `k.Component` | Functions that return a `Group` are just Python |
| Events | Typed; no strings | Autocomplete and checking |
| Math | LaTeX syntax, built-in engine; optional `engine="tex"` | AI knows LaTeX; no installation |
| Coordinates | 16 × 9 u, origin at the center, y up | Mathematical convention and familiarity with Manim |
| Derived values | Automatic tracing into the IR; opaque Python only with k.python(fn), precomputed in resolve | The render never calls Python; cost is always explicit |
| Data | Arrow contract (PyCapsule); polars is the reference; numpy for n-D arrays via the buffer protocol | Zero-copy and no hard dependency on any library |
| Time | Only k.time (clock of the scene under construction); s.time does not exist; self.age remains | Works at module level, in contexts and in components; a single name |
| Slides | Break only with s.mark(slide=True); s.pause does not exist; mark name optional | One name per concept |
| Interactive web | Core in WASM, no Pyodide; everything that depends on a parameter must be native (W1302 becomes an error) | Small package; the render never calls back into Python |
| Renderer | Interface with two backends; tiny-skia is the default and the reference; Vello becomes the default once the entire snapshot suite is within tolerance and the gain is ≥ 3× at 1080p | Determinism and GPU-free CI from the start; switch guided by an objective criterion |
| Math engine | typst + mitex, accepted if ≥ 98% of a corpus of 500 real formulas renders and passes visual comparison with LaTeX; otherwise, evaluate an alternative before v0.3 | Measurable criterion; engine="tex" remains as an emergency exit |
| TTS | Pluggable interface; local and offline default; with no provider, silence with estimated duration + W1401 | Never blocks the dev; no network dependency |
| Name | kinemo (import kinemo as k); kino was taken on PyPI and crates.io | Free on both registries as of Oct 1, 2026; the alias k keeps all the code unchanged |

**Open questions.** None blocks v1.0. They remain as RFCs for after v1:

- **Polars expressions in the IR.** `pl.col("kw") * 1.1` is already a lazy graph; a subset could be translated directly into the IR.
- **Pyodide on the interactive web.** Only if there is demand for parameter-dependent `k.python` in the browser.
- **Full 3D.** Lighting, materials and scene import beyond the basics described here.

**Proposed roadmap.**

1. **v0.1 — Core.** `add`/`play`/`start`/`.to()`/`place`, shapes, text, basic verbs, during, tempo, signals and native derived values, MP4 render with tiny-skia, `check`.
2. **v0.2 — DX.** `kinemo dev` with timeline, `inspect`, `snap`, complete diagnostics, `--fix`, Manim translation.
3. **v0.3 — Expressiveness.** `Math` and morph, `Code`, `Axes`/plots, components with Prop/Out/Event, context, tracing, k.python, Arrow data.
4. **v0.4 — Advanced time.** `k.when`, `on`/`wait_for`, `integrate`, `simulate`, `voice`, slides.
5. **v0.5 — Scale.** Vello in the preview (becomes the final render default once it passes the switch criterion), vectorized objects, per-segment cache, parallel render, `kinemo mcp`.
6. **v1.0 — API freeze; afterwards, v1.x: 3D and interactive web.**

## Implementation guide

This section turns the spec into work: where each part lives, how the IR is designed, how to test, and when each milestone is done.

### Repository

Monorepo with the Python package and the Rust crates:

```
kinemo/
├─ python/kinemo/          # public API, everything exported as k.*
│  ├─ scene.py             # @scene, Scene, cursor, play/start/wait/mark/during/tempo/voice
│  ├─ objects/             # shapes, Group, Text, Math, Code, Axes, charts, Points
│  ├─ reactive/            # Signal, computed, tracer, k.python, when, integrate, simulate
│  ├─ component.py         # Component, Prop, Out, Event, field, context/provide
│  ├─ anim.py              # verbs, seq/par/stagger, ease, @clip
│  ├─ layout.py            # place, Row/Column/Grid/Stack (declaration only)
│  ├─ diagnostics/         # codes, messages, fixes, Manim → kinemo table
│  ├─ cli/                 # new, dev, check, inspect, snap, render, docs, explain, upgrade, mcp
│  └─ testing.py
├─ crates/
│  ├─ kinemo-ir/           # IR types, MessagePack/JSON serialization, version
│  ├─ kinemo-eval/         # expression graph, interpolation, easing
│  ├─ kinemo-resolve/      # sampling, events, fixed point, conflicts, visual lints
│  ├─ kinemo-layout/       # taffy + cassowary
│  ├─ kinemo-text/         # text, math (typst + mitex), code (tree-sitter)
│  ├─ kinemo-render/       # Backend trait; tiny-skia and Vello
│  ├─ kinemo-encode/       # ffmpeg, GIF, PNG, SVG
│  ├─ kinemo-server/       # preview (axum + WebSocket)
│  └─ kinemo-py/           # PyO3 bindings; the only crate that knows about Python
├─ tests/                  # golden scenes, snapshots, math corpus, AI eval
└─ docs/                   # generated llms.txt, canonical examples
```

Rule: only `kinemo-py` depends on PyO3. All other crates are testable in pure Rust, starting from an IR in JSON.

### Python ↔ Rust boundary

- In the build phase, the Python API creates the IR nodes directly as Rust objects via `kinemo-py`. There is no in-process serialization; MessagePack/JSON is only for the cache, `check --json` and `inspect`.
- The core calls Python only in the resolve phase: `.on` handlers, `k.python` batches and `k.simulate` steps. The GIL is released during the render.
- Every IR node carries its source `span` (file, line, column), captured at construction with `sys._getframe`. Diagnostics, `inspect` and clicking in the preview depend on it.
- Node ids are derived from `span` + an ordinal within the span, so that untouched nodes keep their id across rebuilds (cache and preview state).

### IR: main types

| Node | Essential fields |
| --- | --- |
| `Object` | id, kind, parent, props, span, lifecycle (enter\_t, exit\_t) |
| `PropValue` | `Const` \| `Expr` \| `Binding(source)` \| `Animated(segments)` |
| `Expr` | op, args; ops: arithmetic, comparison, logical, `k` functions, `interp(Arrow table)`, `format(spec)`, `python(ref, table)` |
| `Animation` | target, prop, to, t0, t1, ease, blend, span |
| `Constraint` | kind (above, inside, row…), a, b, gap (Expr), axis, weak |
| `Effect` | `When(cond, action, once, rearm)` |
| `Stateful` | `Integrate(expr, d, initial, clamp)`, `Trace`, `Simulate(Python ref, state, dt, until)` |
| `Event` | source, payload schema, handlers (Python ref) |
| `Mark` | optional name, t, slide |
| `Scene` | ir\_version, size, fps, seed, tail, theme, params, nodes |

Invariants: times in seconds as `f64` (frames exist only in the render); acyclic expression graph (derived values are read-only); `ir_version` follows its own semver.

### Testing strategy

- **Unit and property tests** in each crate (proptest for interpolation, easing and layout).
- **Golden scenes:** the four examples in this spec + one scene per verb and per built-in component. For each one: `check --json` output compared exactly, and PNGs at fixed instants compared exactly with tiny-skia (Vello with tolerance).
- **Diagnostics:** every error and lint code has a snippet that triggers it, the expected message and the fix. The fix applied by `--fix` must produce code that passes `check`.
- **Edge-case contracts:** each row of the edge-case table is a test.
- **Math corpus:** 500 formulas, 98% criterion.
- **AI eval:** 50 natural-language requests; a model generates the scene using only `llms.txt` and `check`. v1.0 target: ≥ 90% passing `check --strict` within two iterations.
- **Performance:** benchmarks in CI with the limits from the targets table; a regression above 10% breaks the build.
- **Types:** Pyright strict over the public API and all examples.
- **Platforms:** Linux x86\_64 and aarch64, macOS arm64, Windows x86\_64; Python 3.11 to 3.14.

### Milestones and acceptance criteria

| Milestone | Scope | Done when |
| --- | --- | --- |
| v0.1 Core | IR, `add`/`play`/`start`/`wait`/`.to`/`.set`, `place`, `Row`/`Column`, shapes, `Text`, entry/exit verbs, `during`, `tempo`, signals and operator-derived values, tiny-skia, MP4, `check` | `hello` and `bubble_sort` render identical to the snapshot; `check` < 300 ms |
| v0.2 DX | `dev` with timeline and hot reload, `inspect`, `snap`, diagnostics with fixes, `--fix`, K11xx (Manim) | Rebuild < 500 ms; every implemented code has a fix test |
| v0.3 Expressiveness | `Math` and morph, `Code`, `Axes`/plots, charts, components (Prop/Out/Event), context, tracing, `k.python`, Arrow | `pythagoras` passes; math corpus ≥ 98% |
| v0.4 Advanced time | `k.when`, `on`/`wait_for`, `integrate`, `simulate`, `trace`, `voice` + TTS, slides | `solar_day` and `bounce` pass; fixed-point and `K0501` tests |
| v0.5 Scale | Vello in the preview, vectorized objects, per-segment cache, parallel render, `mcp` | Performance targets met; AI eval ≥ 90% |
| v1.0 | API freeze, `llms.txt`, docs, semver commitment | All 35 edge-case contracts pass; no breakage foreseen |

### First tasks

1. `kinemo-ir` with `Object`, `PropValue`, `Animation`; Python skeleton that generates IR for `s.add(k.Circle())` + `s.play(c.to(x=2))`.
2. `kinemo-eval`: interpolation and easing; `kinemo-render` with tiny-skia generating a PNG at t.
3. `kinemo-encode`: MP4 via ffmpeg; `kinemo render` command.
4. `kinemo-layout`: `place(at=, below=, gap=)` and `Row`.
5. `kinemo check` printing the timeline, with the first diagnostics (`K0101`, `K0201`, `K0401`).
6. `k.Text` with parley; complete `hello` scene as the first golden snapshot.

## Appendix: quick reference

**Essential API.**

| Area | Symbols |
| --- | --- |
| Scene | `@k.scene`, `s.play`, `s.start`, `s.wait`, `s.wait_for`, `s.add`, `s.remove`, `s.mark`, `s.during`, `s.tempo`, `s.voice`, `k.time`, `s.frame`, `s.camera`, `s.hud`, `s.marks` |
| Object state | `.to`, `.set`, `.place`, `.to_place`, `.unpin`, `.unbind`, `.copy`, `k.reparent` |
| Verbs | `k.draw`, `k.write`, `k.fade_in`, `k.fade_out`, `k.grow`, `k.shrink`, `k.morph`, `k.indicate`, `k.flash`, `k.squash`, `k.follow`, `k.sound` |
| Composition | `k.seq`, `k.par`, `k.stagger`, `@k.clip`, `.with_`, `k.ease.*` |
| Reactive | `k.signal`, `k.computed`, `.map`, `.now`, `k.list`, `k.when`, `k.integrate`, `k.trace`, `k.simulate`, `k.State`, `k.sin`/`k.clamp`/`k.mix`/`k.where` |
| Components | `k.Component`, `k.Prop`, `k.Out`, `k.Event`, `k.field`, `k.prop`, `build`, `enter`, `exit`, `k.context`, `k.provide`, `k.from_context` |
| Layout | `k.Row`, `k.Column`, `k.Grid`, `k.Stack`, `.fit` |
| Text | `k.Text`, `k.Math`, `k.Code` |
| Charts | `k.Axes`, `k.NumberLine`, `k.PolarAxes`, `k.BarChart`, `k.LineChart`, `k.Table`, `k.Points`, `k.VectorField`, `k.StreamLines` |
| Output | `k.movie`, `k.cut`, `k.crossfade`, `k.morph_cut`, `k.Int`/`k.Float`/`k.Bool`/`k.Choice` |
| Native blocks | k.python, k.where, k.piecewise, k.interp, k.spline, k.smoothstep, k.noise, k.floor, k.min, k.max, k.pi |

**Manim → kinemo.**

| Manim | kinemo |
| --- | --- |
| `class S(Scene): def construct(self)` | `@k.scene def s(s: k.Scene)` |
| `self.play(Create(x))` | `s.play(k.draw(x))` |
| `self.play(Write(t))` | `s.play(k.write(t))` |
| `self.add(x)` / `self.remove(x)` | `s.add(x)` / `s.remove(x)` |
| `FadeIn` / `FadeOut` | `k.fade_in` / `k.fade_out` |
| `GrowFromCenter(x)` | `k.grow(x)` |
| `Transform(a, b)` / `ReplacementTransform` | `k.morph(a, b)` |
| `TransformMatchingTex(a, b)` | `k.morph(a, b)` (TeX matching is the default) |
| `x.animate.shift(UP)` | `s.play(x.to(y=x.y.now + 1))` |
| `x.animate.set_color(RED)` | `s.play(x.to(color=k.RED))` |
| `x.next_to(y, DOWN)` | `x.place(below=y)` |
| `x.to_edge(UP)` / `x.to_corner(UL)` | `x.place(at="top")` / `x.place(at="top-left")` |
| `VGroup(a, b).arrange(RIGHT)` | `k.Row(a, b)` |
| `ValueTracker(0)` | `k.signal(0)` |
| `x.add_updater(f)` | `x.set(prop=signal_or_lambda)` |
| `always_redraw(lambda: ...)` | Reactive props via lambda |
| `AnimationGroup(a, b, lag_ratio=r)` | `k.stagger([a, b], lag=...)` |
| `Succession(a, b)` | `k.seq(a, b)` |
| `self.wait()` | `s.wait()` |
| `MathTex(r"...")` / `Tex` | `k.Math(r"...")` / `k.Text` |
| `Axes(...).plot(f)` | `k.Axes(...).plot(f)` |
| `ThreeDScene` + `set_camera_orientation` | `@k.scene(camera="3d")` + `s.camera.to(orbit=...)` |
