# Objects and layout

Everything you see is an object: shapes, text, formulas, axes, containers and your own
components. Objects are plain Python values with props (which are signals), a lifecycle
(they enter and leave the scene), and a position that usually comes from **constraints**
rather than coordinates. This guide covers how to create, change, position and group them.

Reference: [objects](../reference/objects.md), [object state](../reference/object-state.md)
([`obj.to`](../reference/object-state.md#node-to), [`obj.set`](../reference/object-state.md#node-set),
[`obj.place`](../reference/object-state.md#node-place)), [layout](../reference/layout.md).

## Objects are values

Creating an object does not put it on screen. It enters the scene with `s.add(obj)`
(instantly) or with an entrance verb (`k.draw`, `k.write`, `k.fade_in`, `k.grow`), which
animates its arrival:

```python
import kinemo as k


@k.scene
def entering(s: k.Scene):
    box = k.Rect(w=3, h=1.5).place(at="center")
    label = k.Text("Ready").place(inside=box)
    s.add(box)                     # instant, at t = 0
    s.play(k.write(label))         # animated, 0 → 1
    s.wait(0.5)
    s.play(box.to(color=k.GREEN))
```

Because objects are values, you can build them in ordinary Python (lists, comprehensions,
helper functions) and decide later when each one enters.

## Lifecycle

An object goes through three states, always in this order:

| State | Entered via | Accepts `.to()` | Leaves via |
| --- | --- | --- | --- |
| Created | The constructor (`k.Circle()`) | No: `K0101` | `s.add` or an entrance verb |
| In the scene | `s.add`, `k.draw`, `k.write`, `k.fade_in`, `k.grow` | Yes | `s.remove` or an exit verb |
| Removed | `s.remove`, `k.fade_out`, `k.shrink` | No: `K0102`, with the line and instant of the exit | An entrance verb again |

```python
import kinemo as k


@k.scene
def lifecycle(s: k.Scene):
    a = k.Text("Before").place(at="center")
    b = k.Text("After").place(at="center")
    s.add(a)
    s.wait(1)
    s.remove(a)                    # instant exit
    s.add(b)
    s.wait(1)
    s.play(k.fade_out(b))          # animated exit
    s.play(k.fade_in(a))           # a comes back
    s.wait(0.5)
```

Every object also has two built-in events, `obj.entered` and `obj.exited`, which you can use
with `@obj.entered.on` or `s.wait_for(obj.exited)`.

## Props

Every public property of an object is a **signal**: `dot.x`, `box.color`, `txt.opacity`.
They share a common set:

| Group | Props |
| --- | --- |
| Transform | `x`, `y`, `position`, `rotate` (degrees), `scale`, `scale_x`, `scale_y`, `anchor` |
| Style | `color` (shorthand for `stroke` and `fill`), `fill`, `fill_opacity`, `stroke`, `stroke_width`, `dash`, `opacity` |
| Composition | `z` (draw order), `visible`, `bleed` (cropped by the frame edge on purpose) |
| Read-only (derived from layout) | `width`, `height`, `bbox`, `left`, `right`, `top`, `bottom`, `center` |

Shapes add their own (`r` for `k.Circle`, `w`/`h` for `k.Rect`, `start`/`end` for
`k.Line`, `text` for `k.Text`, `value` for `k.Bar`...). Every constructor argument accepts a
value, a signal or a lambda.

Objects are drawn by `z` (higher on top); with equal `z`, the one that entered the scene
later is on top, so `s.add(background, label)` puts the label above. Inside a group,
children draw in their order.

### `set` and `to`

- `obj.set(**props)` is an **instant** change at the cursor.
- `obj.to(**props)` is an **animated** change; it returns an animation that you pass to
  `s.play` or `s.start`.

```python
import kinemo as k


@k.scene
def state(s: k.Scene):
    square = k.Square(1.5).place(at="center")
    s.play(k.draw(square))
    square.set(fill=k.BLUE, fill_opacity=0.3)                 # instant
    s.wait(0.5)
    s.play(square.to(color=k.RED, rotate=45, scale=1.5), duration=1.5)
    s.wait(0.5)
```

`.to()` interpolates from the value at the cursor to the target: numbers linearly in easing
space, colors in OKLab (no gray in the middle), shapes point by point, text strings glyph
by glyph. `duration`, `ease`, `delay` and `place` are reserved keywords of `.to()`, never
props.

Each prop is also usable on its own: `s.play(dot.x.to(3))` is the same as
`s.play(dot.to(x=3))`, and `dot.x.now` reads the value at the cursor.

Props are never assigned with `=`. `box.fill = k.RED` raises `K0105` and suggests
`box.set(fill=...)` or `s.play(box.to(fill=...))`. The same holds for the `color` shorthand.

### Bindings: `set` with a signal or lambda

Passing a signal or a lambda instead of a value creates a **reactive binding** from the
cursor on. The prop then follows its source at every instant:

```python
import kinemo as k


@k.scene
def binding(s: k.Scene):
    leader = k.Dot(r=0.25, x=-4, y=1)
    follower = k.Dot(r=0.15, fill=k.RED)
    s.add(leader, follower)
    follower.set(x=leader.x, y=leader.y - 2)
    s.play(leader.to(x=4), duration=2)
    follower.unbind("x")           # keeps its current value, free again
    s.play(follower.to(x=0))
```

`obj.unbind(*names)` removes bindings (all of them when no name is given) and keeps the
current value. An axis held by a binding cannot be animated until it is unbound (`K0401`).

## Coordinates and the frame

The frame measures **16 × 9 units**, with the origin at the center and y pointing up.
`s.frame` exposes `left`, `right`, `top`, `bottom`, `width`, `height`, `center` and `safe`
(the area 0.5 units inside the edges, which the `W1001` lint checks). Position props are
local to the parent; `obj.world.position` and `obj.world.center` give global values.

You can position by coordinates (`k.Dot(x=-4, y=1)`), and that is fine for things that
move freely. For layout, use constraints.

## Constraints: `.place(...)`

`.place(...)` declares where the object sits relative to the frame or to another object,
and the relation keeps holding while things move. It returns the object, so it chains with
the constructor.

| Argument | Example | Effect |
| --- | --- | --- |
| `at=` | `"center"`, `"top-left"`, `(2, 1)`, `ax.point(3, 9)` | Anchor on the frame, at a point, or at a reactive point |
| `margin=` | `margin=0.6` | Distance from the frame edge (with `at=`) |
| `above=`, `below=`, `left_of=`, `right_of=` | `below=tri` | Side relative to another object |
| `inside=` | `inside=box, align="bottom", pad=0.1` | Inside another object; `pad=` is the inner distance |
| `gap=` | `gap=0.3`, `gap=sim.y` | Distance from the other object; accepts a signal |
| `align=` | `align="left"` | Alignment on the perpendicular axis |
| `clamp=` | `clamp=True` | Keeps the object inside `s.frame.safe` |

Anchors: `center`, `top`, `bottom`, `left`, `right`, `top-left`, `top-right`,
`bottom-left`, `bottom-right`.

```python
import kinemo as k


@k.scene
def positions(s: k.Scene):
    box = k.Square(2).place(at="center")
    title = k.Text("Title").place(at="top", margin=0.6)
    label = k.Text("box", size=0.4).place(below=box, gap=0.3)
    note = k.Text("note", size=0.35).place(right_of=box, gap=0.4, align="top")
    marker = k.Dot(r=0.12, fill=k.RED).place(inside=box, align="top", pad=0.2)
    s.add(box, title, label, note, marker)
    s.play(box.to(scale=1.5))      # label, note and marker follow the box
    s.wait(0.5)
```

A single `.place` call holds one relation (plus `at=`, `gap=`, `align=`...). Calling
`.place` again later in the script replaces the placement from the cursor on, instantly.

### Constraints versus animation

A `.place(...)` pins **both** axes of the object. An axis held by a constraint cannot be
animated directly (`K0401`): the constraint and the animation would both decide where the
object is. You have two options:

```python
import kinemo as k


@k.scene
def move_placed(s: k.Scene):
    tri = k.Triangle().place(at="center")
    title = k.Text("title", size=0.5).place(above=tri, gap=0.4)
    s.add(tri, title)
    s.play(title.to_place(right_of=tri, gap=0.4))   # 1. animate the constraint change
    s.play(title.to(x=3, y=2, unpin=True))          # 2. release it and animate freely
    s.wait(0.5)
```

1. `obj.to_place(...)` is the `.to` of `.place`: it takes the same keywords as `.place(...)`
   (plus `duration=`, `ease=`, `delay=`) and animates from the current placement to the new
   one. The new constraint keeps holding afterwards.
2. `obj.to(..., unpin=True)` releases the constraint where the animation starts, keeping the
   current position, and then animates `x`/`y` freely. `obj.unpin()` does the same instantly
   at the cursor, outside an animation.

## Derived props and `edge()`

`width`, `height`, `left`, `right`, `top`, `bottom`, `center` (in the parent) and
`obj.world.position`, `obj.world.center` (global) are read-only expressions derived from
the layout. They are reactive, so other objects can follow them:

```python
import kinemo as k


@k.scene
def derived(s: k.Scene):
    a = k.RoundedRect(w=2, h=1.2).place(at="left", margin=2)
    b = k.RoundedRect(w=2, h=1.2).place(at="right", margin=2)
    link = k.Arrow(start=a.edge("right"), end=b.edge("left"))
    marker = k.Dot(r=0.1, fill=k.YELLOW, x=a.right + 0.3, y=a.top)
    s.add(a, b, marker)
    s.play(k.draw(link))
    s.play(b.to_place(at="top-right", margin=1.2))         # the arrow follows
    s.play(a.to(scale=1.3))                                # the marker follows
    s.wait(0.5)
```

`obj.edge(anchor)` is the point of the object's box named by an anchor (`"right"`,
`"top-left"`...), in the parent's coordinates. Reading `a.width.now` gives the current value
during build. Animating or setting a derived prop is `K0303`: animate its source (position,
scale or size) instead.

## Angles

`k.Angle(a, vertex, b)` marks the angle at `vertex` between the rays toward `a` and `b` (the
smaller one) with an arc, a label or its measure; `k.RightAngle(a, vertex, b)` draws the square
mark. The points can be reactive, so the marker follows an angle that opens:

```python
import kinemo as k


@k.scene
def angle(s: k.Scene):
    deg = k.signal(20.0)
    origin = (-1.5, -1.0)
    tip = k.vec(-1.5 + 3 * k.cos(deg * k.pi / 180), -1 + 3 * k.sin(deg * k.pi / 180))
    s.add(k.Line(start=origin, end=(1.5, -1.0)), k.Line(start=origin, end=tip))
    theta = k.Angle((1.5, -1.0), origin, tip, r=0.8, label="θ", show_value=True)
    s.play(k.draw(theta))
    s.play(deg.to(120), duration=2)
    s.wait(0.5)
```

- `r=` is the arc's radius, `label=` a name beside it, `show_value=True` its measure
  (`unit="rad"` for radians); the label stays clear of the arc as the angle changes.
- Points are in world coordinates. A polygon's `vertices` are in its own coordinates; its
  `sides` (`side.start`, `side.end`) are in world coordinates, so mark a triangle's right angle
  with `k.RightAngle(legs[0].end, legs[0].start, legs[2].start)` where `legs = tri.sides`.

## Containers

Containers lay out their children and keep them laid out (flexbox and grid style):

```python
k.Row(a, b, c, gap=0.4, align="bottom")    # horizontal; align: center, top, bottom
k.Column(title, body, gap=0.2, align="left")  # vertical; align: center, left, right
k.Grid(*cards, cols=3, gap=0.3)
k.Stack(background, icon)                  # overlapping, centered (or align=)
```

Changing children through the container's transitions animates the reflow. `swap`,
`insert` and `pop` are sugar for `group.to(children=[...])`. Children that pass each other
travel on opposite arcs instead of through each other (`path="straight"` on any of them
keeps them on straight lines); an inserted child grows in while its neighbours make room,
and a popped one shrinks away in its slot:

```python
import kinemo as k


@k.scene
def reflow(s: k.Scene):
    a, b, c = k.Square(0.8), k.Circle(r=0.4), k.Triangle(scale=0.5)
    row = k.Row(a, b, c, gap=0.4).place(at="center")
    s.play(k.draw(row))
    s.play(row.swap(0, 2))                             # c, b, a
    s.play(row.to(children=[b, c, a]))                 # any order
    s.play(row.insert(1, k.Dot(r=0.2, fill=k.RED)))    # b, dot, c, a
    s.play(row.pop(0))                                 # dot, c, a
    s.wait(0.5)
```

Containers are groups: they are iterable and indexable, and **indices reflect the order at
the cursor**, already accounting for transitions scheduled earlier. That is what makes
algorithm animations read naturally:

```python
import kinemo as k


@k.scene
def bubble(s: k.Scene):
    row = k.Row(*[k.Bar(v, label=True) for v in [5, 2, 8, 1, 4]], gap=0.2, align="bottom").place(at="center")
    s.play(k.stagger([k.grow(b, from_="bottom") for b in row], lag=0.05))
    n = len(row)
    with s.tempo(2):
        for i in range(n):
            for j in range(n - 1 - i):
                a, b = row[j], row[j + 1]          # positions at the cursor
                if a.value.now > b.value.now:
                    s.play(row.swap(j, j + 1), duration=0.4)
            s.play(row[n - 1 - i].to(color=k.GREEN), duration=0.2)
```

`group.fit(area, margin=0.0)` scales a group once, at the cursor, so it fills an area as
far as its proportions allow: smaller groups grow, larger ones shrink. It sets `scale`, so
a later `.to(scale=...)` is absolute (`scale=0.9` is 0.9 of the original size, not of the
fitted one):

```python
import kinemo as k


@k.scene
def fit(s: k.Scene):
    cards = [k.RoundedRect(w=3, h=2) for _ in range(12)]
    grid = k.Grid(*cards, cols=4, gap=0.4).place(at="center").fit(s.frame.safe)
    s.play(k.stagger([k.draw(c) for c in cards], lag=0.05))
    s.play(grid.to(scale=grid.scale.now * 0.9))   # 90% of the fitted size
    s.wait(0.5)
```

A child's position belongs to its container, so `child.to(x=...)` is `K0401`; reorder
through the container instead.

## Groups

`k.Group(a, b, c)` groups objects without laying them out: children keep their own
positions, transforms compose (moving, scaling or rotating the group affects all of them),
and `opacity` multiplies.

```python
import kinemo as k


@k.scene
def group(s: k.Scene):
    sun = k.Circle(r=0.6, fill=k.YELLOW, fill_opacity=1)
    ray = k.Line(start=(0.8, 0), end=(1.4, 0), stroke=k.YELLOW)
    icon = k.Group(sun, ray).place(at="center")
    s.play(k.draw(icon))
    s.play(icon.to(scale=1.5, rotate=90))
    s.play(icon[0].to(fill=k.ORANGE))
```

Positions inside a group are local to it. An object has **exactly one parent**: adding it
to a second group is `K0103`.

## Cards

`k.Card(content, title=..., caption=..., accent=...)` puts content on a rounded panel sized to
it, with a title in the corner and a caption under it; cards in a `k.Row` compare things side by
side:
## Callouts and speech bubbles

`k.Callout(text, to=obj)` puts a box with text beside an object, with a tail pointing at it, and
keeps it there as the object moves:
## Arrays

`k.Array(values)` draws an array as cells with their indices, for algorithm videos: swap cells,
compare them, change a value and point at indices:

```python
import kinemo as k


@k.scene
def versus(s: k.Scene):
    before = k.Card(k.Text("O(n²)", size=0.6), title="Bubble sort", caption="compares every pair", accent=k.RED)
    after = k.Card(k.Text("O(n log n)", size=0.6), title="Merge sort", caption="splits, then merges", accent=k.GREEN)
    s.play(k.fade_in(k.Row(before, after, gap=1).place(at="center")))
    s.wait(0.5)
```

- `w=` and `h=` fix the panel's size; `pad=` is the space around the content, `radius=` the
  corners. The caption is dimmer than the title and keeps a readable contrast.
- The parts are addressable: `card.content`, `card.title`, `card.box`, `card.caption`,
  `card.accent` (`s.play(k.indicate(card.content))`).
def bubble(s: k.Scene):
    fox = k.Circle(r=0.6, fill=k.ORANGE, fill_opacity=1).place(at="center")
    s.add(fox)
    s.play(k.fade_in(k.Callout("Wait... the slope changes at every point?", to=fox, max_width=3)))
    s.play(fox.to(x=-2, unpin=True), duration=1.5)
    s.wait(0.5)
```

- `side=` is where the box goes (`top-right` by default, any corner or side), `gap=` how far.
- `style="bubble"` is a filled balloon with dark text, `"box"` an outlined box, `"line"` text
  with a leader line; `max_width=` wraps the text.
- The contrast lint judges the text against the bubble behind it, not the scene background.
def pass_one(s: k.Scene):
    arr = k.Array([5, 2, 9, 1]).place(at="center")
    s.play(k.fade_in(arr))
    for j in range(3):
        s.play(arr.pointer("j", j), duration=0.3)
        s.play(arr.compare(j, j + 1), duration=0.4)
        if int(arr.cells[j].value.text.now) > int(arr.cells[j + 1].value.text.now):
            s.play(arr.swap(j, j + 1), duration=0.5)
    s.wait(0.5)
```

- `arr.cells[i]` is the cell at index `i` at the cursor (after the swaps scheduled so far);
  each cell has `.box` and `.value`.
- `arr.pointer(name, i)` adds a labelled arrow under index `i` the first time and moves it
  afterwards; several pointers stack below each other and follow the array if it moves.

## Changing parents: `k.reparent`

`k.reparent(obj, new_parent)` moves an object to another group at the scheduled time. The
move is instant: outside a container the object keeps its world position; inside a
container it takes its place in the flow at once.

```python
import kinemo as k


@k.scene
def change_group(s: k.Scene):
    dot = k.Dot(r=0.25, fill=k.RED)
    left = k.Row(dot, k.Square(0.8), gap=0.3).place(at="left", margin=2)
    right = k.Row(k.Square(0.8), gap=0.3).place(at="right", margin=2)
    s.add(left, right)
    s.wait(0.5)
    s.play(k.reparent(dot, right))   # the dot jumps into the right row
    s.wait(0.5)
```

## Copies

`obj.copy()` creates a new identity with the same props. By default the copy **keeps the
original's bindings**: a prop bound to a signal or a lambda follows the same values in
both objects. Changes made later with `.to()` belong to the object they are made on.
`obj.copy(frozen=True)` copies the values at the cursor, with no bindings:

```python
import kinemo as k


@k.scene
def copies(s: k.Scene):
    angle = k.signal(0.0)
    original = k.Square(1.2, fill=k.TEAL, fill_opacity=0.5, rotate=angle).place(at="left", margin=3)
    s.play(k.draw(original))
    mirror = original.copy().place(at="center")
    snapshot = original.copy(frozen=True).place(at="right", margin=3)
    s.add(mirror, snapshot)
    s.play(angle.to(45), original.to(color=k.RED))   # the mirror turns too; the color is the original's own
    s.wait(0.5)
```

A component's `copy()` rebuilds it with the same arguments.

## Graphs

`k.Graph(nodes, edges, layout=...)` draws nodes (circles with their names) joined by edges,
for trees, searches and small networks. Edges are `(u, v)` pairs, or `(u, v, weight)` with
a label; `directed=True` draws arrows. The layout is `"force"`, `"tree"` (from `root=`),
`"layered"` (left to right) or `"circle"`, or a dict of positions:

```python
import kinemo as k


@k.scene
def search(s: k.Scene):
    g = k.Graph(["a", "b", "c", "d", "e"], [("a", "b"), ("a", "c"), ("b", "d"), ("c", "e")], layout="tree", width=7, height=4)
    s.play(k.draw(g))
    s.play(g.add_node("f", edges=[("c", "f")]))
    s.play(g.path(["a", "c", "f"]))
    s.play(g.relayout("circle"), duration=1.5)
```

- Edges follow their nodes, so moving a node (`g.node("a").to(x=2)`) or `g.relayout(...)`
  carries them along.
- `g.add_node(name, edges=...)` lays the graph out again with the new node; `at=(x, y)`
  puts it somewhere instead. `g.add_edge(u, v)` and `g.remove(name, (u, v))` change edges.

## Identity and keys

An object's identity is its Python identity: there are no string ids. `key=` is only needed
to match **different** objects, for example in a morph or across the scenes of a movie
(`k.Circle(key="sun")` with `k.morph_cut`). `name=` gives a readable name in diagnostics to
objects created without a direct assignment.

> **Common mistakes**
>
> | You see | Why | Fix |
> | --- | --- | --- |
> | `K0101 'c' is not in the scene yet` | `.to()` on an object that never entered. | `s.add(c)` or an entrance verb first. |
> | `K0102 'a' already left the scene at t = 2.00 s` | `.to()` after `s.remove` / `k.fade_out` / `k.shrink`. | Animate it before the exit, or bring it back with `k.fade_in(a)`. |
> | `K0103 'a' already belongs to 'g1'` | The same object passed to two groups or containers. | `a.copy()` for a second visual, `k.reparent(a, new_parent)` to move it. |
> | `K0401 'title' cannot animate x: the axis is held by a constraint` | `.to(x=...)` on an object positioned with `.place`. | `title.to_place(...)`, or `title.to(x=..., unpin=True)`. |
> | `K0401 ... held by the container 'row'` | Animating `x`/`y` of a container child. | Reorder through the container: `row.swap(i, j)`, `row.to(children=[...])`. |
> | `K0401 ... held by a reactive binding` | Animating a prop bound with `set(x=signal)`. | `obj.unbind("x")` first. |
> | `K0402 constraint cycle: a → b → a` | Objects placed relative to each other in a loop. | Anchor one of them to the frame (`at=`) or to a third object. |
> | `K0403 conflicting constraints on the same axis` | `left_of=` and `right_of=` (or `above=`/`below=`) in one `place`. | Keep one. |
> | `K0105 one relation per place call` | Two sides on different axes (`above=a, right_of=b`) in one `place`. | Use one relation plus `align=`, or a container. |
> | `K0404 unknown anchor` | A typo in `at=`, `align=`, `edge()` or `from_=`. | Use `center`, `top`, `bottom`, `left`, `right` or a combination like `top-left`. |
> | `K0303 ... is derived from the layout and is read-only` | `.set`/`.to` on `width`, `left`, `center`... | Animate the source: `scale`, `w`/`h`, position. |
> | `K0105 props are not assigned with '='` | `box.fill = k.RED`. | `box.set(fill=k.RED)` or `s.play(box.to(fill=k.RED))`. |
> | `K0106 Circle has no prop 'fil'` | Unknown prop name. | Follow the "did you mean 'fill'?" suggestion; when there is no close match, the message lists every prop of the type (`k.Circle` uses `r`, not `radius`). |
> | `W1001 ... leaves the safe area` | Part of an object is within 0.5 u of the frame edge. Objects entirely outside the frame (waiting to slide in) are not reported. | More `margin=`, smaller size, `clamp=True`, or `.fit(s.frame.safe)`. For an object cropped on purpose (a horizon, a planet), `bleed=True`. |
