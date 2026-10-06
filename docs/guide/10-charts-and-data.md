# Charts and data

kinemo has two levels of charts:

- **Axes and functions** (`k.Axes`, `k.NumberLine`, `k.PolarAxes`) for explanations: a curve
  that grows while a signal advances, a dot that slides along it, a tangent that turns, an
  animated zoom.
- **Data charts** (`k.BarChart`, `k.LineChart`, `k.Table`) for tables: you pass a DataFrame
  and `chart.to(data=df2)` animates the change.

Both are ordinary components. You place them with `.place`, enter them with `k.draw`, and
every part is an object.

Data comes in through Apache Arrow: polars, pandas (2.2 or later), pyarrow and duckdb
objects are read without copying, and dicts of lists or lists of dicts work for small
cases. kinemo does not import any of these libraries itself.

## Axes

```python signature
k.Axes(x=(0, 10), y=(0, 5), *, labels=None, grid=False, width=8.0, height=4.5, tick_labels=True)
```

- `x=(min, max, step)` and `y=(min, max, step)` give the visible ranges and the tick step
  (the step is optional).
- `labels=("x", "y")` names the axes; `grid=True` adds grid lines.
- `width=`/`height=` are the size in scene units (the frame is 16 × 9).
- `x_ticks=[4, 9, 16]`/`y_ticks=` set tick values by hand; `tick_format="{:.1f}"` (or a
  function from value to text) writes the labels.

The visible ranges are signals. `ax.zoom_to(x=(a, b), y=(c, d))` animates them, and every
curve, tick and marker on the axes follows. Ticks are regenerated for the new ranges with a
nice step, so a zoom from `(0, 10)` to `(0, 1)` shows `0, 0.2, …, 1`. It is a named
transition, equivalent to `ax.to(x_range=..., y_range=...)` plus the tick change.

Your own markers can live in the axes too. `ax.add(obj, enter_with_axes=True)` adopts them
in the axes' coordinates, so `k.Dot(position=ax.local_point(4, 8))` follows zooms like a
plot does. `ax.origin()` is where the axes cross, and `ax.in_view(x=8)` is a reactive bool
for `visible=` that hides a marker when a zoom leaves its value out.

Your own markers can live in the axes too. `ax.add(obj, enter_with_axes=True)` adopts them
in the axes' coordinates, so `k.Dot(position=ax.local_point(4, 8))` follows zooms like a
plot does. `ax.origin()` is where the axes cross, and `ax.in_view(x=8)` is a reactive bool
for `visible=` that hides a marker when a zoom leaves its value out.

### Plotting functions

`ax.plot(fn, *, until=None, from_=None, domain=None, color=None, label=None, samples=160)`
draws `y = fn(x)` with adaptive sampling (more points where the curve bends) and breaks at
discontinuities instead of drawing asymptotes.

Write `fn` with `k` functions (`k.sin`, `k.exp`, `k.where`, `k.max`). The same function then
works with floats (for sampling) and with signals (for `point_at`, `slope_at` and `.map`,
which are traced). `math.sin` fails with `K0310` as soon as something traces the function.

- **`until=`/`from_=`** accept signals: the curve grows as the signal moves.
- **`label=`** puts a label at the end of the curve.
- **Curves are clipped** to the visible ranges. Choose `y=` to cover the values that
  matter.

### Points, tangents and slopes on a curve

`ax.plot` returns a curve with reactive helpers:

| Call | Returns |
| --- | --- |
| `curve.point_at(x)` | World position of the curve at `x`. Use it with `place(at=...)`. |
| `curve.value_at(x)` | The y value at `x` |
| `curve.slope_at(x)` | The numerical derivative at `x`. Read it with `curve.slope_at(x)()` inside a lambda. |
| `curve.tangent_at(x, length=2.0, enter_with_axes=True, **style)` | A tangent segment centered on the curve, added to the axes |
| `ax.point(x, y)` | World position of a data point, for markers |

All of them are reactive when `x` is a signal:

