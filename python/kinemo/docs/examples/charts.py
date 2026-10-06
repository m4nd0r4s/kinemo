"""Axes and plots: `k.Axes`, `k.NumberLine`, `ax.plot` and the curve helpers."""

from __future__ import annotations

from ..entry import DocEntry

ENTRIES = (
    DocEntry(
        "k.PolarAxes",
        "Charts",
        "Polar axes (rings and spokes): `r=(0, r_max, step)`, `radius=` in units, "
        "`spokes=`. `pa.plot(lambda a: r(a))` draws `r = f(θ)`; `pa.point(r, θ)` gives the "
        "world position.",
        '''
import kinemo as k

def petals(a: float) -> float:
    return abs(k.cos(3 * a))

@k.scene
def rose(s: k.Scene):
    pa = k.PolarAxes(r=(0, 1, 0.25), radius=3).place(at="center")
    curve = pa.plot(petals, color=k.PINK)
    s.add(pa)
    s.play(k.draw(curve), duration=2)
''',
        related=("k.Axes", "Axes.parametric"),
    ),
    DocEntry(
        "Axes.parametric",
        "Charts",
        "Parametric curve `(fx(t), fy(t))` for `t=(start, end)`; clipped to the visible "
        "ranges. Siblings: `ax.bars(xs, heights, width=)` (bars in data units) and "
        "`ax.scatter(xs, ys)`.",
        '''
import kinemo as k

def fx(t: float) -> float:
    return k.sin(2 * t)

def fy(t: float) -> float:
    return k.sin(3 * t)

@k.scene
def loop(s: k.Scene):
    ax = k.Axes(x=(-1.5, 1.5), y=(-1.5, 1.5), width=5, height=5).place(at="center")
    curve = ax.parametric(fx, fy, color=k.TEAL)
    s.add(ax)
    s.play(k.draw(curve), duration=2)
''',
        related=("Axes.plot", "k.Axes"),
        aliases=("Axes.bars",),
    ),
    DocEntry(
        "k.Axes",
        "Charts",
        "Cartesian axes with ticks, labels and an optional grid: `x=(min, max, step)`, "
        "`y=(min, max)`, `labels=(\"x\", \"y\")`, `width=`/`height=` in units. The visible "
        "ranges are signals: `ax.zoom_to(...)` animates them and everything on the axes follows. "
        "`x_ticks=`/`y_ticks=` set the tick values by hand and `tick_format=` (`\"{:.1f}\"` or a "
        "function) writes their labels; y labels are right-aligned to the axis.",
        '''
import kinemo as k

@k.scene
def axes(s: k.Scene):
    ax = k.Axes(x=(0, 10, 2), y=(0, 5, 1), labels=("t", "v"), grid=True).place(at="center")
    s.play(k.draw(ax))
    s.wait(0.5)

@k.scene
def custom_ticks(s: k.Scene):
    ax = k.Axes(x=(0, 30), y=(0, 1, 0.25), x_ticks=[4, 9, 16, 25], tick_format="{:.2f}").place(at="center")
    s.play(k.draw(ax))
''',
        related=("Axes.plot", "Axes.zoom_to", "k.NumberLine"),
    ),
    DocEntry(
        "k.NumberLine",
        "Charts",
        "A horizontal number line: a `k.Axes` with only the x axis. Use `nl.point(x, 0)` to "
        "position markers.",
        '''
import kinemo as k

@k.scene
def number_line(s: k.Scene):
    nl = k.NumberLine(x=(-3, 3, 1), width=10).place(at="center")
    x = k.signal(-2.0)
    dot = k.Dot(r=0.15, fill=k.RED).place(at=nl.point(x, 0))
    s.play(k.draw(nl), k.fade_in(dot))
    s.play(x.to(2), duration=2)
''',
        related=("k.Axes", "Axes.point"),
    ),
    DocEntry(
        "k.NumberPlane",
        "Charts",
        "A coordinate grid with axes and the basis vectors î (green) and ĵ (red): "
        "`x=(min, max, step)`, `y=...`, `unit=` scene units per step. `plane.apply(matrix)` "
        "deforms it; `plane.vector(x, y)`, `plane.dot(x, y)`, `plane.polygon(points)` and "
        "`plane.add(obj, at=(x, y))` put objects on it that the transformations carry.",
        '''
import kinemo as k

@k.scene
def plane(s: k.Scene):
    plane = k.NumberPlane(x=(-6, 6, 1), y=(-3, 3, 1))
    v = plane.vector(2, 1, color=k.YELLOW)
    s.play(k.draw(plane))
    s.play(k.indicate(v))
''',
        related=("NumberPlane.apply", "NumberPlane.polygon", "k.Axes"),
    ),
    DocEntry(
        "k.ComplexPlane",
        "Charts",
        "A `k.NumberPlane` labelled as the complex plane (real ticks, `i` ticks, `Re`/`Im`) whose "
        "points are complex numbers: `cp.dot(2 + 1j)`, `cp.vector(1 - 2j)`, `cp.coords(z)`. "
        "`cp.apply(1j)` multiplies everything by a complex number (a quarter turn), "
        "`cp.apply(lambda z: z ** 2)` maps the plane with a function of `z`.",
        '''
import kinemo as k

@k.scene
def rotation(s: k.Scene):
    cp = k.ComplexPlane(re=(-4, 4, 1), im=(-3, 3, 1))
    cp.vector(2 + 1j, color=k.YELLOW)
    s.play(k.draw(cp))
    s.play(cp.apply(1j), duration=2)
''',
        related=("k.NumberPlane", "NumberPlane.apply"),
    ),
    DocEntry(
        "NumberPlane.apply",
        "Charts",
        "Animated transformation of the plane, composed after the ones already applied: a "
        "matrix `[[a, b], [c, d]]` sends î to `(a, c)` and ĵ to `(b, d)`; a function "
        "`(x, y) -> (x2, y2)` bends the grid for non-linear maps. Grid lines, basis vectors and "
        "the objects made on the plane all move. `plane.reset()` goes back.",
        '''
import math
import kinemo as k

@k.scene
def shear(s: k.Scene):
    plane = k.NumberPlane(x=(-6, 6, 1), y=(-3, 3, 1))
    eigen = plane.vector(1, 0, color=k.YELLOW)
    s.play(k.draw(plane))
    s.play(plane.apply([[1, 1], [0, 1]]), duration=2)
    s.play(k.indicate(eigen))  # an eigenvector: still on its span
    s.play(plane.apply(lambda x, y: (x + 0.3 * math.sin(y), y)), duration=2)
    s.play(plane.reset())
''',
        related=("k.NumberPlane", "NumberPlane.polygon"),
    ),
    DocEntry(
        "NumberPlane.polygon",
        "Charts",
        "A filled shape with vertices in data coordinates that deforms with the plane. The "
        "unit square shows the determinant: its area after `apply(m)` is `det(m)`.",
        '''
import kinemo as k

@k.scene
def determinant(s: k.Scene):
    plane = k.NumberPlane(x=(-6, 6, 1), y=(-3, 3, 1))
    square = plane.polygon([(0, 0), (1, 0), (1, 1), (0, 1)], fill=k.YELLOW)
    s.play(k.draw(plane))
    s.play(plane.apply([[2, 1], [0, 1.5]]), duration=2)
    s.play(k.indicate(square))  # area 3 = det
''',
        related=("NumberPlane.apply", "k.NumberPlane"),
    ),
    DocEntry(
        "Axes.plot",
        "Charts",
        "Draws the curve `y = fn(x)` on the axes, with adaptive sampling. `fn` uses `k` "
        "functions (`k.sin`, `k.max`...), so the same function works for floats and signals. "
        "`until=`/`from_=` accept signals: the curve grows as the signal moves. "
        "`label=` puts a label at the end of the curve.",
        '''
import kinemo as k

def wave(x: float) -> float:
    return 2 + 1.5 * k.sin(x)

@k.scene
def wave_plot(s: k.Scene):
    ax = k.Axes(x=(0, 10, 2), y=(0, 4, 1)).place(at="center")
    t = k.signal(0.0)
    ax.plot(wave, until=t, color=k.YELLOW, label="wave")
    s.play(k.draw(ax))
    s.play(t.to(10), duration=3, ease=k.ease.linear)
''',
        related=("Plot.point_at", "Axes.area", "k.sin"),
    ),
    DocEntry(
        "Axes.area",
        "Charts",
        "Filled region under a curve (down to the x axis) or between two curves (`between=`). "
        "Accepts a curve from `ax.plot` or a function, plus style (`fill=`, `fill_opacity=`).",
        '''
import kinemo as k

def f(x: float) -> float:
    return 0.1 * x * x

@k.scene
def area(s: k.Scene):
    ax = k.Axes(x=(0, 6, 1), y=(0, 4, 1)).place(at="center")
    curve = ax.plot(f, color=k.BLUE)
    ax.area(curve, domain=(1, 5), fill=k.BLUE, fill_opacity=0.3)
    s.play(k.draw(ax))
    s.wait(0.5)
''',
        related=("Axes.plot",),
    ),
    DocEntry(
        "Axes.vline",
        "Charts",
        "Vertical line on the axes at `at=` (accepts a signal: the line moves with it); "
        "`style=\"dashed\"` makes it dashed.",
        '''
import kinemo as k

@k.scene
def marker(s: k.Scene):
    ax = k.Axes(x=(0, 24, 6), y=(0, 5)).place(at="center")
    hour = k.signal(6.0)
    ax.vline(at=hour, style="dashed", stroke=k.YELLOW)
    s.play(k.draw(ax))
    s.play(hour.to(18), duration=2)
''',
        related=("Axes.hline", "Axes.plot"),
    ),
    DocEntry(
        "Axes.hline",
        "Charts",
        "Horizontal line on the axes at `at=` (accepts a signal); `style=\"dashed\"` makes it "
        "dashed. Good for limits and targets.",
        '''
import kinemo as k

@k.scene
def limit(s: k.Scene):
    ax = k.Axes(x=(0, 10, 2), y=(0, 5, 1)).place(at="center")
    ax.hline(at=4, style="dashed", stroke=k.RED)
    s.play(k.draw(ax))
    s.wait(0.5)
''',
        related=("Axes.vline",),
    ),
    DocEntry(
        "Axes.scatter",
        "Charts",
        "Points `(xs[i], ys[i])` on the axes, as a group of `k.Dot`. Accepts lists, numpy "
        "arrays and Arrow columns (polars, pandas, pyarrow).",
        '''
import kinemo as k

@k.scene
def scatter(s: k.Scene):
    ax = k.Axes(x=(0, 5, 1), y=(0, 5, 1)).place(at="center")
    pts = ax.scatter([1, 2, 3, 4], [1.5, 2.2, 3.1, 3.8], radius=0.1, fill=k.TEAL)
    s.play(k.draw(ax))
    s.play(k.indicate(pts))
''',
        related=("Axes.plot", "k.Dot"),
    ),
    DocEntry(
        "Axes.zoom_to",
        "Charts",
        "Named transition: animates the visible ranges of the axes (`x=(a, b)`, `y=(c, d)`). "
        "Curves, ticks and points follow, and ticks are regenerated with a nice step for the new "
        "ranges: new ones grow in, ones that no longer fit fade out. Equivalent to "
        "`ax.to(x_range=..., y_range=...)` plus the tick change.",
        '''
import kinemo as k

@k.scene
def zoom(s: k.Scene):
    ax = k.Axes(x=(-4, 4, 1), y=(-1, 9, 1)).place(at="center")
    ax.plot(lambda x: x * x, color=k.YELLOW)
    s.play(k.draw(ax))
    s.play(ax.zoom_to(x=(0, 2), y=(0, 4)), duration=1.5)
''',
        related=("k.Axes", "Axes.plot"),
    ),
    DocEntry(
        "Axes.point",
        "Charts",
        "Data point `(x, y)` in world coordinates, reactive when `x` or `y` are "
        "signals. It is the target of `place(at=...)` for markers on the axes.",
        '''
import kinemo as k

@k.scene
def point(s: k.Scene):
    ax = k.Axes(x=(0, 10, 2), y=(0, 10, 2)).place(at="center")
    pin = k.Dot(r=0.12, fill=k.RED).place(at=ax.point(3, 9))
    label = k.Text("(3, 9)", size=0.35).place(right_of=pin, gap=0.2)
    s.play(k.draw(ax))
    s.play(k.fade_in(pin, label))
''',
        related=("Plot.point_at", "Node.place"),
    ),
    DocEntry(
        "Axes.add",
        "Charts",
        "Puts objects inside the axes, in its own coordinates, so they follow zooms like "
        "plots do; place them with `position=ax.local_point(x, y)` or `ax.origin()`. They enter with "
        "the axes; with `enter_with_axes=False` they stay hidden until a verb brings them in.",
        '''
import kinemo as k

@k.scene
def marker(s: k.Scene):
    ax = k.Axes(x=(0, 10, 2), y=(0, 10, 2)).place(at="center")
    peak = k.Dot(r=0.12, fill=k.RED, position=ax.local_point(4, 8))
    ax.add(peak, enter_with_axes=False)
    s.play(k.draw(ax))
    s.play(k.fade_in(peak))
    s.play(ax.zoom_to(x=(2, 6), y=(4, 10)), duration=1.5)
''',
        related=("Axes.origin", "Axes.in_view", "Axes.point"),
    ),
    DocEntry(
        "Axes.segment",
        "Charts",
        "A line between two data points `(x, y)`, cut to the visible ranges with `clip=True` (the "
        "default) and hidden when it falls entirely outside them; it follows zooms.",
        '''
import kinemo as k

@k.scene
def secant(s: k.Scene):
    ax = k.Axes(x=(0, 10, 2), y=(0, 10, 2)).place(at="center")
    ax.plot(lambda x: 0.1 * x * x)
    line = ax.segment((-2, -1), (12, 11), stroke=k.YELLOW)
    s.play(k.draw(ax))
    s.play(k.indicate(line))
    s.play(ax.zoom_to(x=(4, 10), y=(4, 10)), duration=1.5)
''',
        related=("Axes.hband", "Axes.zoom_to"),
    ),
    DocEntry(
        "Axes.hband",
        "Charts",
        "`ax.hband(y0, y1)`: a translucent band across the plot between two data values; "
        "`ax.vband(x0, x1)` the same up the plot. Cut to the visible range, hidden outside it, "
        "following zooms. Style with `fill=`, `fill_opacity=`.",
        '''
import kinemo as k

@k.scene
def comfort(s: k.Scene):
    ax = k.Axes(x=(0, 24, 6), y=(0, 30, 10), labels=("h", "°C")).place(at="center")
    ax.hband(18, 24)
    ax.vband(9, 17, fill=k.GREEN)
    ax.plot(lambda h: 15 + 8 * k.sin((h - 9) * 3.14159 / 12))
    s.play(k.draw(ax))
''',
        related=("Axes.segment", "Axes.vline"),
        aliases=("Axes.vband",),
    ),
    DocEntry(
        "Axes.origin",
        "Charts",
        "Where the two axes cross, in the axes' own coordinates: the data origin clamped "
        "to the visible ranges. Reactive, so it moves with zooms.",
        '''
import kinemo as k

@k.scene
def origin(s: k.Scene):
    ax = k.Axes(x=(-2, 8, 2), y=(-2, 8, 2)).place(at="center")
    ax.add(k.Dot(r=0.1, fill=k.YELLOW, position=ax.origin()))
    s.play(k.draw(ax))
    s.play(ax.zoom_to(x=(2, 8)), duration=1.5)
''',
        related=("Axes.add", "k.Axes"),
    ),
    DocEntry(
        "Axes.in_view",
        "Charts",
        "Whether a data value is inside the visible ranges, as a reactive bool for `visible=`: "
        "`ax.in_view(x=3)`, `ax.in_view(y=5)` or both. Markers hide when a zoom leaves them out.",
        '''
import kinemo as k

@k.scene
def in_view(s: k.Scene):
    ax = k.Axes(x=(0, 10, 2), y=(0, 10, 2)).place(at="center")
    tag = k.Text("x = 8", size=0.3, position=ax.local_point(8, 9), visible=ax.in_view(x=8))
    ax.add(tag)
    s.play(k.draw(ax))
    s.play(ax.zoom_to(x=(0, 5)), duration=1.5)
''',
        related=("Axes.add", "Axes.zoom_to"),
    ),
    DocEntry(
        "Plot.point_at",
        "Charts",
        "World position of the curve at `x`; reactive when `x` is a signal. With "
        "`place(at=...)` it makes a dot slide along the curve. `curve.value_at(x)` gives the y value.",
        '''
import kinemo as k

def f(x: float) -> float:
    return 0.15 * x**3 - 0.9 * x + 1.5

@k.scene
def slide(s: k.Scene):
    ax = k.Axes(x=(-3, 3, 1), y=(-1, 5, 1)).place(at="center")
    curve = ax.plot(f, color=k.YELLOW)
    x = k.signal(-2.0)
    dot = k.Dot(r=0.1, fill=k.RED).place(at=curve.point_at(x))
    s.play(k.draw(ax), k.fade_in(dot))
    s.play(x.to(2.5), duration=3)
''',
        related=("Plot.tangent_at", "Plot.slope_at", "Axes.point"),
        aliases=("Plot.value_at",),
    ),
    DocEntry(
        "Plot.tangent_at",
        "Charts",
        "Tangent segment `length` units long, centered on the curve at `x`, reactive when `x` is "
        "a signal. It belongs to the axes and enters with it; `enter_with_axes=False` keeps it "
        "hidden until a verb brings it in. Accepts style (`stroke=`).",
        '''
import kinemo as k

@k.scene
def tangent(s: k.Scene):
    ax = k.Axes(x=(-3, 3, 1), y=(-1, 9, 1)).place(at="center")
    curve = ax.plot(lambda x: x * x, color=k.YELLOW)
    x = k.signal(-2.0)
    curve.tangent_at(x, length=3, stroke=k.RED)
    s.play(k.draw(ax))
    s.play(x.to(2), duration=3)
''',
        related=("Plot.slope_at", "Plot.point_at"),
    ),
    DocEntry(
        "Plot.slope_at",
        "Charts",
        "Numerical derivative of the curve at `x`, reactive when `x` is a signal. Use it inside "
        "lambdas with a tracked read: `curve.slope_at(x)()`.",
        '''
import kinemo as k

@k.scene
def slope(s: k.Scene):
    ax = k.Axes(x=(-3, 3, 1), y=(-1, 9, 1)).place(at="center")
    curve = ax.plot(lambda x: x * x, color=k.YELLOW)
    x = k.signal(-2.0)
    label = k.Text(lambda: f"f'({x():.1f}) = {curve.slope_at(x)():.1f}").place(at="top", margin=0.5)
    s.play(k.draw(ax), k.fade_in(label))
    s.play(x.to(2), duration=3)
''',
        related=("Plot.tangent_at",),
    ),
    DocEntry(
        "k.BarChart",
        "Charts",
        "Bar chart from a table: `x=` is the category column, `y=` the value column and "
        "`key=` identifies each bar. Accepts Arrow sources without copying (polars, pandas, "
        "pyarrow, duckdb), dicts of lists and lists of dicts. `chart.to(data=df2)` animates the "
        "change: bars grow, move, enter and leave by key; the value axis follows.",
        '''
import kinemo as k

@k.scene
def energy(s: k.Scene):
    chart = k.BarChart({"country": ["PT", "ES"], "gwh": [50, 260]}, x="country", y="gwh").place(at="center")
    s.play(k.draw(chart))
    s.play(chart.to(data={"country": ["ES", "PT", "FR"], "gwh": [300, 80, 540]}), duration=2)
''',
        related=("k.LineChart", "k.Table", "k.Bar"),
    ),
    DocEntry(
        "k.LineChart",
        "Charts",
        "A `k.Axes` with one line per `y=` column (one or several), connecting the table's "
        "points in `x=` order. `chart.to(data=df2)` morphs the lines point by point; the axis "
        "ranges stay fixed (use `y_range=` to cover all the data).",
        '''
import kinemo as k

@k.scene
def lines(s: k.Scene):
    chart = k.LineChart({"h": [0, 12, 24], "kw": [0, 6, 0]}, x="h", y="kw", y_range=(0, 8)).place(at="center")
    s.play(k.draw(chart))
    s.play(chart.to(data={"h": [0, 6, 12, 18, 24], "kw": [0, 3, 7, 3, 0]}), duration=2)
''',
        related=("k.Axes", "k.BarChart"),
    ),
    DocEntry(
        "k.Table",
        "Charts",
        "Table of `k.Text` with a highlighted header; `columns=` selects and orders the columns. "
        "`table.to(data=df2)` updates the cells: changed texts flash with the new value, "
        "new rows appear and removed ones leave. `table.cells[r][c]` are the cells. Columns fit "
        "their text; `reserve=[df2]` sizes them for data shown later (they keep their width as "
        "rows arrive) and `widths=` sets minimum widths per column.",
        '''
import kinemo as k

@k.scene
def table(s: k.Scene):
    t = k.Table({"country": ["PT", "ES"], "gwh": [50, 260]}).place(at="center")
    s.play(k.fade_in(t))
    s.play(t.to(data={"country": ["PT", "ES", "FR"], "gwh": [80, 260, 1200]}))
''',
        related=("k.BarChart", "k.Text"),
    ),
)
