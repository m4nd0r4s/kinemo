"""Fixed reference text shared by `llms.txt` and `kinemo docs`: the seven rules, the agent
loop, diagnostic code ranges and the Manim → kinemo table (from docs/specs.md)."""

from __future__ import annotations

from dataclasses import dataclass

from . import signatures

RULES = (
    "Scene code runs once and produces a timeline. The frame at instant t is a pure function of t.",
    "Objects are values. Creating an object does not put it in the scene; it enters with `s.add()` (instant) "
    "or with a verb (`k.draw`, `k.write`, …).",
    "What takes time goes through `s.play` (blocks the cursor) or `s.start` (does not block). What is "
    "instant is a direct call: `s.add`, `s.remove`, `obj.set`, `x.set`.",
    "A state change is `obj.to(...)`. Components may expose named transitions (`row.swap(i, j)`), "
    "always sugar for a `.to()`.",
    "Position comes from constraints (`.place`, `k.Row`), not from coordinates. Coordinates exist, but they are "
    "the rare case.",
    "Passing a signal or a lambda creates a reactive binding. There are no updaters.",
    "Two reads, two names: `x.now` reads the value at the cursor during construction; `x()` is a tracked "
    "read inside lambdas, `k.computed` and `.map`.",
)

AGENT_LOOP = (
    "Read this `llms.txt` (or `kinemo docs <symbol>` for the symbols you will use).",
    "Write the scene.",
    "`kinemo check scene.py --json --strict`. If there are errors, apply the fixes (or `--fix`) and repeat.",
    "`kinemo inspect scene.py --at <t> --json` at the key instants (end of each `play`) to "
    "confirm positions.",
    "Optional: `kinemo snap scene.py --at 0,2.5,end` (or `--at marks --sheet`: one contact sheet, a frame per mark) and a visual review.",
    "`kinemo render scene.py`.",
)

CONVENTIONS = (
    "`import kinemo as k`; a scene is `@k.scene def name(s: k.Scene): ...`.",
    "Frame of 16 × 9 units, origin at the center, y up; `s.frame.safe` is the safe area.",
    "Every verb and every `.to()` lasts 1 s with `k.ease.smooth`; they accept `duration=`, `ease=` and `delay=`.",
    "One form per concept: this reference shows only the canonical form of each thing.",
    "Functions used in `.map`, lambdas and `ax.plot` use `k` blocks (`k.sin`, `k.where`, `k.min`), "
    "never `math.*`, `if` on signals or the built-in `min()`/`max()`.",
    "The `k.simulate` step and `.on` handlers are plain Python: `if`, `min()`, `math.*` are fine there "
    "(only lambdas, `.map` and `k.computed` are traced).",
    "Layout-derived props, read-only and reactive: `obj.left`, `obj.right`, `obj.top`, "
    "`obj.bottom`, `obj.width`, `obj.height`, `obj.center` (in the parent) and `obj.world.position`, "
    "`obj.world.center` (global). Edge points: `obj.edge(\"right\")`, for example "
    "`k.Arrow(start=a.edge(\"right\"), end=b.edge(\"left\"))` follows both objects.",
    "Text parts: `txt[\"world\"]` (first occurrence), `txt.find_all(\"a\")`, `txt.chars[3:7]`, "
    "`txt.words[1]`, `txt.lines[0]`; in formulas, `eq[\"name\"]` (from `\\id{name}{...}`) or `eq[\"c^2\"]`. "
    "Each part is an object: `s.play(txt[\"world\"].to(color=k.YELLOW))`.",
    "Containers: `row[i]` is the order at the cursor (already accounting for swaps scheduled earlier); "
    "`row.to(children=[...])` reorders freely; `swap`, `insert` and `pop` are shortcuts for it.",
    "`ax.plot` curves are clipped to the visible range of the axes (x and y); choose `y=` to cover "
    "the values that matter.",
    "For bars that grow from one side, position by constraint: "
    "`k.Rect(w=p * 6, h=0.4).place(inside=track, align=\"left\")`.",
    "Every prop accepts a value, a signal or a lambda (`k.Val[T]`), including in constructors: "
    "`k.Polygon.regular(n)` with a signal `n` changes the number of sides.",
    "Anchors for `at=`, `align=`, `edge()` and `k.grow(from_=)`: `center`, `top`, `bottom`, `left`, `right`, "
    "`top-left`, `top-right`, `bottom-left`, `bottom-right`. `place(inside=box, align=\"bottom\", pad=0.1)`.",
    "`dash=(12, 10)`: dash and gap in pixels at 1080p resolution (like `stroke_width`).",
    "Geometry on edges: `tri.sides` (at the cursor) and `k.Square.on(side, outward=True)`.",
    "Lint fixes point to objects by variable name (`curve.label`); use `name=` to name "
    "objects created without a direct assignment.",
    "An object cropped by the frame on purpose (a horizon, a planet) takes `bleed=True`; objects "
    "entirely offstage (waiting to slide in) are not reported by W1001.",
    "Narration: `with s.voice(script[\"B01\"]) as v` and `v.at(\"phrase\")` instead of hand-tuned "
    "waits; `kinemo voice scene.py` makes the missing audio and `kinemo check --json` lists each "
    "scene's `marks` and `narration`.",
    "`k.Math` accepts mathematical LaTeX (fractions, roots, sums, integrals, matrices, "
    "`\\left…\\right`, accents, Greek letters, `\\text{}`); document-level commands (`\\section`, `tabular`, TikZ) give K0801.",
)