```python
import kinemo as k


def f(x: float) -> float:
    return 0.15 * x**3 - 0.9 * x + 1.5


@k.scene
def derivative(s: k.Scene):
    ax = k.Axes(x=(-3, 3, 1), y=(-1, 5, 1), labels=("x", "y"), grid=True).place(at="center")
    t = k.signal(-3.0)
    curve = ax.plot(f, until=t, color=k.YELLOW, label="f")
    s.play(k.draw(ax))
    s.play(t.to(3), duration=2, ease=k.ease.linear)

    x = k.signal(-2.0)
    dot = k.Dot(r=0.1, fill=k.RED).place(at=curve.point_at(x))
    tan = curve.tangent_at(x, length=2.5, stroke=k.RED, enter_with_axes=False)
    slope = k.Text(lambda: f"slope = {curve.slope_at(x)():.2f}", size=0.4).place(at="top", margin=0.5)
    s.play(k.fade_in(dot, tan, slope))
    s.play(x.to(2), duration=3)
    s.play(ax.zoom_to(x=(0, 3), y=(0, 4)), duration=1.5)
    s.wait(0.5)
```

Objects that belong to the axes (plots, tangents, `vline`/`hline`, areas, scatter points,
bars) are added to it directly and enter with it. Markers you create yourself, like `dot`,
enter with a verb.

To introduce one of the axes' objects on its own, create it with `enter_with_axes=False`: it
stays hidden while the axes appear, and enters with its own verb (or `s.add`). A plot's label
comes in with the plot.

```python
tan = curve.tangent_at(x, length=3, stroke=k.RED, enter_with_axes=False)
s.play(k.draw(ax))        # the axes and the curve, without the tangent
s.play(k.fade_in(tan))    # now the tangent
```

### Areas, lines and limits

- `ax.area(curve, domain=(a, b), fill=..., fill_opacity=...)` fills the region under a curve
  down to the x axis. `between=other` fills between two curves. `until=` accepts a signal,
  so the area can grow.
- `ax.vline(at=x)` and `ax.hline(at=y)` draw vertical and horizontal lines. `at=` accepts a
  signal, and `style="dashed"` makes them dashed.
- `ax.segment((x0, y0), (x1, y1))` draws a line between two data points, cut to the visible
  ranges (and hidden when it falls outside them) as the axes zoom.
- `ax.hband(y0, y1)` and `ax.vband(x0, x1)` shade a band between two values, across or up
  the plot, cut to the visible range.
- `ax.vector((3, 1), at=(0, 0), label="F", components=True)` draws a vector in data units
  with its dashed components; `v=` and `at=` are signals (`vector.to(v=...)` turns it), and
  `k.vector_sum(a, b, a + b)` adds two vectors tip to tail.

```python
import kinemo as k


def top(x: float) -> float:
    return 3 - 0.2 * (x - 3) ** 2


def bottom(x: float) -> float:
    return 0.5 + 0.1 * x


@k.scene
def between(s: k.Scene):
    ax = k.Axes(x=(0, 6, 1), y=(0, 4, 1)).place(at="center")
    f = ax.plot(top, color=k.BLUE)
    g = ax.plot(bottom, color=k.ORANGE)
    t = k.signal(0.0)
    ax.area(f, between=g, domain=(1, 5), until=t, fill=k.GREEN, fill_opacity=0.3)
    ax.hline(at=3, style="dashed", stroke=k.GRAY)
    s.play(k.draw(ax))
    s.play(t.to(5), duration=2)
    s.wait(0.5)
```

### Parametric curves, bars and scatter

- `ax.parametric(fx, fy, t=(start, end))` draws `(fx(t), fy(t))`.
- `ax.bars(xs, heights, width=0.6)` draws bars in data units (`width` too). They follow
  the axes when it zooms.
- `ax.scatter(xs, ys, radius=0.06)` draws a group of `k.Dot`. For thousands of points, use
  `k.Points` instead (see [Mass objects](11-mass-objects.md)).

`xs`, `heights` and `ys` accept lists, numpy arrays and Arrow columns.

