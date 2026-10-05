"""Objects and their state: shapes, `k.Text`, `k.Bar`, `k.Group`, `.to`/`.set`/`.copy`."""

from __future__ import annotations

from ..entry import DocEntry

ENTRIES = (
    DocEntry(
        "k.StyleKeywords",
        "Object state",
        "The keyword arguments of shapes and text, as types, to reuse a style with `**` and keep it "
        "checked: `k.PaintKeywords` (`fill`, `fill_opacity`, `stroke`, `stroke_width`, `dash`), "
        "`k.ColorKeywords` (`color`), `k.TransformKeywords` (position, rotation, scale, opacity, "
        "visibility), `k.StyleKeywords` (all of those), and `k.TextKeywords`, `k.RectKeywords`, "
        "`k.ArrowKeywords` for the keywords those objects add. A plain `dict(...)` loses the types: "
        "annotate the style instead.",
        '''
import kinemo as k

dashed: k.PaintKeywords = {"stroke": k.GRAY, "dash": (8, 8)}
note: k.TextKeywords = {"color": k.YELLOW, "mono": True}

@k.scene
def styles(s: k.Scene):
    s.add(k.Line(start=(-3, 0), end=(3, 0), **dashed), k.Circle(r=1, **dashed))
    s.add(k.Text("same dash, typed", size=0.4, **note).place(at="top", margin=1))
    s.wait(0.5)
''',
        related=("Node.to", "k.Text"),
    ),
    DocEntry(
        "k.Card",
        "Objects",
        "A panel around `content` (sized to it, or `w=`, `h=`): `title=` in its top-left corner, "
        "`caption=` under it, `accent=` a color bar beside the title; `pad=`, `radius=`. Cards line up "
        "in a `k.Row` for side-by-side comparisons. Parts: `card.box`, `card.content`, `card.title`, "
        "`card.caption`, `card.accent`.",
        '''
import kinemo as k

@k.scene
def compare(s: k.Scene):
    rocket = k.Card(k.Triangle.right(2, 2, scale=0.6), title="Rocket", caption="pushes the gas down", accent=k.ORANGE)
    gas = k.Card(k.Circle(r=0.6, fill=k.BLUE, fill_opacity=0.6), title="Gas", caption="pushes the rocket up", accent=k.BLUE)
    s.play(k.fade_in(k.Row(rocket, gas, gap=1).place(at="center")))
    s.play(k.indicate(gas.content))
    s.wait(0.5)
''',
        related=("k.Row", "k.RoundedRect"),
    ),
    DocEntry(
        "Node.to",
        "Object state",
        "Animated state change: interpolates each prop from its value at the cursor to the target. "
        "Accepts any public prop (`x`, `y`, `scale`, `rotate`, `color`, `opacity`...) plus "
        "`duration=`, `ease=`, `delay=`, `blend=\"add\"`, and `unpin=True` to release a `.place` "
        "constraint where the animation starts (to switch constraints instead, use "
        "`obj.to_place(...)`). Colors interpolate in OKLab.",
        '''
import kinemo as k

@k.scene
def state(s: k.Scene):
    square = k.Square(1.5).place(at="center")
    s.play(k.draw(square))
    s.play(square.to(color=k.RED, rotate=45, scale=1.5), duration=1.5)
    s.wait(0.5)
''',
        related=("Node.set", "Animation.with_", "Scene.during"),
    ),
    DocEntry(
        "Node.set",
        "Object state",
        "Instant change at the cursor. Passing a signal or a lambda creates a reactive binding "
        "from the cursor on (there are no updaters); `obj.unbind(\"x\")` removes the binding.",
        '''
import kinemo as k

@k.scene
def binding(s: k.Scene):
    leader = k.Dot(r=0.25, x=-4, y=1)
    follower = k.Dot(r=0.15, fill=k.RED)
    s.add(leader, follower)
    follower.set(x=leader.x, y=leader.y - 2)
    s.play(leader.to(x=4), duration=2)
''',
        related=("Node.to", "Node.unbind", "k.signal"),
    ),
    DocEntry(
        "Node.unbind",
        "Object state",
        "Removes reactive bindings (all props when no name is given), keeping the current "
        "value. Required before animating a bound prop (error K0401).",
        '''
import kinemo as k

@k.scene
def unbind(s: k.Scene):
    a = k.Dot(r=0.25, x=-3)
    b = k.Dot(r=0.25, x=-3, y=-1, fill=k.RED)
    s.add(a, b)
    b.set(x=a.x)
    s.play(a.to(x=3))
    b.unbind("x")
    s.play(b.to(x=-3))
''',
        related=("Node.set", "Node.unpin"),
    ),
    DocEntry(
        "Node.copy",
        "Object state",
        "Creates a new identity with the same props. By default the copy follows the original's "
        "reactive bindings; `frozen=True` copies only the values at the cursor. Use it to show "
        "the same visual in two places (an object has a single parent).",
        '''
import kinemo as k

@k.scene
def copy(s: k.Scene):
    original = k.Circle(r=0.8, fill=k.TEAL, fill_opacity=0.5).place(at="left", margin=3)
    s.play(k.draw(original))
    twin = original.copy(frozen=True).place(at="right", margin=3)
    s.play(k.fade_in(twin))
''',
        related=("k.Group", "k.reparent"),
    ),
    DocEntry(
        "k.reparent",
        "Object state",
        "Moves an object to another group at the scheduled time, keeping its world position "
        "(inside a container, it takes its place in the flow). This is how you change parents: "
        "an object has exactly one (error K0103).",
        '''
import kinemo as k

@k.scene
def change_group(s: k.Scene):
    dot = k.Dot(r=0.25)
    left = k.Row(dot, k.Square(0.8), gap=0.3).place(at="left", margin=2)
    right = k.Row(k.Square(0.8), gap=0.3).place(at="right", margin=2)
    s.add(left, right)
    s.play(k.reparent(dot, right))
    s.wait(0.5)
''',
        related=("Node.copy", "k.Group", "k.Row"),
    ),
    DocEntry(
        "k.Circle",
        "Objects",
        "Circle of radius `r`, centered on its position. Like every shape, it accepts the style "
        "props `color` (shorthand for stroke and fill), `fill`, `fill_opacity`, `stroke`, "
        "`stroke_width`, `dash` and the transform props.",
        '''
import kinemo as k

@k.scene
def circle(s: k.Scene):
    c = k.Circle(r=1.2, stroke=k.BLUE, fill=k.BLUE, fill_opacity=0.3).place(at="center")
    s.play(k.draw(c))
    s.play(c.to(r=2))
''',
        related=("k.Dot", "k.Ellipse", "k.Arc"),
    ),
    DocEntry(
        "k.Dot",
        "Objects",
        "Filled dot (default radius 0.08), with no stroke. It is the marker used in charts and "
        "for points that follow curves.",
        '''
import kinemo as k

@k.scene
def dots(s: k.Scene):
    a = k.Dot(r=0.15, fill=k.RED).place(at="center")
    label = k.Text("P").place(above=a, gap=0.2)
    s.play(k.fade_in(a, label))
    s.wait(0.5)
''',
        related=("k.Circle", "Plot.point_at"),
    ),
    DocEntry(
        "k.Ellipse",
        "Objects",
        "Ellipse of width `w` and height `h`, centered on its position.",
        '''
import kinemo as k

@k.scene
def ellipse(s: k.Scene):
    e = k.Ellipse(w=4, h=2, stroke=k.PURPLE).place(at="center")
    s.play(k.draw(e))
    s.play(e.to(w=2, h=3))
''',
        related=("k.Circle",),
    ),
    DocEntry(
        "k.Rect",
        "Objects",
        "Rectangle of width `w` and height `h`, centered on its position; `radius=` rounds the "
        "corners (for rounded corners prefer `k.RoundedRect`).",
        '''
import kinemo as k

@k.scene
def rectangle(s: k.Scene):
    r = k.Rect(w=4, h=2, fill=k.GREEN, fill_opacity=0.3).place(at="center")
    s.play(k.draw(r))
    s.play(r.to(w=6))
''',
        related=("k.RoundedRect", "k.Square"),
    ),
    DocEntry(
        "k.RoundedRect",
        "Objects",
        "Rectangle with rounded corners (`radius=0.15` by default). Good for boxes and cards "
        "with text inside.",
        '''
import kinemo as k

@k.scene
def card(s: k.Scene):
    box = k.RoundedRect(w=4, h=2.4, radius=0.3).place(at="center")
    title = k.Text("Card").place(inside=box, align="top", pad=0.3)
    s.play(k.draw(box), k.write(title))
    s.wait(0.5)
''',
        related=("k.Rect", "Node.place"),
    ),
    DocEntry(
        "k.Square",
        "Objects",
        "Square with side `side`, centered on its position. It is a `k.Rect` with `w == h`.",
        '''
import kinemo as k

@k.scene
def square(s: k.Scene):
    sq = k.Square(2, fill=k.YELLOW, fill_opacity=0.4).place(at="center")
    s.play(k.draw(sq))
    s.play(sq.to(rotate=90))
''',
        related=("k.Rect",),
    ),
    DocEntry(
        "k.Polygon",
        "Objects",
        "Polygon from its vertices (`k.Polygon((0, 0), (2, 0), (1, 1))`), centered on its "
        "bounding box. `k.Polygon.regular(n, r=)` creates the regular n-sided polygon.",
        '''
import kinemo as k

@k.scene
def hexagon(s: k.Scene):
    hex_ = k.Polygon.regular(6, r=1.5).place(at="center")
    s.play(k.draw(hex_))
    s.play(hex_.to(rotate=30))
''',
        related=("k.Triangle", "k.Path"),
    ),
    DocEntry(
        "k.Triangle",
        "Objects",
        "Triangle from its three vertices (no arguments: equilateral with radius 1). "
        "`k.Triangle.right(a, b, scale=)` creates the right triangle with legs `a` and `b`.",
        '''
import kinemo as k

@k.scene
def triangle(s: k.Scene):
    tri = k.Triangle.right(3, 4, scale=0.6).place(at="center")
    s.play(k.draw(tri))
    s.wait(0.5)
''',
        related=("k.Polygon",),
    ),
    DocEntry(
        "k.Line",
        "Objects",
        "Segment from `start` to `end` (local coordinates), or centered with `length=`. The "
        "endpoints accept signals, which makes the line follow other objects.",
        '''
import kinemo as k

@k.scene
def line(s: k.Scene):
    floor = k.Line(length=10).place(at="bottom", margin=1.5)
    ray = k.Line(start=(0, 0), end=(2, 1), stroke=k.BLUE)
    s.play(k.draw(floor), k.draw(ray))
    s.wait(0.5)
''',
        related=("k.Arrow", "k.Path"),
    ),
    DocEntry(
        "k.Arrow",
        "Objects",
        "Arrow from `start` to `end` with a tip of size `tip`. The endpoints accept signals.",
        '''
import kinemo as k

@k.scene
def arrow(s: k.Scene):
    a = k.Text("A").place(at="left", margin=3)
    b = k.Text("B").place(at="right", margin=3)
    link = k.Arrow(start=(-3.5, 0), end=(3.5, 0), stroke=k.YELLOW, fill=k.YELLOW)
    s.add(a, b)
    s.play(k.draw(link))
''',
        related=("k.Line",),
    ),
    DocEntry(
        "k.Arc",
        "Objects",
        "Circular arc of radius `r`, starting at `start_angle` and sweeping `angle` degrees "
        "(counterclockwise).",
        '''
import kinemo as k

@k.scene
def arc(s: k.Scene):
    sweep = k.Arc(r=1.5, start_angle=0, angle=270, stroke=k.ORANGE).place(at="center")
    s.play(k.draw(sweep))
    s.play(sweep.to(angle=360))
''',
        related=("k.Circle",),
    ),
    DocEntry(
        "k.Path",
        "Objects",
        "Path from SVG commands (`d=\"M 0 0 L 1 1\"`) or a polyline from a list of points; "
        "`closed=True` closes the outline.",
        '''
import kinemo as k

@k.scene
def path(s: k.Scene):
    zigzag = k.Path([(-3, 0), (-1, 1), (1, -1), (3, 0)], stroke=k.TEAL).place(at="center")
    s.play(k.draw(zigzag), duration=1.5)
    s.wait(0.5)
''',
        related=("k.Polygon", "k.follow"),
    ),
    DocEntry(
        "k.union",
        "Objects",
        "Boolean operations between shapes: `k.union(a, b)`, `k.intersect(a, b)` and "
        "`k.subtract(a, b)` return a new `k.Path` computed from the outlines at the cursor (with "
        "the style of `a`, unless another one is passed).",
        '''
import kinemo as k

@k.scene
def moon(s: k.Scene):
    disk = k.Circle(1.5, fill=k.YELLOW, fill_opacity=1, stroke_width=0)
    shadow = k.Circle(1.3, x=0.8)
    crescent = k.subtract(disk, shadow)
    s.play(k.draw(crescent))
''',
        related=("k.Path", "k.Circle"),
        aliases=("k.intersect", "k.subtract"),
    ),
    DocEntry(
        "k.Text",
        "Text",
        "Text with minimal inline markup (`**bold**`, `*italic*`, `` `code` ``). "
        "`size=` sets the size, `width=` wraps lines, `align=` aligns. With a lambda the "
        "text is reactive: `k.Text(lambda: f\"{x():.1f} kWh\")`.",
        '''
import kinemo as k

@k.scene
def text(s: k.Scene):
    x = k.signal(0.0)
    title = k.Text("**Solar** energy", size=0.7).place(at="top", margin=0.8)
    value = k.Text(lambda: f"{x():.1f} kWh").place(at="center")
    s.play(k.write(title), k.fade_in(value))
    s.play(x.to(12), duration=2)
''',
        related=("k.write", "k.signal"),
    ),
    DocEntry(
        "k.Bar",
        "Objects",
        "A value shown as a bar that grows from its base, with an optional label "
        "(`label=True`). `bar.value` is a signal: animating it changes the height and the label. "
        "Used in algorithms and charts.",
        '''
import kinemo as k

@k.scene
def bar(s: k.Scene):
    b = k.Bar(3, label=True).place(at="center")
    s.play(k.grow(b, from_="bottom"))
    s.play(b.to(value=7))
    s.wait(0.5)
''',
        related=("k.grow", "k.Row", "Group.swap"),
    ),
    DocEntry(
        "k.Group",
        "Objects",
        "Groups objects: transforms compose and opacity multiplies. An object has exactly one "
        "parent. Groups are iterable and indexable (`g[0]`), with indices at the cursor.",
        '''
import kinemo as k

@k.scene
def group(s: k.Scene):
    sun = k.Circle(r=0.6, fill=k.YELLOW, fill_opacity=1)
    ray = k.Line(start=(0.8, 0), end=(1.4, 0), stroke=k.YELLOW)
    icon = k.Group(sun, ray).place(at="center")
    s.play(k.draw(icon))
    s.play(icon.to(scale=1.5, rotate=90))
''',
        related=("k.Row", "k.Stack", "k.Component"),
    ),
)
