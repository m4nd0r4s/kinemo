"""Layout by constraints: `.place`, `.unpin`, containers and their named transitions."""

from __future__ import annotations

from ..entry import DocEntry

ENTRIES = (
    DocEntry(
        "Node.place",
        "Layout",
        "Declares where the object sits, relative to the frame (`at=\"top\"`, `margin=`) or to another "
        "object (`above=`, `below=`, `left_of=`, `right_of=`, `inside=` with `pad=`), with "
        "`gap=` (accepts a signal) and `align=`. The relation keeps holding while the objects "
        "move. Returns the object itself, so it chains with the constructor.",
        '''
import kinemo as k

@k.scene
def positions(s: k.Scene):
    box = k.Square(2).place(at="center")
    title = k.Text("Title").place(at="top", margin=0.6)
    label = k.Text("box", size=0.4).place(below=box, gap=0.3)
    s.add(box, title, label)
    s.play(box.to(scale=1.5))
''',
        related=("Node.to_place", "Node.unpin", "k.Row", "Node.to"),
        signature="obj.place(at=, above=, below=, left_of=, right_of=, inside=, gap=, margin=, align=, pad=, clamp=False, weak=False)",
    ),
    DocEntry(
        "Node.to_place",
        "Layout",
        "Animated change of placement: the `.to` of `.place`. Takes the same keywords as "
        "`.place(...)` plus `duration=`, `ease=` and `delay=`, and moves the object from its current "
        "placement to the new one. The new constraint keeps holding afterwards.",
        '''
import kinemo as k

@k.scene
def replace(s: k.Scene):
    tri = k.Triangle().place(at="center")
    title = k.Text("title", size=0.5).place(above=tri, gap=0.4)
    s.add(tri, title)
    s.play(title.to_place(right_of=tri, gap=0.4))
    s.play(tri.to_place(at="left", margin=2))   # the title follows
''',
        related=("Node.place", "Node.unpin", "Node.to"),
        signature="obj.to_place(at=, above=, below=, left_of=, right_of=, inside=, gap=, margin=, align=, pad=, clamp=False, weak=False, duration=None, ease=None, delay=0.0)",
    ),
    DocEntry(
        "Node.unpin",
        "Layout",
        "Releases the position constraint at the cursor: the object keeps its current position and "
        "is free to animate `x`/`y`. Inside an animation, `obj.to(x=..., unpin=True)` does the same "
        "where the animation starts. To switch constraints instead, use `obj.to_place(...)`.",
        '''
import kinemo as k

@k.scene
def release(s: k.Scene):
    tri = k.Triangle().place(at="center")
    title = k.Text("free").place(above=tri, gap=0.4)
    s.add(tri, title)
    s.play(title.to(x=3, unpin=True))
    title.unpin()  # the instant form, at the cursor
''',
        related=("Node.place", "Node.to_place", "Node.to"),
    ),
    DocEntry(
        "k.Row",
        "Layout",
        "Container that lays its children out in a row (flexbox), with `gap=` and `align=` "
        "(`\"center\"`, `\"top\"`, `\"bottom\"`). Changing children with the container's transitions "
        "(`row.swap`, `row.insert`, `row.pop`) animates the reflow.",
        '''
import kinemo as k

@k.scene
def row(s: k.Scene):
    items = [k.Square(0.8) for _ in range(4)]
    r = k.Row(*items, gap=0.4).place(at="center")
    s.play(k.draw(r))
    s.play(r.swap(0, 3))
''',
        related=("k.Column", "k.Grid", "Group.swap"),
    ),
    DocEntry(
        "k.Column",
        "Layout",
        "Container that stacks its children in a column, with `gap=` and `align=` (`\"center\"`, "
        "`\"left\"`, `\"right\"`).",
        '''
import kinemo as k

@k.scene
def column(s: k.Scene):
    title = k.Text("Steps", size=0.7)
    steps = [k.Text(t, size=0.45) for t in ("1. measure", "2. compare", "3. decide")]
    col = k.Column(title, *steps, gap=0.3, align="left").place(at="center")
    s.play(k.write(col))
    s.wait(0.5)
''',
        related=("k.Row", "k.Grid"),
    ),
    DocEntry(
        "k.Grid",
        "Layout",
        "Grid container with `cols=` columns and `gap=`. Combine with `.fit(s.frame.safe)` "
        "to scale it down until it fits the frame.",
        '''
import kinemo as k

@k.scene
def grid(s: k.Scene):
    cards = [k.RoundedRect(w=1.6, h=1) for _ in range(6)]
    g = k.Grid(*cards, cols=3, gap=0.3).place(at="center")
    s.play(k.stagger([k.draw(c) for c in cards], lag=0.1))
    s.wait(0.5)
''',
        related=("k.Row", "Group.fit"),
    ),
    DocEntry(
        "k.Stack",
        "Layout",
        "Container that overlays its children, centered (or aligned by `align=`). Good for "
        "icons over backgrounds.",
        '''
import kinemo as k

@k.scene
def stack(s: k.Scene):
    background = k.Circle(r=1.2, fill=k.BLUE, fill_opacity=0.3)
    icon = k.Text("42", size=0.9)
    badge = k.Stack(background, icon).place(at="center")
    s.play(k.fade_in(badge))
    s.wait(0.5)
''',
        related=("k.Group", "k.Row"),
    ),
    DocEntry(
        "Group.fit",
        "Layout",
        "Scales the group once, at the cursor, until it fits an area (usually "
        "`s.frame.safe`, the frame's safe area), with an optional `margin=`.",
        '''
import kinemo as k

@k.scene
def fit(s: k.Scene):
    cards = [k.RoundedRect(w=3, h=2) for _ in range(12)]
    grid = k.Grid(*cards, cols=4, gap=0.4).place(at="center").fit(s.frame.safe)
    s.play(k.draw(grid))
    s.wait(0.5)
''',
        related=("k.Grid",),
    ),
    DocEntry(
        "Group.swap",
        "Layout",
        "Named transition: swaps the places of two children and the container animates the reflow. "
        "Equivalent to `group.to(children=[...])` with `i` and `j` swapped. Children that pass each "
        "other travel on opposite arcs; `path=\"straight\"` moves them in straight lines (calmer "
        "for bar-like rows at high tempo).",
        '''
import kinemo as k

@k.scene
def swap(s: k.Scene):
    bars = [k.Bar(v, label=True) for v in [4, 1, 3]]
    row = k.Row(*bars, gap=0.3, align="bottom").place(at="center")
    s.add(row)
    s.play(row.swap(0, 1), duration=0.6)
    s.play(row.swap(1, 2), duration=0.6)
''',
        related=("Group.insert", "Group.pop", "k.Row"),
    ),
    DocEntry(
        "Group.insert",
        "Layout",
        "Named transition: inserts a child at position `i`; it enters together with the reflow. "
        "Equivalent to `group.to(children=[...])`.",
        '''
import kinemo as k

@k.scene
def insert(s: k.Scene):
    row = k.Row(k.Square(0.8), k.Square(0.8), gap=0.4).place(at="center")
    s.add(row)
    s.play(row.insert(1, k.Circle(r=0.4, fill=k.RED, fill_opacity=1)))
    s.wait(0.5)
''',
        related=("Group.pop", "Group.swap"),
    ),
    DocEntry(
        "Group.pop",
        "Layout",
        "Named transition: removes the child at position `i` (default: the last one); it exits "
        "together with the reflow. Equivalent to `group.to(children=[...])`.",
        '''
import kinemo as k

@k.scene
def remove(s: k.Scene):
    row = k.Row(*[k.Square(0.8) for _ in range(4)], gap=0.4).place(at="center")
    s.add(row)
    s.play(row.pop(0))
    s.wait(0.5)
''',
        related=("Group.insert", "Group.swap"),
    ),
)