```python
import kinemo as k


def fx(t: float) -> float:
    return k.cos(t) * 1.2


def fy(t: float) -> float:
    return k.sin(2 * t)


@k.scene
def shapes(s: k.Scene):
    ax = k.Axes(x=(-1.5, 6, 1), y=(-1.5, 3, 1), width=10, height=5).place(at="center")
    loop = ax.parametric(fx, fy, t=(0, 2 * k.pi), color=k.TEAL, enter_with_axes=False)
    bars = ax.bars([2, 3, 4, 5], [1, 2.5, 1.5, 2], width=0.6, fill=k.PURPLE, enter_with_axes=False)
    pts = ax.scatter([2, 3, 4, 5], [1.2, 2.7, 1.7, 2.2], radius=0.08, fill=k.YELLOW, enter_with_axes=False)
    s.play(k.draw(ax))
    s.play(k.draw(loop), k.stagger([k.grow(b, from_="bottom") for b in bars], lag=0.1))
    s.play(k.fade_in(pts))
    s.wait(0.5)
```

## Number lines and polar axes

`k.NumberLine(x=(0, 10, 1), width=10.0)` is an `Axes` with only the x axis. Position markers
with `nl.point(x, 0)`.

`k.PolarAxes(r=(0, r_max, step), radius=3.0, spokes=12)` draws rings and spokes.
`pa.plot(fn)` draws `r = fn(θ)` (θ in radians, from 0 to 2π by default, `theta=` to change
it), and `pa.point(r, θ)` gives a world position.

```python
import kinemo as k


def petals(a: float) -> float:
    return abs(k.cos(3 * a))


@k.scene
def polar(s: k.Scene):
    pa = k.PolarAxes(r=(0, 1, 0.25), radius=2.5, spokes=12).place(at="left", margin=2.5)
    rose = pa.plot(petals, color=k.PINK)
    angle = k.signal(0.0)
    marker = k.Dot(r=0.12, fill=k.YELLOW).place(at=pa.point(1, angle))
    nl = k.NumberLine(x=(0, 2, 0.5), width=5).place(at="right", margin=1)
    pos = k.signal(0.0)
    tick = k.Dot(r=0.12, fill=k.RED).place(at=nl.point(pos, 0))
    s.add(pa, nl)
    s.play(k.draw(rose), k.fade_in(marker, tick), duration=2)
    s.play(angle.to(k.pi), pos.to(2), duration=2)
    s.wait(0.5)
```

## Number planes and linear transformations

`k.NumberPlane(x=(-7, 7, 1), y=(-4, 4, 1))` is a grid with axes and the basis vectors î
(green) and ĵ (red). `plane.apply(matrix)` animates the whole plane through a 2×2 matrix
`[[a, b], [c, d]]`, sending î to `(a, c)` and ĵ to `(b, d)`. A function `(x, y) -> (x2, y2)`
bends the grid for non-linear maps. Each call composes after the previous ones, and
`plane.reset()` goes back.

Objects made on the plane go along: `plane.vector(x, y)` is an arrow from the origin,
`plane.dot(x, y)` a point, `plane.polygon(points)` a shape that deforms (the unit square's
area is the determinant), and `plane.add(obj, at=(x, y))` moves any object with the plane
while keeping its shape.

```python
import kinemo as k

@k.scene
def shear(s: k.Scene):
    plane = k.NumberPlane(x=(-6, 6, 1), y=(-3, 3, 1))
    square = plane.polygon([(0, 0), (1, 0), (1, 1), (0, 1)], fill=k.YELLOW)
    s.play(k.draw(plane))
    s.play(plane.apply([[1, 1], [0, 1]]), duration=2)
    s.play(k.indicate(square))
```

## Data charts

### Where data comes from

Every data-taking API (`k.BarChart`, `k.LineChart`, `k.Table`, `ax.scatter`, `ax.bars`,
`k.interp`, `k.Points`) accepts:

