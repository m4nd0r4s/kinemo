"""Movies: several scenes composed into one output (`k.movie` and its transitions)."""

from __future__ import annotations

from ..entry import DocEntry

_MOVIE_EXAMPLE = '''
import kinemo as k

@k.scene
def intro(s: k.Scene):
    s.play(k.write(k.Text("Chapter 1").place(at="center")))

@k.scene
def body(s: k.Scene):
    s.play(k.draw(k.Circle(r=1.5).place(at="center")))

movie = k.movie([intro, body], transitions=[k.crossfade(0.5)])
'''

ENTRIES = (
    DocEntry(
        "k.movie",
        "Output",
        "Composes several scenes into a single output, with one transition per join (`k.cut` when "
        "omitted). `kinemo render` renders the movie as a single video.",
        _MOVIE_EXAMPLE,
        related=("k.crossfade", "k.cut", "k.morph_cut"),
    ),
    DocEntry(
        "k.cut",
        "Output",
        "Hard-cut transition between two scenes of a `k.movie` (the default).",
        '''
import kinemo as k

@k.scene
def before(s: k.Scene):
    s.play(k.write(k.Text("Before").place(at="center")))

@k.scene
def after(s: k.Scene):
    s.play(k.write(k.Text("After").place(at="center")))

movie = k.movie([before, after], transitions=[k.cut])
''',
        related=("k.movie", "k.crossfade"),
    ),
    DocEntry(
        "k.crossfade",
        "Output",
        "Transition in which the end of one scene dissolves into the start of the next, over "
        "`duration` seconds.",
        _MOVIE_EXAMPLE,
        related=("k.movie", "k.cut", "k.morph_cut"),
    ),
    DocEntry(
        "k.morph_cut",
        "Output",
        "Transition in which objects with the same `key=` in neighboring scenes travel across the cut.",
        '''
import kinemo as k

@k.scene
def one(s: k.Scene):
    s.play(k.draw(k.Circle(r=1, key="sun").place(at="left", margin=3)))

@k.scene
def two(s: k.Scene):
    s.play(k.draw(k.Circle(r=1, key="sun").place(at="right", margin=3)))

movie = k.movie([one, two], transitions=[k.morph_cut(0.8)])
''',
        related=("k.movie", "k.crossfade"),
    ),
)
