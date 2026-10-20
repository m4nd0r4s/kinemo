"""The quiz stretch of a question: what a lesson's video shows in place of the interactive stop.

Built by `s.ask` right after the question, like a branch (it starts from the state at the
question and leaves nothing behind): the prompt and the answer's controls on a band at a side
of the safe area, "Pause and answer" with a countdown of `think=` seconds, then the reveal (the
right card lights up, the number is written in, the slider moves). While it plays, the
renderer shrinks the rest of the scene into the part of the frame the band leaves free. The
interactive player skips it; a video in quiz mode (`questions="quiz"`) plays it before the
correct branch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .._runtime.spans import Span
    from ..objects.node import Node
    from .scene import Scene

#: Seconds of the band coming in, of the reveal, of the right answer staying on screen, and of
#: the band leaving.
INTRO = 0.5
REVEAL = 0.8
HOLD = 1.6
OUTRO = 0.4
#: Default time to think, in seconds (`s.ask(..., think=)`).
THINK = 5.0

LETTERS = "ABCDEFGHIJ"


@dataclass
class Part:
    """One object of the band, at its place relative to the band's center."""

    node: "Node"
    dx: float
    dy: float


@dataclass
class Controls:
    """The answer's controls on the band: their parts, height, and what the reveal does."""

    parts: list[Part]
    height: float
    reveal: Callable[[float], None]


def _number(value: float) -> str:
    return f"{value:g}"


#: Where the band goes (`s.ask(..., quiz_at=)`).
PLACES = ("bottom", "top", "left", "right")