| Input | Example |
| --- | --- |
| polars (the reference in these docs) | `pl.DataFrame(...)`, `df["gwh"]` |
| pandas 2.2 or later (with pyarrow) | `pd.DataFrame(...)`, `df["gwh"]` |
| pyarrow | `pa.table(...)`, `pa.array(...)` |
| duckdb | a relation |
| numpy (columns and arrays) | `np.array([...])` |
| plain Python | `{"country": [...], "gwh": [...]}` or `[{"country": "PT", "gwh": 50}, ...]` |

Anything that implements the Arrow PyCapsule Interface is read without copying. An object
that does not is `K1201`, and the fix suggests a conversion such as `pl.from_pandas(df)`.

### `k.BarChart`

```python signature
k.BarChart(data, x, y, *, key=None, width=8.0, height=4.5, color=None, labels=True, grid=False, bar_ratio=0.7, label_size=0.28)
```

`x=` is the category column, `y=` the value column, and `key=` identifies each bar across
data changes (default: the category). `chart.to(data=df2)` animates to the new table: bars
grow and shrink, move to their new slot, enter and leave by key, and the value axis rescales.
`chart.bar("IT")` returns one bar and `chart.keys` the keys in order. `color=` takes one
color or a dict from key to color.

```python
import polars as pl

import kinemo as k

Y2020 = pl.DataFrame({"country": ["PT", "ES", "FR"], "gwh": [50, 260, 540]})
Y2025 = pl.DataFrame({"country": ["ES", "PT", "FR", "IT"], "gwh": [300, 80, 600, 420]})


@k.scene
def generation(s: k.Scene):
    title = k.Text("Solar generation (GWh)", size=0.5).place(at="top", margin=0.6)
    chart = k.BarChart(Y2020, x="country", y="gwh", key="country", width=8, height=4).place(below=title, gap=0.6)
    s.play(k.write(title), k.draw(chart))
    s.play(chart.to(data=Y2025), duration=2)
    s.play(k.indicate(chart.bar("IT")))
    s.wait(0.5)
```

### `k.LineChart`

```python signature
k.LineChart(data, x, y, *, x_range=None, y_range=None, width=8.0, height=4.5, colors=None, dots=False, legend=True)
```

A `k.Axes` with one line per `y=` column (a string or a list), connecting the points in `x=`
order. With several columns, a legend names them. `chart.to(data=df2)` morphs the lines point
by point. **The axis ranges stay fixed** after construction: pass `y_range=` (and
`x_range=`) covering every dataset you will show.

```python
import pandas as pd

import kinemo as k

DAY = pd.DataFrame({"hour": [0, 6, 12, 18, 24], "solar": [0, 2, 6, 2, 0], "load": [1, 2, 3, 5, 2]})
CLOUDY = pd.DataFrame({"hour": [0, 6, 12, 18, 24], "solar": [0, 1, 2.5, 1, 0], "load": [1, 2, 3, 5, 2]})


@k.scene
def day(s: k.Scene):
    chart = k.LineChart(DAY, x="hour", y=["solar", "load"], y_range=(0, 7), dots=True).place(at="center")
    s.play(k.draw(chart), duration=2)
    s.play(chart.to(data=CLOUDY), duration=2)
    s.wait(0.5)
```

### `k.Table`

```python signature
k.Table(data, columns=None, *, size=0.32, header_color=None, rule=True, widths=None, reserve=())
```

A table of `k.Text` with a highlighted header. `columns=` selects and orders the columns.
`table.to(data=df2)` updates the cells: changed texts fade out and back in with the new
value, new rows fade in while the table makes room, and removed rows fade out.
`table.cells[r][c]` are the body cells and `table.header[c]` the header texts.

Columns are as wide as their longest text. For a table that will grow, `reserve=[AFTER]`
sizes them for the data shown later too, so they keep their width when rows arrive;
`widths=[2.0, None]` sets minimum widths per column (in units).

