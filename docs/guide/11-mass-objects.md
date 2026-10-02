# Mass objects

A scatter plot of 10,000 samples, a particle cloud or a flow field would mean thousands of
Python objects if each point were a `k.Dot`. That makes the build slow, the scene graph
huge and the render needlessly expensive. kinemo has three *vectorized* types instead.
Each one is a **single object** that stores arrays and is drawn in batches by the native
core:

| Type | What it draws |
| --- | --- |
| `k.Points` | Many dots, with per-point radius and color |
| `k.VectorField` | Arrows of a field `(x, y) → (vx, vy)` on a grid, sized and colored by magnitude |
| `k.StreamLines` | Lines that follow a field, integrated with RK4 in the core |

They are ordinary objects. They enter with `k.draw`/`k.fade_in`, accept `.place`, `scale`,
`opacity` and `.to()`, and their props accept signals.

## `k.Points`

```python
k.Points(xy=None, radius=0.02, color=None, *, x=None, y=None, **props)
```

The coordinates can be:

- a numpy array of shape `(n, 2)`;
- a list of `(x, y)` pairs;
- two columns with `x=` and `y=` (Arrow columns from polars, pandas or pyarrow, numpy
  arrays or lists).

`k.draw(pts)` reveals the points in index order. `pts.count` (or `len(pts)`) is the number
of points.

```python
import numpy as np

import kinemo as k


@k.scene
def cloud(s: k.Scene):
    rng = np.random.default_rng(1)
    xy = rng.normal(0, 1.5, size=(8000, 2))
    pts = k.Points(
        xy,
        radius=lambda p: 0.015 + 0.02 * p.t,
        color=lambda t, p: k.mix(k.BLUE, k.RED, k.clamp((p.x + 3) / 6, 0, 1)),
    )
    s.play(k.draw(pts), duration=2)
    s.play(pts.to(scale=0.6), duration=1)
    s.wait(0.5)
```

Columns from a DataFrame go in directly, without copying:

```python
import polars as pl

import kinemo as k

STATIONS = pl.DataFrame({"lon": [-3.0, 0.0, 3.0, 1.5], "lat": [-1.0, 1.0, 0.0, -2.0]})


@k.scene
def stations(s: k.Scene):
    pts = k.Points(x=STATIONS["lon"], y=STATIONS["lat"], radius=0.12, color=k.YELLOW)
    s.play(k.draw(pts))
    s.wait(0.5)
```

### Moving the points

`xy` is a prop that interpolates point by point. `pts.to(xy=new)` with the same number of
points moves each point to its new position:

```python
import numpy as np

import kinemo as k


@k.scene
def regroup(s: k.Scene):
    rng = np.random.default_rng(3)
    scattered = rng.uniform((-6, -3), (6, 3), size=(2000, 2))
    angles = np.linspace(0, 2 * np.pi, 2000)
    circle = np.column_stack([2.5 * np.cos(angles), 2.5 * np.sin(angles)])
    pts = k.Points(scattered, radius=0.03, color=lambda p: k.mix(k.TEAL, k.PINK, p.t))
    s.play(k.fade_in(pts))
    s.play(pts.to(xy=circle), duration=2)
    s.wait(0.5)
```

## Per-point values

`radius` and `color` (and the color of fields) accept any of these forms:

| Form | Example | Evaluated |
| --- | --- | --- |
| One value or signal for every point | `radius=0.03`, `color=k.TEAL`, `radius=r_signal` | Natively |
| One value per point | `radius=np.array([...])`, `color=[k.RED, k.BLUE, ...]` | Stored as a list |
| A function of the symbolic point | `lambda p: 0.02 + 0.01 * p.t` | Traced once, then vectorized natively |
| A function of time and the point | `lambda t, p: k.sin(p.x - t)` | Traced once, re-evaluated every frame natively |
| `k.python(fn, vectorized=True)` | `fn(p)` receives numpy arrays | Called once, at build time |

The symbolic point `p` has:

| Attribute | Meaning |
| --- | --- |
| `p.x`, `p.y` | Coordinates |
| `p.xy` | The point as a vector |
| `p.index` | Position in the set (0-based) |
| `p.count` | Number of points |
| `p.t` | `index / (count - 1)`, from 0 to 1 |

Per-point functions follow the same tracing rules as lambdas and `.map`. Use `k` functions
(`k.sin`, `k.mix`, `k.where`, `k.clamp`), not `math.*`, `if` or the built-in
`min()`/`max()`. A function that cannot be traced is `K0310`.

With `lambda t, p:`, `t` is the scene time, so values can change continuously:

```python
import kinemo as k


@k.scene
def wave(s: k.Scene):
    pts = k.Points(
        [(x / 10 - 6, 0.0) for x in range(121)],
        radius=lambda t, p: 0.04 + 0.03 * k.sin(p.x * 2 - t * 4),
        color=k.TEAL,
    )
    s.add(pts)
    s.wait(3)
```

When the logic really needs numpy (or another library), compute it once with a
vectorized `k.python`. The function receives a point whose attributes are numpy arrays
and must return one value per point:

```python
import numpy as np

import kinemo as k


def bands(p) -> np.ndarray:
    return np.where(np.hypot(p.x, p.y) < 2, 0.05, 0.02)


@k.scene
def rings(s: k.Scene):
    xy = np.random.default_rng(0).uniform((-5, -3), (5, 3), size=(3000, 2))
    pts = k.Points(xy, radius=k.python(bands, vectorized=True), color=k.TEAL)
    s.play(k.fade_in(pts))
    s.wait(0.5)
```

