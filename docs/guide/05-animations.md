# Animations

An animation in kinemo is an immutable **value** with a duration, an easing and a target.
It does nothing until you pass it to `s.play` or `s.start`. There are two families:
**verbs**, module functions such as `k.draw` and `k.morph` that bring objects in and out or
add emphasis, and **state changes**, `obj.to(...)`. This guide tours both and shows how to
combine them.

Reference: [verbs](../reference/verbs.md) (for example [`k.morph`](../reference/verbs.md#k-morph)),
[composition](../reference/composition.md) ([`k.ease`](../reference/composition.md#k-ease)),
[text](../reference/text.md).

## Verbs at a glance

| Verb | Category | What it does |
| --- | --- | --- |
| `k.draw(*objs)` | Entry | Traces the outline, then fills |
| `k.write(*objs)` | Entry | Writes text character by character; other objects are drawn |
| `k.fade_in(*objs, shift=)` | Entry | Opacity 0 → 1, optionally arriving from an offset |
| `k.grow(obj, from_=)` | Entry | Scales up from the center or a side |
| `k.fade_out(*objs, shift=)` | Exit | Opacity 1 → 0, then leaves the scene |
| `k.shrink(obj, to=)` | Exit | The inverse of `k.grow`, then leaves the scene |
| `k.morph(a, b, match=)` | Swap | `a` leaves, `b` enters, matching parts travel |
| `k.indicate(obj, color=, scale=)` | Emphasis | Temporary tint and pulse; ends as it started |
| `k.flash(obj, color=)` | Emphasis | A ring of light that expands from the edge |
| `k.squash(obj, amount=)` | Emphasis | Elastic squash against the base |
| `k.follow(obj, path, rotate=)` | Motion | Travels along a path |
| `k.sound(path, gain=)` | Audio | Plays a sound file at that instant |

Every verb and every `.to()` lasts 1 s with `k.ease.smooth`, except the two short
accents: `k.flash` (0.6 s) and `k.squash` (0.4 s), both with `k.ease.out`. All of them
accept `duration=`, `ease=` and `delay=`.

## Entrances and exits

```python
import kinemo as k


@k.scene
def entrances(s: k.Scene):
    title = k.Text("Entrances", size=0.7).place(at="top", margin=0.8)
    circle = k.Circle(r=0.8, fill=k.BLUE, fill_opacity=0.4)
    bar = k.Bar(5, label=True)
    card = k.RoundedRect(w=2, h=1.4)
    k.Row(circle, bar, card, gap=1, align="bottom").place(at="center")
    s.play(k.write(title))
    s.play(k.draw(circle))
    s.play(k.grow(bar, from_="bottom"))
    s.play(k.fade_in(card, shift=(0, 0.5)))       # arrives from 0.5 u below
    s.wait(0.5)
    s.play(k.fade_out(circle, card), k.shrink(bar, to="bottom"))
    s.play(k.fade_out(title, shift=(0, 0.5)))    # leaves upwards
```

The row itself never entered the scene in that example, yet its children are drawn in
place: the container still lays them out. An entry verb on a group (`k.draw(row)`) brings in the
group and all of its children together.

When the object is a [component](07-components.md) that defines `enter()` or `exit()`, the
verbs use those implementations instead of the default behavior.

## State changes with `.to()`

`obj.to(**props)` animates any public prop from its value at the cursor to the target:

```python
import kinemo as k


@k.scene
def state_changes(s: k.Scene):
    square = k.Square(1.5, x=-3)
    bar = k.Bar(2, label=True, x=3, y=-1.5)
    s.add(square, bar)
    s.play(square.to(x=0, rotate=45, color=k.RED, fill_opacity=0.4))
    s.play(bar.to(value=6), square.to(scale=0.6), duration=1.5)
    s.play(square.to(opacity=0.3, ease=k.ease.out))
```

How values interpolate:

| Type | Interpolation |
| --- | --- |
| `float`, `int`, vectors | Linear in easing space (`int` rounds) |
| Colors | In OKLab, so there is no gray in the middle |
| Paths and shapes | Point correspondence with resampling |
| Strings in `k.Text` | Glyph morph (see [Text changes](#text-changes)) |
| `bool`, enums | Step at the end |
| Lists and custom types | Need `lerp=` on the signal; otherwise `K0205` |

Components expose **named transitions** that read better than a raw `.to()`: `row.swap(i,
j)`, `row.insert(i, obj)`, `row.pop(i)`, `ax.zoom_to(x=..., y=...)`,
`code.highlight(lines=[...])`, `chart.to(data=...)`. Each one is documented as sugar for a
`.to()` and behaves exactly like it, including in conflicts.

## Easing

```python signature
k.ease.linear       k.ease.smooth (default)   k.ease.in_     k.ease.out    k.ease.in_out
k.ease.out_back     k.ease.out_elastic        k.ease.spring(stiffness=100, damping=10)
k.ease.steps(n)     k.ease.custom(fn)         k.ease.reverse(e)
```

```python
import kinemo as k


def decelerate(t: float) -> float:
    return 1 - (1 - t) ** 3


@k.scene
def easing(s: k.Scene):
    eases = [k.ease.linear, k.ease.smooth, k.ease.out_back, k.ease.spring(stiffness=120, damping=8),
             k.ease.steps(5), k.ease.custom(decelerate)]
    dots = [k.Dot(r=0.15, x=-5, y=2.5 - i) for i in range(len(eases))]
    s.add(*dots)
    s.wait(0.5)
    s.play(*[d.to(x=5, ease=e) for d, e in zip(dots, eases)], duration=2)
    s.wait(0.5)
```

`ease=` on `s.play(..., ease=...)` applies to the whole group. Use `k.ease.linear` for
anything that should move at constant speed: clocks, scans, travel along a path.

## Morph

`k.morph(a, b)` swaps one object for another: `a` leaves, `b` enters, and the parts they
share travel from one to the other while the rest fades out and in. It works for text,
formulas, code and shapes.

```python
import kinemo as k


@k.scene
def morph_text(s: k.Scene):
    a = k.Text("a + b = c", size=0.8).place(at="center")
    b = k.Text("c = a + b", size=0.8).place(at="center")
    s.play(k.write(a))
    s.play(k.morph(a, b))      # the letters slide to their new places
    s.wait(0.5)
```

### Equations

Between `k.Math` formulas, parts are matched in this order:

1. your explicit `match=`;
2. subexpressions named with `\id{name}{...}` that share a name;
3. identical TeX subtrees, largest first (`c^2` and `c^{2}` are the same);
4. identical glyphs, by relative position (this breaks ties between repeated terms);
5. whatever is left fades out from `a` and fades in to `b`.

```python
import kinemo as k


@k.scene
def morph_math(s: k.Scene):
    eq1 = k.Math(r"a^2 + b^2 = c^2").place(at="center")
    eq2 = k.Math(r"c = \sqrt{a^2 + b^2}").place(at="center")
    eq3 = k.Math(r"\id{len}{\sqrt{a^2 + b^2}} = c").place(at="center")
    s.play(k.write(eq1))
    s.play(k.morph(eq1, eq2))          # a^2 + b^2 and c travel
    s.play(k.morph(eq2, eq3))
    s.play(eq3["len"].to(color=k.YELLOW))
    s.wait(0.5)
```

`match=` maps glyph keys of `a` (the characters or symbols you see) to glyph keys of `b`, to
force pieces that differ to travel into each other:

```python
import kinemo as k


@k.scene
def morph_match(s: k.Scene):
    before = k.Math(r"f(a) = a^2 + 1").place(at="center")
    after = k.Math(r"f(x) = x^2 + 1").place(at="center")
    s.play(k.write(before))
    s.play(k.morph(before, after, match={"a": "x"}))   # each a slides into an x
    s.wait(0.5)
```

### Code

Between two `k.Code` blocks, the morph diffs lines and then tokens: identical lines slide,
inserted ones enter, removed ones leave.

```python
import kinemo as k

V1 = """
def area(r):
    return 3.14 * r * r
"""

V2 = """
import math

def area(r):
    return math.pi * r ** 2
"""


@k.scene
def morph_code(s: k.Scene):
    code = k.Code(V1, lang="python", line_numbers=True).place(at="center")
    s.play(k.write(code))
    s.play(code.highlight(lines=[2]))
    s.play(k.morph(code, k.Code(V2, lang="python", line_numbers=True).place(at="center")))
    s.wait(0.5)
```

With nothing in common (say, a circle into a word), the morph does a warp plus crossfade
and emits lint `W0801`.

## Text changes

Changing the string of a `k.Text` with `.to(text=...)` is a morph under the hood: shared
characters travel, the rest fades. Parts of a text are objects of their own, so you can
animate a word or a range of characters:

```python
import kinemo as k


@k.scene
def text_changes(s: k.Scene):
    txt = k.Text("Hello world, hello kinemo", size=0.6).place(at="center")
    s.play(k.write(txt))
    s.play(txt["world"].to(color=k.YELLOW))          # first occurrence
    s.play(k.stagger([w.to(scale=1.1) for w in txt.words], lag=0.1))
    s.play(*[p.to(color=k.TEAL) for p in txt.find_all("o")])
    s.play(txt.to(text="Goodbye world"))
    s.wait(0.5)
```

Parts: `txt["world"]` (first occurrence), `txt.find_all("o")`, `txt.chars[3:7]`,
`txt.words[1]`, `txt.lines[0]`. In formulas, `eq["name"]` from `\id{name}{...}` or a TeX
subexpression like `eq["c^2"]`.

For text that changes continuously with a value (a counter, a clock), do not chain
`.to(text=...)`: bind it with a lambda, `k.Text(lambda: f"{x():.1f} kWh")`. See
[reactive values](06-reactive.md).

## Emphasis

```python
import kinemo as k


@k.scene
def emphasis(s: k.Scene):
    word = k.Text("important", size=0.8).place(at="top", margin=1.2)
    dot = k.Dot(r=0.3).place(at="center")
    ball = k.Circle(r=0.6, fill=k.ORANGE, fill_opacity=1).place(at="bottom", margin=1.2)
    s.add(word, dot, ball)
    s.play(k.indicate(word, color=k.YELLOW, scale=1.3))
    s.play(k.flash(dot, color=k.YELLOW))
    s.play(k.squash(ball, amount=0.4))
    s.wait(0.5)
```

All three return the object to its initial state. `k.indicate` is reversible, so it also
works inside `s.during(...)` (it holds the highlight for the duration of the block).

## Motion along a path: `k.follow`

`k.follow(obj, path)` moves an object along the outline of another object or along a list
of points, in world coordinates. `rotate=True` keeps it aligned with the tangent.

```python
import kinemo as k


@k.scene
def orbit(s: k.Scene):
    track = k.Circle(r=2.5, stroke=k.GRAY).place(at="center")
    ship = k.Triangle(scale=0.25, fill=k.BLUE, fill_opacity=1)
    s.add(track, ship)
    s.play(k.follow(ship, track, rotate=True), duration=3, ease=k.ease.linear)
    ship.unbind("x", "y", "rotate")          # free it before moving it again
    s.play(k.follow(ship, [(2.5, 0), (0, -3), (-3, 0)]), duration=2)
```

`k.follow` drives `x`, `y` (and `rotate`) through bindings that stay in place after it
ends, so call `obj.unbind("x", "y", "rotate")` before animating the position again,
including with a second `k.follow`. It only moves objects that have no parent, and not
objects pinned by `.place(...)`.

## Composition patterns

Animations are values, so ordinary Python composes them.

**One animation per item, staggered.**

```python
import kinemo as k


@k.scene
def cascade(s: k.Scene):
    cards = [k.RoundedRect(w=1.6, h=1) for _ in range(6)]
    grid = k.Grid(*cards, cols=3, gap=0.3).place(at="center")
    s.play(k.stagger([k.draw(c) for c in cards], lag=0.1))
    s.play(k.stagger([c.to(color=k.TEAL) for c in grid], lag=0.05, order="random(1)"))
    s.wait(0.5)
```

**Build a step once, reuse it with variations.**

```python
import kinemo as k


@k.scene
def variations(s: k.Scene):
    dot = k.Dot(r=0.25, x=-4)
    s.add(dot)
    move = dot.to(x=4)
    s.play(move.with_(duration=2, ease=k.ease.out_back))
    s.play(dot.to(x=-4).with_(ease=k.ease.linear, delay=0.2))
```

**Enter a whole diagram in a choreographed order.**

```python
import kinemo as k


@k.scene
def choreography(s: k.Scene):
    a = k.RoundedRect(w=2, h=1.2).place(at="left", margin=2.5)
    b = k.RoundedRect(w=2, h=1.2).place(at="right", margin=2.5)
    la = k.Text("client", size=0.4).place(inside=a)
    lb = k.Text("server", size=0.4).place(inside=b)
    link = k.Arrow(start=a.edge("right"), end=b.edge("left"))
    s.play(k.seq(k.par(k.draw(a), k.draw(b)), k.par(k.write(la), k.write(lb)), k.grow(link, from_="left")),
           duration=2.5)
    s.wait(0.5)
```

**Sum two motions on purpose with `blend="add"`.** A shake on top of a movement writes the
same prop at the same time, which is normally a conflict (`K0201`). `blend="add"` adds the
animation to whatever else is writing that prop:

```python
import kinemo as k


@k.scene
def shake(s: k.Scene):
    box = k.Square(1.2, x=-4)
    s.add(box)
    steps = [0.15, -0.3, 0.3, -0.3, 0.3, -0.3, 0.3, -0.15]   # each step adds; they sum to 0
    jitter = k.seq(*[box.to(x=dx, blend="add", duration=0.1) for dx in steps])
    s.play(box.to(x=4, duration=2), jitter.with_(delay=0.6))   # both write box.x
    s.wait(0.5)
```

**Temporary state while something else happens:** `with s.during(...)`, and **reusable
multi-step sequences:** `@k.clip`. Both are covered in [the timeline guide](03-timeline.md).

> **Common mistakes**
>
> | You see | Why | Fix |
> | --- | --- | --- |
> | `K0201 two animations write c.x at the same time` | Two animations on the same prop overlap. | `k.seq` them, or `blend="add"` when summing is the intent. |
> | `K0203 not an animation` | `s.play(obj)` or `s.play([a, b])`. | `s.play(k.draw(obj))`; unpack lists: `s.play(*anims)` or `s.play(k.stagger(anims))`. |
> | `K0204 ... is not reversible and cannot be used in s.during` | An entrance/exit verb inside `s.during`. | Only `.to(...)` and `k.indicate` there. |
> | `K0205 this list does not know how to interpolate` | `.to()` on a list signal without `lerp=`. | `k.signal([...], lerp=k.lerp.pointwise)` or `lerp=None` (step). |
> | `K0401 ... held by a reactive binding` after `k.follow` | `k.follow` leaves `x`/`y` bound to the path. | `obj.unbind("x", "y", "rotate")` before moving it again. |
> | `K0401 ... held by a constraint` | `.to(x=...)` on a placed object. | `.to_place(...)`, or `.to(x=..., unpin=True)`. |
> | `K0404 unknown anchor` | A typo in `from_=` / `to=` of `k.grow` / `k.shrink`. | Use `center`, `top`, `bottom`, `left`, `right` or a corner like `top-left`. |
> | `W0801 morph without matches` | Morphing two things with nothing in common. | Expected for shape swaps; otherwise give `match=` or use `\id{...}` names. |
> | `K0801 unsupported LaTeX command` | Text-mode or package commands (TikZ...) in `k.Math`. | Keep `k.Math` to math; put prose in `k.Text`. |
> | `K1101` / `K1102` | Manim names: `Create`, `x.animate.shift(UP)`. | `k.draw(x)`, `s.play(x.to(y=x.y.now + 1))`. |