```python
import pyarrow as pa

import kinemo as k

BEFORE = pa.table({"site": ["A", "B"], "mw": [12.5, 8.0]})
AFTER = pa.table({"site": ["A", "B", "C"], "mw": [14.0, 8.0, 3.2]})


@k.scene
def sites(s: k.Scene):
    table = k.Table(BEFORE, size=0.4, reserve=[AFTER]).place(at="center")
    s.play(k.fade_in(table))
    s.play(table.to(data=AFTER))
    s.play(table.cells[0][1].to(color=k.YELLOW))
    s.wait(0.5)
```

### Columns in functions: `k.interp`

`k.interp(x, xs, ys)` and `k.spline(x, xs, ys)` interpolate a table natively. `xs`/`ys` can
be Arrow columns or numpy arrays, and the function works in `ax.plot` and `.map` alike:

```python
import numpy as np
import polars as pl

import kinemo as k

PROFILE = pl.DataFrame({"hour": [0, 6, 12, 18, 24], "kw": [0.5, 0.8, 1.2, 2.5, 0.6]})
HOURS = PROFILE["hour"]
KW = np.asarray(PROFILE["kw"])


def load(h: float) -> float:
    return k.interp(h, HOURS, KW)


@k.scene
def profile(s: k.Scene):
    ax = k.Axes(x=(0, 24, 6), y=(0, 3, 1), labels=("h", "kW")).place(at="center")
    hour = k.signal(0.0)
    ax.plot(load, until=hour, color=k.RED)
    ax.vline(at=hour, style="dashed")
    s.play(k.draw(ax))
    s.play(hour.to(24), duration=3, ease=k.ease.linear)
    s.wait(0.5)
```

## Gauges

`k.Gauge` is a dial whose needle follows a value, for speeds, pressures and levels. The value
can be a signal shared with the rest of the scene:

```python
import kinemo as k


@k.scene
def dial(s: k.Scene):
    speed = k.signal(20.0)
    gauge = k.Gauge(value=speed, range=(0, 120), ticks=6, label="km/h", zones=[(90, 120, k.RED)]).place(at="center")
    s.play(k.fade_in(gauge))
    s.play(speed.to(105), duration=2)
    s.play(gauge.to(value=60), duration=1)
    s.wait(0.5)
```

- `sweep=` is the dial's angle (240° by default), `ticks=` the number of intervals between the
  numbered marks, `digits=` the decimals of the numbers and the readout.
- The needle stays within `range=` even when the value leaves it; `readout=False` hides the
  value under the hub.

## Common mistakes

> | Diagnostic | What happened | Fix |
> | --- | --- | --- |
> | `K0310` | The plotted function uses `math.sin` (or `if`, `min()`), and `point_at`, `slope_at` or `.map` traced it. | Use `k.sin`, `k.where`, `k.min`; for opaque code, `k.python(fn)`. |
> | `K0401` | `ax.to(x=(0, 3))` to change the range. In `.to()`, `x` is the position prop, which `.place(...)` holds; the constructor's `x=` range is a different thing. | `ax.zoom_to(x=(0, 3))` to change ranges; `ax.to_place(...)` to move the axes. |
> | many `W1001` | `chart.to(data=...)` on a `LineChart` whose new values exceed the ranges fixed at construction. The lines grow past the axes and the chart is re-centered. | Pass `y_range=` covering all datasets. |
> | `K1201` | The data object does not implement the Arrow PyCapsule Interface (for example, pandas older than 2.2). | `pl.from_pandas(df)`, or pass a dict of lists. |
> | `K1202` | `x=`, `y=` or `key=` names a column that does not exist. The fix lists the available columns. | Use the exact column name (it is case-sensitive). |
> | `K1203` | The value column is not numeric. | Cast it before charting (`df.with_columns(pl.col("gwh").cast(pl.Float64))`). |
> | `K1204` | `key=` has duplicate values. | Aggregate first (`df.group_by("country").sum()`) or choose another key. |
> | `W0901` | `ax.scatter` (or a loop of `k.Dot`) with more than 1000 points. | `k.Points(x=..., y=...)`. |

See also: [Charts reference](../reference/charts.md),
[`k.interp`](../reference/native-blocks.md#k-interp),
[Diagnostics](../reference/diagnostics.md#range-12).
