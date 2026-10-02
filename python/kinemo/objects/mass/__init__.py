"""Mass objects: thousands of marks in one native object.

- `k.Points(xy, radius=, color=)` — dots; `radius`/`color` may be per point.
- `k.VectorField(fn, density=)` — arrows of `fn(x, y) -> (vx, vy)` on a grid.
- `k.StreamLines(field, seeds=)` — RK4 integral curves of a field.

Per-point functions are traced once with a symbolic point `p` (`p.x`, `p.y`,
`p.index`, `p.count`, `p.t`) and evaluated natively over all points; Python never runs
at render time. `k.python(fn, vectorized=True)` is the explicit escape hatch: `fn`
gets real numpy arrays once, at build time.
"""

from .points import Points
from .stream_lines import StreamLines
from .symbolic_point import SymbolicPoint
from .vector_field import VectorField

__all__ = ["Points", "StreamLines", "SymbolicPoint", "VectorField"]
