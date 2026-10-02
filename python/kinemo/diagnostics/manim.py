"""K11xx: recognize Manim names and answer with the kinemo equivalent."""

from __future__ import annotations

from typing import Any

from .diagnostic import KinemoError

#: Manim verbs/classes → (kinemo form, code).
VERBS = {
    "Create": "k.draw(obj)",
    "DrawBorderThenFill": "k.draw(obj)",
    "Write": "k.write(text)",
    "FadeIn": "k.fade_in(obj)",
    "FadeOut": "k.fade_out(obj)",
    "GrowFromCenter": "k.grow(obj)",
    "GrowFromEdge": 'k.grow(obj, from_="bottom")',
    "Transform": "k.morph(a, b)",
    "ReplacementTransform": "k.morph(a, b)",
    "TransformMatchingTex": "k.morph(a, b)",
    "Indicate": "k.indicate(obj)",
    "Flash": "k.flash(obj)",
    "MoveAlongPath": "k.follow(obj, path)",
    "Uncreate": "k.fade_out(obj)",
    "ShrinkToCenter": "k.shrink(obj)",
    "AnimationGroup": "k.par(a, b)  or  k.stagger([a, b], lag=...)",
    "Succession": "k.seq(a, b)",
    "LaggedStart": "k.stagger([a, b], lag=0.1)",
    "VGroup": "k.Group(a, b)",
    "MathTex": 'k.Math(r"...")',
    "Tex": 'k.Text("...")',
}

CLASSES = {
    "ValueTracker": ("K1104", "k.signal(0)"),
    "ThreeDScene": ("K1103", '@k.scene(camera="3d")'),
    "MovingCameraScene": ("K1103", "@k.scene + s.camera.to(...)"),
}

DIRECTIONS = {
    "UP": "y=... or .place(above=...)",
    "DOWN": "y=... or .place(below=...)",
    "LEFT": "x=... or .place(left_of=...)",
    "RIGHT": "x=... or .place(right_of=...)",
    "ORIGIN": '.place(at="center")',
    "UL": '.place(at="top-left")',
    "UR": '.place(at="top-right")',
    "DL": '.place(at="bottom-left")',
    "DR": '.place(at="bottom-right")',
}

#: Manim methods on mobjects → kinemo form.
METHODS = {
    "animate": ("K1102", "s.play(obj.to(...))"),
    "shift": ("K1102", "s.play(obj.to(y=obj.y.now + 1))"),
    "move_to": ("K1102", "obj.set(x=..., y=...) or .place(at=...)"),
    "next_to": ("K1106", "obj.place(below=other)"),
    "to_edge": ("K1106", 'obj.place(at="top")'),
    "to_corner": ("K1106", 'obj.place(at="top-left")'),
    "arrange": ("K1106", "k.Row(a, b)  or  k.Column(a, b)"),
    "set_color": ("K1102", "obj.set(color=k.RED)  or  s.play(obj.to(color=k.RED))"),
    "set_fill": ("K1102", "obj.set(fill=..., fill_opacity=...)"),
    "scale_to_fit_width": ("K1106", "group.fit(s.frame.safe)"),
    "add_updater": ("K1105", "obj.set(x=other.x)"),
    "get_center": ("K1106", "obj.center.now"),
    "get_x": ("K1106", "obj.x.now"),
    "get_y": ("K1106", "obj.y.now"),
}


def module_attribute(name: str) -> KinemoError | None:
    """`k.Create` and friends."""
    if name in VERBS:
        return KinemoError.make("K1101", f"'{name}' is a Manim name. In kinemo: {VERBS[name]}", fixes=[("use", VERBS[name])])
    if name in CLASSES:
        code, form = CLASSES[name]
        return KinemoError.make(code, f"'{name}' is a Manim name. In kinemo: {form}", fixes=[("use", form)])
    if name in DIRECTIONS:
        return KinemoError.make(
            "K1106", f"'{name}' is a Manim direction; in kinemo, position comes from constraints",
            fixes=[("use", DIRECTIONS[name])],
        )
    return None


def manim_attribute(obj: Any, name: str) -> KinemoError | None:
    if name in METHODS:
        code, form = METHODS[name]
        return KinemoError.make(code, f"'.{name}' is a Manim method. In kinemo: {form}", fixes=[("use", form)])
    return None


def manim_hint(value: Any) -> KinemoError | None:
    """A Manim-shaped value passed where a kinemo animation was expected."""
    name = type(value).__name__
    if name in VERBS:
        return module_attribute(name)
    return None