DIAGNOSTIC_RANGES = (
    ("K01xx", "Object lifecycle"),
    ("K02xx / W02xx", "Animations, conflicts, interpolation"),
    ("K03xx / W03xx", "Reactive system"),
    ("K04xx", "Layout and constraints"),
    ("K05xx", "Resolution (loops, convergence)"),
    ("K06xx / W06xx", "Components"),
    ("K07xx / W07xx", "Events"),
    ("K08xx / W08xx", "Text and math"),
    ("W09xx", "Performance"),
    ("W10xx", "Visual legibility"),
    ("K11xx", "Names from other libraries (Manim)"),
    ("K12xx", "Data and interoperability (Arrow, arrays)"),
    ("W13xx", "Parameters and export"),
    ("W14xx", "Audio and voice"),
)


@dataclass(frozen=True)
class ManimRow:
    manim: str
    kinemo: str
    #: kinemo symbols the translation uses; the row is published only when all exist.
    requires: tuple[str, ...] = ()

    @property
    def available(self) -> bool:
        return all(signatures.exists(symbol) for symbol in self.requires)


MANIM_TABLE = (
    ManimRow("`class S(Scene): def construct(self)`", "`@k.scene def s(s: k.Scene)`"),
    ManimRow("`self.play(Create(x))`", "`s.play(k.draw(x))`"),
    ManimRow("`self.play(Write(t))`", "`s.play(k.write(t))`"),
    ManimRow("`self.add(x)` / `self.remove(x)`", "`s.add(x)` / `s.remove(x)`"),
    ManimRow("`FadeIn` / `FadeOut`", "`k.fade_in` / `k.fade_out`"),
    ManimRow("`GrowFromCenter(x)`", "`k.grow(x)`"),
    ManimRow("`ShrinkToCenter(x)`", "`k.shrink(x)`"),
    ManimRow("`Indicate(x)` / `Flash(x)`", "`k.indicate(x)` / `k.flash(x)`"),
    ManimRow("`MoveAlongPath(x, path)`", "`k.follow(x, path)`"),
    ManimRow("`Transform(a, b)` / `ReplacementTransform`", "`k.morph(a, b)`", ("k.morph",)),
    ManimRow("`TransformMatchingTex(a, b)`", "`k.morph(a, b)` (matching by TeX is the default)", ("k.morph", "k.Math")),
    ManimRow("`x.animate.shift(UP)`", "`s.play(x.to(y=x.y.now + 1))`"),
    ManimRow("`x.animate.set_color(RED)`", "`s.play(x.to(color=k.RED))`"),
    ManimRow("`x.next_to(y, DOWN)`", "`x.place(below=y)`"),
    ManimRow("`x.to_edge(UP)` / `x.to_corner(UL)`", '`x.place(at="top")` / `x.place(at="top-left")`'),
    ManimRow("`VGroup(a, b).arrange(RIGHT)`", "`k.Row(a, b)`"),
    ManimRow("`VGroup(a, b)`", "`k.Group(a, b)`"),
    ManimRow("`ValueTracker(0)`", "`k.signal(0)`"),
    ManimRow("`x.add_updater(f)`", "`x.set(prop=signal_or_lambda)`"),
    ManimRow("`always_redraw(lambda: ...)`", "Reactive props via lambda"),
    ManimRow("`AnimationGroup(a, b, lag_ratio=r)` / `LaggedStart`", "`k.stagger([a, b], lag=...)`"),
    ManimRow("`Succession(a, b)`", "`k.seq(a, b)`"),
    ManimRow("`self.wait()`", "`s.wait()`"),
    ManimRow("`Tex(r\"...\")` / `Text(\"...\")`", '`k.Text("...")`'),
    ManimRow("`MathTex(r\"...\")`", '`k.Math(r"...")`', ("k.Math",)),
    ManimRow("`Code(...)`", '`k.Code(src, lang="python")`', ("k.Code",)),
    ManimRow("`Axes(...).plot(f)`", "`k.Axes(...).plot(f)`"),
    ManimRow("`NumberLine(...)`", "`k.NumberLine(...)`"),
    ManimRow(
        "`ThreeDScene` + `set_camera_orientation`",
        '`@k.scene(camera="3d")` + `s.camera.to(orbit=...)`',
        ("Scene.camera",),
    ),
)


def manim_rows() -> list[ManimRow]:
    return [row for row in MANIM_TABLE if row.available]