class QuizBuilder:
    def __init__(self, s: "Scene", answer: dict[str, Any], default: Any, at: str, span: "Span") -> None:
        self.s, self.answer, self.default, self.at, self.span = s, answer, default, at, span
        self.rings: list[tuple["Node", float, float]] = []
        safe = s.frame.safe
        portrait = s.frame.height > s.frame.width
        side = at in ("left", "right")
        #: Options are stacked in a column (portrait frames, bands at a side).
        self.vertical = portrait or side
        self.width = min(safe.width * 0.36, 5.4) if side else min(safe.width - 0.4, 11.0)
        self.size = 0.5 if portrait else 0.38 if side else 0.42

    # ---- small helpers -----------------------------------------------------------------------

    def ramp(self, node: "Node", prop: str, t: float, duration: float, a: Any, b: Any) -> None:
        from ..anim.ease import ease
        from ..anim.verbs import _ramp  # pyright: ignore[reportPrivateUsage]

        _ramp(self.s, node, prop, t, duration, ease.smooth, a, b, self.span)

    def text(self, content: str, size: float, fill: Any, width: float | None = None, opacity: float = 1.0) -> "Node":
        from ..objects.captions import _escaped  # pyright: ignore[reportPrivateUsage]
        from ..objects.text import Text

        escaped = " ".join(_escaped(w) for w in content.split(" "))
        # The band is kinemo's own overlay, styled to be read: the scene's text lints skip it
        # (W1503 reports what it covers instead).
        return Text(escaped, size=size, fill=fill, align="center", opacity=opacity, emphasis="decorative", width=width)

    # ---- controls for each kind of answer --------------------------------------------------------

    def choice(self) -> Controls:
        from ..objects.shapes import RoundedRect
        from ..values.color import GREEN

        theme = self.s.theme
        options: list[str] = self.answer["options"]
        labels = [self.text(f"{LETTERS[i]}   {o}", self.size, theme.fg) for i, o in enumerate(options)]
        pad, gap = 0.28, 0.25
        heights = [float(t.height.now) + 2 * pad for t in labels]
        widths = [float(t.width.now) + 2 * pad for t in labels]
        row = not self.vertical and sum(widths) + gap * (len(widths) - 1) <= self.width
        parts: list[Part] = []
        cards: list[tuple["Node", "Node", float, float]] = []
        if row:
            h = max(heights)
            x = -(sum(widths) + gap * (len(widths) - 1)) / 2
            spots = []
            for w in widths:
                spots.append((x + w / 2, 0.0, w, h))
                x += w + gap
            height = h
        else:
            w = min(self.width, max(widths))
            h = max(heights)
            total = h * len(labels) + gap * (len(labels) - 1)
            spots = [(0.0, total / 2 - h / 2 - i * (h + gap), w, h) for i in range(len(labels))]
            height = total
        for label, (cx, cy, w, h) in zip(labels, spots):
            card = RoundedRect(w=w, h=h, radius=0.14, fill=theme.bg, fill_opacity=0.6, stroke=theme.muted, stroke_width=2.0, emphasis="decorative")
            parts += [Part(card, cx, cy), Part(label, cx, cy)]
            cards.append((card, label, cx, cy))
        correct = set(self.answer["correct"])

        def reveal(t: float) -> None:
            for i, (card, label, _, _) in enumerate(cards):
                if i in correct:
                    self.ramp(card, "stroke", t, REVEAL, theme.muted, GREEN)
                    self.ramp(card, "fill", t, REVEAL, theme.bg, GREEN)
                    self.ramp(card, "fill_opacity", t, REVEAL, 0.6, 0.35)
                else:
                    for node in (card, label):
                        self.ramp(node, "opacity", t, REVEAL, 1.0, 0.3)

        return Controls(parts, height, reveal)

    def boxed(self, before: str, after: str) -> Controls:
        """A box holding `before` (a "?" or a blank) that becomes `after` at the reveal."""
        from ..objects.shapes import RoundedRect
        from ..values.color import GREEN

        theme = self.s.theme
        old = self.text(before, self.size * 1.2, theme.muted)
        new = self.text(after, self.size * 1.2, GREEN, opacity=0.0)
        w = max(2.2, float(new.width.now) + 0.8)
        h = float(new.height.now) + 0.5
        box = RoundedRect(w=w, h=h, radius=0.14, fill=theme.bg, fill_opacity=0.6, stroke=theme.muted, stroke_width=2.0, emphasis="decorative")

        def reveal(t: float) -> None:
            self.ramp(old, "opacity", t, REVEAL / 2, 1.0, 0.0)
            self.ramp(new, "opacity", t + REVEAL / 3, REVEAL * 2 / 3, 0.0, 1.0)
            self.ramp(box, "stroke", t, REVEAL, theme.muted, GREEN)

        return Controls([Part(box, 0, 0), Part(old, 0, 0), Part(new, 0, 0)], h, reveal)

    def slider(self) -> Controls:
        from ..objects.shapes import Circle, Line
        from ..values.color import GREEN

        theme = self.s.theme
        lo, hi = self.answer["lo"], self.answer["hi"]
        length = min(self.width * 0.62, 7.0)
        start = float(self.default if self.default is not None else lo)

        def at(v: float) -> float:
            return -length / 2 + length * (v - lo) / (hi - lo)

        track = Line((-length / 2, 0), (length / 2, 0), stroke=theme.muted, stroke_width=6.0, emphasis="decorative")
        knob = Circle(r=0.16, fill=theme.accent, fill_opacity=1.0, stroke_width=0.0, emphasis="decorative")
        old = self.text(_number(start), self.size, theme.fg)
        new = self.text(_number(self.answer["correct"]), self.size, GREEN, opacity=0.0)
        readout_x = length / 2 + 0.3 + max(float(old.width.now), float(new.width.now)) / 2
        parts = [Part(track, -0.4, 0), Part(knob, at(start) - 0.4, 0), Part(old, readout_x - 0.4, 0), Part(new, readout_x - 0.4, 0)]

        def reveal(t: float) -> None:
            x0 = float(knob.x.now)
            self.ramp(knob, "x", t, REVEAL, x0, x0 + at(self.answer["correct"]) - at(start))
            self.ramp(knob, "fill", t, REVEAL, theme.accent, GREEN)
            self.ramp(old, "opacity", t, REVEAL / 2, 1.0, 0.0)
            self.ramp(new, "opacity", t + REVEAL / 2, REVEAL / 2, 0.0, 1.0)

        return Controls(parts, 0.4, reveal)

    def point(self) -> Controls:
        """No control on the band: the reveal rings the right place on the frame."""
        from ..objects.shapes import Circle
        from ..values.color import GREEN

        ring = Circle(r=0.35, stroke=GREEN, stroke_width=4.0, fill_opacity=0.0, opacity=0.0, emphasis="decorative")
        x, y = self.answer["correct"]
        self.rings.append((ring, x, y))

        def reveal(t: float) -> None:
            self.ramp(ring, "opacity", t, REVEAL / 2, 0.0, 1.0)
            self.ramp(ring, "scale", t, REVEAL, 2.0, 1.0)

        return Controls([], 0.0, reveal)

    def controls(self) -> Controls:
        kind = self.answer["kind"]
        if kind == "choice":
            return self.choice()
        if kind == "number" and self.answer["lo"] is not None and self.answer["hi"] is not None:
            return self.slider()
        if kind == "number":
            return self.boxed("?", _number(self.answer["correct"]))
        if kind == "point":
            return self.point()
        return self.boxed("…", self.answer["correct"][0])