A non-vectorized `k.python(fn)` cannot run per point (that would mean one Python call per
point per frame), and it is `K0310`.

## `k.VectorField`

```python
k.VectorField(fn, density=30, *, length=0.8, x_range=None, y_range=None, color=None)
```

Arrows of `fn` on a grid with `density` columns across the region (`x_range` × `y_range`,
default: the frame inset by 1 unit). The arrow length is `length` × cell size × |v| / max|v|,
and the color goes from the theme's accent to its secondary color by magnitude, unless you
pass `color=` (a value or a function of the point).

`fn` can be written in several ways. It is traced once and evaluated natively at every grid
point:

| Form | Example |
| --- | --- |
| Function of `x, y` | `lambda x, y: (-y, x)` |
| Function of time and position | `lambda t, x, y: (k.sin(t + y), 0.3)` |
| Function of the symbolic point | `lambda p: (-p.y, p.x)` |

```python
import kinemo as k


@k.scene
def colored(s: k.Scene):
    field = k.VectorField(
        lambda p: (-p.y, p.x),
        density=20,
        length=0.6,
        color=lambda p: k.mix(k.BLUE, k.YELLOW, k.clamp(p.x / 6 + 0.5, 0, 1)),
    )
    s.play(k.draw(field))
    s.wait(0.5)
```

## `k.StreamLines`

```python
k.StreamLines(field, seeds=200, *, step=0.05, steps=60, progress=1.0, tail=1.0, fade=0.0, x_range=None, y_range=None, color=None)
```

Lines that follow `field`, which is a `k.VectorField` or a function in any of the forms
above.

- **`seeds`** is a count (deterministic, well-spread points over the region) or the starting
  points (an `(n, 2)` array or a list).
- Each line advances `step` units per RK4 step, for at most `steps` steps, and stops at the
  region border or where the field vanishes.
- **`progress`** (0 to 1) draws the lines over time. **`tail`** is the fraction of each line
  visible behind its head, and the tail fades to **`fade`** opacity.

```python
import kinemo as k


@k.scene
def swirl(s: k.Scene):
    field = k.VectorField(lambda x, y: (-y, x - 0.3 * y), density=24, x_range=(-6, 6), y_range=(-3.5, 3.5))
    lines = k.StreamLines(field, seeds=150, progress=0.0, tail=0.4, fade=0.2)
    s.play(k.draw(field), duration=1.5)
    s.play(k.fade_in(lines), lines.to(progress=1), duration=3)
    s.wait(0.5)
```

In `s.play(k.fade_in(lines), lines.to(progress=1))`, put the entrance first. The
animations run in parallel, but a `.to()` listed before the verb that brings the object in
is checked first and fails with `K0101`.

Seeds given as points let you choose where the flow starts:

```python
import kinemo as k


@k.scene
def gusts(s: k.Scene):
    field = k.VectorField(lambda t, x, y: (1 + 0.5 * k.sin(t * 2 + y), 0.3 * k.cos(x - t)), density=20)
    seeds = [(-6.0, y / 2) for y in range(-6, 7)]
    lines = k.StreamLines(field, seeds=seeds, steps=120, progress=0.0, tail=0.3)
    s.add(field)
    s.play(k.fade_in(lines), lines.to(progress=1), duration=3)
    s.wait(1)
```

## `W0901`: too many individual objects

When one source line creates more than 1000 individual objects (a list comprehension of
`k.Dot`, or `ax.scatter` with thousands of points), lint `W0901` warns and suggests the
vectorized type:

```
W0901  1200 Dot objects created on this line: use a vectorized type   :6
       fix: k.Points(xy, radius=0.02, color=lambda p: ...)
```

The rewrite usually takes a few lines: collect the coordinates into an array (or two
columns) and move any per-object logic into a per-point function.

```python
# Before: W0901
dots = [k.Dot(r=0.02, x=(i % 50) * 0.2 - 5, y=(i // 50) * 0.2 - 2) for i in range(1200)]
s.add(*dots)

# After: one object
xy = [((i % 50) * 0.2 - 5, (i // 50) * 0.2 - 2) for i in range(1200)]
s.add(k.Points(xy, radius=0.02))
```

## Common mistakes

> | Diagnostic | What happened | Fix |
> | --- | --- | --- |
> | `W0901` | A loop created more than 1000 `k.Dot` (or other leaf objects) on one line. | `k.Points(xy, ...)`, `k.VectorField`, `k.StreamLines`. |
> | `K0310` | A per-point lambda uses `math.sin`, `if` or `min()`. | `k.sin`, `k.where`, `k.min`, or `k.python(fn, vectorized=True)` with numpy. |
> | `K0310` | `radius=k.python(fn)` without `vectorized=True`. | Add `vectorized=True`: `fn` then receives numpy arrays once, at build time. |
> | `K0310` | A vectorized `k.python` returned a different number of values than there are points. | Return one value per point (`np.where(...)` keeps the shape). |
> | `K1201` | Coordinates passed both as `xy` and as `x=`/`y=`, or only one of `x=`/`y=`. | Pass `xy`, or `x=` and `y=` together. |
> | `K0101` | `s.play(lines.to(progress=1), k.fade_in(lines))`: the `.to()` comes before the entrance. | Put the entrance first: `s.play(k.fade_in(lines), lines.to(progress=1))`. |

See also: [`k.Points`](../reference/objects.md#k-points),
[`k.VectorField`](../reference/objects.md#k-vectorfield),
[`k.StreamLines`](../reference/objects.md#k-streamlines),
[`k.python`](../reference/reactive.md#k-python), [Charts and data](10-charts-and-data.md).
