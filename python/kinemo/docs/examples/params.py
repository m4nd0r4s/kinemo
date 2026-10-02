"""Scene parameters, theme and colors."""

from __future__ import annotations

from ..entry import DocEntry

_PARAMS_NOTE = (
    " Parameters reach the scene function as signals: in video they take the `default` (or "
    "`--param name=value` on the CLI) and in interactive output they become controls. Reading a "
    "parameter with `.now` freezes it at build time (lint W1301)."
)

ENTRIES = (
    DocEntry(
        "k.Int",
        "Parameters",
        "Integer scene parameter in the range `[lo, hi]`: `k.Int(3, 12, default=5)`."
        + _PARAMS_NOTE,
        '''
import kinemo as k

@k.scene(params={"n": k.Int(1, 10, default=3)})
def count(s: k.Scene, n: k.Signal[int]):
    label = k.Text(lambda: f"n = {n():.0f}", size=0.9).place(at="center")
    s.play(k.write(label))
''',
        related=("k.Float", "k.scene"),
    ),
    DocEntry(
        "k.Float",
        "Parameters",
        "Real-valued scene parameter in the range `[lo, hi]`: `k.Float(0.5, 2, default=1)`."
        + _PARAMS_NOTE,
        '''
import kinemo as k

@k.scene(params={"r": k.Float(0.5, 3, default=1.5)})
def radius(s: k.Scene, r: k.Signal[float]):
    c = k.Circle(r=r).place(at="center")
    s.play(k.draw(c))
''',
        related=("k.Int", "k.scene"),
    ),
    DocEntry(
        "k.Bool",
        "Parameters",
        "Boolean scene parameter: `k.Bool(default=True)`." + _PARAMS_NOTE,
        '''
import kinemo as k

@k.scene(params={"grid": k.Bool(default=True)})
def with_grid(s: k.Scene, grid: k.Signal[bool]):
    ax = k.Axes(x=(0, 5, 1), y=(0, 3, 1)).place(at="center")
    tag = k.Text("grid on", visible=grid).place(above=ax, gap=0.3)
    s.play(k.draw(ax), k.fade_in(tag))
''',
        related=("k.Choice", "k.scene"),
    ),
    DocEntry(
        "k.Choice",
        "Parameters",
        "Scene parameter with fixed options: `k.Choice([k.BLUE, k.RED])` (the default is the "
        "first option, or `default=`)." + _PARAMS_NOTE,
        '''
import kinemo as k

@k.scene(params={"color": k.Choice([k.BLUE, k.RED], default=k.RED)})
def choice(s: k.Scene, color: k.Signal[k.Color]):
    sq = k.Square(2, fill=color, fill_opacity=0.6).place(at="center")
    s.play(k.draw(sq))
''',
        related=("k.Int", "k.scene"),
    ),
    DocEntry(
        "k.Str",
        "Parameters",
        "Text scene parameter: `k.Str(default=\"...\")`. (`k.Text` is the text object; "
        "one name per concept.)" + _PARAMS_NOTE,
        '''
import kinemo as k

@k.scene(params={"heading": k.Str(default="Hello")})
def greeting(s: k.Scene, heading: k.Signal[str]):
    title = k.Text(heading, size=0.9).place(at="center")
    s.play(k.write(title))
''',
        related=("k.Text", "k.scene"),
    ),
    DocEntry(
        "k.theme",
        "Theme and colors",
        "Tokens of the current theme: `k.theme.bg`, `fg`, `accent`, `muted`, `secondary`. They are "
        "resolved when the scene is built, so switching the theme changes the whole scene without "
        "touching the code. `k.RED`, `k.BLUE`... are the fixed palette.",
        '''
import kinemo as k

@k.scene(theme=k.themes.blueprint)
def tokens(s: k.Scene):
    box = k.RoundedRect(w=4, h=2, stroke=k.theme.accent).place(at="center")
    note = k.Text("blueprint theme", fill=k.theme.secondary).place(below=box, gap=0.3)
    s.play(k.draw(box), k.write(note))
''',
        related=("k.themes", "k.BLUE"),
        signature="k.theme.bg | k.theme.fg | k.theme.accent | k.theme.muted | k.theme.secondary",
    ),
    DocEntry(
        "k.themes",
        "Theme and colors",
        "Built-in themes: `k.themes.dark` (default), `k.themes.light` and `k.themes.blueprint`. "
        "Choose one with `@k.scene(theme=...)` or in `kinemo.toml`; `theme.with_(accent=k.PINK)` "
        "creates a variation.",
        '''
import kinemo as k

@k.scene(theme=k.themes.light.with_(accent=k.PINK))
def light(s: k.Scene):
    dot = k.Circle(r=1, fill=k.theme.accent, fill_opacity=1).place(at="center")
    s.play(k.grow(dot))
''',
        related=("k.theme",),
        signature="k.themes.dark | k.themes.light | k.themes.blueprint",
    ),
    DocEntry(
        "k.BLUE",
        "Theme and colors",
        "Fixed palette: `k.BLUE`, `k.RED`, `k.GREEN`, `k.YELLOW`, `k.ORANGE`, `k.PURPLE`, "
        "`k.PINK`, `k.TEAL`, `k.WHITE`, `k.BLACK`, `k.GRAY` and `k.TRANSPARENT`. Colors "
        "interpolate in OKLab. For theme-dependent colors use `k.theme.*`.",
        '''
import kinemo as k

@k.scene
def palette(s: k.Scene):
    colors = [k.BLUE, k.RED, k.GREEN, k.YELLOW, k.PURPLE]
    dots = [k.Circle(r=0.5, fill=c, fill_opacity=1, stroke=c) for c in colors]
    row = k.Row(*dots, gap=0.4).place(at="center")
    s.play(k.stagger([k.grow(d) for d in dots], lag=0.1))
''',
        related=("k.rgb", "k.theme", "k.mix"),
        aliases=(
            "k.RED", "k.GREEN", "k.YELLOW", "k.ORANGE", "k.PURPLE", "k.PINK", "k.TEAL",
            "k.WHITE", "k.BLACK", "k.GRAY", "k.TRANSPARENT",
        ),
        signature="k.BLUE | k.RED | k.GREEN | k.YELLOW | k.ORANGE | k.PURPLE | k.PINK | k.TEAL | k.WHITE | k.BLACK | k.GRAY | k.TRANSPARENT",
    ),
    DocEntry(
        "k.rgb",
        "Theme and colors",
        "Color from components from 0 to 1 (`a=` is the opacity). Outside the palette and the theme, "
        "this is the way to define a color.",
        '''
import kinemo as k

@k.scene
def custom_color(s: k.Scene):
    amber = k.rgb(1.0, 0.55, 0.1)
    sq = k.Square(2, fill=amber, fill_opacity=1).place(at="center")
    s.play(k.draw(sq))
''',
        related=("k.BLUE", "k.mix"),
    ),
)
