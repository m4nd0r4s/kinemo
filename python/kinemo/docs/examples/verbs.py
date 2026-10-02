"""Verbs: module functions that animate (`k.draw`, `k.write`, `k.fade_in`, ...)."""

from __future__ import annotations

from ..entry import DocEntry

ENTRIES = (
    DocEntry(
        "k.draw",
        "Verbs",
        "Entrance verb: traces the outline and then fills it. The object enters the scene at the start "
        "of the animation. If the object is a component with `enter()`, the verb uses that implementation.",
        '''
import kinemo as k

@k.scene
def drawing(s: k.Scene):
    circle = k.Circle(r=1.5, fill=k.BLUE, fill_opacity=0.4).place(at="center")
    s.play(k.draw(circle))
    s.wait(0.5)
''',
        related=("k.write", "k.fade_in", "k.grow"),
    ),
    DocEntry(
        "k.write",
        "Verbs",
        "Entrance verb: writes the text character by character. Other objects passed to "
        "`k.write` are drawn as with `k.draw`.",
        '''
import kinemo as k

@k.scene
def writing(s: k.Scene):
    title = k.Text("Hello, kinemo", size=0.8).place(at="center")
    s.play(k.write(title), duration=1.5)
    s.wait(0.5)
''',
        related=("k.Text", "k.draw", "k.fade_in"),
    ),
    DocEntry(
        "k.fade_in",
        "Verbs",
        "Entrance verb: opacity from 0 to 1. Accepts multiple objects; `shift=(dx, dy)` makes "
        "each object arrive from an offset of `-shift` to its final position.",
        '''
import kinemo as k

@k.scene
def appear(s: k.Scene):
    a = k.Square(1.2).place(at="center")
    label = k.Text("square").place(below=a, gap=0.3)
    s.play(k.fade_in(a, label, shift=(0, 0.5)))
    s.wait(0.5)
''',
        related=("k.fade_out", "k.draw"),
    ),
    DocEntry(
        "k.fade_out",
        "Verbs",
        "Exit verb: opacity from 1 to 0, and then the objects leave the scene. Accepts multiple "
        "objects and `shift=` to exit with an offset.",
        '''
import kinemo as k

@k.scene
def vanish(s: k.Scene):
    title = k.Text("See you soon").place(at="center")
    s.play(k.write(title))
    s.play(k.fade_out(title, shift=(0, 0.5)))
''',
        related=("k.fade_in", "k.shrink", "Scene.remove"),
    ),
    DocEntry(
        "k.grow",
        "Verbs",
        "Entrance verb: scales up from the center (default) or from a side (`from_=\"bottom\"`, "
        "`\"left\"`, `\"top-left\"`...). It is the natural entrance for bars and boxes.",
        '''
import kinemo as k

@k.scene
def grow(s: k.Scene):
    bar = k.Bar(6, label=True).place(at="center")
    s.play(k.grow(bar, from_="bottom"))
    s.wait(0.5)
''',
        related=("k.shrink", "k.Bar", "k.stagger"),
    ),
    DocEntry(
        "k.shrink",
        "Verbs",
        "Exit verb: the inverse of `k.grow`. Shrinks toward the center (default) or toward a "
        "side (`to=\"bottom\"`) and takes the object out of the scene.",
        '''
import kinemo as k

@k.scene
def shrink(s: k.Scene):
    box = k.RoundedRect(w=3, h=2).place(at="center")
    s.play(k.draw(box))
    s.play(k.shrink(box, to="bottom"))
''',
        related=("k.grow", "k.fade_out"),
    ),
    DocEntry(
        "k.indicate",
        "Verbs",
        "Emphasis: temporarily tints and pulses the object; the final state equals the initial one. "
        "It is reversible, so it also works inside `s.during`.",
        '''
import kinemo as k

@k.scene
def emphasis(s: k.Scene):
    word = k.Text("important", size=0.8).place(at="center")
    s.play(k.write(word))
    s.play(k.indicate(word, color=k.YELLOW, scale=1.3))
    s.wait(0.5)
''',
        related=("k.flash", "k.squash", "Scene.during"),
    ),
    DocEntry(
        "k.flash",
        "Verbs",
        "Emphasis: a ring of light that expands from the object's edge and fades away. It does not "
        "change the object.",
        '''
import kinemo as k

@k.scene
def pulse(s: k.Scene):
    dot = k.Dot(r=0.3).place(at="center")
    s.add(dot)
    s.play(k.flash(dot, color=k.YELLOW))
    s.wait(0.5)
''',
        related=("k.indicate", "k.when"),
    ),
    DocEntry(
        "k.squash",
        "Verbs",
        "Emphasis: an elastic squash against the object's base; `amount=` controls the intensity. "
        "The state returns to the initial one. Good for impacts.",
        '''
import kinemo as k

@k.scene
def impact(s: k.Scene):
    ball = k.Circle(r=0.6, fill=k.ORANGE, fill_opacity=1).place(at="center")
    s.add(ball)
    s.play(k.squash(ball, amount=0.4))
    s.wait(0.5)
''',
        related=("k.indicate", "k.simulate"),
    ),
    DocEntry(
        "k.follow",
        "Verbs",
        "Motion: the object travels along a path (the outline of another object or a list of "
        "points, in world coordinates). `rotate=True` aligns the object with the tangent.",
        '''
import kinemo as k

@k.scene
def orbit(s: k.Scene):
    track = k.Circle(r=2.5, stroke=k.GRAY).place(at="center")
    planet = k.Dot(r=0.2, fill=k.BLUE)
    s.add(track, planet)
    s.play(k.follow(planet, track), duration=3, ease=k.ease.linear)
''',
        related=("k.trace", "k.Path"),
    ),
    DocEntry(
        "k.sound",
        "Verbs",
        "Audio: plays a sound file at the moment it is scheduled (zero duration in the "
        "script). `gain=` adjusts the volume. For narration, use `s.voice`.",
        '''
import kinemo as k

@k.scene
def click(s: k.Scene):
    button = k.RoundedRect(w=2, h=0.8).place(at="center")
    s.play(k.draw(button))
    s.play(k.sound("click.wav", gain=0.8), k.indicate(button))
''',
        related=("Scene.voice",),
        assets=("click.wav",),
    ),
)