def build_quiz(s: "Scene", prompt: str, answer: dict[str, Any], default: Any, think: float, at: str, span: "Span") -> dict[str, Any]:
    """Build the quiz stretch from the cursor; returns its `{t0, reveal, t1}` (and the band's
    box, `rect`) and moves the cursor to its end."""
    from ..objects.shapes import RoundedRect

    first_object = s._b.object_count()  # pyright: ignore[reportPrivateUsage]
    b = QuizBuilder(s, answer, default, at, span)
    theme = s.theme
    safe = s.frame.safe
    pad, gap = 0.35, 0.3
    title = b.text(prompt, b.size, theme.fg, width=b.width - 2 * pad)
    hint = b.text("Pause and answer", max(0.28, b.size * 0.72), theme.muted)
    controls = b.controls()
    bar_h = 0.08
    rows = [float(title.height.now)] + ([controls.height] if controls.height > 0 else []) + [bar_h, float(hint.height.now)]
    height = sum(rows) + gap * (len(rows) - 1) + 2 * pad
    plate = RoundedRect(w=b.width, h=height, radius=0.2, fill=theme.bg, fill_opacity=0.85, stroke_width=0.0, emphasis="decorative")
    bar_w = b.width - 2 * pad
    bar = RoundedRect(w=bar_w, h=bar_h, radius=bar_h / 2, fill=theme.accent, fill_opacity=1.0, stroke_width=0.0, emphasis="decorative")
    middle_x, middle_y = (safe.left + safe.right) / 2, (safe.bottom + safe.top) / 2
    cx, cy = {
        "bottom": (middle_x, safe.bottom + height / 2),
        "top": (middle_x, safe.top - height / 2),
        "left": (safe.left + b.width / 2, middle_y),
        "right": (safe.right - b.width / 2, middle_y),
    }[at]
    y = cy + height / 2 - pad
    placed: list[Part] = [Part(plate, 0, 0)]
    y -= rows[0] / 2
    placed.append(Part(title, 0, y - cy))
    y -= rows[0] / 2 + gap
    if controls.height > 0:
        y -= controls.height / 2
        placed += [Part(p.node, p.dx, p.dy + y - cy) for p in controls.parts]
        y -= controls.height / 2 + gap
    y -= bar_h / 2
    placed.append(Part(bar, 0, y - cy))
    y -= bar_h / 2 + gap
    placed.append(Part(hint, 0, y - cy - float(hint.height.now) / 2))

    t0 = s.cursor
    reveal = t0 + INTRO + think
    t1 = reveal + REVEAL + HOLD + OUTRO
    for part in placed:
        part.node.set(x=cx + part.dx, y=cy + part.dy)
    for ring, x, y_ring in b.rings:
        ring.set(x=x, y=y_ring)
    for node in [*(part.node for part in placed), *(ring for ring, _, _ in b.rings)]:
        s._enter(node, t0)  # pyright: ignore[reportPrivateUsage]
        b.ramp(node, "_fade", t0, INTRO, 0.0, 1.0)
        b.ramp(node, "_fade", t1 - OUTRO, OUTRO, 1.0, 0.0)
        s._exit(node, t1)  # pyright: ignore[reportPrivateUsage]
    # The countdown: the bar shrinks toward its left end while the learner thinks.
    left = cx - bar_w / 2
    b.ramp(bar, "w", t0 + INTRO, think, bar_w, 0.0)
    b.ramp(bar, "x", t0 + INTRO, think, cx, left)
    b.ramp(hint, "opacity", reveal, REVEAL / 2, 1.0, 0.0)
    controls.reveal(reveal)
    s.cursor = t1
    s._max_end = max(s._max_end, t1)  # pyright: ignore[reportPrivateUsage]
    rect = [cx - b.width / 2, cy - height / 2, cx + b.width / 2, cy + height / 2]
    # Everything made from here on is the quiz's own: the renderer shrinks the rest of the
    # scene beside the band while it plays.
    objects = [first_object, s._b.object_count()]  # pyright: ignore[reportPrivateUsage]
    return {"t0": t0, "reveal": reveal, "t1": t1, "at": at, "rect": rect, "content": scene_box(s, t0, first_object), "objects": objects}


def scene_box(s: "Scene", t: float, before: int) -> list[float]:
    """What the scene shows at `t` (objects made before id `before`), as one box in scene units;
    the camera fits it beside the band."""
    import json

    b = s._b  # pyright: ignore[reportPrivateUsage]
    box: list[float] | None = None
    for node in s._nodes:  # pyright: ignore[reportPrivateUsage]
        if node._id >= before or node._parent is not None or not b.present(node._id, t):
            continue
        sides = [json.loads(b.derived(node._id, side, t, True))["Float"] for side in ("left", "bottom", "right", "top")]
        if sides[2] <= sides[0] and sides[3] <= sides[1]:
            continue
        box = sides if box is None else [min(box[0], sides[0]), min(box[1], sides[1]), max(box[2], sides[2]), max(box[3], sides[3])]
    return box or [0.0, 0.0, 0.0, 0.0]
