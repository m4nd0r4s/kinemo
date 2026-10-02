# The timeline

Time in kinemo is explicit. Nothing moves unless you schedule it, and every scheduling call
says whether the script waits for it (`s.play`) or not (`s.start`). Animations are values
you can compose (`k.seq`, `k.par`, `k.stagger`), rescale (`duration=`) and package
(`@k.clip`). This guide covers all of the time controls a scene has.

Reference: [scene](../reference/scene.md) ([`s.play`](../reference/scene.md#scene-play),
[`s.start`](../reference/scene.md#scene-start), [`s.during`](../reference/scene.md#scene-during),
[`s.tempo`](../reference/scene.md#scene-tempo), [`s.mark`](../reference/scene.md#scene-mark)) and
[composition](../reference/composition.md) ([`k.seq`](../reference/composition.md#k-seq),
[`k.stagger`](../reference/composition.md#k-stagger), [`k.clip`](../reference/composition.md#k-clip)).

## `play`, `start` and `wait`

| Call | Cursor | Returns | Use it for |
| --- | --- | --- | --- |
| `s.play(*anims, duration=, ease=, at=)` | Moves to the end | `TimeSpan` | The next step of the script. |
| `s.start(*anims, duration=, ease=, at=)` | Stays | `TimeSpan` | Background motion while the script continues. |
| `s.wait(d=1.0)` | Moves `d` seconds | `TimeSpan` | A pause. Started animations keep running. |

Several animations passed to one `s.play` run in parallel; the call lasts as long as the
longest one. By definition, `s.play(a, b)` is `s.play(k.par(a, b))`.

```python
import kinemo as k


@k.scene
def background(s: k.Scene):
    dot = k.Dot(r=0.2, x=-5, y=-1)
    title = k.Text("In parallel").place(at="top", margin=0.8)
    s.add(dot)
    s.start(dot.to(x=5), duration=4, ease=k.ease.linear)   # 0 → 4, cursor stays at 0
    s.play(k.write(title))                                 # 0 → 1
    s.wait(1)                                              # 1 → 2
    s.play(title.to(color=k.YELLOW))                       # 2 → 3, dot still moving
    s.wait(1)
```

Every verb and every `.to()` lasts **1 s** with `k.ease.smooth` unless you say otherwise.
Each one accepts `duration=`, `ease=` and `delay=`:

```python
import kinemo as k


@k.scene
def timings(s: k.Scene):
    a = k.Circle(r=0.6, x=-3)
    b = k.Circle(r=0.6, x=3)
    s.play(k.draw(a, duration=0.5), k.draw(b, delay=0.5, duration=0.5))
    s.play(a.to(y=2, ease=k.ease.out_back), b.to(y=-2, duration=2))
```

### The `TimeSpan`

`s.play`, `s.start` and `s.wait` return a `TimeSpan` with `start`, `end`, `duration` and
`done` (an event at its end). Use it to anchor other things to that moment:

```python
import kinemo as k


@k.scene
def anchored(s: k.Scene):
    dot = k.Dot(r=0.2, x=-5)
    title = k.Text("Moving...").place(at="top", margin=0.8)
    s.add(dot)
    h = s.start(dot.to(x=5), duration=3)
    s.play(k.write(title))
    s.wait_for(h.done)                  # the cursor jumps to h.end (3.0)
    s.play(k.fade_out(dot, title))
```

`s.wait_for(event)` moves the cursor to the next firing of an event after the cursor. It
only sees what has already been scheduled, which is why the pattern is "`s.start` first,
then `s.wait_for`". Waiting on a condition or simulation with no guaranteed end requires
`timeout=`.

### Scheduling at an absolute time: `at=`

`at=` schedules an animation at a given instant instead of at the cursor, and does not move
the cursor. Use it with `s.start`:

```python
import kinemo as k


@k.scene
def absolute(s: k.Scene):
    a = k.Square(1.2, x=-3)
    b = k.Square(1.2, x=3)
    h = s.play(k.draw(a))
    s.play(k.draw(b))
    s.start(k.indicate(a), at=h.end + 0.5)   # at 1.5 s, while the script is at 2.0
    s.wait(1)
```

`s.play(..., at=...)` behaves exactly like `s.start` and raises lint `W0110`, which asks you
to write `s.start` to make the intent explicit.

## Rescaling with `duration=`

`duration=` on `s.play` / `s.start` sets the **total** duration of everything passed, and
the content is rescaled proportionally:

- `s.play(a, b, duration=2)`: both last 2 s (each was 1 s);
- `s.play(k.seq(a, b), duration=2)`: the sequence lasts 2 s, so each part lasts 1 s;
- `s.play(k.seq(a.with_(duration=3), b), duration=2)`: 3 + 1 = 4 s natural, so `a` becomes
  1.5 s and `b` 0.5 s.

```python
import kinemo as k


@k.scene
def rescale(s: k.Scene):
    dot = k.Dot(r=0.25, x=-4)
    s.add(dot)
    path = k.seq(dot.to(x=0), dot.to(y=2), dot.to(x=4))   # natural length: 3 s
    s.play(path, duration=1.5)                            # each step: 0.5 s
    s.wait(0.5)
```

`anim.with_(duration=, ease=, delay=)` returns a copy with other parameters; animations are
immutable, so the original is unchanged.

## Composition: `seq`, `par`, `stagger`

```python
k.seq(a, b, c)                          # one after the other
k.par(a, b, c)                          # all together; lasts as long as the longest
k.stagger([a, b, c], lag=0.1)           # each starts 0.1 s after the previous
k.stagger(anims, lag=0.1, order="center")   # "sequence", "reverse", "center", "random(seed)"
```

They return ordinary animations, so they nest:

```python
import kinemo as k


@k.scene
def compose(s: k.Scene):
    bars = [k.Bar(v) for v in [3, 5, 2, 6, 4, 1, 5]]
    row = k.Row(*bars, gap=0.3, align="bottom").place(at="center")
    title = k.Text("Composition", size=0.6).place(at="top", margin=0.8)
    entrance = k.stagger([k.grow(b, from_="bottom") for b in row], lag=0.08, order="center")
    s.play(k.seq(entrance, k.write(title)))
    s.play(k.seq(k.par(bars[0].to(scale=1.2), bars[-1].to(scale=1.2)), title.to(color=k.TEAL)))
    s.play(*[b.to(color=k.TEAL) for b in bars], duration=0.6)
    s.wait(0.5)
```

`k.par` is only needed when a parallel group is *part of* another composition; at the top
level, pass the animations straight to `s.play`.

## `s.during`: apply, then revert

`with s.during(*anims):` applies state changes on entry and reverts them, animated, on
exit. It is the natural way to highlight something temporarily while other things happen:

```python
import kinemo as k


@k.scene
def highlight(s: k.Scene):
    a = k.Circle(r=0.6)
    b = k.Circle(r=0.6)
    row = k.Row(a, b, gap=1).place(at="center")
    s.play(k.draw(row))
    with s.during(a.to(color=k.YELLOW), b.to(color=k.YELLOW), duration=0.3):
        s.play(row.swap(0, 1))
    s.wait(0.5)
```

The timeline is: entry (0.3 s), the block body, then the revert (0.3 s). By default the
revert uses the same duration and easing as the entry. Change it with `revert=`:

| `revert=` | Effect |
| --- | --- |
| `"instant"` | Snap back with no animation. |
| `0.8` | Revert over another duration. |
| `k.ease.out` | Revert with another easing. |

Only reversible animations are accepted: `.to(...)` and `k.indicate`. Entrance and exit
verbs (`k.fade_in`, `k.draw`, ...) have no reverse and give `K0204`.

## `s.tempo`: speed up a whole block

`with s.tempo(f):` divides every duration and wait inside the block by `f`.
`s.tempo(1, to=8)` ramps the speed from 1× to 8× over the block. Tempos nest by
multiplying.

```python
import kinemo as k


@k.scene
def speed_up(s: k.Scene):
    dots = [k.Dot(r=0.2) for _ in range(8)]
    row = k.Row(*dots, gap=0.6).place(at="center")
    s.add(row)
    with s.tempo(1, to=4):              # each pulse is shorter than the previous
        for d in dots:
            s.play(k.indicate(d), duration=0.5)
    with s.tempo(2):
        s.play(row.to(scale=1.5))       # 0.5 s instead of 1 s
        s.wait(1)                       # 0.5 s
```

Signals derived from `k.time` are not affected by tempo: the scene clock keeps advancing at
one second per second.

## Marks

`s.mark(name=None, slide=False)` records the cursor without moving it and returns the time.
Named marks are available as `s.marks[name]`, which is handy with `at=`. `slide=True`
defines a slide break for `kinemo render --format slides`: each section plays until the
next break and waits for a key press.

```python
import kinemo as k


@k.scene
def presentation(s: k.Scene):
    title = k.Text("Part 1").place(at="center")
    s.play(k.write(title))
    s.mark("part2", slide=True)
    s.play(title.to(text="Part 2"))
    s.start(k.indicate(title), at=s.marks["part2"] + 1.5)
    s.wait(2)
```

Marks also come from narration: in `with s.voice("Every right [triangle]{tri} ...")`, the
word in brackets becomes `s.marks["tri"]` at the instant it is spoken.

## Clips: reusable sequences

A clip is a function with its own cursor, packaged as an animation. Decorate a function
`def name(s: k.Scene, ...) -> None` with `@k.clip`; calling it returns an `Animation`:

```python
import kinemo as k


@k.clip
def present(s: k.Scene, obj: k.Node) -> None:
    s.play(k.draw(obj))
    s.wait(0.3)
    s.play(k.indicate(obj))


@k.scene
def with_clips(s: k.Scene):
    a = k.Circle(r=0.8).place(at="left", margin=3)
    b = k.Square(1.6).place(at="right", margin=3)
    title = k.Text("Clips", size=0.6).place(at="top", margin=0.8)
    s.play(present(a), k.write(title))       # composes like any animation
    s.play(present(b), duration=1.15)        # natural 2.3 s, rescaled to half
    s.play(k.seq(present(k.Dot(r=0.3).place(at="bottom", margin=1.5)), k.fade_out(title)))
```

- The clip body runs in the build phase at the moment the clip is scheduled, with the
  cursor starting at the clip's beginning.
- Its duration is wherever its internal cursor ends.
- Inside a clip, use the full scene API: `s.play`, `s.start`, `s.wait`, `s.during`,
  `s.tempo`, `.now` reads.
- Components can define clips as methods: see [components](07-components.md#named-transitions-and-clips).

> **Common mistakes**
>
> | You see | Why | Fix |
> | --- | --- | --- |
> | `K0201 two animations write c.x at the same time` | Two animations on the same prop overlap, often an `s.start` that is still running when a later `s.play` touches the same prop. | Chain them with `k.seq`, wait for the first (`s.wait_for(h.done)`), or add them on purpose with `blend="add"`. |
> | `K0204 FadeIn is not reversible and cannot be used in s.during` | An entrance/exit verb inside `s.during(...)`. | Only `.to(...)` and `k.indicate` go in `during`; play entrance verbs before the block. |
> | `W0110 play(..., at=) does not move the cursor` | `s.play` with `at=`. | Write `s.start(..., at=...)`. |
> | `K0202 invalid duration` | A negative, infinite or NaN `duration=` or wait. | Use a finite number ≥ 0. |
> | `K0203 not an animation` | You passed an object, a list or `None` to `s.play`. | Pass animations: `s.play(k.draw(obj))`, `s.play(*anims)` or `s.play(k.stagger(anims))`. |
> | `K0702` / `K0703` from `s.wait_for` | The event did not happen before `timeout=`, or it already happened before the cursor. | Raise the timeout; schedule the source with `s.start` (not `s.play`) before waiting on it. |
> | The scene is longer than expected | Something started with `s.start` ends after the final cursor; the scene always includes it, plus `tail`. | Check the timeline in `kinemo check`; shorten the background animation or set `@k.scene(tail=...)`. |
