"""Native building blocks: polymorphic functions traced to the IR (`k.sin`, `k.where`...)."""

from __future__ import annotations

from ..entry import DocEntry

_POLYMORPHIC = (
    " Like every `k` function, it accepts floats, signals and numpy arrays: the same function "
    "works for `ax.plot` (floats) and for `.map` (traced, native)."
)

ENTRIES = (
    DocEntry(
        "k.sin",
        "Native blocks",
        "Native math functions: `k.sin`, `k.cos`, `k.tan`, `k.exp`, `k.log`, `k.sqrt` and "
        "`k.atan2(y, x)`. Use them instead of `math.*`, which is not traceable (error K0305/K0310)."
        + _POLYMORPHIC,
        '''
import kinemo as k

@k.scene
def oscillator(s: k.Scene):
    dot = k.Dot(r=0.2, x=k.cos(k.time * 2) * 3, y=k.sin(k.time * 2) * 2)
    s.add(dot)
    s.wait(4)
''',
        related=("k.pi", "Expr.map", "k.time"),
        aliases=("k.cos", "k.tan", "k.exp", "k.log", "k.sqrt", "k.atan2"),
    ),
    DocEntry(
        "k.floor",
        "Native blocks",
        "Native rounding down (`k.floor`) and up (`k.ceil`). They replace `int()` and "
        "`math.floor`, which are not traceable." + _POLYMORPHIC,
        '''
import kinemo as k

@k.scene
def counter(s: k.Scene):
    hour = k.time * 2
    clock = k.Text(lambda: f"{k.floor(hour()):02.0f}:00", size=0.9).place(at="center")
    s.add(clock)
    s.wait(4)
''',
        related=("k.time", "k.clamp"),
        aliases=("k.ceil",),
    ),
    DocEntry(
        "k.min",
        "Native blocks",
        "Native minimum and maximum of two or more values (`k.min(a, b, c)`). They replace the "
        "built-in `min()`/`max()`, which are not traceable." + _POLYMORPHIC,
        '''
import kinemo as k

@k.scene
def capped(s: k.Scene):
    hour = k.time.map(lambda t: k.min(t * 6, 24))
    label = k.Text(lambda: f"{hour():.0f} h", size=0.9).place(at="center")
    s.add(label)
    s.wait(5)
''',
        related=("k.clamp", "k.where"),
        aliases=("k.max",),
    ),
    DocEntry(
        "k.clamp",
        "Native blocks",
        "Clamps a value to the range `[lo, hi]`, natively." + _POLYMORPHIC,
        '''
import kinemo as k

@k.scene
def limit(s: k.Scene):
    x = k.signal(-6.0)
    dot = k.Dot(r=0.2, x=k.clamp(x, -3, 3))
    s.add(dot)
    s.play(x.to(6), duration=3)
''',
        related=("k.min", "k.smoothstep"),
    ),
    DocEntry(
        "k.where",
        "Native blocks",
        "The traceable `if`: `a` where `cond` holds, otherwise `b`. Combine conditions with `&`, "
        "`|` and `~` (not with `and`/`or`)." + _POLYMORPHIC,
        '''
import kinemo as k

def tariff(h: float) -> float:
    return k.where((h >= 18) & (h < 21), 1.8, 0.6)

@k.scene
def peak(s: k.Scene):
    hour = k.time * 6
    label = k.Text(lambda: f"{hour():.0f} h: $ {tariff(hour()):.2f}").place(at="center")
    s.add(label)
    s.wait(4)
''',
        related=("k.piecewise", "k.when"),
    ),
    DocEntry(
        "k.piecewise",
        "Native blocks",
        "Piecewise function: `k.piecewise((cond1, v1), (cond2, v2), default=v)`; the first "
        "true condition wins." + _POLYMORPHIC,
        '''
import kinemo as k

def band(v: float) -> k.Color:
    return k.piecewise((v < 1, k.GREEN), (v < 2, k.YELLOW), default=k.RED)

@k.scene
def traffic_light(s: k.Scene):
    v = k.signal(0.0)
    lamp = k.Circle(r=1, fill=v.map(band), fill_opacity=1).place(at="center")
    s.add(lamp)
    s.play(v.to(3), duration=3)
''',
        related=("k.where",),
    ),
    DocEntry(
        "k.spline",
        "Native blocks",
        "Smooth table interpolation (natural cubic spline): `k.spline(x, xs, ys)`. Same "
        "inputs as `k.interp`; outside the range it holds the endpoint value." + _POLYMORPHIC,
        '''
import kinemo as k

@k.scene
def smooth(s: k.Scene):
    x = k.signal(0.0)
    height = k.spline(x, [0, 1, 2, 3], [0, 2, 1, 2])
    dot = k.Dot(r=0.15, x=x * 2 - 3, y=height - 1)
    s.add(dot)
    s.play(x.to(3), duration=2)
''',
        related=("k.interp", "k.smoothstep"),
    ),
    DocEntry(
        "k.interp",
        "Native blocks",
        "Linear table interpolation: `k.interp(x, xs, ys)`. `xs`/`ys` can be lists, numpy "
        "arrays or Arrow columns (polars, pandas, pyarrow), without copying." + _POLYMORPHIC,
        '''
import kinemo as k

HOURS = [0, 6, 12, 18, 24]
KW = [0.5, 0.8, 1.2, 2.5, 0.6]

@k.scene
def load(s: k.Scene):
    hour = k.time * 4
    label = k.Text(lambda: f"{k.interp(hour(), HOURS, KW):.2f} kW").place(at="center")
    s.add(label)
    s.wait(5)
''',
        related=("Axes.plot", "k.mix"),
    ),
    DocEntry(
        "k.mix",
        "Native blocks",
        "Linear mix `a + (b - a) * t` of numbers, vectors or colors (colors in OKLab, with no "
        "gray in the middle)." + _POLYMORPHIC,
        '''
import kinemo as k

@k.scene
def gradient(s: k.Scene):
    t = k.signal(0.0)
    box = k.Square(2, fill=k.mix(k.RED, k.GREEN, t), fill_opacity=1).place(at="center")
    s.add(box)
    s.play(t.to(1), duration=2)
''',
        related=("k.interp", "k.smoothstep"),
    ),
    DocEntry(
        "k.smoothstep",
        "Native blocks",
        "Smooth transition from 0 to 1 as `x` goes from `e0` to `e1` (cubic Hermite)."
        + _POLYMORPHIC,
        '''
import kinemo as k

@k.scene
def fade_glow(s: k.Scene):
    glow = k.smoothstep(1, 3, k.time)
    c = k.Circle(r=1.5, fill=k.YELLOW, fill_opacity=glow).place(at="center")
    s.add(c)
    s.wait(4)
''',
        related=("k.clamp", "k.mix"),
    ),
    DocEntry(
        "k.noise",
        "Native blocks",
        "Smooth, deterministic noise in [-1, 1] (`seed=` changes the sequence). Good for jitter "
        "and organic motion.",
        '''
import kinemo as k

@k.scene
def jitter(s: k.Scene):
    leaf = k.Ellipse(w=1.2, h=0.6, fill=k.GREEN, fill_opacity=1)
    leaf.set(x=k.noise(k.time, seed=1) * 2, y=k.noise(k.time, seed=2))
    s.add(leaf)
    s.wait(4)
''',
        related=("k.sin", "k.time"),
    ),
    DocEntry(
        "k.vec",
        "Native blocks",
        "2D vector from two values (numbers or signals). With signals, the vector is "
        "reactive: use it in point props such as a line's `start=`/`end=`.",
        '''
import kinemo as k

@k.scene
def clock_hand(s: k.Scene):
    angle = k.time * 2
    hand = k.Line(start=(0, 0), end=k.vec(k.cos(angle) * 2, k.sin(angle) * 2))
    s.add(hand)
    s.wait(4)
''',
        related=("k.sin", "k.Line"),
    ),
    DocEntry(
        "k.pi",
        "Native blocks",
        "Constants `k.pi`, `k.tau` (2π) and `k.e`, for use inside traced functions.",
        '''
import kinemo as k

@k.scene
def orbit(s: k.Scene):
    angle = k.time * k.tau / 4
    dot = k.Dot(r=0.2, x=k.cos(angle) * 2, y=k.sin(angle) * 2)
    s.add(dot)
    s.wait(4)
''',
        related=("k.sin",),
        aliases=("k.tau", "k.e"),
    ),
)
