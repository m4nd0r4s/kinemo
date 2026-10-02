"""Mass objects: `k.Points`, `k.VectorField`, `k.StreamLines`."""

from __future__ import annotations

from ..entry import DocEntry

ENTRIES = (
    DocEntry(
        "k.Points",
        "Objects",
        "Thousands of points in a single object, batch-drawn in the core. `xy` is a numpy array "
        "`(n, 2)`, a list of `(x, y)` or columns (`x=`, `y=`). `radius` and `color` accept one "
        "value, one per point, or a function of the symbolic point `p` (`p.x`, `p.y`, `p.index`, "
        "`p.t`), traced and vectorized in Rust. Never create thousands of `k.Dot` in a loop (W0901).",
        '''
import numpy as np
import kinemo as k

@k.scene
def cloud(s: k.Scene):
    xy = np.random.default_rng(1).uniform((-6, -3), (6, 3), size=(5000, 2))
    pts = k.Points(xy, radius=0.03, color=lambda t, p: k.mix(k.BLUE, k.RED, (p.x + 6) / 12))
    s.play(k.draw(pts), duration=2)
''',
        related=("k.VectorField", "k.StreamLines", "k.python"),
    ),
    DocEntry(
        "k.VectorField",
        "Objects",
        "Arrows of a field `fn(x, y) -> (vx, vy)` on a grid with `density` columns across the width "
        "of the region (`x_range`, `y_range`). Size and color (theme accent → secondary) follow the "
        "magnitude; `length` scales the arrows. `fn` is traced once and may use `k.time`.",
        '''
import kinemo as k

@k.scene
def rotation(s: k.Scene):
    field = k.VectorField(lambda x, y: (-y, x), density=24)
    s.play(k.draw(field), duration=2)
''',
        related=("k.StreamLines", "k.Points"),
    ),
    DocEntry(
        "k.StreamLines",
        "Objects",
        "Streamlines of a field (a `k.VectorField` or a function), integrated with RK4 in the "
        "core from `seeds` (a count or points). `progress` draws the lines over time; `tail` is "
        "the visible fraction behind the head and `fade` the opacity of the tail.",
        '''
import kinemo as k

@k.scene
def stream(s: k.Scene):
    field = k.VectorField(lambda x, y: (-y, x), density=24)
    lines = k.StreamLines(field, seeds=150, progress=0.0, tail=0.5)
    s.add(field)
    s.play(k.fade_in(lines), lines.to(progress=1), duration=3)
''',
        related=("k.VectorField",),
    ),
)
